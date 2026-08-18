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
from app.services.usage_logger import UsageLogger
import time

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

    def _enforce_phrase_anchoring(self, query: str, profile: CompoundSearchProfile) -> str:
        """
        Wrap the longest matching material term in the query in double-quotes
        so that Google Patents (via Serper) treats it as a phrase match.

        Without this, a query like "low acrylonitrile nitrile rubber" is treated
        as an independent keyword search for [low] [acrylonitrile] [nitrile] [rubber]
        and Serper returns battery/electrode patents because "acrylonitrile" is a
        common electrode binder ingredient.

        With this, the query becomes: low acrylonitrile "nitrile rubber"
        which forces Google Patents to return only patents that literally contain
        the phrase "nitrile rubber" in their indexed fields.
        """
        import re as _re

        # Build ordered list of material terms (longest first) to match and quote
        def _norm(s):
            return _re.sub(r'[-\s]+', ' ', s.lower().strip()) if s else ""

        material_terms = sorted(set(
            [_norm(profile.base_chemistry), _norm(profile.compound_name)]
            + [_norm(s) for s in profile.synonyms]
            + [_norm(a) for a in getattr(profile, "abbreviations", [])]
        ), key=len, reverse=True)

        # Remove terms that are <= 3 chars (too short to phrase-quote safely)
        material_terms = [t for t in material_terms if len(t) > 3]

        query_lower = query.lower()

        for term in material_terms:
            if term in query_lower and f'"{term}"' not in query_lower:
                # Find the original-case version in the query and wrap in quotes
                # Use case-insensitive replacement, preserving original casing
                pattern = _re.compile(_re.escape(term), _re.IGNORECASE)
                quoted = pattern.sub(f'"{term}"', query, count=1)
                logger.debug("PHRASE ANCHOR: '%s' -> '%s'", query, quoted)
                return quoted

        return query

    def build_queries(self, profile: CompoundSearchProfile) -> List[Dict[str, Any]]:
        """Deterministically generate raw queries from the profile's search strategy."""
        queries = []
        seen_queries = set()
        
        # Helper to add a query if it's unique
        def add_query(raw_query: str, tier: str, priority: str, field: str = "TITLE"):
            import re
            # Strip legacy TI= or TAC= prefixes if they somehow exist
            raw_query = re.sub(r'^(?:TI|TAC)=\((.*)\)$', r'\1', raw_query.strip(), flags=re.IGNORECASE)

            # Sanitize mismatched quotes and parentheses
            if raw_query.count('"') % 2 != 0:
                raw_query = raw_query.replace('"', '')
            if raw_query.count('(') != raw_query.count(')'):
                raw_query = raw_query.replace('(', '').replace(')', '')

            # Additional sanity check: if the query is just empty or too short
            if len(raw_query.strip()) < 3:
                return

            # Enforce phrase-anchoring so Serper returns material-specific results
            raw_query = self._enforce_phrase_anchoring(raw_query, profile)

            # Deduplicate semantically identical queries
            norm_query = re.sub(r'[^a-zA-Z0-9\s]', '', raw_query.lower()).strip()
            # Collapse multiple spaces
            norm_query = re.sub(r'\s+', ' ', norm_query)
            if norm_query in seen_queries:
                return
            seen_queries.add(norm_query)

            queries.append({
                "query": raw_query,
                "tier": tier,
                "priority": priority,
                "search_field": field
            })

        # 1. Base material and synonyms
        material_terms = [profile.compound_name] + getattr(profile, "material_aliases", []) + profile.synonyms
        material_terms = [t for t in material_terms if t]
        
        if not material_terms:
            material_terms = [profile.compound]
            
        primary_material = material_terms[0]
        
        # Intent 1: Direct target material (Primary)
        add_query(primary_material, "PRIMARY", "PRIMARY")
        
        # Helper to safely get the first N terms from a list
        def get_top_terms(term_list, n=2):
            return [t for t in (term_list or []) if t][:n]
            
        synthesis_terms = get_top_terms(getattr(profile, "synthesis_terms", []) or profile.manufacturing_keywords, 3)
        transformation_terms = get_top_terms(getattr(profile, "transformation_terms", []), 2)
        attributes = get_top_terms(getattr(profile, "target_attributes", []), 2)
        if not attributes and hasattr(profile, "target_composition_keywords"):
            attributes = get_top_terms(profile.target_composition_keywords, 2)
            
        precursors = get_top_terms(getattr(profile, "precursor_terms", []), 2)
        parameters = get_top_terms(getattr(profile, "relevant_parameter_categories", []), 2)

        # Intents 2, 3, 4: Target material + synthesis/preparation/transformation
        for syn_term in synthesis_terms + transformation_terms:
            if syn_term:
                add_query(f"{primary_material} {syn_term}", "SYNTHESIS", "PRIMARY")
                
                # Try with a synonym if available
                if len(material_terms) > 1:
                    add_query(f"{material_terms[1]} {syn_term}", "SYNTHESIS", "SECONDARY")

        # Intent 5: Target material + target attribute
        for attr in attributes:
            if attr:
                attr_name = getattr(attr, "name", str(attr))
                add_query(f"{attr_name} {primary_material}", "ATTRIBUTE", "PRIMARY")
                
                # Combine attribute with synthesis
                if synthesis_terms:
                    add_query(f"{attr_name} {primary_material} {synthesis_terms[0]}", "ATTRIBUTE_SYNTHESIS", "SECONDARY")

        # Intent 6: Precursor + transformation
        if precursors and transformation_terms:
            add_query(f"{precursors[0]} {transformation_terms[0]}", "PRECURSOR", "SECONDARY")
            if len(precursors) > 1:
                add_query(f"{precursors[0]} {precursors[1]} {transformation_terms[0]}", "PRECURSOR", "SECONDARY")

        # Intent 7: Target material + relevant parameter categories
        for param in parameters:
            if param:
                add_query(f"{primary_material} {param}", "PARAMETER", "SECONDARY")

        # Fallback: Process any LLM queries that weren't caught
        for sq in profile.search_queries:
            q_str = sq.query if hasattr(sq, "query") else str(sq)
            tier = sq.category.value if hasattr(sq, "category") and hasattr(sq.category, "value") else str(getattr(sq, "category", "LLM_GENERATED"))
            priority = sq.priority.value if hasattr(sq, "priority") and hasattr(sq.priority, "value") else str(getattr(sq, "priority", "SECONDARY"))
            add_query(q_str, tier, priority)

        logger.debug("Backend generated %d universal raw search queries for %s.", len(queries), profile.compound_name)
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
            
        formatted_query = query_str
        # Serper free tier blocks advanced operators like TI=() and TAC=() with complex AND/OR.
        # We will pass the raw keywords instead.
            
        # DO NOT inject jurisdiction or date modifiers into the Serper query string.
        # Serper Google Patents integration frequently fails to parse complex OR/date logic 
        # and returns 0 organic results. All filtering must be done deterministically in Python.

        payload = {
            "q": formatted_query,
            "page": page,
            "num": 20 # 20 results per page
        }
        
        # Diagnostic logging
        logger.debug(f"  Serper Query: {formatted_query}")
        logger.debug(f"  Endpoint: https://google.serper.dev/patents")
        logger.debug(f"  Page: {page}")
        
        headers = {
            'X-API-KEY': self.serper_api_key,
            'Content-Type': 'application/json'
        }
        
        all_results = []
        start_time = time.time()
        
        async with httpx.AsyncClient() as client:
            try:
                # [DIAGNOSTIC LOGGING]
                logger.debug(f"Serper API Request -> URL: https://google.serper.dev/patents | Payload: {payload}")
                
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
                logger.debug(f"  HTTP Status: {response.status_code}")
                logger.debug(f"  Raw Results: {len(data.get('organic', []))}")
                
                # Log a sanitized version of the actual first page for debugging
                if page == 1:
                    sanitized_data = {
                        "searchParameters": data.get("searchParameters"),
                        "organic_count": len(data.get("organic", [])),
                        "first_organic_item": data.get("organic", [])[0] if data.get("organic") else None
                    }
                    logger.debug(f"[DIAGNOSTIC] Serper JSON Response Sample: {sanitized_data}")
                
                import re
                organic_results = data.get("organic", [])
                
                logger.debug(f"[DIAGNOSTIC] Query '{formatted_query}' Page {page} Raw Results: {len(organic_results)}")
                
                for idx, result in enumerate(organic_results):
                    link = result.get("link", "")
                    title = result.get("title", "")
                    pub_date = result.get("publicationDate", "")
                    
                    if not title:
                        logger.warning(f"[DIAGNOSTIC] TITLE EXTRACTION FAILED | query={formatted_query} | result_index={idx} | available_fields={list(result.keys())}")
                    else:
                        if page == 1 and idx < 10:
                            logger.debug(f"[DIAGNOSTIC] SERPER RESULT: raw result index = {idx} | title = {title} | url = {link} | pub_date = {pub_date}")

                    patent_number = ""
                    authority = "XX"
                    
                    if link and "patents.google.com" in link:
                        match = re.search(r'patents\.google\.com/patent/([a-zA-Z0-9\-]+)', link)
                        if match:
                            patent_number = match.group(1)
                            # Extract authority if starts with 2 letters
                            auth_match = re.match(r'^([a-zA-Z]{2})', patent_number)
                            if auth_match:
                                authority = auth_match.group(1).upper()
                    
                    if not patent_number:
                        if not link:
                            continue
                        import hashlib
                        patent_number = "URL_" + hashlib.md5(link.encode()).hexdigest()[:10]
                        
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
                            
                duration_ms = int((time.time() - start_time) * 1000)
                
                logger.debug("SERPER REQUEST")
                logger.debug("-" * 14)
                try:
                    from app.core.telemetry import get_current_run_id, get_current_stage
                    run_id = get_current_run_id() or 'UNKNOWN'
                    stage = get_current_stage()
                    stage_name = stage.name if hasattr(stage, 'name') else str(stage) if stage else 'UNKNOWN'
                    logger.debug(f"Run ID: {run_id}")
                    logger.debug(f"Stage: {stage_name}")
                    logger.debug(f"Query: {formatted_query}")
                    logger.info(f"Page: {page}")
                    logger.debug(f"Results Returned: {len(all_results)}")
                    logger.info(f"HTTP Status: {response.status_code}")
                    logger.debug(f"Credits/Usage if available: {data.get('credits', 1)}")
                    logger.debug(f"Latency: {duration_ms}ms")
                    logger.debug(f"Status: SUCCESS")
                    logger.debug(f"Error: NONE")
                    logger.debug("=" * 60)
                    await UsageLogger.record_api_usage(
                        provider="serper",
                        operation="google_patents_search",
                        latency_ms=duration_ms,
                        status="success",
                        http_status=response.status_code,
                        metadata={
                            "query": formatted_query,
                            "jurisdictions": jurisdictions,
                            "page": page,
                            "results_returned": len(all_results),
                            "credits": data.get("credits", 1)
                        }
                    )
                except Exception as telemetry_error:
                    logger.warning("TELEMETRY FAILURE — search result preserved: %s", telemetry_error)
                            
            except httpx.HTTPStatusError as e:
                # Log detailed error information for HTTP errors
                error_body = ""
                try:
                    error_body = e.response.text
                except:
                    error_body = "Could not extract response body"
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                logger.debug("SERPER REQUEST")
                logger.debug("-" * 14)
                try:
                    from app.core.telemetry import get_current_run_id, get_current_stage
                    run_id = get_current_run_id() or 'UNKNOWN'
                    stage = get_current_stage()
                    stage_name = stage.name if hasattr(stage, 'name') else str(stage) if stage else 'UNKNOWN'
                    logger.debug(f"Run ID: {run_id}")
                    logger.debug(f"Stage: {stage_name}")
                    logger.debug(f"Query: {formatted_query}")
                    logger.info(f"Page: {page}")
                    logger.debug(f"Results Returned: 0")
                    logger.info(f"HTTP Status: {e.response.status_code}")
                    logger.debug(f"Credits/Usage if available: N/A")
                    logger.debug(f"Latency: {duration_ms}ms")
                    logger.debug(f"Status: FAILED")
                    logger.debug(f"Error: HTTPStatusError - {error_body}")
                    logger.debug("=" * 60)
                    await UsageLogger.record_api_usage(
                        provider="serper",
                        operation="google_patents_search",
                        latency_ms=duration_ms,
                        status="failed",
                        http_status=e.response.status_code,
                        error_type="HTTPStatusError",
                        error_message=str(e),
                        request_count=0,  # Do not inflate usage/cost on failed requests
                        metadata={
                            "query": formatted_query,
                            "jurisdictions": jurisdictions,
                            "page": page
                        }
                    )
                except Exception as telemetry_error:
                    logger.warning("TELEMETRY FAILURE — search result preserved: %s", telemetry_error)
                
                # Check for credit exhaustion
                if e.response.status_code == 400 and "Not enough credits" in error_body:
                    raise SerperCreditsExhaustedError("Serper API credits exhausted")
                
                return [], False
            except SerperCreditsExhaustedError:
                # Re-raise to be caught by orchestrator for fail-fast handling
                raise
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                
                logger.debug("SERPER REQUEST")
                logger.debug("-" * 14)
                try:
                    from app.core.telemetry import get_current_run_id, get_current_stage
                    run_id = get_current_run_id() or 'UNKNOWN'
                    stage = get_current_stage()
                    stage_name = stage.name if hasattr(stage, 'name') else str(stage) if stage else 'UNKNOWN'
                    logger.debug(f"Run ID: {run_id}")
                    logger.debug(f"Stage: {stage_name}")
                    logger.debug(f"Query: {formatted_query}")
                    logger.info(f"Page: {page}")
                    logger.debug(f"Results Returned: 0")
                    logger.info(f"HTTP Status: N/A")
                    logger.debug(f"Credits/Usage if available: N/A")
                    logger.debug(f"Latency: {duration_ms}ms")
                    logger.debug(f"Status: FAILED")
                    logger.debug(f"Error: {type(e).__name__} - {str(e)}")
                    logger.debug("=" * 60)
                    await UsageLogger.record_api_usage(
                        provider="serper",
                        operation="google_patents_search",
                        latency_ms=duration_ms,
                        status="failed",
                        error_type=type(e).__name__,
                        error_message=str(e),
                        metadata={
                            "query": formatted_query,
                            "jurisdictions": jurisdictions,
                            "page": page
                        }
                    )
                except Exception as telemetry_error:
                    logger.warning("TELEMETRY FAILURE — search result preserved: %s", telemetry_error)
                
                return [], False
                
        return all_results, True

