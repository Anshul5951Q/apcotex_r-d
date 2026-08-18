"""
app/services/pipeline/extractor_service.py

Extraction Subsystem — DETERMINISTIC ONLY
==========================================
Architecture: 2 LLM calls per pipeline run (query expansion + report generation).
This service is NOT one of them.

1. Runs DeterministicExtractor on fetched patent text
2. Returns ExtractionResult with PARTIAL status always
3. Zero LLM calls
"""
import logging
import time

from app.services.pipeline.schemas import (
    PatentExtraction, ParsedPatent,
    ExtractionResult, ExtractionStatus
)
from app.services.pipeline.deterministic_extractor import DeterministicExtractor

logger = logging.getLogger(__name__)


class ExtractorService:
    """
    Purely deterministic patent extractor.
    No LLM calls. Extraction quality depends entirely on regex/rule-based extraction.
    """

    def __init__(self):
        self.deterministic_extractor = DeterministicExtractor()

    async def extract_patent(
        self,
        parsed_patent: ParsedPatent,
        patent_number: str,
        title: str,
        jurisdiction: str,
        source_url: str,
        profile=None,
        skip_llm: bool = True,  # kept for interface compatibility; always True now
    ) -> ExtractionResult:
        """
        Run deterministic extraction only. Returns ExtractionResult.PARTIAL always.

        LLM extraction has been removed by architecture decision:
        only 2 LLM calls are allowed per pipeline run (query expansion + report generation).
        """
        t0 = time.time()

        # Build initial extraction skeleton with metadata
        initial_json = PatentExtraction()
        initial_json.metadata.patent_number = patent_number
        initial_json.metadata.patent_title = title
        initial_json.metadata.jurisdiction = jurisdiction
        initial_json.metadata.url = source_url

        try:
            det_result, detected_count = self.deterministic_extractor.extract(
                parsed_patent, initial_json, profile=profile
            )
        except Exception as e:
            logger.error(
                "[EXTRACT] %s -> DETERMINISTIC_FAILED: %s: %s",
                patent_number, type(e).__name__, str(e)[:200]
            )
            # Return a minimal extraction with just metadata so the patent is not dropped
            initial_json.metadata.quality = "EXTRACTION_ERROR"
            return ExtractionResult(
                status=ExtractionStatus.PARTIAL,
                patent_number=patent_number,
                extraction=initial_json
            )

        det_params = len(det_result.parameters)
        det_examples = len(det_result.examples)
        latency_ms = int((time.time() - t0) * 1000)

        if det_params == 0 and det_examples == 0:
            det_result.metadata.quality = "NO_DETERMINISTIC_EVIDENCE"
            logger.info(
                "[EXTRACT] %s -> NO_DETERMINISTIC_EVIDENCE (0 params, 0 examples, lat=%dms)",
                patent_number, latency_ms
            )
        else:
            det_result.metadata.quality = "DETERMINISTIC"
            det_result.metadata.extraction_score = det_params
            logger.info(
                "[EXTRACT] %s -> DETERMINISTIC_OK (%d params, %d examples, lat=%dms)",
                patent_number, det_params, det_examples, latency_ms
            )

        return ExtractionResult(
            status=ExtractionStatus.PARTIAL,
            patent_number=patent_number,
            extraction=det_result
        )
