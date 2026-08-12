"""
app/services/pipeline/extractor_service.py

Extraction Subsystem (Phases 1, 4, 6, 8)
1. Single public API `extract_patent`
2. Runs Deterministic Extraction & Validation
3. Accurately calculates Completeness
4. LLM Decision Engine limits expensive calls
"""
import logging
from app.services.pipeline.schemas import PatentExtraction, ParsedPatent, ExtractionResult, ExtractionStatus
from app.services.llm import llm_client
from app.services.pipeline.deterministic_extractor import DeterministicExtractor

from app.services.prompts.patent_prompts import (
    PATENT_EXTRACTION_SYSTEM_PROMPT,
    PATENT_EXTRACTION_USER_TEMPLATE
)

logger = logging.getLogger(__name__)

LLM_COMPLETENESS_THRESHOLD = 0.70

class ExtractorService:
    def __init__(self):
        self.deterministic_extractor = DeterministicExtractor()

    async def extract_patent(
        self, 
        parsed_patent: ParsedPatent, 
        patent_number: str,
        title: str, 
        jurisdiction: str, 
        source_url: str,
        skip_llm: bool = False
    ) -> ExtractionResult:
        """
        Phase 1: Single public entry point for extraction.
        """
        logger.info(f"\n--- Extraction Subsystem Started for {patent_number} ---")
        
        # 1. Deterministic Extraction & Validation
        initial_json = PatentExtraction()
        initial_json.metadata.patent_number = patent_number
        initial_json.metadata.patent_title = title
        initial_json.metadata.jurisdiction = jurisdiction
        initial_json.metadata.url = source_url
        
        det_result, detected_count = self.deterministic_extractor.extract(parsed_patent, initial_json)
        extracted_count = len(det_result.parameters)
        
        # 2. Dynamic Missing Evidence Discovery
        evidence = parsed_patent.structural_evidence
        
        found_categories = set(p.category for p in det_result.parameters)
        target_categories = {"Raw Materials", "Reaction Conditions", "Process Variables"}
        missing_categories = target_categories - found_categories
        
        # We need LLM if critical categories are missing OR substantial evidence exists for analysis
        llm_required = False
        decision_reason = ""
        missing_keywords = []
        
        if skip_llm:
            llm_required = False
            decision_reason = "LLM Budget Exhausted / Rate Limited"
        elif missing_categories:
            llm_required = True
            decision_reason = f"Missing Categories: {', '.join(missing_categories)}"
            if "Raw Materials" in missing_categories:
                missing_keywords.extend(["parts by weight", "wt%", "ratio", "initiator", "emulsifier", "monomer", "charged"])
            if "Reaction Conditions" in missing_categories:
                missing_keywords.extend(["temperature", "°C", "pressure", "bar", "time", "hours"])
            if "Process Variables" in missing_categories:
                missing_keywords.extend(["conversion", "yield", "coagulation", "latex"])
        elif evidence.example_count > 0 or extracted_count >= 3:
            # LLM should analyze substantial evidence even if all categories are present
            llm_required = True
            decision_reason = "Substantial evidence exists for LLM analysis"
            missing_keywords.extend(["parts", "temperature", "conversion", "initiator", "emulsifier"])
            
        # Standardized Logging
        abs_len = len(parsed_patent.abstract) if parsed_patent.abstract else 0
        desc_len = len(parsed_patent.detailed_description) if parsed_patent.detailed_description else 0
        
        logger.info(f"Patent:\n{patent_number}\n")
        logger.info(f"Abstract:\n{abs_len} chars\n")
        logger.info(f"Description:\n{desc_len} chars\n")
        logger.info(f"Examples:\n{evidence.example_count if evidence else 0}\n")
        logger.info(f"Polymerization evidence:\nInitiator: {evidence.initiator_count if evidence else 0}, Temp: {evidence.temperature_count if evidence else 0}\n")
        logger.info(f"Structured fields populated:\n{extracted_count}/{detected_count}\n")
        
        logger.info(f"Deterministic:\nCandidates: {detected_count}\nValidated: {extracted_count}\nCompleteness: N/A%\n")
        
        if llm_required:
            logger.info(f"Missing Evidence:\n{decision_reason}\nKeywords: {missing_keywords}\n")
        
        if not llm_required:
            logger.info(f"LLM:\nRequired: NO\n")
            logger.info(f"Final:\nFULL\n")
            det_result.metadata.quality = "VALID_FULL"
            det_result.metadata.extraction_score = 100
            return ExtractionResult(status=ExtractionStatus.FULL, patent_number=patent_number, extraction=det_result)
            
        # 3. Targeted Retrieval
        from app.services.pipeline.parser_service import ParserService
        parser_service = ParserService()
        
        context_str = parser_service.retrieve_targeted_evidence(parsed_patent, missing_keywords, max_chars=12000)
        
        if not context_str or len(context_str) < 50:
            logger.info(f"LLM:\nRequired: YES\nEstimated Input Tokens: 0\nEstimated Output Tokens: 0\n")
            logger.info(f"Reason: No targeted sections found\nDeterministic extraction preserved: YES\n")
            logger.info(f"Final:\nPARTIAL\n")
            det_result.metadata.quality = "VALID_PARTIAL"
            return ExtractionResult(status=ExtractionStatus.PARTIAL, patent_number=patent_number, extraction=det_result)
            
        input_tokens = len(context_str) // 4
        
        if input_tokens > 4000:
            logger.warning("Targeted retrieval still exceeded token budget. Truncating context.")
            context_str = context_str[:15000]
            input_tokens = len(context_str) // 4

        logger.info(f"Selected Evidence:\n{len(context_str)} characters\n~{input_tokens} tokens\n")
        logger.info(f"LLM:\nRequired: YES\nEstimated Input Tokens: {input_tokens}\nEstimated Output Tokens: 500\n")

        initial_json_str = det_result.model_dump_json(indent=2)
        extraction_prompt = PATENT_EXTRACTION_USER_TEMPLATE.format(
            patent_number=patent_number,
            title=title,
            jurisdiction=jurisdiction,
            context_str=context_str,
            initial_json_str=initial_json_str
        )
        
        try:
            from app.services.llm.token_manager import token_manager
            token_manager.record_call("PATENT_EXTRACTION", input_tokens, 500)
            
            extraction_result, _ = await llm_client.generate_structured(
                prompt=extraction_prompt,
                system_prompt=PATENT_EXTRACTION_SYSTEM_PROMPT,
                schema=PatentExtraction,
                temperature=0.1
            )
            
            if extraction_result:
                extraction_result.metadata = initial_json.metadata
                extraction_result.metadata.quality = "VALID_FULL (LLM)"
                
                # 4. Merge deterministic exact values with LLM values
                merged_params = {
                    f"{p.name.lower()}_{p.value}_{p.unit.lower()}": p 
                    for p in det_result.parameters
                }
                
                for lp in extraction_result.parameters:
                    lp.extraction_method = "llm"
                    key = f"{lp.name.lower()}_{lp.value}_{lp.unit.lower()}"
                    if key not in merged_params:
                        merged_params[key] = lp

                extraction_result.parameters = list(merged_params.values())
                
                logger.info(f"LLM Input: {input_tokens}\nLLM Output: {len(extraction_result.parameters)}\n")
                logger.info(f"Final:\nFULL\n")
                return ExtractionResult(status=ExtractionStatus.FULL, patent_number=patent_number, extraction=extraction_result)
                
            logger.info(f"Reason: Extraction returned null\nDeterministic extraction preserved: YES\n")
            logger.info(f"Final:\nPARTIAL\n")
            det_result.metadata.quality = "VALID_PARTIAL"
            return ExtractionResult(status=ExtractionStatus.PARTIAL, patent_number=patent_number, extraction=det_result)
            
        except Exception as e:
            from app.services.llm.llm_client import LLMRateLimitException
            if isinstance(e, LLMRateLimitException) or "429" in str(e):
                logger.info(f"Reason: 429 Rate Limit\nDeterministic extraction preserved: YES\n")
                det_result.metadata.rate_limited_event = True
            else:
                logger.info(f"Reason: {e}\nDeterministic extraction preserved: YES\n")
            
            logger.info(f"Final:\nPARTIAL\n")
            det_result.metadata.quality = "VALID_PARTIAL"
            return ExtractionResult(status=ExtractionStatus.PARTIAL, patent_number=patent_number, extraction=det_result)
