import json
import logging
import os
from pathlib import Path

from app.services.pipeline.schemas import CompoundSearchProfile
from app.services.llm import llm_client

logger = logging.getLogger(__name__)

PROFILE_PROMPT = """
You are an expert polymer chemist and patent analyst.
The user wants to research patents for the following compound: {compound_name}
Competitors to keep an eye on (if any): {competitors}

Your goal is to generate a comprehensive Compound Search Profile for this chemistry.
This profile will be used to automatically find and filter RAW SYNTHESIS and POLYMERIZATION PROCESS patents.

Follow these rules:
1. polymer_family: The broad class (e.g. NBR, HNBR, SBR, CR).
2. primary_compounds: Identify the core chemical names or abbreviations (e.g. 'NBR', 'nitrile rubber').
3. secondary_terms: Common aliases, abbreviations, or descriptors (e.g. 'Low ACN', 'Bound Acrylonitrile').
4. required_chemistry: The exact core monomers that MUST be present to consider the patent relevant (e.g. 'acrylonitrile', 'butadiene').
5. polymerization_keywords: Identify terms that strongly indicate a raw polymerization method (e.g. 'emulsion polymerization', 'initiator', 'coagulation').
6. negative_compounds: Identify unrelated end-products, alternative polymers, or irrelevant technologies (e.g. 'chloroprene', 'polyethylene', 'battery', 'adhesive', 'olefin').
6. preferred_cpc: The standard patent classifications (e.g. 'C08F', 'C08L').
7. target_authorities: Typical authorities (e.g., 'US', 'EP', 'WO', 'CN').
8. minimum_examples: Standard text indicating examples (e.g., 'Experimental Example', 'Example').

Return the JSON strictly matching the CompoundSearchProfile schema.
"""

class ProfileManager:
    def __init__(self):
        self.profiles_dir = Path("app/data/profiles")
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _get_profile_path(self, compound_name: str) -> Path:
        """Sanitize compound name for file storage."""
        safe_name = "".join(c if c.isalnum() else "_" for c in compound_name).lower()
        return self.profiles_dir / f"{safe_name}.json"

    async def get_or_create_profile(self, compound_name: str, competitors: list[str]) -> CompoundSearchProfile:
        """
        Attempt to load an existing profile for the compound. 
        If it doesn't exist, use the LLM to generate one, save it, and return it.
        """
        profile_path = self._get_profile_path(compound_name)

        if profile_path.exists():
            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profile = CompoundSearchProfile(**data)
                logger.info("\nCompound Profile Loaded\nFamily: %s\nLLM Used: No", profile.polymer_family)
                return profile
            except Exception as e:
                logger.warning("Failed to load existing profile for %s: %s. Generating new one...", compound_name, e)

        # Profile not found or corrupt, generate via LLM
        logger.info("\nCompound Profile Not Found\nGenerating Profile via LLM...")
        comp_str = ", ".join(competitors) if competitors else "None"
        prompt = PROFILE_PROMPT.format(compound_name=compound_name, competitors=comp_str)

        try:
            result, provider_id = await llm_client.generate_structured(
                prompt=prompt,
                system_prompt="You are a JSON generator. Do not include markdown blocks.",
                schema=CompoundSearchProfile,
                temperature=0.1
            )
            
            if not result:
                raise Exception("LLM returned None for CompoundSearchProfile.")
                
            # Save the new profile
            with open(profile_path, "w", encoding="utf-8") as f:
                f.write(result.model_dump_json(indent=4))
                
            logger.info("Saved New Profile: Yes (Provider: %s)", provider_id)
            return result
            
        except Exception as e:
            logger.error("Failed to generate Compound Search Profile: %s", e)
            # Fallback deterministic profile if LLM fails completely
            fallback = CompoundSearchProfile(
                compound=compound_name,
                polymer_family="Unknown",
                primary_compounds=[compound_name],
                secondary_terms=[],
                required_chemistry=[],
                polymerization_keywords=["polymerization", "synthesis", "preparation method"],
                negative_compounds=["polyethylene", "battery", "adhesive", "film", "medical"],
                preferred_cpc=["C08F", "C08L"],
                target_authorities=["US", "EP", "WO"],
                minimum_examples="Example"
            )
            return fallback
