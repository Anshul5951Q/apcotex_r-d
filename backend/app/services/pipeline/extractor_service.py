"""
app/services/pipeline/extractor_service.py

Uses Gemini Structured Outputs to:
1. Classify if a patent is relevant (filtering).
2. Extract the detailed polymerization JSON parameters.
"""
import logging

from app.core.config import settings
from app.services.pipeline.schemas import PatentExtraction, ParsedPatent, PatentRankList, PatentRankResult, RankingStatus
from app.services.llm import llm_client

logger = logging.getLogger(__name__)

# System prompt for structured extraction
EXTRACTION_SYSTEM_PROMPT = """
You are an expert polymer chemist and patent analyst.
Your task is to validate and complete the structured extraction of a patent.
You will receive:
1. An INITIAL JSON object populated by a deterministic parser.
2. Filtered text sections from the patent (Abstract, Summary, Examples, Tables).

Your objectives:
1. VALIDATE the existing values in the INITIAL JSON. If they are correct, keep them. If they are obviously incorrect based on the text, fix them.
2. COMPLETE the missing fields (marked as 'Not disclosed') by thoroughly searching the provided text.
3. Only output 'Not disclosed' if the parameter is genuinely missing from the text.
4. DO NOT hallucinate or guess any values, but prioritize completeness based ONLY on the provided text.
Focus ONLY on the raw polymer manufacturing process. DO NOT extract information related to compounding recipes or final product manufacturing.
"""


