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

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_actions import AuditAction, AuditEntityType
from app.core.config import settings
from app.core.telemetry import set_current_run_id, set_current_stage, TelemetryStage
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
from app.services.pipeline.title_scorer import TitleScorer, TitleScreeningStatus, TIER_ACCEPT, TIER_GENERIC_VERIFY, TIER_REJECTED
from app.services.pipeline.schemas import CompoundSearchProfile, ParsedPatent, ExtractionStatus
from app.repositories.patent_document_repository import PatentDocumentRepository
from app.services.audit_service import AuditService
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

            # Log research lifecycle events (non-blocking)
            try:
                audit_service = AuditService(session)
                if status == RunStatus.SEARCHING:
                    # Research actually starts when we begin searching
                    await audit_service.log(
                        user_id=str(run.created_by),
                        action=AuditAction.RESEARCH_STARTED,
                        entity_type=AuditEntityType.RESEARCH_RUN,
                        entity_id=str(run.id),
                        detail={"compound": run.compound_name},
                    )
                elif status == RunStatus.COMPLETED:
                    await audit_service.log(
                        user_id=str(run.created_by),
                        action=AuditAction.RESEARCH_COMPLETED,
                        entity_type=AuditEntityType.RESEARCH_RUN,
                        entity_id=str(run.id),
                        detail={"compound": run.compound_name, "status": "COMPLETED"},
                    )
            except Exception as e:
                # Audit logging failures must not break the research pipeline
                logger.exception("Failed to log audit event for status %s", status.name)
        except Exception as e:
            await session.rollback()
            logger.error("Failed to update status to %s for run %s: %s", status.name, self.run_id, e)
            raise e

    async def safe_update_run_status(self, session: AsyncSession, run: ResearchRun, status: RunStatus):
        try:
            await self._update_status(session, run, status)
        except Exception as e:
            logger.error("Primary status update to %s failed: %s", status.name, e)
            if status != RunStatus.FAILED:
                logger.info("Attempting fallback status update to FAILED")
                try:
                    await self._update_status(session, run, RunStatus.FAILED)
                except Exception as fallback_e:
                    logger.critical("CRITICAL: Fallback status update to FAILED also failed! Run %s is stuck. Error: %s", self.run_id, fallback_e)

    async def _mark_failed(self, session: AsyncSession, run: ResearchRun, error_msg: str):
        logger.error("Run %s FAILED: %s", self.run_id, error_msg)
        # Rollback any existing failed transaction before attempting to update status
        await session.rollback()
        await self.safe_update_run_status(session, run, RunStatus.FAILED)

        # Log research failure (non-blocking)
        try:
            audit_service = AuditService(session)
            await audit_service.log(
                user_id=str(run.created_by),
                action=AuditAction.RESEARCH_FAILED,
                entity_type=AuditEntityType.RESEARCH_RUN,
                entity_id=str(run.id),
                detail={"compound": run.compound_name, "error": error_msg[:500]},  # Truncate long errors
            )
        except Exception as e:
            # Audit logging failures must not break the research pipeline
            logger.exception("Failed to log research failure audit event")

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
                # --- MOCK TESTING BLOCKS (TEST B, C, D) ---
                if run.compound_name == "Test B":
                    raise ProviderExhaustedException("Mock Gemini quota exhausted")
                if run.compound_name == "Test C":
                    raise Exception("Mock generic exception")
                if run.compound_name == "Test D":
                    await self._update_status(session, run, RunStatus.COMPLETED)
                    logger.info("Mock Test D completed.")
                    return
                # --- END MOCK TESTING BLOCKS ---
                
                from app.services.llm.llm_client import llm_client
                llm_client.reset_health()
                
                extractions_by_patent = {}
                allowed_authorities = run.jurisdictions if run.jurisdictions else ["US", "EP"]
                date_start = run.publication_filter.get("year_from", "") if run.publication_filter else ""
                if date_start: date_start = f"{date_start}0101"
                date_end = run.publication_filter.get("year_to", "") if run.publication_filter else ""
                if date_end: date_end = f"{date_end}1231"

                # ── Step 1: Profile Loading
                set_current_run_id(self.run_id)
                set_current_stage(TelemetryStage.QUERY_EXPANSION)
                profile = await self.compound_intelligence.generate_profile(run.compound_name)
                title_scorer = TitleScorer(profile)
                
                await self._update_status(session, run, RunStatus.SEARCHING)
                
                # ── QUERY EXPANSION LOGGING
                from app.models.api_usage_log import APIUsageLog
                try:
                    usage_res = await session.execute(
                        select(
                            func.sum(APIUsageLog.total_tokens).label("total_tokens"),
                            func.sum(APIUsageLog.input_tokens).label("input_tokens"),
                            func.sum(APIUsageLog.output_tokens).label("output_tokens")
                        ).where(APIUsageLog.research_run_id == self.run_id)
                    )
                    usage_row = usage_res.first()
                    qe_in = usage_row.input_tokens or 0
                    qe_out = usage_row.output_tokens or 0
                    qe_tot = usage_row.total_tokens or 0
                except:
                    qe_in, qe_out, qe_tot = 0, 0, 0

                logger.info("")
                logger.info("============================================================")
                logger.info("QUERY EXPANSION")
                logger.info(f"- Input tokens: {qe_in}")
                logger.info(f"- Output tokens: {qe_out}")
                logger.info(f"- Total tokens: {qe_tot}")
                logger.info("============================================================")
                
                # ── Step 2: Build Queries & Pagination Search
                set_current_stage(TelemetryStage.PATENT_SEARCH)
                raw_queries = self.search_service.build_queries(profile)
                
                # ── DISCOVERY CONFIGURATION LOGGING
                logger.info("=" * 60)
                logger.info("DISCOVERY CONFIGURATION")
                logger.info("=" * 60)
                logger.info(f"Original Input: {profile.original_input}")
                logger.info(f"Base Compound: {profile.compound_name}")
                logger.info(f"Competitors: {', '.join(run.competitors) if run.competitors else 'None'}")
                logger.info(f"External Websites: {', '.join(run.mentioned_websites) if run.mentioned_websites else 'None'}")
                logger.info(f"Jurisdictions: {', '.join(run.jurisdictions) if run.jurisdictions else 'ALL (Unrestricted)'}")
                
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
                global_pool = {} # Family ID -> best ACCEPTED SearchResult
                target_families = settings.PRIMARY_PATENT_TARGET
                final_keep_patents = []
                validated_publication_numbers = set()
                
                # Global Diagnostic Accumulators
                total_queries_attempted = 0
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
                total_non_polymerization_rejected = 0
                total_exact_duplicates = 0
                total_family_duplicates = 0
                total_family_unique = 0
                global_pool = {}
                global_pool_raw = {}
                family_seen = set()
                competitor_pool = {}
                failed_queries = []
                all_evaluated_candidates = []
                rejection_reason_counts = {}  # Compact rejection reason histogram
                # Main Search (Global Pool Collection)
                search_exhausted = False
                llm_provider_exhausted = False
                serper_credits_exhausted = False
                
                logger.info("============================================================")
                logger.info("DETERMINISTIC DISCOVERY (PHASE 2)")
                logger.info("============================================================")
                logger.info(f"Target FINAL KEEP primary candidates: {target_families}")
                
                max_pages = settings.MAX_SEARCH_PAGES_PER_QUERY
                
                for idx, q_dict in enumerate(raw_queries):
                    if serper_credits_exhausted or search_exhausted:
                        break
                        
                    for page in range(1, max_pages + 1):
                        if serper_credits_exhausted:
                            break
                        logger.info(f"\n--- STARTING DISCOVERY QUERY {q_dict['query']} (PAGE {page}) ---")
                        
                        if page == 1:
                            is_valid, validation_reason = self.search_service.validate_query(q_dict["query"], q_dict["search_field"])
                            if not is_valid:
                                total_queries_failed += 1
                                continue
                            
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
                            await session.flush()
                            if not hasattr(self, '_sq_models'): self._sq_models = {}
                            self._sq_models[idx] = sq_model
                            total_queries_attempted += 1
                        
                        sq_model = getattr(self, '_sq_models', {}).get(idx)
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
                            if page == 1: total_queries_failed += 1
                            continue

                        # Implement 1-retry fallback for 400 errors / failures on page 1
                        if not page_success and page == 1:
                            logger.warning(f"Query failed on page 1: '{q_dict['query']}'. Sanitizing and retrying once.")
                            import re as regex
                            sanitized_query = regex.sub(r'[^a-zA-Z0-9\s]', ' ', q_dict["query"])
                            sanitized_query = regex.sub(r'\s+', ' ', sanitized_query).strip()
                            
                            # IMPORTANT: Update the query so subsequent pages use the sanitized version
                            q_dict["query"] = sanitized_query
                            if sq_model:
                                sq_model.query_text = sanitized_query
                                session.add(sq_model)
                                await session.flush()
                            
                            try:
                                page_results, page_success = await self.search_service.search_patents_page(
                                    query_str=sanitized_query,
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
                                continue
                            
                        if page_success:
                            total_pages_successful += 1
                            if sq_model and page == 1:
                                total_queries_successful += 1
                                sq_model.status = SearchQueryStatus.COMPLETED
                        else:
                            total_pages_failed += 1
                            if page == 1: total_queries_failed += 1
                            break
                            
                        if not page_results:
                            break
                            
                        total_raw_results += len(page_results)
                        import re as regex
                        
                        for res in page_results:
                            if search_exhausted:
                                break
                            
                            if not res.get("title"):
                                continue
                            total_titles_extracted += 1
                            
                            # Jurisdiction Filter
                            if allowed_authorities and res["jurisdiction"] not in [j.upper() for j in allowed_authorities]:
                                total_jurisdiction_rejected += 1
                                continue
                                
                            # Date Filter
                            if date_start or date_end:
                                pub_date = res.get("publication_date", "").replace("-", "")
                                if pub_date:
                                    if date_start and pub_date < date_start:
                                        total_date_rejected += 1
                                        continue
                                    if date_end and pub_date > date_end:
                                        total_date_rejected += 1
                                        continue
                            
                            # Exact Deduplication
                            pn = res["patent_number"]
                            if pn in global_pool_raw:
                                total_exact_duplicates += 1
                                continue
                            global_pool_raw[pn] = True
                            
                            # Family Deduplication
                            family_id = regex.sub(r'[A-Za-z]\d?$', '', pn)
                            is_duplicate = family_id in family_seen
                            if is_duplicate:
                                total_family_duplicates += 1
                            else:
                                family_seen.add(family_id)
                                total_family_unique += 1
                            # Candidate Relevance Filter (Strict Two-Stage Title Screen)
                            score, tier, signals = title_scorer.score_candidate_tiered(
                                title=res.get("title", ""),
                                snippet=res.get("snippet", ""),
                                source_query=q_dict.get("query", "")
                            )
                            # Backward-compat status for DB storage
                            _, status, _ = title_scorer.score_candidate(
                                title=res.get("title", ""),
                                snippet=res.get("snippet", ""),
                                source_query=q_dict.get("query", "")
                            )

                            # ── STRUCTURED PATENT TITLE SCREEN LOG ──────────────
                            logger.info("\nPATENT TITLE SCREEN")
                            logger.info(f"Patent: {res.get('patent_number')}")
                            logger.info(f"Title: {res.get('title')}")
                            logger.info(f"Target Material: {signals.get('matched_material') or 'NO MATCH'}")
                            logger.info(f"Synthesis Terms: {signals.get('matched_synthesis') or 'NO MATCH'}")
                            logger.info(f"Downstream Subject: {signals.get('matched_downstream') or 'NOT DETECTED'}")
                            logger.info(f"Exclusion Match: {signals.get('matched_exclusion') or 'NONE'}")
                            logger.info(f"Direct Synthesis Candidate: {'YES' if tier == TIER_ACCEPT else ('PENDING VERIFY' if tier == TIER_GENERIC_VERIFY else 'NO')}")
                            logger.info(f"Decision: {tier}")
                            if tier == TIER_ACCEPT:
                                reason_str = signals.get('rejection_reason') or 'ACCEPT — direct target polymer synthesis'
                            elif tier == TIER_GENERIC_VERIFY:
                                reason_str = signals.get('rejection_reason') or 'GENERIC_VERIFY — target evidence + synthesis requires content check'
                            else:
                                reason_str = signals.get('rejection_reason') or 'REJECTED'
                            logger.info(f"Reason: {reason_str}")
                            logger.info("-" * 60)

                            all_evaluated_candidates.append({
                                'patent_number': res['patent_number'],
                                'title': res['title'],
                                'score': score,
                                'tier': tier,
                                'status': status.name,
                                'rejection_reason': signals.get('rejection_reason', ''),
                                'signals': signals,
                            })

                            if tier == TIER_REJECTED:
                                total_titles_rejected += 1
                                reason_code = signals.get("rejection_reason", "UNKNOWN")
                                rejection_reason_counts[reason_code] = rejection_reason_counts.get(reason_code, 0) + 1
                                continue

                            total_titles_accepted += 1
                            
                            db_res = SearchResult(
                                research_run_id=self.run_id,
                                search_query_id=sq_model.id if sq_model else None,
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
                            # Tag whether this is a GENERIC_VERIFY candidate
                            db_res._title_tier = tier  # transient attr for content-verify pass
                            session.add(db_res)

                            # Route to primary pool only
                            target_pool = global_pool

                            if is_duplicate:
                                existing = target_pool.get(family_id)
                                if existing:
                                    queries = existing.discovered_by_queries or []
                                    if q_dict["query"] not in queries:
                                        queries.append(q_dict["query"])
                                    if (existing.title_score or 0) < score:
                                        db_res.discovered_by_queries = queries
                                        target_pool[family_id] = db_res
                                    else:
                                        existing.discovered_by_queries = list(queries)
                                else:
                                    target_pool[family_id] = db_res
                            else:
                                target_pool[family_id] = db_res
                        await session.flush()
                        
                        if sq_model:
                            sq_model.page_count = page
                            sq_model.result_count = (sq_model.result_count or 0) + len(page_results)
                            await session.commit()
                            
                        # Check Early Stopping — only when primary pool is large enough
                        if len(global_pool) >= target_families:
                            search_exhausted = True
                            logger.info(
                                "Target of %d PRIMARY candidates reached. Stopping search early.",
                                target_families
                            )
                            break

                # ── SEARCH RESULTS SUMMARY ──────────────────────────────────
                logger.info("")
                logger.info("SEARCH RESULTS:")
                logger.info(f"Raw unique patents: {total_family_unique}")
                logger.info("")
                logger.info("TITLE SCREEN:")
                logger.info(f"Accepted: {total_titles_accepted}")
                logger.info(f"Rejected: {total_titles_rejected}")

                # ── Stage 2: Content Verification for GENERIC_VERIFY candidates ──
                # Fetch these candidates' content now (before final selection) to
                # decide whether they should be upgraded to ACCEPT or rejected.
                generic_verify_candidates = [
                    cand for cand in global_pool.values()
                    if getattr(cand, '_title_tier', TIER_ACCEPT) == TIER_GENERIC_VERIFY
                ]
                content_verified = 0
                content_rejected = 0
                generic_verify_rejected_ids = set()

                logger.info("")
                logger.info("CONTENT VERIFICATION:")
                logger.info(f"Verified candidates: {len(generic_verify_candidates)}")

                for gv_cand in generic_verify_candidates:
                    # Try to get cached document first
                    try:
                        gv_doc = await self.patent_repo.get_by_patent_number(session, gv_cand.publication_number)
                        if gv_doc:
                            gv_parsed = ParsedPatent(
                                url=gv_cand.url,
                                abstract=gv_doc.abstract or "",
                                detailed_description=gv_doc.description or "",
                                examples=gv_doc.examples or "",
                                claims=gv_doc.claims or "",
                                patent_number=gv_cand.publication_number
                            )
                        else:
                            gv_parsed = await self.fetcher_service.fetch_patent(gv_cand.url)
                            if gv_parsed:
                                gv_parsed.patent_number = gv_cand.publication_number
                    except Exception as e:
                        logger.warning("Content fetch failed for GENERIC_VERIFY %s: %s", gv_cand.publication_number, e)
                        gv_parsed = None

                    val_result = title_scorer.verify_content(gv_parsed, profile)
                    
                    logger.info("CONTENT VERIFY | %s | %s", gv_cand.publication_number, val_result.rejection_reason)
                    if val_result.target_identity_evidence:
                        logger.info(f"  [TARGET_IDENTITY_EVIDENCE] {val_result.target_identity_evidence}")
                    if val_result.precursor_evidence and val_result.transformation_evidence:
                        logger.info(f"  [PRECURSOR_EVIDENCE] {val_result.precursor_evidence}")
                        logger.info(f"  [TRANSFORMATION_EVIDENCE] {val_result.transformation_evidence}")
                    logger.info(f"  [MATERIAL] {'MATCH' if val_result.material_match else 'NO_MATCH'}")
                    logger.info(f"  [SYNTHESIS] {'MATCH' if val_result.synthesis_match else 'NO_MATCH'} | [SYNTHESIS_EVIDENCE] {val_result.synthesis_evidence}")
                    logger.info(f"  [ATTRIBUTE] {val_result.attribute_match} | [ATTRIBUTE_EVIDENCE] {val_result.attribute_evidence}")
                    logger.info(f"  [FORMULATION_ONLY] {'YES' if val_result.formulation_only else 'NO'}")
                    logger.info(f"  [DOWNSTREAM_ONLY] {'YES' if val_result.downstream_only else 'NO'}")
                    logger.info(f"  [BACKGROUND_ONLY] {'YES' if val_result.background_only else 'NO'}")
                    logger.info(f"  [PRECURSOR_ONLY] {'YES' if val_result.precursor_only else 'NO'}")
                    logger.info(f"  [VALIDATION] {val_result.final_decision}")

                    if val_result.final_decision == "UNCERTAIN":
                        logger.info("  -> Attempting targeted extraction to resolve uncertainty")
                        if gv_parsed:
                            try:
                                ext_res = await self.extractor_service.extract_patent(
                                    parsed_patent=gv_parsed,
                                    patent_number=gv_cand.publication_number,
                                    title=gv_cand.title,
                                    jurisdiction=gv_cand.jurisdiction,
                                    source_url=gv_cand.url,
                                    profile=profile
                                )
                                if ext_res and ext_res.extraction and (len(ext_res.extraction.parameters) > 0 or len(ext_res.extraction.examples) > 0):
                                    val_result.final_decision = "ACCEPT"
                                    logger.info("  -> RESOLVED TO ACCEPT via targeted extraction")
                                else:
                                    val_result.final_decision = "REJECT"
                                    logger.info("  -> RESOLVED TO REJECT (targeted extraction found 0 evidence)")
                            except Exception as e:
                                logger.error(f"Targeted extraction failed for {gv_cand.publication_number}: {e}")
                                val_result.final_decision = "REJECT"

                    if val_result.final_decision == "ACCEPT":
                        content_verified += 1
                        gv_cand._title_tier = TIER_ACCEPT  # promote
                        # Cache for later fetch step
                        if gv_parsed and gv_doc is None:
                            try:
                                await self.patent_repo.create_or_update(session, {
                                    "patent_number": gv_cand.publication_number,
                                    "jurisdiction": gv_cand.jurisdiction,
                                    "title": gv_cand.title,
                                    "abstract": gv_parsed.abstract,
                                    "description": gv_parsed.detailed_description,
                                    "examples": gv_parsed.examples,
                                    "claims": gv_parsed.claims,
                                    "publication_date": gv_cand.publication_date
                                })
                            except Exception:
                                pass
                    else:
                        content_rejected += 1
                        generic_verify_rejected_ids.add(gv_cand.publication_number)
                        # Remove from pool
                        for fid, poolcand in list(global_pool.items()):
                            if poolcand.publication_number == gv_cand.publication_number:
                                del global_pool[fid]
                                break

                logger.info(f"Accepted after verification: {content_verified}")
                logger.info(f"Rejected after verification: {content_rejected}")

                # Rank primary pool by score descending, cap at target_families
                primary_candidates = sorted(
                    global_pool.values(),
                    key=lambda x: -(x.title_score or 0)
                )
                final_keep_patents = primary_candidates[:target_families]

                total_detected = total_family_unique
                total_eligible = len(final_keep_patents)
                
                # Mark candidates for DB tracking
                for rank, candidate in enumerate(final_keep_patents, 1):
                    candidate.selection_rank = rank
                    candidate.is_final_selection = True
                    candidate.gemini_decision = "KEEP"

                await session.commit()

                # ── FINAL TELEMETRY ────────────────────────────
                total_downstream_rejected = 0
                total_variant_rejected = 0
                total_material_match = 0
                total_synthesis_match = 0

                for c in all_evaluated_candidates:
                    sigs = c.get('signals', {})
                    if sigs.get('matched_material'):
                        total_material_match += 1
                    if sigs.get('matched_synthesis'):
                        total_synthesis_match += 1
                    reason = c.get('rejection_reason', '')
                    if 'downstream' in reason.lower():
                        total_downstream_rejected += 1
                    if 'exclusion' in reason.lower() or 'mismatch' in reason.lower():
                        total_variant_rejected += 1

                logger.info("")
                logger.info("============================================================")
                logger.info("FINAL TELEMETRY")
                logger.info("============================================================")
                logger.info(f"RAW RESULTS: {total_raw_results}")
                logger.info(f"UNIQUE RESULTS: {total_family_unique}")
                logger.info(f"TITLE MATERIAL MATCH: {total_material_match}")
                logger.info(f"SYNTHESIS TITLE MATCH: {total_synthesis_match}")
                logger.info(f"DOWNSTREAM REJECTED: {total_downstream_rejected}")
                logger.info(f"VARIANT MISMATCH REJECTED: {total_variant_rejected}")
                logger.info(f"CONTENT VERIFY REJECTED: {content_rejected}")
                logger.info(f"FAMILY DUPLICATES REMOVED: {total_family_duplicates}")
                logger.info(f"FINAL RELEVANT PATENTS: {len(final_keep_patents)} / {target_families}")
                logger.info("============================================================")
                logger.info("")
                
                logger.info("")
                logger.info("============================================================")
                logger.info("PATENT SEARCH")
                logger.info(f"- Queries generated: {len(raw_queries)}")
                logger.info(f"- Searches executed: {total_pages_attempted}")
                logger.info(f"- Successful requests: {total_pages_successful}")
                logger.info(f"- Failed requests: {total_pages_failed}")
                logger.info(f"- Serper credits: {total_pages_successful}")
                
                logger.info("")
                logger.info("TITLE SCREENING")
                logger.info(f"- Candidates: {total_detected}")
                logger.info(f"- Accepted: {total_eligible}")
                logger.info(f"- Rejected: {total_titles_rejected}")
                
                logger.info("")
                logger.info("PATENT SELECTION")
                logger.info(f"- Target maximum: {target_families}")
                logger.info(f"- Relevant patents found: {total_eligible}")
                logger.info(f"- Final selected count: {len(final_keep_patents)}")
                logger.info("============================================================")

                logger.info("")
                logger.info("FINAL SELECTION:")
                logger.info(f"Selected: {len(final_keep_patents)} / {target_families}")
                direct_synthesis_only = all(
                    getattr(c, '_title_tier', TIER_ACCEPT) in (TIER_ACCEPT,)
                    for c in final_keep_patents
                )
                logger.info(f"FINAL QUALITY CHECK:")
                logger.info(f"Direct synthesis patents only: {'YES' if direct_synthesis_only else 'NO'}")
                
                if len(final_keep_patents) == 0:
                    if total_raw_results == 0:
                        msg = "Pipeline FAILED — SEARCH_FAILED: No search results were returned by the discovery layer."
                        if total_pages_successful == 0 and total_pages_attempted > 0:
                            msg = "Pipeline FAILED — SEARCH_FAILED: All Serper API requests failed."
                    else:
                        msg = "Pipeline FAILED — RELEVANCE_VALIDATION_FAILED: Candidates were found but rejected by relevance validation."
                    logger.error(msg)
                    await self._update_status(session, run, RunStatus.FAILED)
                    return
                
                # ── Step 5: Deep Extraction
                await self._update_status(session, run, RunStatus.EXTRACTING)
                set_current_stage(TelemetryStage.PATENT_EXTRACTION)

                logger.info("")
                logger.info("============================================================")
                logger.info("DEEP EXTRACTION")
                logger.info("============================================================")

                extraction_success_count = 0
                extraction_failure_count = 0

                # 1. Fetch and Prepare Extraction
                logger.info("Fetching documents and preparing extraction...")
                fetch_attempted = len(final_keep_patents)
                fetch_successful = 0
                fetch_failed = 0
                fetch_failure_reasons = []
                
                prep_successful = 0
                prep_failed = 0
                prep_failure_reasons = []
                
                prep_contexts = {}
                provider_safe_limit = 9000 # GROQ safe limit
                
                extraction_results = {}
                
                for cand in final_keep_patents:
                    try:
                        doc = await self.patent_repo.get_by_patent_number(session, cand.publication_number)
                        if doc:
                            cand._parsed = ParsedPatent(
                                url=cand.url, abstract=doc.abstract or "", detailed_description=doc.description or "",
                                examples=doc.examples or "", claims=doc.claims or "", patent_number=cand.publication_number
                            )
                        else:
                            cand._parsed = await self.fetcher_service.fetch_patent(cand.url)
                            if cand._parsed:
                                cand._parsed.patent_number = cand.publication_number
                                await self.patent_repo.create_or_update(session, {
                                    "patent_number": cand.publication_number, "jurisdiction": cand.jurisdiction,
                                    "title": cand.title, "abstract": cand._parsed.abstract,
                                    "description": cand._parsed.detailed_description, "examples": cand._parsed.examples,
                                    "claims": cand._parsed.claims, "publication_date": cand.publication_date
                                })
                        
                        if cand._parsed:
                            fetch_successful += 1
                        else:
                            fetch_failed += 1
                            fetch_failure_reasons.append(f"{cand.publication_number}: parser returned None")
                            continue
                            
                    except Exception as e:
                        fetch_failed += 1
                        fetch_failure_reasons.append(f"{cand.publication_number}: fetch error {str(e)}")
                        logger.error(f"Fetch failed for {cand.publication_number}: {e}")
                        continue
                        
                    # EXTRACTION PHASE (Integrated deterministic & LLM)
                    try:
                        ext_res = await self.extractor_service.extract_patent(
                            parsed_patent=cand._parsed,
                            patent_number=cand.publication_number,
                            title=cand.title,
                            jurisdiction=cand.jurisdiction,
                            source_url=cand.url,
                            profile=profile
                        )
                        
                        if ext_res and ext_res.extraction:
                            ext_res.extraction.metadata.publication_year = cand.publication_date
                            extractions_by_patent[cand.publication_number] = ext_res.extraction
                            extraction_results[cand.publication_number] = ext_res
                            extraction_success_count += 1
                        else:
                            logger.error(f"Extraction failed (null result) for {cand.publication_number}")
                            
                    except Exception as e:
                        logger.error(f"Extraction failed for {cand.publication_number}: {e}")
                        continue
                
                # Check for 0 usable evidence
                if extraction_success_count == 0:
                    logger.info("=" * 60)
                    logger.info("EXTRACTION FAILED")
                    logger.info("-" * 17)
                    logger.info(f"Selected: {len(final_keep_patents)}")
                    logger.info(f"Fetched: {fetch_successful}")
                    logger.info(f"Usable evidence: 0")
                    logger.info(f"\nStatus: FAILED")
                    logger.info(f"Reason: No usable patent evidence available")
                    logger.info("=" * 60)
                    raise ValueError("No usable patent evidence available for report generation.")
                
                logger.info("=" * 60)
                logger.info("PATENT EXTRACTION")
                logger.info("=" * 60)
                logger.info(f"Selected patents: {fetch_attempted}")
                logger.info(f"Fetched successfully: {fetch_successful}")
                logger.info(f"Total parameters extracted: {sum(len(e.parameters) for e in extractions_by_patent.values())}")
                logger.info(f"Usable evidence (patents): {extraction_success_count}")
                logger.info(f"Extraction mode: DETERMINISTIC_ONLY (0 LLM calls)")
                logger.info(f"Extraction failed: {fetch_successful - extraction_success_count}")
                logger.info("=" * 60)

                # Build parsed patent lookup for source_text extraction in evidence service
                parsed_patents_by_number = {}
                for cand in final_keep_patents:
                    if hasattr(cand, '_parsed') and cand._parsed is not None:
                        parsed_patents_by_number[cand.publication_number] = cand._parsed
                
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
                                profile=profile
                            )
                            
                            if comp_ext and comp_ext.extraction:
                                comp_ext.extraction.metadata.publication_year = comp_cand.publication_date
                                competitor_extractions_by_patent[comp_cand.publication_number] = comp_ext.extraction
                                logger.info(f"  Extraction: SUCCESS | %d params, %d examples",
                                    len(comp_ext.extraction.parameters),
                                    len(comp_ext.extraction.examples)
                                )
                            else:
                                logger.warning(f"  Extraction: FAILED")
                                
                        except Exception as e:
                            logger.error(f"COMPETITOR EXTRACTION FAILED for {comp_cand.publication_number}: {e}")
                            logger.error("Continuing with other competitor patents...")
                            continue
                    
                    logger.info("=" * 60)
                    logger.info(f"COMPETITOR EXTRACTION COMPLETE: {len(competitor_extractions_by_patent)} extracted")
                    logger.info("=" * 60)

                # ── Step 5.5: Log zero-value patents (no longer dropped)
                zero_param_count = sum(
                    1 for ext in extractions_by_patent.values()
                    if not ext.parameters and not ext.examples
                )
                if zero_param_count:
                    logger.info(
                        "[EXTRACTION] %d patent(s) have 0 det params and 0 det examples — "
                        "included in report (LLM will synthesize from metadata/text).",
                        zero_param_count
                    )

                # ── Step 6: Generate Report

                if len(extractions_by_patent) == 0:
                    logger.error(
                        "EXTRACTION FAILED: 0 patents extracted. Halting pipeline."
                    )
                    await self.safe_update_run_status(session, run, RunStatus.FAILED)
                    return

                await self._update_status(session, run, RunStatus.GENERATING)
                set_current_stage(TelemetryStage.REPORT_GENERATION)

                total_chars = sum(len(ext.model_dump_json()) for ext in extractions_by_patent.values())
                logger.info("")
                logger.info("EXTRACTION")
                logger.info(f"- Selected: {len(final_keep_patents)}")
                logger.info(f"- Fetched: {fetch_successful}")
                logger.info(f"- Evidence prepared: {len(extractions_by_patent)}")
                await session.commit()

                from app.services.pipeline.report_evidence_service import ReportEvidenceService
                report_evidence_svc = ReportEvidenceService()

                final_evidence = await report_evidence_svc.prepare_final_evidence(
                    extractions_by_patent,
                    self.token_manager,
                    competitor_extractions_by_patent,
                    profile=profile,
                    selected_candidates=final_keep_patents,
                    parsed_patents_by_number=parsed_patents_by_number
                )

                # Build patent manifest (ordered list of all expected patent numbers)
                patent_manifest = list(extractions_by_patent.keys())
                structured_report, usage_data = await self.report_service.generate_structured_report(
                    run.compound_name, final_evidence,
                    patent_manifest=patent_manifest
                )


                # Guard against None report generation
                if structured_report is None:
                    logger.error("REPORT_GENERATION_FAILED: generate_structured_report returned None")
                    await self._mark_failed(session, run, "Report generation failed - LLM returned None")
                    return

                # Get expected patent numbers from extractions
                expected_patent_numbers = set(extractions_by_patent.keys())
                logger.info(f"Expected patent numbers: {sorted(expected_patent_numbers)}")

                # Count unique patent numbers in report
                report_patent_numbers = set()
                for patent in structured_report.methodology_patents:
                    if patent.patent_details and patent.patent_details.patent_number:
                        report_patent_numbers.add(patent.patent_details.patent_number)

                logger.info(f"Report patent numbers: {sorted(report_patent_numbers)}")
                logger.info(f"Unique patents in report: {len(report_patent_numbers)}")

                # Identify missing patents
                missing_patents = expected_patent_numbers - report_patent_numbers
                if missing_patents:
                    logger.error(f"REPORT VALIDATION FAILED: Missing {len(missing_patents)} patents in report")
                    logger.error(f"Missing patent numbers: {sorted(missing_patents)}")
                    logger.error("The LLM dropped patents during report generation. This is unacceptable.")
                    await self._mark_failed(session, run, f"Report generation failed: LLM dropped {len(missing_patents)} patents: {sorted(missing_patents)}")
                    return

                if len(structured_report.methodology_patents) != len(extractions_by_patent):
                    logger.error(f"REPORT VALIDATION FAILED: Expected {len(extractions_by_patent)} patents but report contains {len(structured_report.methodology_patents)}")
                    logger.error("The LLM dropped patents during report generation. This is unacceptable.")
                    await self._mark_failed(session, run, f"Report generation failed: LLM returned {len(structured_report.methodology_patents)} patents instead of {len(extractions_by_patent)}")
                    return

                if len(report_patent_numbers) != len(extractions_by_patent):
                    logger.error(f"REPORT VALIDATION FAILED: Expected {len(extractions_by_patent)} unique patents but report contains {len(report_patent_numbers)}")
                    await self._mark_failed(session, run, f"Report generation failed: Duplicate or missing patents in report")
                    return

                logger.info("============================================================")
                logger.info("REPORT GENERATION")
                in_tokens = 0
                out_tokens = 0
                if usage_data:
                    if isinstance(usage_data, dict):
                        in_tokens = usage_data.get("prompt_tokens", 0) or usage_data.get("input_tokens", 0)
                        out_tokens = usage_data.get("completion_tokens", 0) or usage_data.get("output_tokens", 0)
                    else:
                        in_tokens = getattr(usage_data, "prompt_tokens", getattr(usage_data, "input_tokens", 0))
                        out_tokens = getattr(usage_data, "completion_tokens", getattr(usage_data, "output_tokens", 0))
                
                logger.info(f"- Input tokens: {in_tokens}")
                logger.info(f"- Output tokens: {out_tokens}")
                logger.info(f"- Total tokens: {in_tokens + out_tokens}")
                logger.info("============================================================")

                # Pass extraction metadata to report service for deterministic reference generation
                extraction_metadata = {}
                for patent_number, extraction in extractions_by_patent.items():
                    extraction_metadata[patent_number] = {
                        'patent_title': extraction.metadata.patent_title,
                        'assignee': extraction.metadata.assignee,
                        'jurisdiction': extraction.metadata.jurisdiction,
                        'publication_year': extraction.metadata.publication_year,
                        'url': extraction.metadata.url
                    }
                self.report_service._extraction_metadata = extraction_metadata

                # ── Report Consistency Validation ──────────────────────────────
                consistency_ok, consistency_errors = self.report_service.validate_report_consistency(
                    structured_report,
                    primary_manifest=patent_manifest
                )
                if not consistency_ok:
                    logger.error(
                        "REPORT CONSISTENCY VALIDATION FAILED (%d errors). Marking run FAILED.",
                        len(consistency_errors)
                    )
                    await self._update_status(session, run, RunStatus.FAILED)
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
                # DOCX now built from canonical structured object (not Markdown string)
                docx_path = await self.report_service.export_to_docx(structured_report, docx_name)

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
                # Skip DOCX insertion as "DOCX" is not in ReportFileType DB Enum
                session.add(ReportFile(report_metadata_id=meta.id, file_type="MARKDOWN", file_name=md_name, file_path=os.path.join(export_dir, md_name)))
                session.add(ReportFile(report_metadata_id=meta.id, file_type="JSON", file_name=json_name, file_path=os.path.join(export_dir, json_name)))

                await self._update_status(session, run, RunStatus.COMPLETED)
                logger.info("Pipeline Complete!")

            except ProviderExhaustedException as e:
                import traceback
                logger.error("Pipeline failure (LLM_PROVIDER_EXHAUSTED): %s\n%s", e, traceback.format_exc())
                if not extractions_by_patent:
                    await self.safe_update_run_status(session, run, RunStatus.LLM_PROVIDER_EXHAUSTED)
                else:
                    await self.safe_update_run_status(session, run, RunStatus.COMPLETED_PARTIAL)
            except Exception as e:
                import traceback
                logger.error("Pipeline failure: %s\n%s", e, traceback.format_exc())
                await self._mark_failed(session, run, str(e))
            finally:
                # Ensure the final run summary is logged
                # Fetch telemetry for the summary
                from app.models.api_usage_log import APIUsageLog
                try:
                    usage_res = await session.execute(
                        select(
                            func.sum(APIUsageLog.total_tokens).label("total_tokens"),
                            func.sum(APIUsageLog.input_tokens).label("input_tokens"),
                            func.sum(APIUsageLog.output_tokens).label("output_tokens"),
                            func.sum(APIUsageLog.estimated_cost).label("cost")
                        ).where(APIUsageLog.research_run_id == self.run_id)
                    )
                    usage_row = usage_res.first()
                    input_tokens = usage_row.input_tokens or 0
                    output_tokens = usage_row.output_tokens or 0
                    total_tokens = usage_row.total_tokens or 0
                    total_cost = usage_row.cost or 0.0
                except:
                    input_tokens, output_tokens, total_tokens, total_cost = 0, 0, 0, 0.0
                
                # Determine how many LLM calls actually completed vs attempted
                llm_calls_completed = 0
                if 'qe_in' in locals() and qe_in > 0:
                    llm_calls_completed += 1
                if 'in_tokens' in locals() and in_tokens > 0:
                    llm_calls_completed += 1
                
                logger.info("")
                logger.info("============================================================")
                logger.info("TOTAL RUN")
                logger.info(f"- LLM calls attempted: 2")
                logger.info(f"- LLM calls completed: {llm_calls_completed}")
                logger.info(f"- Input tokens: {input_tokens}")
                logger.info(f"- Output tokens: {output_tokens}")
                logger.info(f"- Total tokens: {total_tokens}")
                logger.info(f"- Serper credits: {total_pages_attempted if 'total_pages_attempted' in locals() else 0}")
                logger.info("============================================================")
                
                # Final Diagnostic requested by user
                logger.info("")
                logger.info("QUERY EXPANSION")
                logger.info(f"Provider calls: {1 if 'qe_in' in locals() and qe_in > 0 else 0}")
                logger.info(f"Input: {qe_in if 'qe_in' in locals() else 0}")
                logger.info(f"Output: {qe_out if 'qe_out' in locals() else 0}")
                logger.info("")
                logger.info("SEARCH")
                logger.info(f"Queries: {len(raw_queries) if 'raw_queries' in locals() else 0}")
                logger.info(f"Serper credits: {total_pages_attempted if 'total_pages_attempted' in locals() else 0}")
                logger.info(f"Unique patents: {total_detected if 'total_detected' in locals() else 0}")
                logger.info("")
                logger.info("SELECTION")
                logger.info(f"Relevant: {total_eligible if 'total_eligible' in locals() else 0}")
                logger.info(f"Selected: {len(final_keep_patents) if 'final_keep_patents' in locals() else 0} / 15")
                logger.info("")
                logger.info("REPORT")
                logger.info(f"Provider calls: {1 if 'in_tokens' in locals() and in_tokens > 0 else 0}")
                logger.info(f"Input: {in_tokens if 'in_tokens' in locals() else 0}")
                logger.info(f"Output: {out_tokens if 'out_tokens' in locals() else 0}")
                logger.info(f"Total: {(in_tokens + out_tokens) if 'in_tokens' in locals() and 'out_tokens' in locals() else 0}")
                logger.info("")
                logger.info("RUN STATUS:")
                logger.info(f"{run.status.name if hasattr(run.status, 'name') else str(run.status)}")
                logger.info("============================================================")

