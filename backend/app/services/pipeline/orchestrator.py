"""
app/services/pipeline/orchestrator.py

Main state machine for the Patent Research Pipeline.
Updates database status and executes the 9 steps sequentially.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
import time
import httpx
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import engine
from app.repositories.patent_document_repository import PatentDocumentRepository
from app.core.config import settings
from app.models.research_run import ResearchRun, RunStatus
from app.models.report_metadata import ReportMetadata
from app.models.report_file import ReportFile
from app.services.pipeline.schemas import PatentExtraction, PatentRank, PatentRankList, RankingStatus, CompoundSearchProfile, EvidenceLedger, CandidateState
from app.services.pipeline.search_service import SearchService
from app.services.pipeline.fetcher_service import FetcherService
from app.services.pipeline.parser_service import ParserService
from app.services.pipeline.extractor_service import ExtractorService
from app.services.pipeline.cache_service import CacheService
from app.services.pipeline.rule_engine import RuleEngineService
from app.services.pipeline.report_service import ReportService
from app.services.pipeline.compound_intelligence import CompoundIntelligenceService

logger = logging.getLogger(__name__)

async def get_background_session() -> AsyncSession:
    """Provide a new session for background tasks."""
    return AsyncSession(engine, expire_on_commit=False)

class TokenBudgetManager:
    def __init__(self):
        self.budgets = {
            "Compound Profile": 500,
            "Query Expansion": 300,
            "Ranking": 3000,
            "Extraction": 1200 * 15, # 1200 per patent
            "Report": 4000,
            "Recipe": 4000
        }
        self.used = {k: 0 for k in self.budgets}
        
    def add_tokens(self, stage: str, tokens: int):
        self.used[stage] += tokens
        if self.used[stage] > self.budgets.get(stage, float('inf')):
            logger.warning(f"TOKEN BUDGET EXCEEDED for {stage}! (Used: {self.used[stage]}, Budget: {self.budgets[stage]})")
            
    def get_summary(self):
        return "\n".join([f"{k}: {self.used[k]}/{self.budgets[k]}" for k in self.budgets])

class PipelineOrchestrator:
    def __init__(self, run_id: UUID):
        self.run_id = run_id
        self.search_service = SearchService()
        self.fetcher_service = FetcherService()
        self.parser_service = ParserService()
        self.extractor_service = ExtractorService()
        self.cache_service = CacheService()
        self.rule_engine = RuleEngineService()
        self.report_service = ReportService()
        self.compound_intelligence = CompoundIntelligenceService(self.cache_service)
        self.token_manager = TokenBudgetManager()
        self.patent_repo = PatentDocumentRepository()

    async def _update_status(self, session: AsyncSession, run: ResearchRun, status: RunStatus):
        run.status = status
        run.updated_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info("Run %s transitioned to %s", self.run_id, status.name)

    async def _mark_failed(self, session: AsyncSession, run: ResearchRun, error_msg: str):
        logger.error("Run %s FAILED: %s", self.run_id, error_msg)
        await self._update_status(session, run, RunStatus.FAILED)

    def _log_stage(self, stage: str, t0: float, t1: float, tokens: str = "No LLM", cache_hit: str = "No", status: str = "Completed"):
        duration = t1 - t0
        logger.info(
            "\nStage: %s\nStart Time: %s\nEnd Time: %s\nDuration: %.2f sec\nTokens: %s\nCache Hit: %s\nStatus: %s\n",
            stage, 
            datetime.fromtimestamp(t0).strftime('%H:%M:%S'),
            datetime.fromtimestamp(t1).strftime('%H:%M:%S'),
            duration, tokens, cache_hit, status
        )

    async def execute(self):
        """
        Main entry point for the background task.
        Uses a Global Candidate Pool architecture.
        """
        async with await get_background_session() as session:
            result = await session.execute(select(ResearchRun).where(ResearchRun.id == self.run_id))
            run = result.scalar_one_or_none()

            if not run:
                logger.error("Orchestrator could not find run %s", self.run_id)
                return

            try:
                if getattr(run, 'jurisdictions', None):
                    allowed_authorities = run.jurisdictions
                else:
                    # Fallback for old runs
                    source_to_auth = {
                        "USPTO": "US",
                        "Espacenet": "EP",
                        "inPASS": "IN"
                    }
                    allowed_authorities = [source_to_auth[src] for src in run.selected_sources if src in source_to_auth]

                # ── Step 1: Profile Loading
                t0_profile = time.time()
                profile = await self.compound_intelligence.generate_profile(run.compound_name)
                self._log_stage("Compound Search Profile Loading", t0_profile, time.time())
                
                # ── Step 2 & 3: Run Searches & Build Global Candidate Pool
                await self._update_status(session, run, RunStatus.SEARCHING)
                t0_search = time.time()
                
                global_pool = {} # Dict mapping patent_number to candidate metadata
                
                for authority in allowed_authorities:
                    queries = self.search_service.build_queries(profile, authority)
                    
                    # Fetch rich metadata results
                    jurisdiction_results = await self.search_service.search_patents(queries, authority)
                    logger.info("\nJurisdiction Filter\n%s\nAccepted\n%d hits\n", authority, len(jurisdiction_results))
                    
                    for res in jurisdiction_results:
                        pn = res["patent_number"]
                        tier = res["tier"]
                        q = res["query_matched"]
                        
                        if pn not in global_pool:
                            global_pool[pn] = {
                                "metadata": res,
                                "ledger": EvidenceLedger()
                            }
                            
                        # Aggregate evidence
                        ledger = global_pool[pn]["ledger"]
                        ledger.query_match_count += 1
                        ledger.matched_queries.append(q)
                        ledger.log(f"Matched {tier} query in {authority}: '{q}'")
                        
                        # Add tier weights to search confidence
                        if tier == "Tier 1":
                            ledger.dimensions.search_confidence += 30
                        elif tier == "Tier 2":
                            ledger.dimensions.search_confidence += 15
                        elif tier == "Tier 3":
                            ledger.dimensions.search_confidence += 5

                self._log_stage("Serper Search & Global Pool Aggregation", t0_search, time.time())
                
                if not global_pool:
                    raise Exception("No patents found across any query or jurisdiction.")
                    
                logger.info("\nGlobal Candidate Pool\nTotal Unique Patents\n%d\n", len(global_pool))
                
                # ── Step 4 & 5: Progressive Qualification on Metadata
                await self._update_status(session, run, RunStatus.FILTERING)
                t0_meta = time.time()
                
                for pn, candidate in global_pool.items():
                    self.rule_engine.evaluate_candidate_metadata(candidate["metadata"], candidate["ledger"], profile)
                
                # ── Step 6: Candidate Pool Reduction
                # Sort by overall confidence, excluding REJECTED
                valid_candidates = [c for c in global_pool.values() if c["ledger"].state != CandidateState.REJECTED]
                valid_candidates.sort(key=lambda x: x["ledger"].dimensions.overall_confidence, reverse=True)
                
                logger.info("\nQualification Results\nTotal Candidates\n%d\nRejected\n%d\nSurviving\n%d\n", 
                            len(global_pool), len(global_pool) - len(valid_candidates), len(valid_candidates))
                
                # Log rejected patents
                rejected_candidates = [c for c in global_pool.values() if c["ledger"].state == CandidateState.REJECTED]
                if rejected_candidates:
                    logger.info("\n=== REJECTED PATENTS ===")
                    for c in rejected_candidates:
                        logger.info(f"Patent: {c['metadata']['patent_number']} | Rejected because: {c['ledger'].rejection_reason}")

                # We will process candidates progressively up to a target
                from app.core.config import settings
                target_valid_patents = settings.TARGET_PATENTS # Default is 5
                
                # ── Stage 4 & 6: Progressive Download and Structural Analysis
                t0_rank = time.time()
                structurally_valid_candidates = []
                
                for candidate in valid_candidates:
                    if len(structurally_valid_candidates) >= target_valid_patents:
                        logger.info("Early stopping: Target of %d structurally validated patents reached.", target_valid_patents)
                        break
                        
                    meta = candidate["metadata"]
                    ledger = candidate["ledger"]
                    pn = meta["patent_number"]
                    url = meta["url"]
                    
                    try:
                        doc = await self.patent_repo.get_by_patent_number(session, pn)
                        
                        if doc:
                            from app.services.pipeline.schemas import ParsedPatent
                            parsed_patent = ParsedPatent(
                                url=url,
                                abstract=doc.abstract or "",
                                detailed_description=doc.description or "",
                                examples=doc.examples or "",
                                claims=doc.claims or ""
                            )
                        else:
                            # Progressive HTML download
                            parsed_patent = await self.fetcher_service.fetch_patent(url)
                            if parsed_patent:
                                patent_data = {
                                    "patent_number": pn,
                                    "jurisdiction": meta.get("jurisdiction", ""),
                                    "title": meta.get("title", ""),
                                    "abstract": parsed_patent.abstract,
                                    "description": parsed_patent.detailed_description,
                                    "examples": parsed_patent.examples,
                                    "claims": parsed_patent.claims,
                                    "publication_date": meta.get("publication_date", "")
                                }
                                await self.patent_repo.create_or_update(session, patent_data)
                                
                        if not parsed_patent:
                            continue
                            
                        # Structural Analysis
                        self.rule_engine.score_content(parsed_patent, profile, ledger)
                        
                        if ledger.state != CandidateState.REJECTED:
                            candidate["parsed_patent"] = parsed_patent
                            structurally_valid_candidates.append(candidate)
                            
                    except Exception as e:
                        logger.error("Failed to parse and score content for %s: %s", pn, e)

                self._log_stage("Progressive Download & Structural Analysis", t0_rank, time.time())
                
                if not structurally_valid_candidates:
                    raise Exception("All fetched patents failed structural validation.")
                    
                # Re-sort the structurally valid candidates by their new overall confidence
                structurally_valid_candidates.sort(key=lambda x: x["ledger"].dimensions.overall_confidence, reverse=True)
                final_candidates = structurally_valid_candidates[:target_valid_patents]
                
                # Format final selection message
                final_selection_msg = "\n=== FINAL SELECTION ===\n"
                for i, candidate in enumerate(final_candidates):
                    ledger = candidate["ledger"]
                    meta = candidate["metadata"]
                    final_selection_msg += f"\nPatent: {meta['patent_number']} (Rank {i+1})\n"
                    final_selection_msg += f"Why Selected: State={ledger.state.value} | Confidence={ledger.dimensions.overall_confidence}\n"
                    final_selection_msg += f"Compound Evidence: {ledger.dimensions.compound_evidence}\n"
                    final_selection_msg += f"Matched monomers: {ledger.dimensions.matched_monomers}\n"
                    final_selection_msg += f"Matched synonyms: {ledger.dimensions.matched_synonyms}\n"
                    final_selection_msg += f"Matched chemistry family: {ledger.dimensions.matched_chemistry_family}\n"
                    final_selection_msg += f"Manufacturing Evidence: {ledger.dimensions.manufacturing_evidence}\n"
                    final_selection_msg += f"Recipe Evidence: {ledger.dimensions.recipe_evidence}\n"
                    final_selection_msg += f"Negative Evidence: {ledger.dimensions.negative_evidence}\n"
                    final_selection_msg += "-" * 30 + "\n"
                    
                logger.info(final_selection_msg)

                # ── Step 10: LLM Extraction ──
                await self._update_status(session, run, RunStatus.EXTRACTING)
                
                t0_ext = time.time()
                extractions = []
                quota_exhausted = False
                
                for candidate in final_candidates:
                    meta = candidate["metadata"]
                    parsed_patent = candidate["parsed_patent"]
                    ledger = candidate["ledger"]
                    url = meta["url"]
                    
                    logger.info("Patent %s: State = QUEUED (Score: %d)", meta["patent_number"], ledger.dimensions.overall_confidence)
                    
                    try:
                        from app.services.pipeline.schemas import PatentExtraction
                        ext = await self.extractor_service.extract_polymerization_data(parsed_patent, initial_json=PatentExtraction())
                        if ext:
                            # Map old fields for downstream report generation compatibility
                            ext.metadata.patent_title = meta.get("title", "")
                            ext.metadata.patent_number = meta["patent_number"]
                            ext.metadata.publication_year = meta.get("publication_date", "")
                            ext.metadata.jurisdiction = meta.get("jurisdiction", "")
                            ext.metadata.url = url
                            
                            val_result = self.extractor_service.validate_extraction(ext)
                            ext.metadata.quality = val_result["quality"]
                            ext.metadata.extraction_score = val_result["score"]
                            
                            extractions.append(ext)
                            logger.info("Patent %s: State = EXTRACTED", meta["patent_number"])
                        else:
                            logger.warning("Patent %s: Extraction failed.", meta["patent_number"])
                    except Exception as e:
                        from app.services.llm.llm_client import ProviderExhaustedException
                        if isinstance(e, ProviderExhaustedException) or "Provider Quota exhausted" in str(e):
                            logger.error("Provider Quota exhausted! Circuit Breaker tripped. Terminating loop.")
                            quota_exhausted = True
                            break
                        else:
                            logger.error("Error during extraction for %s: %s", meta["patent_number"], e)
                        
                self._log_stage("LLM Extraction Loop", t0_ext, time.time())
                
                if len(extractions) == 0:
                    logger.error(
                        "\nTarget Patents: %d\nValid Patents Found: %d\nStatus: FAILED\nReason: No valid patents found.\n",
                        settings.TARGET_PATENTS, len(extractions)
                    )
                    raise Exception("Pipeline failed: Could not extract any valid patents.")
                    
                # Sort extractions: High first, then Medium
                quality_map = {"High": 0, "Medium": 1, "Low": 2}
                extractions.sort(key=lambda x: quality_map.get(getattr(x.metadata, "quality", "Low"), 3))
    
                # ── Step 11: Generate Report & Export
                t0_rep = time.time()
                await self._update_status(session, run, RunStatus.GENERATING)
                
                markdown_report = await self.report_service.generate_markdown_report(run.compound_name, extractions)
                self._log_stage("Report Generation", t0_rep, time.time())
                
                import os
                import json
                from datetime import datetime, timezone
                pdf_name = f"APCOTEX_Report_{self.run_id}_{run.report_version}.pdf"
                docx_name = f"APCOTEX_Report_{self.run_id}_{run.report_version}.docx"
                md_name = f"APCOTEX_Report_{self.run_id}_{run.report_version}.md"
                json_name = f"APCOTEX_Report_{self.run_id}_{run.report_version}.json"
                
                export_dir = self.report_service.export_dir
                md_path = os.path.join(export_dir, md_name)
                json_path = os.path.join(export_dir, json_name)
                
                # Write Markdown and JSON to disk
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(markdown_report)
                
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump([ex.model_dump() for ex in extractions], f, indent=2)

                pdf_path = await self.report_service.export_to_pdf(markdown_report, pdf_name)
                docx_path = await self.report_service.export_to_docx(markdown_report, docx_name)
                
                # ── DB: Save Report Metadata and Files
                meta = ReportMetadata(
                    research_run_id=run.id,
                    title=f"{run.compound_name} Polymerization Report",
                    summary="Automated synthesis pipeline extraction.",
                    patent_count=len(extractions),
                    source_count=len(extractions),
                    version=run.report_version,
                    generated_at=datetime.now(timezone.utc)
                )
                session.add(meta)
                await session.flush()  # to get meta.id
                
                if pdf_path:
                    session.add(ReportFile(
                        report_metadata_id=meta.id,
                        file_type="PDF",
                        file_name=pdf_name,
                        file_path=pdf_path
                    ))
                    
                if docx_path:
                    session.add(ReportFile(
                        report_metadata_id=meta.id,
                        file_type="MARKDOWN", # Proxy for docx to avoid DB ENUM crash
                        file_name=docx_name,
                        file_path=docx_path
                    ))
                
                session.add(ReportFile(
                    report_metadata_id=meta.id,
                    file_type="MARKDOWN",
                    file_name=md_name,
                    file_path=md_path
                ))
                
                session.add(ReportFile(
                    report_metadata_id=meta.id,
                    file_type="JSON",
                    file_name=json_name,
                    file_path=json_path
                ))

                # ── Finalize
                if quota_exhausted:
                    final_db_status = RunStatus.PAUSED
                    final_status_log = "PAUSED (All providers exhausted)"
                else:
                    final_db_status = RunStatus.COMPLETED
                    final_status_log = "PARTIAL_SUCCESS" if len(extractions) < settings.TARGET_PATENTS else "COMPLETED"
                    
                await self._update_status(session, run, final_db_status)
                
                logger.info(
                    "\nPipeline Completion Summary:\n"
                    "Target Patents: %d\n"
                    "Valid Recipes Found: %d\n"
                    "Status: %s\n",
                    settings.TARGET_PATENTS, len(extractions), final_status_log
                )

            except Exception as e:
                import traceback
                logger.error("Pipeline failure: %s\n%s", e, traceback.format_exc())
                await self._mark_failed(session, run, str(e))
