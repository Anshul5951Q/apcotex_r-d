import asyncio
import os
import sys
import logging
from pprint import pprint
import httpx

# Set up logging for the script to capture orchestrator output
logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import AsyncSessionLocal
from app.services.pipeline.compound_intelligence import CompoundIntelligenceService
from app.services.pipeline.search_service import SearchService
from app.services.pipeline.title_scorer import TitleScorer
from app.services.pipeline.validation_service import ValidationService
from app.services.pipeline.cache_service import CacheService

materials = [
    "Low Acrylonitrile NBR",
    "High Acrylonitrile NBR",
    "Generic NBR",
    "Polycarbonate",
    "Polyetheretherketone (PEEK)"
]

async def safe_serper_search(search_service, query_str, field, page):
    for attempt in range(3):
        try:
            results, success = await search_service.search_patents_page(query_str, field, page)
            if success:
                return results, success
        except Exception as e:
            print(f"Retry {attempt+1} Serper error for {query_str}: {type(e).__name__} {e}")
            await asyncio.sleep(2)
    return [], False

async def main():
    cache_service = CacheService()
    compound_intelligence = CompoundIntelligenceService(cache_service)
    search_service = SearchService()
    validation_service = ValidationService()

    for material in materials:
        print(f"\n{'='*80}")
        print(f"DISCOVERY AUDIT: {material}")
        print(f"{'='*80}")
        
        # 1. Profile
        print(f"\n--- Generating Profile ---")
        profile = await compound_intelligence.generate_profile(material)
        print(f"Base Chemistry: {profile.compound_name}")
        print(f"Constraints: {profile.important_constraints}")
        print(f"Synonyms: {profile.synonyms}")
        print(f"Manufacturing Intent: {profile.research_intent}")
        
        # 2. Queries
        print(f"\n--- Building Queries ---")
        queries = search_service.build_queries(profile)
        for i, q in enumerate(queries):
            print(f"Query {i+1}: {q['query']} (Field: {q['search_field']})")
            
        # 3. Discovery
        print(f"\n--- Executing Discovery ---")
        
        raw_candidates = []
        # Run up to 6 queries and up to 2 pages to get enough results to validate
        for q in queries[:6]:
            print(f"\nExecuting Query: {q['query']}")
            for page in range(1, 3):
                results, success = await safe_serper_search(search_service, q['query'], q['search_field'], page)
                print(f"Page {page}: found {len(results)} results (success: {success})")
                if not success or len(results) == 0:
                    break
                raw_candidates.extend(results)
                if len(results) < 20: # Last page reached
                    break
        
        print(f"\nTotal Raw Candidates: {len(raw_candidates)}")
        
        # Deduplicate
        unique = {}
        for rc in raw_candidates:
            if rc['patent_number'] not in unique:
                unique[rc['patent_number']] = rc
                
        print(f"Total Unique Candidates: {len(unique)}")
        
        # 4. Title Scoring
        print(f"\n--- Title Scoring ---")
        title_scorer = TitleScorer(profile)
        eligible = []
        for c in list(unique.values()):
            score, status, signals = title_scorer.score_title(c['title'])
            if status.name in ["STRONG", "MEDIUM", "WEAK"]:
                c['title_status'] = status.name
                c['title_score'] = score
                eligible.append(c)
                
        print(f"Eligible after Title Screening: {len(eligible)}")
        
        # 5. Content Validation (LLM Ranking)
        print(f"\n--- Content Validation ---")
        if eligible:
            # We sort by title score and take top 40 for LLM validation to preserve tokens
            eligible.sort(key=lambda x: x['title_score'], reverse=True)
            validation_input = [{"publication_number": c["patent_number"], "title": c["title"]} for c in eligible[:40]]
            ranked_results = await validation_service.rank_titles(validation_input, profile)
            
            keep = [r for r in ranked_results if r.decision == "KEEP"]
            reject = [r for r in ranked_results if r.decision == "REJECT"]
            
            print(f"Validated KEEP: {len(keep)}")
            for r in keep[:5]:
                print(f"  KEEP: {r.publication_number} -> {r.reason}")
                
            print(f"Validated REJECT: {len(reject)}")
            for r in reject[:5]:
                print(f"  REJECT: {r.publication_number} -> {r.reason}")
        else:
            print("No eligible candidates to validate.")

if __name__ == "__main__":
    asyncio.run(main())
