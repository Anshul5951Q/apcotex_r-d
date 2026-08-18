"""
app/services/pipeline/compound_intelligence.py

Uses Gemini to dynamically generate a CompoundSearchProfile 
from a generic compound input (e.g. "EPDM" or "Low ACN NBR").
"""
import logging
import inspect
from app.services.llm import llm_client
from app.services.pipeline.schemas import CompoundSearchProfile, LLMCompoundSearchProfile

logger = logging.getLogger(__name__)

from app.services.prompts.patent_prompts import (
    COMPOUND_SEARCH_PROFILE_SYSTEM_PROMPT,
    COMPOUND_SEARCH_PROFILE_USER_TEMPLATE
)

class CompoundIntelligenceService:
    def __init__(self, cache_service):
        self.cache_service = cache_service

    def _derive_full_profile(self, original_input: str, llm_profile: LLMCompoundSearchProfile) -> CompoundSearchProfile:
        """Maps the compact LLM profile to the full deterministic pipeline profile safely."""
        profile = CompoundSearchProfile()
        
        # 1. Direct string mappings with defaults
        profile.original_input = str(original_input) if original_input else ""
        profile.compound = str(original_input) if original_input else ""
        profile.compound_name = str(llm_profile.compound_name) if llm_profile.compound_name else ""
        profile.base_chemistry = str(llm_profile.base_chemistry) if llm_profile.base_chemistry else ""
        profile.research_intent = str(llm_profile.manufacturing_intent) if llm_profile.manufacturing_intent else ""
        
        # 2. List mappings with type safety
        profile.target_attributes = list(llm_profile.target_attributes) if llm_profile.target_attributes else []
        profile.synonyms = list(llm_profile.synonyms) if llm_profile.synonyms else []
        profile.material_aliases = list(llm_profile.material_aliases) if getattr(llm_profile, 'material_aliases', None) else []
        profile.precursor_terms = list(llm_profile.precursor_terms) if getattr(llm_profile, 'precursor_terms', None) else []
        profile.transformation_terms = list(llm_profile.transformation_terms) if getattr(llm_profile, 'transformation_terms', None) else []
        profile.synthesis_terms = list(llm_profile.synthesis_terms) if getattr(llm_profile, 'synthesis_terms', None) else []
        profile.downstream_application_terms = list(llm_profile.downstream_application_terms) if getattr(llm_profile, 'downstream_application_terms', None) else []
        profile.relevant_parameter_categories = list(llm_profile.relevant_parameter_categories) if getattr(llm_profile, 'relevant_parameter_categories', None) else []
        profile.derivative_exclusion_terms = list(llm_profile.derivative_exclusion_terms) if getattr(llm_profile, 'derivative_exclusion_terms', None) else []
        
        # 3. Object transformations
        from app.services.pipeline.schemas import SearchQuery, SearchField, SearchCategory, SearchPriority
        if llm_profile.search_queries:
            profile.search_queries = [
                SearchQuery(query=str(q), field=SearchField.TITLE, category=SearchCategory.POLYMERIZATION, priority=SearchPriority.PRIMARY) 
                for q in llm_profile.search_queries if q
            ]
        else:
            profile.search_queries = []
        
        # 4. Derived properties
        profile.chemical_family = profile.base_chemistry
        profile.abbreviations = [str(s) for s in profile.synonyms if isinstance(s, str) and len(s) <= 5 and s.isupper()]
        
        # Extract monomers safely without hardcoding
        profile.major_monomers = []
        # If the LLM generated specific parameter categories that look like monomers, we could map them here in the future
        # For now, rely purely on dynamic parameter extraction downstream
        
        # Map target attribute constraints safely
        profile.important_constraints = [str(attr.name) for attr in profile.target_attributes if hasattr(attr, 'name')]
        
        # Derive generic synthesis/manufacturing fields dynamically
        profile.typical_polymerization_routes = profile.synthesis_terms if profile.synthesis_terms else ["synthesis", "preparation", "manufacturing"]
        
        # Safety mappings to prevent completely empty matches
        base_manufacturing = [
            "method for manufacturing", "process for producing", 
            "method for producing", "process for preparing"
        ]
        profile.typical_manufacturing_keywords = (profile.synthesis_terms if profile.synthesis_terms else []) + base_manufacturing
        profile.manufacturing_keywords = profile.typical_manufacturing_keywords
        
        # Derive negative/exclusion fields
        profile.application_keywords = [
            "hose", "tire", "glove", "seal", "coating", "adhesive", 
            "battery", "electrode", "film", "sheet", "pipe", "tube", "belt"
        ]
        
        # Derive parameter/composition keywords
        if profile.important_constraints:
            profile.target_composition_keywords = list(profile.important_constraints)
        else:
            profile.target_composition_keywords = []
            
        if not profile.relevant_parameter_categories:
            raise ValueError("PROFILE CONTRACT VALIDATION FAILED: Missing fields: relevant_parameter_categories")
            
        return profile

    async def generate_profile(self, compound_input: str) -> CompoundSearchProfile:
        # Check cache first
        cached_profile = self.cache_service.get_compound_profile(compound_input)
        if cached_profile:
            logger.info(f"SEARCH PROFILE REUSED for '{compound_input}'")
            return cached_profile
            
        logger.info(f"SEARCH PROFILE GENERATED for '{compound_input}'")
        
        prompt = COMPOUND_SEARCH_PROFILE_USER_TEMPLATE.format(compound_input=compound_input)
        
        # Estimate input tokens
        sys_tokens = len(COMPOUND_SEARCH_PROFILE_SYSTEM_PROMPT) // 4
        user_tokens = len(prompt) // 4
        
        # Get schema string for estimation
        import json
        schema_dict = LLMCompoundSearchProfile.model_json_schema()
        schema_tokens = len(json.dumps(schema_dict)) // 4
        
        estimated_input = sys_tokens + user_tokens + schema_tokens
        
        logger.debug(f"System prompt tokens: {sys_tokens}")
        logger.debug(f"User input tokens: {user_tokens}")
        logger.debug(f"Structured schema tokens: {schema_tokens}")
        logger.debug(f"Estimated total input: {estimated_input}")
        
        result, provider, usage = await llm_client.generate_structured(
            prompt=prompt,
            system_prompt=COMPOUND_SEARCH_PROFILE_SYSTEM_PROMPT,
            schema=LLMCompoundSearchProfile,
            temperature=0.1
        )
        
        if not result:
            logger.error("LLM Profile generation failed.")
            raise Exception(f"Failed to generate CompoundSearchProfile for {compound_input}")
            
        actual_input = usage.get('input_tokens', 'N/A')
        actual_output = usage.get('output_tokens', 'N/A')
        actual_total = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
            
        # Derive the full internal profile
        try:
            full_profile = self._derive_full_profile(compound_input, result)
        except Exception as e:
            logger.error(f"Internal Profile mapping failed: {str(e)}")
            raise
        
        logger.info("=" * 60)
        logger.info("QUERY EXPANSION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Target: {compound_input}")
        logger.info(f"Profile Validation: PASS")
        logger.info(f"LLM Calls: 1")
        logger.info(f"Total Tokens: {actual_total} (In: {actual_input}, Out: {actual_output})")
        logger.info("=" * 60)
        
        # Save to cache
        self.cache_service.save_compound_profile(compound_input, full_profile)
        
        return full_profile
