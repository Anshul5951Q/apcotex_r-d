"""
app/services/pipeline/orchestrator.py

Main state machine for the Patent Research Pipeline.
Updates database status and executes the redesigned pipeline.
"""
import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
import time

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.research_run import ResearchRun, RunStatus
from app.models.search_query import SearchQueryModel, SearchQueryStatus
from app.models.search_result import SearchResult
from app.models.patent_extraction import PatentExtraction
from app.models.extraction_batch import ExtractionBatch, BatchStatus
from app.models.report_metadata import ReportMetadata
from app.models.report_file import ReportFile, ReportFileType
from app.services.pipeline.search_service import SearchService, SerperCreditsExhaustedError
from app.services.pipeline.fetcher_service import FetcherService
from app.services.pipeline.extractor_service import ExtractorService
from app.services.pipeline.cache_service import CacheService
from app.services.pipeline.rule_engine import RuleEngineService
from app.services.pipeline.validation_service import ValidationService
from app.services.pipeline.report_evidence_service import ReportEvidenceService
from app.services.pipeline.report_service import ReportService
from app.services.pipeline.compound_intelligence import CompoundIntelligenceService
from app.services.pipeline.title_scorer import TitleScorer, TitleScreeningStatus
from app.services.pipeline.schemas import CompoundSearchProfile, ParsedPatent, ExtractionStatus
from app.repositories.patent_document_repository import PatentDocumentRepository
from app.services.llm.llm_client import llm_client, ProviderExhaustedException

logger = logging.getLogger(__name__)

class LLMBudgetManager:
    def __init__(self):
        self.max_calls_per_run = 30
        self.calls_used = 0
        self.exhausted = False
        
    def record_call(self, stage: str, input_tokens: int, output_tokens: int):
        self.calls_used += 1
            
    def can_call(self, stage: str) -> bool:
        if self.exhausted or self.calls_used >= self.max_calls_per_run:
            return False
        return True
        
    def trip_circuit_breaker(self):
        self.exhausted = True

