"""
app/services/pipeline/report_evidence_service.py

Transforms raw PatentExtraction objects into compact ReportPatentEvidence.
Handles semantic batching if the evidence exceeds the token budget.
Preserves patent provenance and ensures one final report generation call.
"""
import logging
import json
import tiktoken
from typing import List, Dict

from app.services.pipeline.schemas import (
    PatentExtraction, ReportPatentEvidence, ReportExampleEvidence, 
    ExtractedParameterSchema, BatchAnalysisResult, PatentBatchFindings
)
from app.services.llm.llm_client import llm_client
from app.services.prompts.patent_prompts import (
    CROSS_PATENT_ANALYSIS_SYSTEM_PROMPT,
    CROSS_PATENT_ANALYSIS_USER_TEMPLATE
)

logger = logging.getLogger(__name__)

REPORT_INPUT_TOKEN_BUDGET = 100000

class ReportEvidenceService:
    def __init__(self):
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.encoder = None

    def estimate_tokens(self, text: str) -> int:
        if self.encoder:
            return len(self.encoder.encode(text))
        return len(text) // 4

    def is_compounding_parameter(self, param: ExtractedParameterSchema) -> bool:
        """
        Heuristic to deprioritize compounding data unless necessary.
        DISABLED: Preserve all extracted parameters for report generation.
        The LLM can determine relevance during analysis.
        """
        return False

    def build_compact_evidence(self, extraction: PatentExtraction, discovery_source: str = "NORMAL", competitor_name: str | None = None) -> ReportPatentEvidence:
        """Transforms a heavy PatentExtraction into a lightweight ReportPatentEvidence."""
        meta = extraction.metadata
        
        evidence = ReportPatentEvidence(
            patent_number=meta.patent_number,
            title=meta.patent_title,
            jurisdiction=meta.jurisdiction,
            assignee=meta.assignee,
            publication_year=meta.publication_year,
            url=meta.url,
            discovery_source=discovery_source,
            competitor_name=competitor_name,
            overall_patent_parameters=[],
            examples=[],
            technical_findings=[],
            limitations_or_missing_data=[]
        )
        
        # Filter global parameters
        for param in extraction.parameters:
            if not self.is_compounding_parameter(param):
                evidence.overall_patent_parameters.append(param)
                
        # Filter examples
        for ex in extraction.examples:
            ex_evidence = ReportExampleEvidence(
                example_id=f"{ex.type} {ex.number}".strip(),
                extracted_parameters=[]
            )
            for param in ex.extracted_parameters:
                if not self.is_compounding_parameter(param):
                    ex_evidence.extracted_parameters.append(param)
            
            if ex_evidence.extracted_parameters:
                evidence.examples.append(ex_evidence)
                
        return evidence

    def serialize_evidence(self, evidence_list: List[ReportPatentEvidence]) -> str:
        """Serializes the evidence list into a structured markdown string for token counting and LLM input."""
        parts = []
        for ev in evidence_list:
            parts.append(f"=== PATENT {ev.patent_number} ===")
            parts.append(f"Title: {ev.title}")
            parts.append(f"Jurisdiction: {ev.jurisdiction}")
            parts.append(f"Assignee: {ev.assignee}")
            parts.append(f"Publication Year: {ev.publication_year}")
            parts.append(f"Source Type: {ev.discovery_source}")
            if ev.competitor_name:
                parts.append(f"Competitor: {ev.competitor_name}")
            
            if ev.overall_patent_parameters:
                parts.append("\nGeneral Parameters:")
                for param in ev.overall_patent_parameters:
                    unit_str = f" {param.unit}" if param.unit else ""
                    parts.append(f"- {param.name}: {param.value}{unit_str} | Source: {param.source_sentence}")
                    
            if ev.examples:
                parts.append("\nExamples:")
                for ex in ev.examples:
                    parts.append(f"  Example {ex.example_id}:")
                    for param in ex.extracted_parameters:
                        unit_str = f" {param.unit}" if param.unit else ""
                        parts.append(f"    - {param.name}: {param.value}{unit_str} | Source: {param.source_sentence}")
            parts.append("\n")
            
        return "\n".join(parts)

    def create_semantic_batches(self, evidence_list: List[ReportPatentEvidence], budget: int) -> List[List[ReportPatentEvidence]]:
        """
        Splits evidence at the patent boundary.
        If a single patent is too large, it splits it at the example boundary into multiple ReportPatentEvidence objects with the same patent_number.
        """
        batches = []
        current_batch = []
        current_tokens = 0
        
        for ev in evidence_list:
            ev_str = self.serialize_evidence([ev])
            tokens = self.estimate_tokens(ev_str)
            
            if tokens > budget:
                # A single patent is too large, need to split by examples
                logger.warning("Patent %s is too large (%d tokens). Splitting by examples.", ev.patent_number, tokens)
                
                # If current batch has stuff, push it
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0
                    
                # Split the large patent
                base_ev = ReportPatentEvidence(
                    patent_number=ev.patent_number,
                    title=ev.title,
                    jurisdiction=ev.jurisdiction,
                    assignee=ev.assignee,
                    publication_year=ev.publication_year,
                    url=ev.url,
                    overall_patent_parameters=ev.overall_patent_parameters
                )
                
                base_tokens = self.estimate_tokens(self.serialize_evidence([base_ev]))
                sub_batch_ev = base_ev.model_copy(deep=True)
                sub_batch_tokens = base_tokens
                
                for ex in ev.examples:
                    # Create a dummy evidence to measure this example
                    dummy = ReportPatentEvidence(patent_number=ev.patent_number, title=ev.title, jurisdiction=ev.jurisdiction, assignee=ev.assignee, publication_year=ev.publication_year, url=ev.url, examples=[ex])
                    ex_tokens = self.estimate_tokens(self.serialize_evidence([dummy]))
                    
                    if sub_batch_tokens + ex_tokens > budget and sub_batch_ev.examples:
                        batches.append([sub_batch_ev])
                        sub_batch_ev = base_ev.model_copy(deep=True)
                        sub_batch_tokens = base_tokens
                        
                    sub_batch_ev.examples.append(ex)
                    sub_batch_tokens += ex_tokens
                    
                if sub_batch_ev.examples or not batches:
                    # Push the last chunk
                    if sub_batch_tokens <= budget:
                        current_batch = [sub_batch_ev]
                        current_tokens = sub_batch_tokens
                    else:
                        batches.append([sub_batch_ev])
                        
            elif current_tokens + tokens > budget:
                batches.append(current_batch)
                current_batch = [ev]
                current_tokens = tokens
            else:
                current_batch.append(ev)
                current_tokens += tokens
                
        if current_batch:
            batches.append(current_batch)
            
        return batches

    async def analyze_batch_with_llm(self, batch: List[ReportPatentEvidence], token_manager) -> BatchAnalysisResult:
        """Runs the batch-level LLM analysis to extract structured findings without prose."""
        prompt = CROSS_PATENT_ANALYSIS_USER_TEMPLATE.format(evidence_data=self.serialize_evidence(batch))
        
        if token_manager:
            token_manager.record_call("PATENT_BATCH_ANALYSIS", self.estimate_tokens(prompt), 0) # Output tokens estimated later
            
        result, provider = await llm_client.generate_structured(
            prompt=prompt,
            system_prompt=CROSS_PATENT_ANALYSIS_SYSTEM_PROMPT,
            schema=BatchAnalysisResult,
            temperature=0.1
        )
        return result

    def merge_batch_findings(self, original_evidence: List[ReportPatentEvidence], batch_results: List[BatchAnalysisResult]):
        """Merges structured findings back into the original compact evidence."""
        # Index original by patent_number
        ev_index = {ev.patent_number: ev for ev in original_evidence}
        
        for res in batch_results:
            if not res:
                continue
            for finding in res.findings_by_patent:
                ev = ev_index.get(finding.patent_number)
                if ev:
                    ev.technical_findings.extend(finding.technical_findings)
                    ev.limitations_or_missing_data.extend(finding.limitations)
                    
                    # Merge example findings
                    ex_index = {ex.example_number: ex for ex in ev.examples}
                    for ex_num, ex_findings in finding.example_findings.items():
                        ex = ex_index.get(ex_num)
                        if ex:
                            ex.technical_findings.extend(ex_findings)

    async def prepare_final_evidence(self, extractions_by_patent: Dict[str, PatentExtraction], token_manager, competitor_extractions_by_patent: Dict[str, PatentExtraction] = None) -> List[ReportPatentEvidence]:
        """
        Orchestrates building compact evidence, token estimation, semantic batching, and merging.
        Handles both primary and competitor patent evidence.
        """
        logger.info("Building compact report evidence for %d primary patents...", len(extractions_by_patent))
        
        compact_evidence = []
        
        # Build primary patent evidence
        for pn, ext in extractions_by_patent.items():
            ev = self.build_compact_evidence(ext, discovery_source="NORMAL", competitor_name=None)
            compact_evidence.append(ev)
            logger.info("Patent %s (PRIMARY): %d parameters, %d examples", pn, len(ev.overall_patent_parameters), len(ev.examples))
        
        # Build competitor patent evidence
        if competitor_extractions_by_patent:
            logger.info("Building compact report evidence for %d competitor patents...", len(competitor_extractions_by_patent))
            for pn, ext in competitor_extractions_by_patent.items():
                # Get competitor name from extraction metadata if available
                competitor_name = ext.metadata.assignee if hasattr(ext.metadata, 'competitor_name') else None
                ev = self.build_compact_evidence(ext, discovery_source="COMPETITOR", competitor_name=competitor_name)
                compact_evidence.append(ev)
                logger.info("Patent %s (COMPETITOR): %d parameters, %d examples", pn, len(ev.overall_patent_parameters), len(ev.examples))
            
        full_text = self.serialize_evidence(compact_evidence)
        estimated_tokens = self.estimate_tokens(full_text)
        
        logger.info("Estimated report input tokens: %d", estimated_tokens)
        logger.info("Configured budget: %d", REPORT_INPUT_TOKEN_BUDGET)
        
        if estimated_tokens <= REPORT_INPUT_TOKEN_BUDGET:
            logger.info("Report evidence fits input budget. Generating final report in one LLM call.")
            return compact_evidence
            
        logger.info("Report evidence exceeds input budget. Starting semantic batch processing...")
        
        batches = self.create_semantic_batches(compact_evidence, REPORT_INPUT_TOKEN_BUDGET)
        batch_results = []
        
        for i, batch in enumerate(batches):
            logger.info("Processing Batch %d/%d...", i+1, len(batches))
            res = await self.analyze_batch_with_llm(batch, token_manager)
            if res:
                batch_results.append(res)
            logger.info("Batch %d completed", i+1)
            
        self.merge_batch_findings(compact_evidence, batch_results)
        logger.info("Batch findings merged.")
        logger.info("Generating final report from consolidated evidence.")
        
        return compact_evidence
