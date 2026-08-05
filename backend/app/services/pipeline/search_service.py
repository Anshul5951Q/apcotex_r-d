"""
app/services/pipeline/search_service.py

Uses Gemini to generate a search strategy, then uses Serper API to find patent links.
"""
import json
import logging
from typing import List

import httpx
import httpx

from app.core.config import settings
from app.services.pipeline.schemas import AIStrategyResult
from app.services.llm import llm_client

logger = logging.getLogger(__name__)

SEARCH_STRATEGY_PROMPT = """
You are an expert patent researcher.
The user wants to research patents for the following compound: {compound_name}
Competitors to keep an eye on (if any): {competitors}

Your goal is to generate 5 highly optimized boolean search queries to find patents 
that describe the RAW SYNTHESIS and POLYMERIZATION PROCESS of this compound.
DO NOT create queries that target gloves, hoses, rubber products, or compounding recipes.

You MUST include the following combinations (incorporating competitor names if provided):
1. "<compound> polymerization"
2. "<compound> manufacturing method"
3. "<compound> emulsion polymerization"
4. "<compound> preparation method"
5. "<compound> synthesis"

Generate the queries in the requested JSON format.
"""

class SearchService:
    def __init__(self):
        self.serper_api_key = settings.SERPER_API_KEY

    async def generate_strategy(self, compound_name: str, competitors: List[str]) -> AIStrategyResult:
        """Use Gemini to create the search strategy."""
        logger.info("Generating search strategy for %s...", compound_name)
        comp_str = ", ".join(competitors) if competitors else "None"
        prompt = SEARCH_STRATEGY_PROMPT.format(compound_name=compound_name, competitors=comp_str)

        try:
            result = await llm_client.generate_structured(
                prompt=prompt,
                system_prompt="You are a JSON generator. Do not include markdown blocks.",
                schema=AIStrategyResult,
                temperature=0.3
            )
            if not result:
                raise Exception("LLM Client returned None for structured extraction.")
            return result
        except Exception as e:
            logger.error("Failed to generate search strategy: %s", e)
            # Fallback
            return AIStrategyResult(
                search_queries=[f'"{compound_name}" (polymerization OR synthesis OR preparation) patent'],
                rationale="Fallback search strategy due to AI generation error."
            )

    async def search_patents(self, queries: List[str]) -> List[str]:
        """Hit the Serper API to get patent links."""
        logger.info("Executing Serper API search for %d queries...", len(queries))
        
        import re
        all_links = []
        seen_families = set()
        
        if not self.serper_api_key:
            logger.warning("SERPER_API_KEY is not set. Returning empty list.")
            return []

        async with httpx.AsyncClient() as client:
            for query in queries:
                # We specifically want patents, so we might enforce site:patents.google.com
                # or just use the "patents" search if Serper supports it.
                # Serper's default search with 'patent' in the query usually works, 
                # but appending site:patents.google.com is safer.
                refined_query = f"{query} site:patents.google.com"
                
                payload = json.dumps({
                    "q": refined_query,
                    "num": 10  # Top 10 per query to ensure high coverage
                })
                headers = {
                    'X-API-KEY': self.serper_api_key,
                    'Content-Type': 'application/json'
                }
                
                try:
                    response = await client.post(
                        "https://google.serper.dev/search", 
                        headers=headers, 
                        data=payload,
                        timeout=15.0
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    organic_results = data.get("organic", [])
                    for result in organic_results:
                        link = result.get("link")
                        if link and "patents.google.com" in link:
                            # Deduplicate patent families by extracting the core patent number (e.g. US123456 from US123456B2)
                            match = re.search(r'patents\.google\.com/patent/([A-Z]{2}\d+)', link)
                            if match:
                                family_id = match.group(1)
                                if family_id not in seen_families:
                                    seen_families.add(family_id)
                                    all_links.append(link)
                except Exception as e:
                    logger.error("Serper API request failed for query '%s': %s", query, e)
                    
        return all_links
