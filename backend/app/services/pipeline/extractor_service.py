"""
app/services/pipeline/extractor_service.py

Uses Gemini Structured Outputs to:
1. Classify if a patent is relevant (filtering).
2. Extract the detailed polymerization JSON parameters.
"""
import logging

from app.core.config import settings
from app.services.pipeline.schemas import ClassificationResult, PatentExtraction
from app.services.llm import llm_client

logger = logging.getLogger(__name__)

# System prompt for structured extraction
EXTRACTION_SYSTEM_PROMPT = """
You are an expert polymer chemist and patent analyst.
Your task is to extract highly specific chemical and process parameters from the provided patent text.
Focus ONLY on the raw polymer manufacturing process (e.g., emulsion polymerization, solution polymerization, etc.).
DO NOT extract information related to compounding recipes, final product manufacturing (e.g., gloves, hoses), or unrelated examples.
IMPORTANT: You MUST strive to extract as much detail as possible for every field. Search the patent thoroughly for parameters.
Only output 'Not disclosed' if the parameter is genuinely missing from the patent after a comprehensive search. Do NOT use it lazily.
DO NOT hallucinate or guess any values, but prioritize completeness.
"""

CLASSIFICATION_SYSTEM_PROMPT = """
You are an expert polymer chemist evaluating patents for a research project on polymer synthesis.
Your task is to quickly read the provided patent text and determine if it contains raw polymerization synthesis details.
REJECT patents if they:
- Only mention the target compound without synthesis details.
- Focus exclusively on end-applications (e.g., making a glove out of rubber).
- Describe compounding (mixing polymer with fillers) rather than polymerization.
- Contain no experimental polymerization examples.
Output `is_relevant: true` only if meaningful synthesis/polymerization details are present.
"""


class ExtractorService:
    def __init__(self):
        pass

    async def classify_patent(self, compound_name: str, patent_text: str) -> ClassificationResult:
        """Quickly check if the patent is relevant to raw synthesis."""
        logger.info("Classifying patent relevance for %s...", compound_name)
        
        prompt = (
            f"Target Compound: {compound_name}\n\n"
            f"Please classify the following patent text according to the system instructions:\n\n"
            f"--- PATENT TEXT ---\n"
            f"{patent_text[:60000]}"  # limit context to ~60k chars to save tokens/time if it's huge
        )

        try:
            result = await llm_client.generate_structured(
                prompt=prompt,
                system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
                schema=ClassificationResult,
                temperature=0.1
            )
            if not result:
                raise Exception("LLM Client returned None for structured classification.")
            return result
        except Exception as e:
            logger.error("Failed to classify patent: %s", e)
            # Default to True so we don't accidentally drop it if API fails slightly
            return ClassificationResult(is_relevant=True, reason=f"Classification failed: {e}")

    def validate_extraction(self, ext: PatentExtraction) -> bool:
        """Validate that the extracted patent contains essential synthesis information."""
        # Must have basic identification
        if ext.patent_number == "Not disclosed" or ext.patent_title == "Not disclosed":
            logger.warning("Extraction validation failed: Missing Patent Number or Title")
            return False
            
        if ext.assignee == "Not disclosed":
            logger.warning("Extraction validation failed: Missing Assignee for %s", ext.patent_number)
            return False
            
        # Must have at least some meaningful polymerization data (not all 'Not disclosed')
        meaningful_fields = [
            ext.polymerization_process, ext.monomer_ratio, ext.water_amount, 
            ext.emulsifier, ext.initiator, ext.temperature, ext.conversion
        ]
        
        # If more than 4 of these critical fields are 'Not disclosed', reject it as a low-quality extraction
        not_disclosed_count = sum(1 for f in meaningful_fields if f == "Not disclosed")
        if not_disclosed_count > 4:
            logger.warning("Extraction validation failed: Insufficient synthesis data for %s", ext.patent_number)
            return False
            
        return True

    async def extract_polymerization_data(self, patent_text: str, url: str = "") -> PatentExtraction | None:
        """Extract the detailed JSON schema from the patent text."""
        logger.info("Extracting structured polymerization data...")
        
        prompt = (
            f"Extract the synthesis parameters from the following patent text:\n\n"
            f"--- PATENT TEXT ---\n"
            f"{patent_text[:120000]}"  # Provide a larger context limit for extraction
        )

        try:
            result = await llm_client.generate_structured(
                prompt=prompt,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                schema=PatentExtraction,
                temperature=0.1
            )
            if result:
                result.url = url
            return result
        except Exception as e:
            logger.error("LLM Extraction failed: %s", e)
            return None