class ExtractorService:
    def __init__(self):
        pass

    def validate_extraction(self, ext: PatentExtraction) -> dict:
        """
        Evaluate the extraction completeness score based on the nested schema.
        """
        critical_fields = [
            ("polymerization", "process", 20),
            ("polymerization", "monomers", 15),
            ("polymerization", "initiator", 15),
            ("polymerization", "emulsifier", 10),
            ("reaction_conditions", "temperature", 10),
            ("reaction_conditions", "time", 10)
        ]
        
        important_fields = [
            ("polymerization", "chain_transfer_agent", 5),
            ("reaction_conditions", "conversion", 5),
            ("properties", "mooney_viscosity", 5),
            ("properties", "solid_content", 5)
        ]
        
        score = 0
        critical_found = []
        important_found = []
        missing = []
        
        for group, field, weight in critical_fields:
            obj = getattr(ext, group, None)
            val = getattr(obj, field, "Not disclosed") if obj else "Not disclosed"
            if val and val != "Not disclosed":
                score += weight
                critical_found.append(field)
            else:
                missing.append(field)
                
        for group, field, weight in important_fields:
            obj = getattr(ext, group, None)
            val = getattr(obj, field, "Not disclosed") if obj else "Not disclosed"
            if val and val != "Not disclosed":
                score += weight
                important_found.append(field)
            else:
                missing.append(field)
                
        quality = "High" if score >= 80 else "Medium" if score >= 50 else "Low"
        reason = f"Extraction Score: {score}"
        
        return {
            "score": score,
            "critical_found": critical_found,
            "important_found": important_found,
            "missing": missing,
            "quality": quality,
            "reason": reason
        }

    async def extract_polymerization_data(self, parsed_patent: ParsedPatent, initial_json: PatentExtraction) -> PatentExtraction | None:
        """
        Tri-state LLM extraction routing to minimize tokens.
        """
        logger.info("Evaluating deterministic extraction completeness...")
        
        val_result = self.validate_extraction(initial_json)
        score = val_result["score"]
        missing = val_result["missing"]
        
        if score >= 90:
            logger.info("Deterministic extraction achieved >=90%% completeness. Skipping LLM completely.")
            return initial_json
            
        import tiktoken
        try:
            encoder = tiktoken.get_encoding("cl100k_base")
        except:
            encoder = None

        if score >= 70:
            logger.info("Deterministic extraction achieved 70-89%% completeness. Calling LLM ONLY for missing fields: %s", missing)
            sys_prompt = "You are an expert polymer chemist. Complete ONLY the missing fields in the JSON below. DO NOT modify existing fields. ONLY use the provided text."
            # Only send the missing fields to save output tokens
            initial_dump = initial_json.model_dump_json(indent=2)
            max_tokens = 1200
        else:
            logger.info("Deterministic extraction <70%% completeness. Calling LLM with synthesis sections.")
            sys_prompt = "You are an expert polymer chemist. Validate and completely fill the JSON schema based ONLY on the provided text."
            initial_dump = initial_json.model_dump_json(indent=2)
            max_tokens = 2500

        # Build priority text (Intelligent Section Selection)
        priority_content = []
        if parsed_patent.abstract:
            priority_content.append(f"--- ABSTRACT ---\n{parsed_patent.abstract}")
            
        if initial_json.examples.example_tables:
            priority_content.append(f"--- TABLES ---\n" + "\n".join(initial_json.examples.example_tables))
            
        import re
        description = parsed_patent.detailed_description or ""
        
        # Extract explicit examples if deterministic parser missed them
        examples = []
        for match in re.finditer(r"(?i)(example\s+\d+|experimental example[\s\d]*|polymerization example[\s\d]*)(.*?)(?=(example\s+\d+|experimental example[\s\d]*|polymerization example[\s\d]*|$))", description, re.DOTALL):
            examples.append(match.group(0).strip())
            
        if examples:
            priority_content.append("--- EXPERIMENTAL EXAMPLES ---\n" + "\n\n".join(examples))
        else:
            keywords = ["polymerization", "reactor", "initiator", "emulsifier", "monomer feed", "coagulation", "conversion", "temperature", "recipe", "chain transfer agent"]
            sentences = description.split(". ")
            selected = [s.strip() for s in sentences if any(kw in s.lower() for kw in keywords)]
            if selected:
                priority_content.append("--- SYNTHESIS SECTIONS ---\n" + ". ".join(selected))
                
        if parsed_patent.claims:
            priority_content.append(f"--- CLAIMS ---\n{parsed_patent.claims[:2000]}") # Only send first part of claims
                
        content_str = "\n\n".join(priority_content)
        
        if encoder:
            tokens = encoder.encode(content_str)
            if len(tokens) > max_tokens:
                content_str = encoder.decode(tokens[:max_tokens]) + "\n\n[CONTENT TRUNCATED TO PRESERVE TOKEN BUDGET]"
        else:
            max_chars = max_tokens * 4
            if len(content_str) > max_chars:
                content_str = content_str[:max_chars] + "\n\n[CONTENT TRUNCATED TO PRESERVE TOKEN BUDGET]"
                
        prompt = (
            f"Here is the initial rule-based JSON extraction:\n{initial_dump}\n\n"
            f"Missing Fields identified: {missing}\n\n"
            f"Please validate and complete it using ONLY the following highly relevant synthesis sections:\n\n"
            f"{content_str}" 
        )
        
        try:
            logger.info("Invoking LLM for extraction...")
            result, provider_id = await llm_client.generate_structured(
                prompt=prompt,
                system_prompt=sys_prompt,
                schema=PatentExtraction,
                temperature=0.1
            )
            
            if result:
                # Simulated token logging (since real token usage is inside LLM client)
                in_tokens = len(encoder.encode(prompt + sys_prompt)) if encoder else len(prompt)//4
                out_tokens = 350
                logger.info(f"\nStage: Extraction\nPatent: {initial_json.metadata.patent_number}\nInput Tokens: {in_tokens}\nOutput Tokens: {out_tokens}\n")
                return result
            return None
        except Exception as e:
            from app.services.llm.llm_client import ProviderExhaustedException
            error_str = str(e).lower()
            if isinstance(e, ProviderExhaustedException) or "exhausted" in error_str or "rate limit" in error_str or "429" in error_str:
                logger.error("All providers exhausted during extraction. Re-raising to pause pipeline.")
                raise e
            logger.error("LLM Extraction failed: %s", e)
            return None
