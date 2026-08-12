import logging
from app.services.llm import llm_client
from app.services.pipeline.schemas import ParsedPatent, ContentValidationSchema, CompoundSearchProfile
from app.services.prompts.patent_prompts import (
    PATENT_VALIDATION_SYSTEM_PROMPT,
    PATENT_VALIDATION_USER_TEMPLATE
)

logger = logging.getLogger(__name__)

class ValidationService:
    async def validate_content(
        self, 
        parsed_patent: ParsedPatent, 
        patent_number: str, 
        profile: CompoundSearchProfile,
        ledger: dict = None
    ) -> ContentValidationSchema:
        """
        Stage 7: LLM Content-Level Validation (Final Authority).
        Uses a highly reduced token window (Part 8).
        """
        logger.info(f"Running LLM Content Validation for {patent_number}...")
        
        # Only use Title (from ledger/metadata later if needed), Abstract, and a small snippet of description
        # We avoid the full `get_llm_context()` which contains expensive tables/examples.
        abstract = parsed_patent.abstract or "No abstract available."
        snippet = (parsed_patent.detailed_description or "")[:1500] 
        
        context_str = f"ABSTRACT:\n{abstract}\n\nDESCRIPTION SNIPPET:\n{snippet}\n"
        
        if ledger:
            context_str += f"\nCHEMISTRY EVIDENCE DETECTED:\n{ledger.dimensions.compound_evidence}\n"
            context_str += f"SYNTHESIS EVIDENCE DETECTED:\n{ledger.dimensions.manufacturing_evidence}\n"
            
        prompt = PATENT_VALIDATION_USER_TEMPLATE.format(
            compound_name=profile.compound_name,
            synonyms=', '.join(profile.synonyms),
            major_monomers=', '.join(profile.major_monomers),
            competing_chemistry=', '.join(profile.competing_chemistry),
            context_str=context_str
        )

        try:
            result, _ = await llm_client.generate_structured(
                prompt=prompt,
                system_prompt=PATENT_VALIDATION_SYSTEM_PROMPT,
                schema=ContentValidationSchema,
                temperature=0.1
            )
            
            if result:
                logger.info(f"Validation Result for {patent_number}: {result.relevance.value} (Confidence: {result.confidence})")
                return result
                
            raise Exception("No result returned from LLM")
            
        except Exception as e:
            logger.error("Content Validation LLM call failed for %s: %s", patent_number, e)
            return ContentValidationSchema(
                relevance="INDIRECT",
                confidence=0,
                target_chemistry_evidence=[],
                synthesis_evidence=[],
                exclusion_reason=f"LLM API Error: {str(e)}"
            )

    async def rank_titles(self, candidates: list[dict], profile: CompoundSearchProfile):
        """
        Takes a list of candidate dictionaries and uses the LLM to semantically rank them.
        """
        from app.services.prompts.patent_prompts import (
            PATENT_TITLE_RANKING_SYSTEM_PROMPT,
            PATENT_TITLE_RANKING_USER_TEMPLATE
        )
        from app.services.pipeline.schemas import RankedCandidateList
        import json

        if not candidates:
            return []

        # Convert candidates to a compact JSON string for the prompt
        compact_candidates = []
        for c in candidates:
            compact_candidates.append({
                "publication_number": c.get("publication_number"),
                "title": c.get("title")
            })

        candidates_json = json.dumps(compact_candidates, indent=2)

        prompt = PATENT_TITLE_RANKING_USER_TEMPLATE.format(
            compound_name=profile.compound_name,
            original_input=profile.original_input if hasattr(profile, 'original_input') else profile.compound_name,
            synonyms=', '.join(profile.synonyms) if profile.synonyms else '',
            abbreviations=', '.join(profile.abbreviations) if profile.abbreviations else '',
            major_monomers=', '.join(profile.major_monomers) if profile.major_monomers else '',
            important_constraints=', '.join(profile.important_constraints) if profile.important_constraints else '',
            application_keywords=', '.join(profile.application_keywords) if profile.application_keywords else '',
            competing_chemistry=', '.join(profile.competing_chemistry) if profile.competing_chemistry else '',
            candidates_json=candidates_json
        )

        try:
            result, _ = await llm_client.generate_structured(
                prompt=prompt,
                system_prompt=PATENT_TITLE_RANKING_SYSTEM_PROMPT,
                schema=RankedCandidateList,
                temperature=0.1
            )
            if result and hasattr(result, 'ranked_candidates'):
                return result.ranked_candidates
            return []
        except Exception as e:
            logger.error("Title Semantic Ranking LLM call failed: %s", e)
            return []
