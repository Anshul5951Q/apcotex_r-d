"""
app/services/pipeline/parser_service.py

Performs deterministic, rule-based extraction to pre-fill the PatentExtraction JSON.
Parses HTML tables into structured JSON.
"""
import logging
import re
from bs4 import BeautifulSoup
from typing import Dict, Any

from app.services.pipeline.schemas import ParsedPatent, PatentExtraction

logger = logging.getLogger(__name__)

class ParserService:
    def __init__(self):
        pass

    def parse_tables(self, html_tables: list[Dict[str, str]]) -> str:
        """
        Converts a list of HTML tables into a structured Markdown or JSON representation
        so the LLM can easily read it without noisy HTML tags.
        """
        parsed_tables = []
        for i, table_dict in enumerate(html_tables):
            html = table_dict.get("html", "")
            if not html:
                continue
                
            soup = BeautifulSoup(html, "html.parser")
            rows = soup.find_all("tr")
            
            table_data = []
            for row in rows:
                cells = [cell.get_text(strip=True) for cell in row.find_all(["th", "td"])]
                if any(cells):  # Skip empty rows
                    table_data.append(" | ".join(cells))
            
            if table_data:
                parsed_tables.append(f"Table {i+1}:\n" + "\n".join(table_data))
                
        return "\n\n".join(parsed_tables)

    def detect_recipe_blocks(self, parsed: ParsedPatent) -> list[str]:
        """
        Identify distinct recipe blocks (e.g., Example 1, Preparation Example) 
        and slice them into isolated strings.
        """
        text = ""
        if parsed.examples:
            text += parsed.examples + "\n"
        if parsed.tables:
            text += self.parse_tables(parsed.tables) + "\n"
            
        if not text:
            # Fallback to detailed description if examples were not split out properly
            text = parsed.detailed_description

        # Simple regex to split by typical Example headers
        # Matches "Example 1", "Comparative Example 2", "Preparation Example", etc.
        pattern = re.compile(r'\n((?:Comparative\s+|Preparation\s+)?(?:Example|Experiment)\s*\d*)\n', re.IGNORECASE)
        
        parts = pattern.split(text)
        blocks = []
        
        # parts[0] is the text before the first example. We skip it unless it's the only part.
        if len(parts) == 1:
            # No specific example headers found, treat the whole thing as one block
            blocks.append(parts[0].strip())
        else:
            # parts will be [pre_text, "Example 1", body_1, "Example 2", body_2, ...]
            for i in range(1, len(parts), 2):
                header = parts[i].strip()
                body = parts[i+1].strip() if i+1 < len(parts) else ""
                block_text = f"--- {header.upper()} ---\n{body}"
                blocks.append(block_text)
                
        return [b for b in blocks if len(b) > 50]  # ignore tiny artifacts

    def extract_deterministic_data(self, parsed: ParsedPatent, recipe_block: str = None) -> PatentExtraction:
        """
        Populate the PatentExtraction nested object using deterministic rules (regex and meta tags).
        Unfound fields remain 'Not disclosed'.
        """
        logger.info("Executing Rule-Based Extraction...")
        
        extraction = PatentExtraction()
        extraction.metadata.url = parsed.url
        
        # 1. Metadata mapping
        if "citation_patent_publication_number" in parsed.metadata:
            extraction.metadata.patent_number = parsed.metadata["citation_patent_publication_number"].replace(":", "")
        elif "citation_patent_number" in parsed.metadata:
            extraction.metadata.patent_number = parsed.metadata["citation_patent_number"]
        elif "DC.identifier" in parsed.metadata:
            extraction.metadata.patent_number = parsed.metadata["DC.identifier"]
            
        if extraction.metadata.patent_number and extraction.metadata.patent_number != "Not disclosed":
            extraction.metadata.jurisdiction = extraction.metadata.patent_number[:2].upper()
            
        if "citation_title" in parsed.metadata:
            extraction.metadata.patent_title = parsed.metadata["citation_title"]
        elif "DC.title" in parsed.metadata:
            extraction.metadata.patent_title = parsed.metadata["DC.title"]
            
        if "citation_assignee" in parsed.metadata:
            extraction.metadata.assignee = parsed.metadata["citation_assignee"]
        elif "DC.contributor" in parsed.metadata:
            extraction.metadata.assignee = parsed.metadata["DC.contributor"]
            
        if "citation_publication_date" in parsed.metadata:
            date_str = parsed.metadata["citation_publication_date"]
        elif "DC.date" in parsed.metadata:
            date_str = parsed.metadata["DC.date"]
        else:
            date_str = ""
            
        if date_str:
            match = re.search(r'\b(19|20)\d{2}\b', date_str)
            if match:
                extraction.metadata.publication_year = match.group(0)

        # Naive rule based searches over the text
        full_text = recipe_block if recipe_block else (parsed.abstract + "\n" + parsed.summary + "\n" + parsed.detailed_description + "\n" + parsed.examples)
        
        temp_matches = set(re.findall(r'(\d{1,3}\s*(?:°C|deg C|degrees C))', full_text, re.IGNORECASE))
        if temp_matches:
            extraction.reaction_conditions.temperature = ", ".join(list(temp_matches)[:5])
            
        time_matches = set(re.findall(r'(\d+(?:\.\d+)?\s*(?:hours|hrs|minutes|mins))', full_text, re.IGNORECASE))
        if time_matches:
            extraction.reaction_conditions.time = ", ".join(list(time_matches)[:5])
            
        conversion_matches = set(re.findall(r'(conversion.*?(\d{1,3}(?:\.\d+)?)\s*%)', full_text, re.IGNORECASE))
        if conversion_matches:
            extraction.reaction_conditions.conversion = ", ".join([m[0] for m in list(conversion_matches)[:5]])
            
        water_matches = set(re.findall(r'((?:\d+(?:\.\d+)?)\s*(?:parts|phr).*?water)', full_text, re.IGNORECASE))
        if water_matches:
            extraction.polymerization.water_amount = ", ".join(list(water_matches)[:5])
            
        acn_matches = set(re.findall(r'(acrylonitrile|ACN).*?(\d{1,3}(?:\.\d+)?)\s*(?:%|parts|phr)', full_text, re.IGNORECASE))
        if acn_matches:
            extraction.polymerization.monomers = "Acrylonitrile: " + ", ".join([f"{m[1]} {m[0].split()[-1]}" for m in list(acn_matches)[:5]])
            
        bd_matches = set(re.findall(r'(butadiene|BD).*?(\d{1,3}(?:\.\d+)?)\s*(?:%|parts|phr)', full_text, re.IGNORECASE))
        if bd_matches:
            bd_str = "Butadiene: " + ", ".join([f"{m[1]} {m[0].split()[-1]}" for m in list(bd_matches)[:5]])
            if extraction.polymerization.monomers != "Not disclosed":
                extraction.polymerization.monomers += "; " + bd_str
            else:
                extraction.polymerization.monomers = bd_str
            
        mooney_matches = set(re.findall(r'(mooney.*?(\d{1,3}(?:\.\d+)?))', full_text, re.IGNORECASE))
        if mooney_matches:
            extraction.properties.mooney_viscosity = ", ".join([m[1] for m in list(mooney_matches)[:3]])
            
        particle_size_matches = set(re.findall(r'(particle size.*?(\d{1,4}(?:\.\d+)?)\s*(?:nm|um|microns))', full_text, re.IGNORECASE))
        if particle_size_matches:
            extraction.properties.other_properties = "Particle Size: " + ", ".join([f"{m[1]} {m[0].split()[-1]}" for m in list(particle_size_matches)[:3]])
                
        tg_matches = set(re.findall(r'(Tg|glass transition).*?(-?\d{1,3}(?:\.\d+)?)\s*°C', full_text, re.IGNORECASE))
        if tg_matches:
            tg_str = "Tg: " + ", ".join([m[1] + "°C" for m in list(tg_matches)[:3]])
            if extraction.properties.other_properties != "Not disclosed":
                extraction.properties.other_properties += "; " + tg_str
            else:
                extraction.properties.other_properties = tg_str
                
        initiator_matches = set(re.findall(r'((?:potassium persulfate|KPS|ammonium persulfate|APS|initiator|catalyst).*?(?:\d+(?:\.\d+)?)\s*(?:parts|phr))', full_text, re.IGNORECASE))
        if initiator_matches:
            extraction.polymerization.initiator = ", ".join(list(initiator_matches)[:5])
            
        cta_matches = set(re.findall(r'((?:t-dodecyl mercaptan|t-DDM|chain transfer agent|CTA).*?(?:\d+(?:\.\d+)?)\s*(?:parts|phr))', full_text, re.IGNORECASE))
        if cta_matches:
            extraction.polymerization.chain_transfer_agent = ", ".join(list(cta_matches)[:5])
            
        emulsifier_matches = set(re.findall(r'((?:potassium oleate|sodium rosinate|sodium dodecylbenzenesulfonate|emulsifier|surfactant).*?(?:\d+(?:\.\d+)?)\s*(?:parts|phr))', full_text, re.IGNORECASE))
        if emulsifier_matches:
            extraction.polymerization.emulsifier = ", ".join(list(emulsifier_matches)[:5])

        # Example tables & Claims
        if parsed.tables:
            extraction.examples.example_tables = [self.parse_tables(parsed.tables)]
            
        if parsed.claims:
            claims_split = re.split(r'\n(?=\d+\.)', parsed.claims)
            indep_claims = [c.strip() for c in claims_split if c.strip() and not re.search(r'claim \d+', c, re.IGNORECASE)]
            extraction.claims = indep_claims[:5]

        return extraction