class PipelineOrchestrator:
    def __init__(self, run_id: uuid.UUID):
        logger.info("[RESEARCH REQUEST] PipelineOrchestrator.__init__() started for run_id: %s", run_id)
        try:
            self.run_id = run_id
            self.search_service = SearchService()
            self.fetcher_service = FetcherService()
            self.extractor_service = ExtractorService()
            self.cache_service = CacheService()
            self.rule_engine = RuleEngineService()
            self.report_service = ReportService()
            self.compound_intelligence = CompoundIntelligenceService(self.cache_service)
            self.validation_service = ValidationService()
            self.token_manager = LLMBudgetManager()
            self.patent_repo = PatentDocumentRepository()
            logger.info("[RESEARCH REQUEST] PipelineOrchestrator.__init__() completed successfully")
        except Exception as e:
            logger.error("[RESEARCH REQUEST FAILED] Stage: PipelineOrchestrator.__init__() | Exception: %s | Message: %s", type(e).__name__, str(e))
            raise

    async def _update_status(self, session: AsyncSession, run: ResearchRun, status: RunStatus):
        try:
            run.status = status
            run.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info("Run %s transitioned to %s", self.run_id, status.name)
        except Exception as e:
            await session.rollback()
            logger.error("Failed to update status to %s for run %s: %s", status.name, self.run_id, e)
            raise e

    async def _mark_failed(self, session: AsyncSession, run: ResearchRun, error_msg: str):
        logger.error("Run %s FAILED: %s", self.run_id, error_msg)
        # Rollback any existing failed transaction before attempting to update status
        await session.rollback()
        await self._update_status(session, run, RunStatus.FAILED)

    def _generate_deterministic_fallback_report(self, extractions: list, profile: CompoundSearchProfile) -> str:
        rep = f"# Technical Patent Research Report: {profile.compound_name}\n\n"
        rep += "> Note: This report was generated deterministically due to LLM provider quota exhaustion.\n\n"
        for ev in extractions:
            ext = ev.extraction
            rep += f"## {ev.patent_number} (Score: {ev.relevance_confidence})\n"
            if ext:
                rep += f"### Parameters\n"
                for param in ext.parameters:
                    rep += f"- **{param.name}**: {param.value} {param.unit or ''}\n"
            rep += "\n---\n"
        return rep

    async def execute(self):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(ResearchRun).where(ResearchRun.id == self.run_id))
            run = result.scalar_one_or_none()
            if not run:
                logger.error("Orchestrator could not find run %s", self.run_id)
                return

            try:
                extractions_by_patent = {}
                allowed_authorities = run.jurisdictions if run.jurisdictions else ["US", "EP"]
                date_start = run.publication_filter.get("year_from", "") if run.publication_filter else ""
                if date_start: date_start = f"{date_start}0101"
                date_end = run.publication_filter.get("year_to", "") if run.publication_filter else ""
                if date_end: date_end = f"{date_end}1231"

                # ── Step 1: Profile Loading
                profile = await self.compound_intelligence.generate_profile(run.compound_name)
                title_scorer = TitleScorer(profile)
                
                await self._update_status(session, run, RunStatus.SEARCHING)
                
                # ── QUERY EXPANSION LOGGING
                logger.info("=" * 60)
                logger.info("QUERY EXPANSION")
                logger.info("=" * 60)
                logger.info(f"Original User Input: {profile.original_input}")
                logger.info(f"Normalized Material: {profile.compound_name}")
                logger.info(f"Important Constraints: {profile.important_constraints if profile.important_constraints else 'None'}")
                logger.info(f"Research Intent: {profile.research_intent if profile.research_intent else 'Not specified'}")
                logger.info(f"Synonyms: {profile.synonyms[:5] if profile.synonyms else 'None'}")
                logger.info("")
                logger.info("Generated Queries:")
                for idx, sq in enumerate(profile.search_queries, 1):
                    priority_str = sq.priority.value if hasattr(sq.priority, 'value') else str(sq.priority)
                    logger.info(f"Query {idx}")
                    logger.info(f"  Priority: {priority_str}")
                    logger.info(f"  Category: {sq.category}")
                    logger.info(f"  Field: {sq.field}")
                    logger.info(f"  Query: {sq.query}")
                logger.info(f"Total Queries Generated: {len(profile.search_queries)}")
                logger.info("=" * 60)
                logger.info("QUERY EXPANSION COMPLETE")
                logger.info("=" * 60)
                logger.info("")
                
                # ── Step 2: Build Queries & Pagination Search
                raw_queries = self.search_service.build_queries(profile)
                
                # ── DISCOVERY CONFIGURATION LOGGING
                logger.info("=" * 60)
                logger.info("DISCOVERY CONFIGURATION")
                logger.info("=" * 60)
                logger.info(f"Original Input: {profile.original_input}")
                logger.info(f"Base Compound: {profile.compound_name}")
                logger.info(f"Competitors: {', '.join(run.competitors) if run.competitors else 'None'}")
                logger.info(f"External Websites: {', '.join(run.mentioned_websites) if run.mentioned_websites else 'None'}")
                logger.info(f"Jurisdictions: {', '.join(run.jurisdictions) if run.jurisdictions else 'None'}")
                
                # Publication date filter
                pub_filter = run.publication_filter
                if pub_filter:
                    filter_type = pub_filter.get('type', 'ANY_TIME')
                    logger.info(f"Publication Filter: {filter_type}")
                    if filter_type != 'ANY_TIME':
                        from app.services.pipeline.date_utils import get_date_window
                        start_date, end_date = get_date_window(filter_type)
                        if start_date:
                            logger.info(f"Publication Date Range: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}")
                else:
                    logger.info("Publication Filter: ANY_TIME")
                logger.info("")
                
                # ── PATENT DISCOVERY LOGGING
                logger.info("=" * 60)
                logger.info("PATENT DISCOVERY")
                logger.info("=" * 60)
                logger.info(f"USER INPUT: {profile.original_input}")
                logger.info(f"BASE COMPOUND: {profile.compound_name}")
                logger.info(f"SYNONYMS: {', '.join(profile.synonyms) if profile.synonyms else 'None'}")
                logger.info(f"ABBREVIATIONS: {', '.join(profile.abbreviations) if profile.abbreviations else 'None'}")
                logger.info(f"CONSTRAINTS: {', '.join(profile.important_constraints) if profile.important_constraints else 'None'}")
                logger.info("")
                logger.info(f"Total Queries to Execute: {len(raw_queries)}")
                logger.info("")
                
                # Log search strategies
                base_production_queries = [q for q in profile.search_queries if q.category in ['POLYMERIZATION', 'PREPARATION', 'SYNTHESIS', 'MANUFACTURING'] and q.priority.name == 'PRIMARY']
                constraint_queries = [q for q in profile.search_queries if 'CONSTRAINT' in str(q.category) or any(c.lower() in q.query.lower() for c in profile.important_constraints)]
                
                logger.info("SEARCH STRATEGY 1: BASE COMPOUND PRODUCTION (BROAD)")
                logger.info(f"Queries: {len(base_production_queries)}")
                for idx, q in enumerate(base_production_queries, 1):
                    logger.info(f"  {idx}. {q.query} (field: {q.field.name})")
                logger.info("")
                
                logger.info("SEARCH STRATEGY 2: CONSTRAINT-SPECIFIC (NARROW)")
                logger.info(f"Queries: {len(constraint_queries)}")
                for idx, q in enumerate(constraint_queries, 1):
                    logger.info(f"  {idx}. {q.query} (field: {q.field.name})")
                logger.info("")
                global_pool = {} # Family ID -> best SearchResult
                target_families = settings.TARGET_PATENTS  # Target: 15 relevant patent families
                # Global Diagnostic Accumulators
                total_queries_attempted = len(raw_queries)
                total_queries_successful = 0
                total_queries_failed = 0
                total_queries_zero_results = 0
                total_pages_attempted = 0
                total_pages_successful = 0
                total_pages_failed = 0
                total_raw_results = 0
                total_titles_extracted = 0
                total_titles_missing = 0
                total_jurisdiction_accepted = 0
                total_jurisdiction_rejected = 0
                total_date_accepted = 0
                total_date_rejected = 0
                total_titles_accepted = 0
                total_titles_rejected = 0
                total_hnbr_excluded = 0
                total_non_polymerization_rejected = 0
                total_duplicates_removed = 0
                total_downstream_rejected = 0
                failed_queries = []
                serper_credits_exhausted = False
                queries_skipped_due_to_credits = 0
                target_reached = False
                
                for idx, q_dict in enumerate(raw_queries):
                    # Check if we've reached target families
                    if len(global_pool) >= target_families:
                        target_reached = True
                        logger.info(f"Target reached: {len(global_pool)} relevant families found (target: {target_families})")
                        logger.info("Stopping search early - sufficient candidates collected")
                        break
                    
                    # Check if Serper credits were exhausted in previous query
                    if serper_credits_exhausted:
                        queries_skipped_due_to_credits += 1
                        logger.info(f"Skipping query {idx+1}/{len(raw_queries)} due to Serper credit exhaustion")
                        continue
                    
                    # Diagnostic logging for each query
                    logger.info(f"Query {idx+1}/{len(raw_queries)}")
                    logger.info(f"  Expanded Query: {q_dict['query']}")
                    logger.info(f"  Category: {q_dict['tier']}")
                    logger.info(f"  Priority: {q_dict['priority']}")
                    logger.info(f"  Search Field: {q_dict['search_field']}")
                    
                    # Validate query before attempting
                    is_valid, validation_reason = self.search_service.validate_query(q_dict["query"], q_dict["search_field"])
                    if not is_valid:
                        total_queries_failed += 1
                        failed_queries.append({
                            "query": q_dict["query"],
                            "field": q_dict["search_field"],
                            "reason": f"Query validation failed: {validation_reason}"
                        })
                        logger.warning(f"Query validation failed: {q_dict['query']} - {validation_reason}")
                        continue
                    
                    # Create DB Query record
                    sq_model = SearchQueryModel(
                        research_run_id=self.run_id,
                        query_text=q_dict["query"],
                        field=q_dict.get("search_field", q_dict.get("field", "TITLE")),
                        category=q_dict["tier"],
                        jurisdiction=",".join(allowed_authorities),
                        date_start=date_start,
                        date_end=date_end,
                        status=SearchQueryStatus.SEARCHING
                    )
                    session.add(sq_model)
                    # Diagnostic Counters
                    diag_raw_results = 0
                    diag_titles_extracted = 0
                    diag_titles_missing = 0
                    diag_titles_screened = 0
                    diag_titles_accepted = 0
                    diag_titles_rejected = 0
                    diag_jurisdiction_rejected = 0
                    diag_date_rejected = 0
                    diag_hnbr_excluded = 0
                    diag_non_polymerization_rejected = 0

                    await session.flush()
                    
                    page = 1
                    max_pages = settings.MAX_SEARCH_PAGES_PER_QUERY
                    query_valid_results = 0
                    query_successful = False
                    
                    while page <= max_pages:
                        total_pages_attempted += 1
                        try:
                            page_results, page_success = await self.search_service.search_patents_page(
                                query_str=q_dict["query"],
                                field=q_dict["search_field"],
                                page=page,
                                jurisdictions=allowed_authorities,
                                date_start=date_start,
                                date_end=date_end
                            )
                        except SerperCreditsExhaustedError:
                            logger.error("SERPER_CREDITS_EXHAUSTED: Stopping remaining discovery queries")
                            serper_credits_exhausted = True
                            total_queries_failed += 1
                            failed_queries.append({
                                "query": q_dict["query"],
                                "field": q_dict["search_field"],
                                "reason": "Serper API credits exhausted"
                            })
                            break
                        
                        if page_success:
                            total_pages_successful += 1
                            query_successful = True
                            logger.info(f"  Page {page} successful")
                        else:
                            total_pages_failed += 1
                            logger.warning(f"  Page {page} failed")
                            # If the first page fails, the entire query fails
                            if page == 1:
                                total_queries_failed += 1
                                failed_queries.append({
                                    "query": q_dict["query"],
                                    "field": q_dict["search_field"],
                                    "reason": "Serper API failure on first page"
                                })
                                break
                            # If a subsequent page fails, stop pagination but keep results from previous pages
                            break
                        
                        if not page_results:
                            # Empty results page - stop pagination
                            if page == 1:
                                total_queries_zero_results += 1
                            break
                            
                        diag_raw_results += len(page_results)
                            
                        page_strong = 0
                        for res in page_results:
                            if not res.get("title"):
                                diag_titles_missing += 1
                                continue
                            diag_titles_extracted += 1
                            
                            # Python Jurisdiction Filter
                            if allowed_authorities and res["jurisdiction"] not in [j.upper() for j in allowed_authorities]:
                                diag_jurisdiction_rejected += 1
                                continue
                                
                            # Python Date Filter
                            if date_start or date_end:
                                pub_date = res.get("publication_date", "").replace("-", "")
                                if pub_date:
                                    # Serper might return YYYY-MM-DD, convert to YYYYMMDD
                                    if date_start and pub_date < date_start:
                                        diag_date_rejected += 1
                                        continue
                                    if date_end and pub_date > date_end:
                                        diag_date_rejected += 1
                                        continue
                                        
                            diag_titles_screened += 1
                            
                            score, status, signals = title_scorer.score_title(res["title"])
                            
                            # Track HNBR exclusions
                            if signals.get("exclusion_reason") == "HNBR/hydrogenated patent excluded":
                                diag_hnbr_excluded += 1
                            
                            # Track downstream application rejections
                            if signals.get("exclusion_reason") == "Downstream application patent excluded":
                                total_downstream_rejected += 1
                            
                            # Track non-polymerization rejections (weak/reject without polymerization signals)
                            if status in [TitleScreeningStatus.WEAK, TitleScreeningStatus.REJECT]:
                                if not signals.get("production_method_phrase") and not signals.get("production_process_term"):
                                    diag_non_polymerization_rejected += 1
                            
                            if status in [TitleScreeningStatus.STRONG, TitleScreeningStatus.MEDIUM]:
                                diag_titles_accepted += 1
                            else:
                                diag_titles_rejected += 1
                                
                            if len(global_pool) < 20:
                                logger.info(f"TITLE SCREENING -> Title: {res['title']} | Target Match: {signals.get('target_match', False)} | Production Intent: {signals.get('production_method_phrase', False) or signals.get('production_process_term', False)} | Score: {score} | Decision: {status.name} | Intent: {signals.get('intent_classification', 'UNKNOWN')}")

                            if status in [TitleScreeningStatus.STRONG, TitleScreeningStatus.MEDIUM]:
                                page_strong += 1
                                query_valid_results += 1
                                
                            db_res = SearchResult(
                                research_run_id=self.run_id,
                                search_query_id=sq_model.id,
                                page_number=page,
                                position=res["position"],
                                title=res["title"],
                                publication_number=res["patent_number"],
                                url=res["url"],
                                jurisdiction=res["jurisdiction"],
                                publication_date=res["publication_date"],
                                snippet=res["snippet"],
                                title_score=score,
                                title_signals=signals,
                                title_screening_status=status,
                                discovered_by_queries=[q_dict["query"]]
                            )
                            session.add(db_res)
                            
                            # Keep track in global pool for deduplication later
                            if status in [TitleScreeningStatus.STRONG, TitleScreeningStatus.MEDIUM]:
                                family_id = re.sub(r'[A-Za-z]\d?$', '', res["patent_number"])
                                if family_id not in global_pool:
                                    global_pool[family_id] = db_res
                                else:
                                    existing = global_pool[family_id]
                                    queries = existing.discovered_by_queries or []
                                    if q_dict["query"] not in queries:
                                        queries.append(q_dict["query"])
                                        
                                    if (existing.title_score or 0) < score:
                                        db_res.discovered_by_queries = queries
                                        global_pool[family_id] = db_res
                                    else:
                                        existing.discovered_by_queries = list(queries)
                                
                        await session.flush()
                        
                        # Check if we've reached target families after this page
                        if len(global_pool) >= target_families:
                            target_reached = True
                            logger.info(f"Target reached: {len(global_pool)} relevant families found (target: {target_families})")
                            logger.info(f"Stopping pagination for query {idx+1} - sufficient candidates collected")
                            break
                        
                        page += 1
                        
                    # Update query-level counters
                    if query_successful:
                        total_queries_successful += 1
                        sq_model.status = SearchQueryStatus.COMPLETED
                    else:
                        sq_model.status = SearchQueryStatus.FAILED
                    
                    sq_model.page_count = page - 1
                    sq_model.result_count = query_valid_results
                    await session.commit()
                    
                    
                    # Accumulate for final report
                    total_raw_results += diag_raw_results
                    total_titles_extracted += diag_titles_extracted
                    total_titles_missing += diag_titles_missing
                    total_jurisdiction_rejected += diag_jurisdiction_rejected
                    total_jurisdiction_accepted += (diag_raw_results - diag_titles_missing - diag_jurisdiction_rejected)
                    total_date_rejected += diag_date_rejected
                    total_date_accepted += (diag_raw_results - diag_titles_missing - diag_jurisdiction_rejected - diag_date_rejected)
                    total_titles_accepted += diag_titles_accepted
                    total_titles_rejected += diag_titles_rejected
                    total_hnbr_excluded += diag_hnbr_excluded
                    total_non_polymerization_rejected += diag_non_polymerization_rejected
                    
                    logger.info(f"Query {idx+1}/{len(raw_queries)} | Page {page-1} | Raw results: {diag_raw_results} | Titles extracted: {diag_titles_extracted} | Titles accepted: {diag_titles_accepted}")
                
                total_duplicates_removed = total_titles_accepted - len(global_pool)
                
                logger.info("================ DISCOVERY SUMMARY ================")
                logger.info(f"User input: {profile.original_input}")
                logger.info(f"Canonical compound: {profile.compound_name}")
                logger.info(f"Important constraints: {profile.important_constraints}")
                logger.info(f"")
                logger.info(f"Queries generated: {len(profile.search_queries)}")
                logger.info(f"Queries executed: {total_queries_successful}/{total_queries_attempted}")
                logger.info(f"Queries failed: {total_queries_failed}")
                logger.info(f"Queries with zero results: {total_queries_zero_results}")
                if serper_credits_exhausted:
                    logger.info(f"Queries skipped due to credit exhaustion: {queries_skipped_due_to_credits}")
                    logger.info(f"Serper credit status: EXHAUSTED")
                logger.info(f"")
                logger.info(f"Pages attempted: {total_pages_attempted}")
                logger.info(f"Pages successful: {total_pages_successful}")
                logger.info(f"Pages failed: {total_pages_failed}")
                logger.info(f"Raw Serper results: {total_raw_results}")
                logger.info(f"")
                logger.info(f"Jurisdiction candidates: {total_jurisdiction_accepted}")
                logger.info(f"Jurisdiction rejected: {total_jurisdiction_rejected}")
                logger.info(f"Date accepted: {total_date_accepted}")
                logger.info(f"Date rejected: {total_date_rejected}")
                logger.info(f"")
                logger.info(f"Title candidates: {total_titles_accepted}")
                logger.info(f"Rejected as downstream applications: {total_downstream_rejected}")
                logger.info(f"Rejected as non-polymerization: {total_non_polymerization_rejected}")
                logger.info(f"Rejected as HNBR: {total_hnbr_excluded}")
                logger.info(f"Duplicates removed: {total_duplicates_removed}")
                logger.info(f"")
                logger.info(f"Unique relevant polymerization families: {len(global_pool)}")
                logger.info(f"Target: {target_families}")
                logger.info(f"Target reached: {'YES' if target_reached else 'NO'}")
                logger.info(f"")
                logger.info(f"Continue searching if: unique relevant families < {target_families}")
                logger.info("=======================================================")
                
                if failed_queries:
                    logger.info("Failed queries:")
                    for i, fq in enumerate(failed_queries, 1):
                        logger.info(f"{i}. {fq['query']} (field: {fq['field']}) - {fq['reason']}")
                
                logger.info("=======================================================")

                # Check if discovery failed due to Serper credit exhaustion
                if serper_credits_exhausted:
                    logger.error("DISCOVERY_FAILED_SERPER: Serper API credits exhausted. No further patent discovery requests were attempted.")
                    raise Exception("DISCOVERY_FAILED_SERPER: Serper API credits exhausted. No further patent discovery requests were attempted.")
                
                # Check if discovery failed due to other Serper API issues
                if total_queries_successful == 0:
                    logger.error("DISCOVERY_FAILED_SERPER: No successful Serper queries")
                    raise Exception("DISCOVERY_FAILED_SERPER: All Serper API requests failed. Check API credits/quotas.")
                
                if not global_pool:
                    logger.error("NO_CANDIDATES_AFTER_SCREENING: 0 candidates found after screening")
                    logger.error(f"Queries successful: {total_queries_successful}")
                    logger.error(f"Raw results received: {total_raw_results}")
                    logger.error("Possible reasons: Title extraction failed, all titles failed relevance, jurisdiction removed all, or date filter removed all.")
                    raise Exception("NO_CANDIDATES_AFTER_SCREENING: No candidate patents found during title screening. See logs for diagnostics.")
                    
                logger.info(f"================ PATENT DISCOVERY SUMMARY ================")
                logger.info(f"Queries executed: {len(raw_queries)}")
                logger.info(f"Unique candidate families found: {len(global_pool)}")
                
                # Check if target was reached
                if not target_reached and len(global_pool) < target_families:
                    logger.warning(f"TARGET NOT REACHED: Found {len(global_pool)} families (target: {target_families})")
                    logger.warning("Proceeding with available candidates. Consider expanding search strategies.")
                    logger.warning("Search strategies exhausted: All generated queries executed.")
                
                # Minimum candidates check
                if len(global_pool) < settings.MIN_REQUIRED_PATENTS:
                    logger.error(f"INSUFFICIENT_CANDIDATES: Found {len(global_pool)} families (minimum: {settings.MIN_REQUIRED_PATENTS})")
                    logger.error("Discovery failed to find minimum required patents.")
                    raise Exception(f"INSUFFICIENT_CANDIDATES: Found {len(global_pool)} families (minimum: {settings.MIN_REQUIRED_PATENTS})")
                
                # ── COMPETITOR DISCOVERY (Separate Channel) ──
                competitor_pool = {}  # Separate pool for competitor patents
                from app.services.pipeline.competitor_service import CompetitorService
                competitor_service = CompetitorService()
                
                if run.competitors:
                    logger.info("")
                    logger.info("=" * 60)
                    logger.info("COMPETITOR DISCOVERY")
                    logger.info("=" * 60)
                    
                    for competitor in run.competitors:
                        try:
                            logger.info(f"[COMPETITOR DISCOVERY] Competitor: {competitor}")
                            
                            # Generate competitor-specific queries
                            competitor_queries = competitor_service.generate_competitor_queries(competitor, profile)
                            logger.info(f"  Queries generated: {len(competitor_queries)}")
                            
                            # Convert to dict format for SearchService
                            competitor_raw_queries = []
                            for cq in competitor_queries:
                                competitor_raw_queries.append({
                                    "query": cq.query,
                                    "search_field": cq.field.name,
                                    "tier": cq.category.name,
                                    "priority": cq.priority.name
                                })
                            
                            # Competitor-specific diagnostics
                            comp_raw_results = 0
                            comp_jurisdiction_accepted = 0
                            comp_jurisdiction_rejected = 0
                            comp_date_accepted = 0
                            comp_date_rejected = 0
                            comp_titles_accepted = 0
                            comp_titles_rejected = 0
                            comp_assignee_matches = 0
                            comp_unique_families = 0
                            
                            # Execute competitor searches
                            for comp_q_dict in competitor_raw_queries:
                                try:
                                    # Validate query
                                    is_valid, validation_reason = self.search_service.validate_query(comp_q_dict["query"], comp_q_dict["search_field"])
                                    if not is_valid:
                                        logger.warning(f"  Query validation failed: {comp_q_dict['query']} - {validation_reason}")
                                        continue
                                    
                                    # Create DB Query record for competitor
                                    comp_sq_model = SearchQueryModel(
                                        research_run_id=self.run_id,
                                        query_text=comp_q_dict["query"],
                                        field=comp_q_dict["search_field"],
                                        category=comp_q_dict["tier"],
                                        jurisdiction=",".join(allowed_authorities),
                                        date_start=date_start,
                                        date_end=date_end,
                                        status=SearchQueryStatus.SEARCHING
                                    )
                                    session.add(comp_sq_model)
                                    await session.flush()
                                    
                                    # Search (limit to 1 page for competitor discovery to save quota)
                                    comp_page_results, comp_page_success = await self.search_service.search_patents_page(
                                        query_str=comp_q_dict["query"],
                                        field=comp_q_dict["search_field"],
                                        page=1,
                                        jurisdictions=allowed_authorities,
                                        date_start=date_start,
                                        date_end=date_end
                                    )
                                    
                                    if comp_page_success and comp_page_results:
                                        comp_raw_results += len(comp_page_results)
                                        
                                        for res in comp_page_results:
                                            if not res.get("title"):
                                                continue
                                            
                                            # Python Jurisdiction Filter
                                            if allowed_authorities and res["jurisdiction"] not in [j.upper() for j in allowed_authorities]:
                                                comp_jurisdiction_rejected += 1
                                                continue
                                            comp_jurisdiction_accepted += 1
                                            
                                            # Python Date Filter
                                            if date_start or date_end:
                                                pub_date = res.get("publication_date", "").replace("-", "")
                                                if pub_date:
                                                    if date_start and pub_date < date_start:
                                                        comp_date_rejected += 1
                                                        continue
                                                    if date_end and pub_date > date_end:
                                                        comp_date_rejected += 1
                                                        continue
                                            comp_date_accepted += 1
                                            
                                            # Title Screening
                                            score, status, signals = title_scorer.score_title(res["title"])
                                            
                                            if status in [TitleScreeningStatus.STRONG, TitleScreeningStatus.MEDIUM]:
                                                comp_titles_accepted += 1
                                            else:
                                                comp_titles_rejected += 1
                                                continue
                                            
                                            # Competitor Ownership Validation
                                            is_competitor_patent = competitor_service.matches_competitor(res, competitor)
                                            if not is_competitor_patent:
                                                continue
                                            comp_assignee_matches += 1
                                            
                                            # Create SearchResult with competitor provenance
                                            comp_db_res = SearchResult(
                                                research_run_id=self.run_id,
                                                search_query_id=comp_sq_model.id,
                                                page_number=1,
                                                position=res["position"],
                                                title=res["title"],
                                                publication_number=res["patent_number"],
                                                url=res["url"],
                                                jurisdiction=res["jurisdiction"],
                                                publication_date=res["publication_date"],
                                                snippet=res["snippet"],
                                                title_score=score,
                                                title_signals=signals,
                                                title_screening_status=status,
                                                discovered_by_queries=[comp_q_dict["query"]],
                                                discovery_source="COMPETITOR",
                                                competitor_name=competitor
                                            )
                                            session.add(comp_db_res)
                                            
                                            # Family deduplication within competitor pool
                                            family_id = re.sub(r'[A-Za-z]\d?$', '', res["patent_number"])
                                            if family_id not in competitor_pool:
                                                competitor_pool[family_id] = comp_db_res
                                                comp_unique_families += 1
                                            
                                            # Log ownership validation
                                            logger.info(f"  Patent: {res['patent_number']}")
                                            logger.info(f"    Title: {res['title']}")
                                            logger.info(f"    Assignee: {res.get('assignee', 'N/A')}")
                                            logger.info(f"    Applicant: {res.get('applicant', 'N/A')}")
                                            logger.info(f"    Ownership Match: YES")
                                            logger.info(f"    Jurisdiction: {res['jurisdiction']}")
                                            logger.info(f"    Publication Date: {res['publication_date']}")
                                    
                                    # Update query status
                                    comp_sq_model.status = SearchQueryStatus.COMPLETED
                                    comp_sq_model.page_count = 1
                                    comp_sq_model.result_count = comp_titles_accepted
                                    
                                except Exception as e:
                                    logger.error(f"  Competitor query failed: {comp_q_dict['query']} - {e}")
                                    continue
                            
                            await session.commit()
                            
                            # Log competitor diagnostics
                            logger.info(f"  Raw results: {comp_raw_results}")
                            logger.info(f"  Jurisdiction accepted: {comp_jurisdiction_accepted}")
                            logger.info(f"  Jurisdiction rejected: {comp_jurisdiction_rejected}")
                            logger.info(f"  Date accepted: {comp_date_accepted}")
                            logger.info(f"  Date rejected: {comp_date_rejected}")
                            logger.info(f"  Titles accepted: {comp_titles_accepted}")
                            logger.info(f"  Assignee/applicant matches: {comp_assignee_matches}")
                            logger.info(f"  Unique families: {comp_unique_families}")
                            logger.info("")
                            
                        except Exception as e:
                            logger.error(f"COMPETITOR DISCOVERY FAILED for {competitor}: {e}")
                            logger.error("Continuing with other competitors...")
                            continue
                    
                    logger.info("=" * 60)
                    logger.info(f"TOTAL COMPETITOR PATENTS: {len(competitor_pool)} families")
                    logger.info("=" * 60)
                else:
                    logger.info("")
                    logger.info("No competitors provided - skipping competitor discovery")
                
                # ── WEBSITE DISCOVERY (Separate Channel) ──
                from app.services.pipeline.website_service import WebsiteService
                website_service = WebsiteService()
                
                if run.mentioned_websites:
                    logger.info("")
                    logger.info("=" * 60)
                    logger.info("WEBSITE DISCOVERY")
                    logger.info("=" * 60)
                    
                    for website_url in run.mentioned_websites:
                        try:
                            domain, website_queries = website_service.generate_website_queries(website_url, profile)
                            logger.info(f"[WEBSITE DISCOVERY] Domain: {domain}")
                            logger.info(f"  Queries generated: {len(website_queries)}")
                            
                            website_evidences = []
                            
                            # Execute website searches (using regular web search, not patents)
                            for wq in website_queries[:3]:  # Limit to 3 queries per website
                                try:
                                    # Note: This would need a web search service, not patent search
                                    # For now, just log the query
                                    logger.info(f"  Query: {wq}")
                                    # TODO: Integrate with web search service when available
                                except Exception as e:
                                    logger.warning(f"  Website query failed: {wq} - {e}")
                                    continue
                            
                            # Store website evidences in ResearchRun
                            if website_evidences:
                                if not run.website_evidences:
                                    run.website_evidences = []
                                run.website_evidences.extend(website_evidences)
                                await session.commit()
                            
                            logger.info(f"  Evidence collected: {len(website_evidences)}")
                            logger.info("")
                            
                        except Exception as e:
                            logger.error(f"WEBSITE DISCOVERY FAILED for {website_url}: {e}")
                            logger.error("Continuing with other websites...")
                            continue
                    
                    logger.info("=" * 60)
                    logger.info(f"TOTAL WEBSITE SOURCES: {len(run.mentioned_websites)}")
                    logger.info("=" * 60)
                else:
                    logger.info("")
                    logger.info("No websites provided - skipping website discovery")
                
                # ── FINAL EVIDENCE SUMMARY ──
                logger.info("")
                logger.info("=" * 60)
                logger.info("FINAL EVIDENCE SUMMARY")
                logger.info("=" * 60)
                logger.info(f"PRIMARY PATENTS: {len(global_pool)} families")
                logger.info(f"COMPETITOR PATENTS: {len(competitor_pool)} families")
                if run.competitors:
                    for comp in run.competitors:
                        comp_count = sum(1 for p in competitor_pool.values() if p.competitor_name == comp)
                        logger.info(f"  {comp}: {comp_count}")
                logger.info(f"WEBSITE SOURCES: {len(run.mentioned_websites) if run.mentioned_websites else 0}")
                logger.info(f"TOTAL PATENT EVIDENCE: Primary={len(global_pool)}, Competitor={len(competitor_pool)}")
                logger.info("=" * 60)
                    
                # ── Step 3: Gemini Semantic Ranking (Primary Only)
                await self._update_status(session, run, RunStatus.FILTERING)

                logger.info("")
                logger.info("=" * 60)
                logger.info("DISCOVERY ELIGIBLE CANDIDATES")
                logger.info("=" * 60)
                logger.info(f"Total families in discovery pool: {len(global_pool)}")

                # Count title screening distribution
                strong_count = sum(1 for r in global_pool.values() if r.title_screening_status == TitleScreeningStatus.STRONG)
                medium_count = sum(1 for r in global_pool.values() if r.title_screening_status == TitleScreeningStatus.MEDIUM)
                weak_count = sum(1 for r in global_pool.values() if r.title_screening_status == TitleScreeningStatus.WEAK)
                none_count = sum(1 for r in global_pool.values() if r.title_screening_status is None)

                logger.info(f"Title screening - STRONG: {strong_count}")
                logger.info(f"Title screening - MEDIUM: {medium_count}")
                logger.info(f"Title screening - WEAK: {weak_count}")
                logger.info(f"Title screening - NONE: {none_count}")

                # Include both STRONG and MEDIUM candidates for ranking
                # Title screening is a quality indicator, not a hard eligibility filter
                candidates_to_rank = [r for r in global_pool.values()
                                      if r.title_screening_status in (TitleScreeningStatus.STRONG, TitleScreeningStatus.MEDIUM)]

                logger.info(f"Candidates eligible for ranking (STRONG + MEDIUM): {len(candidates_to_rank)}")

                # If still insufficient, include WEAK candidates as well
                if len(candidates_to_rank) < settings.MAX_FINAL_PATENTS:
                    weak_candidates = [r for r in global_pool.values() if r.title_screening_status == TitleScreeningStatus.WEAK]
                    candidates_to_rank.extend(weak_candidates)
                    logger.info(f"Supplemented with WEAK candidates: {len(weak_candidates)}")
                    logger.info(f"Total candidates for ranking: {len(candidates_to_rank)}")

                logger.info("=" * 60)
                
                if candidates_to_rank:
                    gemini_ranking_status = "GEMINI_RANKING_FAILED"
                    ranked_results = await self.validation_service.rank_titles(
                        [{"publication_number": c.publication_number, "title": c.title} for c in candidates_to_rank], 
                        profile
                    )
                    
                    # Check if ranking actually succeeded (non-empty results with decision/reason)
                    if ranked_results and all(hasattr(r, 'decision') and hasattr(r, 'reason') for r in ranked_results):
                        gemini_ranking_status = "GEMINI_RANKING_SUCCESS"
                        # Update DB records
                        for rank_item in ranked_results:
                            for db_c in candidates_to_rank:
                                if db_c.publication_number == rank_item.publication_number:
                                    db_c.gemini_score = rank_item.score
                                    db_c.gemini_decision = rank_item.decision
                                    db_c.gemini_reason = rank_item.reason
                                    break
                        await session.commit()
                    else:
                        logger.error("GEMINI_RANKING_FAILED: LLM ranking returned invalid or empty results")
                        logger.error("Schema validation likely failed - missing decision/reason fields")
                        # Do NOT invent Gemini decisions - keep gemini fields as None
                        # Use title-screened candidates as provisional candidates
                        gemini_ranking_status = "DETERMINISTIC_FALLBACK"
                
                # ── Step 4: Top 15 Selection
                logger.info("")
                logger.info("=" * 60)
                logger.info("PRIMARY PATENT SELECTION")
                logger.info("=" * 60)
                logger.info(f"PRIMARY PATENT TARGET: {settings.MAX_FINAL_PATENTS}")
                logger.info(f"Candidates received from discovery: {len(candidates_to_rank)}")

                if gemini_ranking_status == "GEMINI_RANKING_SUCCESS":
                    # Get candidates with Gemini KEEP decision
                    gemini_keep_candidates = [c for c in candidates_to_rank if c.gemini_decision == "KEEP"]
                    gemini_keep_candidates.sort(key=lambda x: x.gemini_score or 0, reverse=True)
                    logger.info(f"Gemini KEEP candidates: {len(gemini_keep_candidates)}")

                    # If Gemini returned fewer than 15, supplement with best title-screened candidates
                    if len(gemini_keep_candidates) < settings.MAX_FINAL_PATENTS:
                        logger.warning(f"WARNING: Gemini returned {len(gemini_keep_candidates)} candidates but {settings.MAX_FINAL_PATENTS} primary patents are required.")
                        logger.warning("Supplementing with best title-screened candidates to reach target.")

                        # Get candidates not in Gemini KEEP set
                        other_candidates = [c for c in candidates_to_rank if c.gemini_decision != "KEEP"]
                        other_candidates.sort(key=lambda x: x.title_score or 0, reverse=True)

                        # Combine: Gemini KEEP first, then best title-screened
                        final_candidates = gemini_keep_candidates + other_candidates
                        logger.info(f"Supplemented with {len(other_candidates)} title-screened candidates")
                    else:
                        final_candidates = gemini_keep_candidates
                        logger.info("Gemini returned sufficient candidates - no supplementation needed")

                    # Sort combined set by score (Gemini score first, then title score)
                    final_candidates.sort(key=lambda x: (x.gemini_score or 0, x.title_score or 0), reverse=True)
                    top_15 = final_candidates[:settings.MAX_FINAL_PATENTS]
                    logger.info(f"GEMINI_RANKING_SUCCESS: {len(top_15)} candidates selected (target: {settings.MAX_FINAL_PATENTS})")
                else:
                    # Ranking failed - use title-screened candidates as provisional
                    logger.warning(f"{gemini_ranking_status}: Using title-screened candidates as provisional selection")
                    top_15 = sorted(candidates_to_rank, key=lambda x: x.title_score or 0, reverse=True)[:settings.MAX_FINAL_PATENTS]
                    # Mark these as provisional in DB
                    for c in top_15:
                        c.gemini_decision = "PROVISIONAL"
                        c.gemini_reason = "Gemini ranking failed; candidate selected using deterministic title screening."
                    await session.commit()
                    logger.info(f"DETERMINISTIC_FALLBACK: {len(top_15)} candidates selected (target: {settings.MAX_FINAL_PATENTS})")

                logger.info("=" * 60)
                
                # Mark final candidates in database
                for rank, candidate in enumerate(top_15, 1):
                    candidate.selection_rank = rank
                    candidate.is_final_selection = True
                await session.commit()
                
                logger.info(f"Top {len(top_15)} candidates selected: {[c.publication_number for c in top_15]}")
                
                # Log final selection details
                logger.info("================ FINAL TOP PATENTS ================")
                for rank, candidate in enumerate(top_15, 1):
                    score = candidate.gemini_score if candidate.gemini_score else candidate.title_score
                    decision = candidate.gemini_decision if candidate.gemini_decision else "PROVISIONAL"
                    reason = candidate.gemini_reason if candidate.gemini_reason else "Title-based selection"
                    logger.info(f"Rank {rank}:")
                    logger.info(f"  Patent: {candidate.publication_number}")
                    logger.info(f"  Title: {candidate.title}")
                    logger.info(f"  Jurisdiction: {candidate.jurisdiction}")
                    logger.info(f"  Score: {score}")
                    logger.info(f"  Decision: {decision}")
                    logger.info(f"  Reason: {reason}")
                logger.info("=======================================================")
                
                # ── Step 5: Deep Extraction
                await self._update_status(session, run, RunStatus.EXTRACTING)

                logger.info("")
                logger.info("=" * 60)
                logger.info("PRIMARY EXTRACTION")
                logger.info("=" * 60)
                logger.info(f"Primary target: {settings.MAX_FINAL_PATENTS}")
                logger.info(f"Primary selected: {len(top_15)}")
                logger.info(f"Extraction started: {len(top_15)}")

                extraction_success_count = 0
                extraction_failure_count = 0

                # Process in Token-Aware batches of 3
                batch_size = 3
                batches = [top_15[i:i + batch_size] for i in range(0, len(top_15), batch_size)]
                
                for b_idx, batch_cands in enumerate(batches):
                    # DB Record
                    b_model = ExtractionBatch(
                        research_run_id=self.run_id,
                        batch_number=b_idx + 1,
                        patent_ids=[c.publication_number for c in batch_cands],
                        status=BatchStatus.PROCESSING,
                        started_at=datetime.now(timezone.utc)
                    )
                    session.add(b_model)
                    await session.commit()
                    
                    for cand in batch_cands:
                        try:
                            # Fetch Full text
                            doc = await self.patent_repo.get_by_patent_number(session, cand.publication_number)
                            if doc:
                                parsed_patent = ParsedPatent(
                                    url=cand.url, abstract=doc.abstract or "", detailed_description=doc.description or "",
                                    examples=doc.examples or "", claims=doc.claims or ""
                                )
                            else:
                                parsed_patent = await self.fetcher_service.fetch_patent(cand.url)
                                if parsed_patent:
                                    await self.patent_repo.create_or_update(session, {
                                        "patent_number": cand.publication_number, "jurisdiction": cand.jurisdiction,
                                        "title": cand.title, "abstract": parsed_patent.abstract,
                                        "description": parsed_patent.detailed_description, "examples": parsed_patent.examples,
                                        "claims": parsed_patent.claims, "publication_date": cand.publication_date
                                    })
                                    
                            if not parsed_patent:
                                logger.error(f"Patent {cand.publication_number}: FAILED - Could not fetch patent document")
                                extraction_failure_count += 1
                                continue

                            # Extract
                            ext = await self.extractor_service.extract_patent(
                                parsed_patent=parsed_patent,
                                patent_number=cand.publication_number,
                                title=cand.title,
                                jurisdiction=cand.jurisdiction,
                                source_url=cand.url,
                                skip_llm=False
                            )
                            if ext and ext.extraction:
                                ext.extraction.metadata.publication_year = cand.publication_date
                                extractions_by_patent[cand.publication_number] = ext.extraction
                                extraction_success_count += 1
                                logger.info(f"Patent {cand.publication_number}: Extraction SUCCESS")

                                # Missing Data Diagnostics
                                logger.info(f"--- MISSING DATA DIAGNOSTICS: {cand.publication_number} ---")
                                logger.info(f"Document length: {len(parsed_patent.detailed_description) + len(parsed_patent.abstract)}")
                                logger.info(f"Examples found: {parsed_patent.structural_evidence.example_count}")

                                extracted_params = {p.name.lower() for p in ext.extraction.parameters}
                                logger.info(f"Acrylonitrile extracted: {'YES' if 'acrylonitrile' in extracted_params else 'NO'}")
                                logger.info(f"Butadiene extracted: {'YES' if 'butadiene' in extracted_params else 'NO'}")
                                logger.info(f"Monomer ratio extracted: {'YES' if any('ratio' in p for p in extracted_params) else 'NO'}")
                                logger.info(f"Water extracted: {'YES' if 'water' in extracted_params else 'NO'}")
                                logger.info(f"Emulsifier extracted: {'YES' if 'emulsifier' in extracted_params else 'NO'}")
                                logger.info(f"Initiator extracted: {'YES' if 'initiator' in extracted_params else 'NO'}")
                                logger.info(f"Temperature extracted: {'YES' if 'temperature' in extracted_params else 'NO'}")
                                logger.info(f"Pressure extracted: {'YES' if 'pressure' in extracted_params else 'NO'}")
                                logger.info(f"pH extracted: {'YES' if 'ph' in extracted_params else 'NO'}")
                                logger.info(f"Reaction time extracted: {'YES' if 'time' in extracted_params else 'NO'}")
                                logger.info(f"Conversion extracted: {'YES' if 'conversion' in extracted_params else 'NO'}")
                                logger.info(f"LLM analysis: {'SUCCESS' if ext.status == ExtractionStatus.FULL else 'PARTIAL'}")
                                logger.info(f"--------------------------------------------------")
                            else:
                                logger.error(f"Patent {cand.publication_number}: Extraction FAILED - No extraction returned")
                                extraction_failure_count += 1

                        except Exception as e:
                            logger.error(f"Patent {cand.publication_number}: Extraction FAILED - Exception: {e}")
                            extraction_failure_count += 1
                            
                    b_model.status = BatchStatus.COMPLETED
                    b_model.completed_at = datetime.now(timezone.utc)
                    await session.commit()

                logger.info(f"Extraction completed: {extraction_success_count}")
                logger.info(f"Extraction failed: {extraction_failure_count}")
                logger.info("=" * 60)

                if not extractions_by_patent:
                    await self._mark_failed(session, run, "No valid patents could be extracted.")
                    return
                
                # ── COMPETITOR PATENT EXTRACTION (Separate Channel) ──
                competitor_extractions_by_patent = {}
                if competitor_pool:
                    logger.info("")
                    logger.info("=" * 60)
                    logger.info("COMPETITOR PATENT EXTRACTION")
                    logger.info("=" * 60)
                    logger.info(f"Competitor patents to extract: {len(competitor_pool)}")
                    
                    # Extract all competitor patents (no limit, all relevant competitor patents)
                    for comp_cand in competitor_pool.values():
                        try:
                            logger.info(f"[COMPETITOR EXTRACTION] Patent: {comp_cand.publication_number}")
                            logger.info(f"  Competitor: {comp_cand.competitor_name}")
                            
                            # Fetch Full text
                            comp_doc = await self.patent_repo.get_by_patent_number(session, comp_cand.publication_number)
                            if comp_doc:
                                comp_parsed_patent = ParsedPatent(
                                    url=comp_cand.url, abstract=comp_doc.abstract or "", detailed_description=comp_doc.description or "",
                                    examples=comp_doc.examples or "", claims=comp_doc.claims or ""
                                )
                            else:
                                comp_parsed_patent = await self.fetcher_service.fetch_patent(comp_cand.url)
                                if comp_parsed_patent:
                                    await self.patent_repo.create_or_update(session, {
                                        "patent_number": comp_cand.publication_number, "jurisdiction": comp_cand.jurisdiction,
                                        "title": comp_cand.title, "abstract": comp_parsed_patent.abstract,
                                        "description": comp_parsed_patent.detailed_description, "examples": comp_parsed_patent.examples,
                                        "claims": comp_parsed_patent.claims, "publication_date": comp_cand.publication_date
                                    })
                            
                            if not comp_parsed_patent:
                                logger.warning(f"  Failed to fetch patent document")
                                continue
                            
                            # Extract using same extraction pipeline
                            comp_ext = await self.extractor_service.extract_patent(
                                parsed_patent=comp_parsed_patent,
                                patent_number=comp_cand.publication_number,
                                title=comp_cand.title,
                                jurisdiction=comp_cand.jurisdiction,
                                source_url=comp_cand.url,
                                skip_llm=False
                            )
                            
                            if comp_ext and comp_ext.extraction:
                                comp_ext.extraction.metadata.publication_year = comp_cand.publication_date
                                competitor_extractions_by_patent[comp_cand.publication_number] = comp_ext.extraction
                                
                                # Log extraction success
                                logger.info(f"  Extraction: SUCCESS")
                                logger.info(f"  Examples found: {comp_parsed_patent.structural_evidence.example_count}")
                                logger.info(f"  LLM analysis: {comp_ext.status.name}")
                            else:
                                logger.warning(f"  Extraction: FAILED")
                                
                        except Exception as e:
                            logger.error(f"COMPETITOR EXTRACTION FAILED for {comp_cand.publication_number}: {e}")
                            logger.error("Continuing with other competitor patents...")
                            continue
                    
                    logger.info("=" * 60)
                    logger.info(f"COMPETITOR EXTRACTION COMPLETE: {len(competitor_extractions_by_patent)} extracted")
                    logger.info("=" * 60)

                # ── Step 6: Generate Report
                await self._update_status(session, run, RunStatus.GENERATING)
                
                # ── FINAL REPORT EVIDENCE LOGGING ──
                logger.info("")
                logger.info("=" * 60)
                logger.info("REPORT EVIDENCE LOGGING")
                logger.info("=" * 60)
                logger.info(f"PRIMARY PATENTS: {len(extractions_by_patent)}")
                logger.info(f"COMPETITOR PATENTS: {len(competitor_extractions_by_patent)}")
                if run.competitors:
                    for comp in run.competitors:
                        comp_count = sum(1 for pn in competitor_extractions_by_patent.keys())
                        logger.info(f"  {comp}: {comp_count}")
                logger.info(f"WEBSITE SOURCES: {len(run.mentioned_websites) if run.mentioned_websites else 0}")
                logger.info(f"TOTAL PATENT EVIDENCE: Primary={len(extractions_by_patent)}, Competitor={len(competitor_extractions_by_patent)}")
                logger.info("")
                
                logger.info("[REPORT EVIDENCE]")
                for pn, ext in extractions_by_patent.items():
                    logger.info(f"Patent: {pn}")
                    logger.info(f"  Title: {ext.metadata.patent_title}")
                    logger.info(f"  Source Type: PRIMARY")
                    logger.info(f"  Competitor: N/A")
                    logger.info(f"  Evidence Size: {len(ext.parameters)} parameters, {len(ext.examples)} examples")
                    logger.info(f"  Examples Available: {len(ext.examples)}")
                    logger.info(f"  Claims Available: {'YES' if ext.claims else 'NO'}")
                    logger.info(f"  Extraction Status: SUCCESS")
                
                for pn, ext in competitor_extractions_by_patent.items():
                    logger.info(f"Patent: {pn}")
                    logger.info(f"  Title: {ext.metadata.patent_title}")
                    logger.info(f"  Source Type: COMPETITOR")
                    logger.info(f"  Competitor: {ext.metadata.assignee}")
                    logger.info(f"  Evidence Size: {len(ext.parameters)} parameters, {len(ext.examples)} examples")
                    logger.info(f"  Examples Available: {len(ext.examples)}")
                    logger.info(f"  Claims Available: {'YES' if ext.claims else 'NO'}")
                    logger.info(f"  Extraction Status: SUCCESS")
                
                logger.info("=" * 60)
                
                from app.services.pipeline.report_evidence_service import ReportEvidenceService
                report_evidence_svc = ReportEvidenceService()
                
                final_evidence = await report_evidence_svc.prepare_final_evidence(
                    extractions_by_patent, 
                    self.token_manager,
                    competitor_extractions_by_patent
                )
                
                structured_report = await self.report_service.generate_structured_report(run.compound_name, final_evidence)
                
                # Guard against None report generation
                if structured_report is None:
                    logger.error("REPORT_GENERATION_FAILED: generate_structured_report returned None")
                    await self._mark_failed(session, run, "Report generation failed - LLM returned None")
                    return
                
                markdown_report = self.report_service.report_to_markdown(structured_report)
                
                pdf_name = f"APCOTEX_Report_{self.run_id}_{run.report_version}.pdf"
                docx_name = f"APCOTEX_Report_{self.run_id}_{run.report_version}.docx"
                md_name = f"APCOTEX_Report_{self.run_id}_{run.report_version}.md"
                json_name = f"APCOTEX_Report_{self.run_id}_{run.report_version}.json"
                
                export_dir = self.report_service.export_dir
                
                with open(os.path.join(export_dir, md_name), "w", encoding="utf-8") as f:
                    f.write(markdown_report)
                with open(os.path.join(export_dir, json_name), "w", encoding="utf-8") as f:
                    f.write(structured_report.model_dump_json(indent=2))

                pdf_path = await self.report_service.export_to_pdf(markdown_report, pdf_name)
                docx_path = await self.report_service.export_to_docx(markdown_report, docx_name)
                
                meta = ReportMetadata(
                    research_run_id=run.id,
                    title=structured_report.title,
                    summary=structured_report.abstract,
                    patent_count=len(extractions_by_patent),
                    source_count=len(extractions_by_patent),
                    version=run.report_version,
                    generated_at=datetime.now(timezone.utc),
                    structured_data=structured_report.model_dump()
                )
                session.add(meta)
                await session.flush()
                
                if pdf_path:
                    session.add(ReportFile(report_metadata_id=meta.id, file_type="PDF", file_name=pdf_name, file_path=pdf_path))
                if docx_path:
                    session.add(ReportFile(report_metadata_id=meta.id, file_type="MARKDOWN", file_name=docx_name, file_path=docx_path))
                session.add(ReportFile(report_metadata_id=meta.id, file_type="MARKDOWN", file_name=md_name, file_path=os.path.join(export_dir, md_name)))
                session.add(ReportFile(report_metadata_id=meta.id, file_type="JSON", file_name=json_name, file_path=os.path.join(export_dir, json_name)))
                
                await self._update_status(session, run, RunStatus.COMPLETED)
                logger.info("Pipeline Complete!")

            except ProviderExhaustedException as e:
                if not extractions_by_patent:
                    logger.error("Pipeline failed due to LLM provider exhaustion before any patents could be extracted: %s", e)
                    await self._mark_failed(session, run, f"LLM provider exhausted: {str(e)}")
                else:
                    logger.error("Pipeline paused due to LLM provider quota exhaustion, partial results available: %s", e)
                    await self._update_status(session, run, RunStatus.COMPLETED_PARTIAL)
            except Exception as e:
                import traceback
                logger.error("Pipeline failure: %s\n%s", e, traceback.format_exc())
                await self._mark_failed(session, run, str(e))
