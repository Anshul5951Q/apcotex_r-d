"""
app/services/pipeline/compound_intelligence.py

Uses Gemini to dynamically generate a CompoundSearchProfile 
from a generic compound input (e.g. "EPDM" or "Low ACN NBR").
"""
import logging
from app.services.llm import llm_client
from app.services.pipeline.schemas import CompoundSearchProfile

logger = logging.getLogger(__name__)

from app.services.prompts.patent_prompts import (
    COMPOUND_SEARCH_PROFILE_SYSTEM_PROMPT,
    COMPOUND_SEARCH_PROFILE_USER_TEMPLATE
)

class CompoundIntelligenceService:
    def __init__(self, cache_service):
        self.cache_service = cache_service

    async def generate_profile(self, compound_input: str) -> CompoundSearchProfile:
        # Check cache first
        cached_profile = self.cache_service.get_compound_profile(compound_input)
        if cached_profile:
            logger.info("Loaded CompoundSearchProfile from cache for: %s", compound_input)
            return cached_profile
            
        logger.info("Generating CompoundSearchProfile dynamically for: %s", compound_input)
        
        prompt = COMPOUND_SEARCH_PROFILE_USER_TEMPLATE.format(compound_input=compound_input)
        
        result, provider = await llm_client.generate_structured(
            prompt=prompt,
            system_prompt=COMPOUND_SEARCH_PROFILE_SYSTEM_PROMPT,
            schema=CompoundSearchProfile,
            temperature=0.1
        )
        
        if not result:
            raise Exception(f"Failed to generate CompoundSearchProfile for {compound_input}")
            
        # Preserve the exact original input for traceability
        result.original_input = compound_input
        result.compound = compound_input
        
        # Save to cache
        self.cache_service.save_compound_profile(compound_input, result)
        
        return result
