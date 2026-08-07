"""
app/services/pipeline/compound_intelligence.py

Uses Gemini to dynamically generate a CompoundSearchProfile 
from a generic compound input (e.g. "EPDM" or "Low ACN NBR").
"""
import logging
from app.services.llm import llm_client
from app.services.pipeline.schemas import CompoundSearchProfile

logger = logging.getLogger(__name__)

COMPOUND_INTELLIGENCE_PROMPT = """
You are an expert polymer chemist and patent intelligence system.
The user has requested to search for synthesis and manufacturing patents related to a specific chemical compound or polymer.
Your job is to generate a comprehensive, highly accurate search profile for this compound.

You must output a JSON object matching the requested schema.

Guidelines:
- compound_name: The formal name.
- chemical_family: The broader family.
- synonyms: A broad list of abbreviations and trade names.
- abbreviations: Known abbreviations.
- major_monomers: The chemical monomers that form this compound.
- alternative_industry_names: Trade names or alternative industry names.
- typical_polymerization_routes: e.g., "Emulsion Polymerization", "Solution Polymerization".
- typical_manufacturing_keywords: e.g., "method for manufacturing", "process for producing", "preparation method".
- typical_cpc: The typical CPC classes (e.g., "C08F", "C08L").
- typical_ipc: The typical IPC classes.
- related_chemistry: Chemicals or compounds often found alongside or related to the target.
- competing_chemistry: Alternative compounds that indicate the patent is likely NOT about the target compound.
- application_keywords: Negative words indicating applications or downstream products (e.g., "glove", "tire", "battery", "adhesive").
- manufacturing_keywords: Words indicating raw synthesis (e.g. "polymerization", "synthesis", "initiator", "emulsifier", "catalyst", "reactor", "conversion").
"""

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
        
        prompt = f"Generate a search profile for the following compound: {compound_input}"
        
        result, provider = await llm_client.generate_structured(
            prompt=prompt,
            system_prompt=COMPOUND_INTELLIGENCE_PROMPT,
            schema=CompoundSearchProfile,
            temperature=0.1
        )
        
        if not result:
            raise Exception(f"Failed to generate CompoundSearchProfile for {compound_input}")
            
        # Overwrite the original compound field with the user's exact input for traceability
        result.compound = compound_input
        
        # Save to cache
        self.cache_service.save_compound_profile(compound_input, result)
        
        return result
