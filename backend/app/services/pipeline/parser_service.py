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
        Converts a list of HTML tables into a structured Markdown representation
        so the LLM can easily read it without noisy HTML tags.
        """
        parsed_tables = []
        for i, table_dict in enumerate(html_tables):
            html = table_dict.get("html", "")
            title = table_dict.get("title", f"Table {i+1}")
            if not html:
                continue
                
            soup = BeautifulSoup(html, "html.parser")
            rows = soup.find_all("tr")
            
            table_data = []
            for r_idx, row in enumerate(rows):
                cells = [cell.get_text(strip=True).replace("\n", " ").replace("|", " ") for cell in row.find_all(["th", "td"])]
                if any(cells):  # Skip empty rows
                    table_data.append("| " + " | ".join(cells) + " |")
                    # Add markdown header separator after first row
                    if r_idx == 0:
                        table_data.append("|" + "|".join(["---" for _ in cells]) + "|")
            
            if table_data:
                parsed_tables.append(f"{title}:\n" + "\n".join(table_data))
                
        return "\n\n".join(parsed_tables)

    def detect_recipe_blocks(self, parsed: ParsedPatent) -> list['PatentExample']:
        """
        Identify distinct recipe blocks using flexible section detection.
        """
        text = ""
        if parsed.examples:
            text += parsed.examples + "\n"
        if parsed.tables:
            text += self.parse_tables(parsed.tables) + "\n"
            
        if not text:
            text = parsed.detailed_description

        # Flexible detection for sections as requested
        # Example, Example 1, Experimental Example, Preparation Example, Working Example,
        # Polymerization Example, Synthesis Example, Preparation of Polymer, Polymer Preparation,
        # Polymerization Procedure, Synthesis Procedure, Experimental Procedure, Production Process,
        # Manufacturing Process, Detailed Description
        
        headers = [
            r"Example\s*\d*",
            r"Experimental Example\s*\d*",
            r"Preparation Example\s*\d*",
            r"Working Example\s*\d*",
            r"Polymerization Example\s*\d*",
            r"Synthesis Example\s*\d*",
            r"Preparation of Polymer\s*\d*",
            r"Polymer Preparation\s*\d*",
            r"Polymerization Procedure\s*\d*",
            r"Synthesis Procedure\s*\d*",
            r"Experimental Procedure\s*\d*",
            r"Production Process\s*\d*",
            r"Manufacturing Process\s*\d*",
            r"Comparative Example\s*\d*",
            r"General Procedure",
            r"General Polymerization Procedure",
            r"Process for Producing",
            r"Reaction Procedure",
            r"Preparation\s*\d*",
            r"Polymerization\s*\d*",
            r"Experimental",
            r"Synthesis",
            r"Detailed Description"
        ]
        
        # Build one big regex: matches start-of-string or newline, followed by any header, optionally a colon or dash, then newline
        pattern_str = r'(?:^|\n)(' + '|'.join(headers) + r')[\s:\-]*\n'
        pattern = re.compile(pattern_str, re.IGNORECASE)
        
        parts = pattern.split(text)
        from app.services.pipeline.schemas import PatentExample
        blocks = []
        
        if len(parts) == 1:
            # No headers found, just return one big block if it's large enough
            if len(parts[0].strip()) > 50:
                blocks.append(PatentExample(
                    number="1",
                    type="GENERAL PROCEDURE",
                    title="General Procedure",
                    raw_text=parts[0].strip()
                ))
        else:
            for i in range(1, len(parts), 2):
                header = parts[i].strip()
                body = parts[i+1].strip() if i+1 < len(parts) else ""
                if len(body) > 50:
                    # Extract number if present
                    num_match = re.search(r'\d+', header)
                    number = num_match.group(0) if num_match else ""
                    
                    # Determine type
                    ex_type = "EXAMPLE"
                    if "comparative" in header.lower():
                        ex_type = "COMPARATIVE EXAMPLE"
                    elif "preparation" in header.lower() or "synthesis" in header.lower():
                        ex_type = "PREPARATION"
                        
                    blocks.append(PatentExample(
                        number=number,
                        type=ex_type,
                        title=header.upper(),
                        raw_text=body
                    ))
                
        return blocks

    def retrieve_targeted_evidence(self, parsed: ParsedPatent, missing_keywords: list[str], max_chars: int = 10000) -> str:
        """
        Targeted retrieval: searches the parsed patent for passages containing the missing keywords.
        Returns paragraphs surrounding the match, safely under the max character limit.
        """
        text = ""
        if parsed.examples:
            text += parsed.examples + "\n"
        if parsed.detailed_description:
            text += parsed.detailed_description + "\n"
        if parsed.tables:
            text += self.parse_tables(parsed.tables) + "\n"
            
        paragraphs = text.split('\n\n')
        retrieved_paragraphs = []
        retrieved_indices = set()
        
        for kw in missing_keywords:
            for i, p in enumerate(paragraphs):
                if i in retrieved_indices:
                    continue
                if kw.lower() in p.lower():
                    # Get surrounding context: i-1, i, i+1
                    start_idx = max(0, i-1)
                    end_idx = min(len(paragraphs), i+2)
                    
                    for j in range(start_idx, end_idx):
                        if j not in retrieved_indices and len(paragraphs[j].strip()) > 20:
                            retrieved_paragraphs.append(paragraphs[j].strip())
                            retrieved_indices.add(j)

        # Truncate context to stay within budget
        context = ""
        for p in retrieved_paragraphs:
            if len(context) + len(p) + 2 > max_chars:
                break
            context += p + "\n\n"
            
        return context.strip()
