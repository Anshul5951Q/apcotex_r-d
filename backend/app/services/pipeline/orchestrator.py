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
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import engine
from app.models.research_run import ResearchRun, RunStatus
from app.models.report_metadata import ReportMetadata
from app.models.report_file import ReportFile
from app.services.pipeline.schemas import PatentExtraction
from app.services.pipeline.search_service import SearchService
from app.services.pipeline.fetcher_service import FetcherService
from app.services.pipeline.extractor_service import ExtractorService
from app.services.pipeline.report_service import ReportService

logger = logging.getLogger(__name__)


async def get_background_session() -> AsyncSession:
    """Provide a new session for background tasks."""
    return AsyncSession(engine, expire_on_commit=False)


class PipelineOrchestrator:
    def __init__(self, run_id: UUID):
        self.run_id = run_id
        self.search_service = SearchService()
        self.fetcher_service = FetcherService()
        self.extractor_service = ExtractorService()
        self.report_service = ReportService()

    async def _update_status(self, session: AsyncSession, run: ResearchRun, status: RunStatus):
        run.status = status
        run.updated_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info("Run %s transitioned to %s", self.run_id, status.name)

    async def _mark_failed(self, session: AsyncSession, run: ResearchRun, error_msg: str):
        logger.error("Run %s FAILED: %s", self.run_id, error_msg)
        await self._update_status(session, run, RunStatus.FAILED)

    async def execute(self):
        """
        Main entry point for the background task.
        """
        async with await get_background_session() as session:
            result = await session.execute(select(ResearchRun).where(ResearchRun.id == self.run_id))
            run = result.scalar_one_or_none()

            if not run:
                logger.error("Orchestrator could not find run %s", self.run_id)
                return

            try:
                # ── Step 1 & 2: Strategy & Search
                await self._update_status(session, run, RunStatus.SEARCHING)
                
                strategy = await self.search_service.generate_strategy(run.compound_name, run.competitors)
                patent_urls = await self.search_service.search_patents(strategy.search_queries)
                
                if not patent_urls:
                    raise Exception("No patents found for the given compound.")

                # ── Step 3, 4, 5, 6 & 7: Fetch, Filter, Extract & Validate
                await self._update_status(session, run, RunStatus.FILTERING)
                await self._update_status(session, run, RunStatus.EXTRACTING)
                
                extractions: list[PatentExtraction] = []
                
                for url in patent_urls:
                    if len(extractions) >= 10:
                        logger.info("Reached target of 10 validated extractions. Stopping extraction phase.")
                        break
                        
                    logger.info("Processing URL: %s", url)
                    raw_text = await self.fetcher_service.fetch_patent_text(url)
                    
                    if not raw_text:
                        logger.warning("Failed to fetch text for URL: %s", url)
                        continue
                        
                    # Classify relevance
                    classification = await self.extractor_service.classify_patent(run.compound_name, raw_text)
                    if not classification.is_relevant:
                        logger.info("Patent rejected during classification: %s", classification.reason)
                        continue
                        
                    # Added a small delay to avoid spiking limits too hard
                    await asyncio.sleep(2)
                    
                    # Extract data
                    ext = await self.extractor_service.extract_polymerization_data(raw_text, url=url)
                    if not ext:
                        logger.warning("Extraction failed entirely for URL: %s", url)
                        continue
                        
                    # Validate quality
                    if self.extractor_service.validate_extraction(ext):
                        extractions.append(ext)
                        logger.info("Successfully validated and added patent: %s", ext.patent_number)
                    else:
                        logger.warning("Extraction rejected during validation for URL: %s", url)
                        
                if len(extractions) < 7:
                    raise Exception(f"Pipeline failed: Could only extract {len(extractions)} valid patents. Minimum requirement is 7.")

                # ── Step 8 & 9: Generate Report & Export
                await self._update_status(session, run, RunStatus.GENERATING)
                
                markdown_report = await self.report_service.generate_markdown_report(run.compound_name, extractions)
                
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
                    patent_count=len(patent_urls),
                    source_count=len(valid_patents_text),
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
                await self._update_status(session, run, RunStatus.COMPLETED)

            except Exception as e:
                await self._mark_failed(session, run, str(e))
