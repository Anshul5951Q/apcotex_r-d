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

class SerperCreditsExhaustedError(Exception):
    """Raised when Serper API returns 'Not enough credits' error."""
    pass

class SearchService:
    def __init__(self):
        self.serper_api_key = settings.SERPER_API_KEY

    def validate_query(self, query_str: str, field: str) -> tuple[bool, str]:
        """
        Basic query validation before sending to Serper.
        Returns (is_valid, reason) tuple.
        """
        if not query_str or not query_str.strip():
            return False, "Empty query"
        
        query_str = query_str.strip()
        
        # Check for obviously malformed parentheses
        open_parens = query_str.count('(')
        close_parens = query_str.count(')')
        if open_parens != close_parens:
            return False, f"Mismatched parentheses: {open_parens} open, {close_parens} close"
        
        # Check for unsupported field syntax if known
        # For now, we accept TI= and TAC= prefixes as they will be stripped
        # But warn about other unsupported prefixes
        if '=' in query_str and not any(query_str.upper().startswith(prefix) for prefix in ['TI=', 'TAC=']):
            return False, f"Unsupported field syntax: {query_str.split('=')[0]}="
        
        return True, ""

    def build_queries(self, profile: CompoundSearchProfile) -> List[Dict[str, Any]]:
        """Deterministically generate raw queries from the profile's search strategy."""
        queries = []
        for sq in profile.search_queries:
            import re
            # Strip legacy TI= or TAC= prefixes if LLM hallucinated them
            raw_query = re.sub(r'^(?:TI|TAC)=\((.*)\)$', r'\1', sq.query.strip(), flags=re.IGNORECASE)
            
            queries.append({
                "query": raw_query,
                "tier": sq.category,
                "priority": sq.priority.value if hasattr(sq.priority, 'value') else str(sq.priority),
                "search_field": sq.field
            })
                
        logger.info("Backend generated %d universal raw search queries for %s.", len(queries), profile.compound_name)
        return queries

    async def search_patents_page(
        self, 
        query_str: str, 
        field: str, 
        page: int, 
        jurisdictions: List[str] = None,
        date_start: str = None, 
        date_end: str = None
    ) -> tuple[List[Dict[str, Any]], bool]:
        """
        Hit the Serper API for a single page.
        Returns (results, success) tuple where success indicates if the API call succeeded.
        Applies jurisdiction and date filters directly to the search query if possible.
        """
        if not self.serper_api_key:
            logger.warning("SERPER_API_KEY is not set. Returning empty list.")
            return [], False
            
        # 1. Format the core query
        formatted_query = query_str
        if field == "TITLE":
            # For Google Patents, assignee, country, before, after are supported natively.
            # However, Serper simply passes the query to Google.
            # Using TI=(...) is old syntax. Google Patents supports simply searching keywords, 
            # or `ti:(...)`. We will just pass the keywords, as Google Patents naturally ranks titles.
            # Let's keep `TI=(...)` if that was the intended syntax for Google Patents.
            # Actually Google Patents uses `title=(...)` or just keywords. Let's use `TI=(...)`.
            formatted_query = f"TI=({query_str})"
        elif field == "TAC":
            formatted_query = f"TAC=({query_str})"
            
        # DO NOT inject jurisdiction or date modifiers into the Serper query string.
        # Serper Google Patents integration frequently fails to parse complex OR/date logic 
        # and returns 0 organic results. All filtering must be done deterministically in Python.

        payload = {
            "q": formatted_query,
            "page": page,
            "num": 20 # 20 results per page
        }
        
        # Diagnostic logging
        logger.info(f"  Serper Query: {formatted_query}")
        logger.info(f"  Endpoint: https://google.serper.dev/patents")
        logger.info(f"  Page: {page}")
        
        headers = {
            'X-API-KEY': self.serper_api_key,
            'Content-Type': 'application/json'
        }
        
        all_results = []
        async with httpx.AsyncClient() as client:
            try:
                # [DIAGNOSTIC LOGGING]
                logger.info(f"Serper API Request -> URL: https://google.serper.dev/patents | Payload: {payload}")
                
                response = await client.post(
                    "https://google.serper.dev/patents", 
                    headers=headers, 
                    json=payload,
                    timeout=15.0
                )
                response.raise_for_status()
                data = response.json()
                success = True
                
                # Log HTTP status and result count
                logger.info(f"  HTTP Status: {response.status_code}")
                logger.info(f"  Raw Results: {len(data.get('organic', []))}")
                
                # Log a sanitized version of the actual first page for debugging
                if page == 1:
                    sanitized_data = {
                        "searchParameters": data.get("searchParameters"),
                        "organic_count": len(data.get("organic", [])),
                        "first_organic_item": data.get("organic", [])[0] if data.get("organic") else None
                    }
                    logger.info(f"[DIAGNOSTIC] Serper JSON Response Sample: {sanitized_data}")
                
                import re
                organic_results = data.get("organic", [])
                
                logger.info(f"[DIAGNOSTIC] Query '{formatted_query}' Page {page} Raw Results: {len(organic_results)}")
                
                for idx, result in enumerate(organic_results):
                    link = result.get("link", "")
                    title = result.get("title", "")
                    pub_date = result.get("publicationDate", "")
                    
                    if not title:
                        logger.warning(f"[DIAGNOSTIC] TITLE EXTRACTION FAILED | query={formatted_query} | result_index={idx} | available_fields={list(result.keys())}")
                    else:
                        if page == 1 and idx < 10:
                            logger.info(f"[DIAGNOSTIC] SERPER RESULT: raw result index = {idx} | title = {title} | url = {link} | pub_date = {pub_date}")

                    if link and "patents.google.com" in link:
                        match = re.search(r'patents\.google\.com/patent/([A-Z]{2}\d+)', link)
                        if match:
                            patent_number = match.group(1)
                            authority = patent_number[:2].upper()
                            
                            # We don't filter here anymore. Pass everything to orchestrator for deterministic filtering and tracking.
                            meta = {
                                "patent_number": patent_number,
                                "jurisdiction": authority,
                                "title": title,
                                "snippet": result.get("snippet", ""),
                                "url": link,
                                "publication_date": pub_date,
                                "position": idx + 1
                            }
                            all_results.append(meta)
                            
            except httpx.HTTPStatusError as e:
                # Log detailed error information for HTTP errors
                error_body = ""
                try:
                    error_body = e.response.text
                except:
                    error_body = "Could not extract response body"
                
                logger.error(
                    "Serper API HTTP %s for query '%s' page %d | Payload: %s | Response: %s",
                    e.response.status_code,
                    formatted_query,
                    page,
                    payload,
                    error_body
                )
                
                # Check for credit exhaustion
                if e.response.status_code == 400 and "Not enough credits" in error_body:
                    raise SerperCreditsExhaustedError("Serper API credits exhausted")
                
                return [], False
            except SerperCreditsExhaustedError:
                # Re-raise to be caught by orchestrator for fail-fast handling
                raise
            except Exception as e:
                logger.error("Serper API request failed for query '%s' page %d: %s", formatted_query, page, e)
                return [], False
                
        return all_results, True
