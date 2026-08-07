"""
app/services/pipeline/search_service.py

Uses Gemini to generate a search strategy, then uses Serper API to find patent links.
"""
import json
import logging
from typing import List, Dict, Any

import httpx

from app.core.config import settings
from app.services.pipeline.schemas import CompoundSearchProfile

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self):
        self.serper_api_key = settings.SERPER_API_KEY

    def build_queries(self, profile: CompoundSearchProfile, jurisdiction: str) -> List[Dict[str, str]]:
        """Deterministically generate jurisdiction-specific queries categorized by intent."""
        queries = []
        
        # Compound
        queries.append({"query": f"{jurisdiction} {profile.compound_name} patent", "tier": "Tier 1"})
        
        # Synonyms
        for syn in profile.synonyms[:2]:
            queries.append({"query": f"{jurisdiction} {syn} patent", "tier": "Tier 2"})
            
        # Monomers
        if profile.major_monomers:
            monomers_str = " ".join(profile.major_monomers)
            queries.append({"query": f"{jurisdiction} {monomers_str} copolymer patent", "tier": "Tier 2"})
            
        # Polymerization route
        for route in profile.typical_polymerization_routes[:2]:
            queries.append({"query": f"{jurisdiction} {route} {profile.compound_name} patent", "tier": "Tier 2"})
            
        # Manufacturing
        for phrase in profile.typical_manufacturing_keywords[:2]:
            queries.append({"query": f"{jurisdiction} {phrase} {profile.compound_name} patent", "tier": "Tier 1"})
            
        # Recipe
        queries.append({"query": f"{jurisdiction} recipe {profile.compound_name} patent", "tier": "Tier 3"})
        
        # Experimental examples
        queries.append({"query": f"{jurisdiction} experimental examples {profile.compound_name} patent", "tier": "Tier 3"})
        
        # CPC
        for cpc in profile.typical_cpc[:2]:
            queries.append({"query": f"{jurisdiction} {cpc} {profile.compound_name} patent", "tier": "Tier 3"})
            
        # IPC
        for ipc in profile.typical_ipc[:2]:
            queries.append({"query": f"{jurisdiction} {ipc} {profile.compound_name} patent", "tier": "Tier 3"})
                
        logger.info("Backend generated %d dynamic search queries for %s (%s).", len(queries), profile.compound, jurisdiction)
        return queries

    async def search_patents(self, queries: List[Dict[str, str]], allowed_jurisdiction: str) -> List[Dict[str, Any]]:
        """Hit the Serper API and extract metadata, returning a list of dictionaries."""
        logger.info("Executing Serper API search for %d queries in jurisdiction %s...", len(queries), allowed_jurisdiction)
        
        import re
        all_results = []
        
        if not self.serper_api_key:
            logger.warning("SERPER_API_KEY is not set. Returning empty list.")
            return []

        async with httpx.AsyncClient() as client:
            for q_dict in queries:
                query_str = q_dict["query"]
                query_tier = q_dict["tier"]
                payload = json.dumps({
                    "q": query_str,
                    "num": 25 # Limit to 25 results per query
                })
                headers = {
                    'X-API-KEY': self.serper_api_key,
                    'Content-Type': 'application/json'
                }
                
                try:
                    response = await client.post(
                        "https://google.serper.dev/patents", 
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
                            match = re.search(r'patents\.google\.com/patent/([A-Z]{2}\d+)', link)
                            if match:
                                patent_number = match.group(1)
                                authority = patent_number[:2].upper()
                                
                                # IMMEDIATE JURISDICTION FILTERING
                                if authority != allowed_jurisdiction.upper():
                                    continue
                                    
                                meta = {
                                    "patent_number": patent_number,
                                    "jurisdiction": authority,
                                    "title": result.get("title", ""),
                                    "snippet": result.get("snippet", ""),
                                    "url": link,
                                    "publication_date": result.get("publicationDate", ""),
                                    "query_matched": query_str,
                                    "tier": query_tier
                                }
                                all_results.append(meta)
                except Exception as e:
                    logger.error("Serper API request failed for query '%s': %s", query_str, e)
                    
        return all_results
