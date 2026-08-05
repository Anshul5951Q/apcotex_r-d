"""
app/services/pipeline/report_service.py

Aggregates extracted patent data, generates a Markdown report via Gemini,
and exports the final report to PDF and DOCX formats.
"""
import logging
import os
import uuid
from typing import List

import markdown
from docx import Document
from xhtml2pdf import pisa

from app.core.config import settings
from app.services.pipeline.schemas import PatentExtraction
from app.services.llm import llm_client

logger = logging.getLogger(__name__)

REPORT_SYSTEM_PROMPT = """
You are an expert polymer scientist and research analyst.
You have been provided with structured data extracted from multiple patents related to {compound_name}.
Your task is to synthesize this data into a professional, cohesive technical report.
The report MUST strictly follow this exact structure:

# {compound_name}
## POLYMERIZATION / SYNTHESIS PATENT RESEARCH REPORT

### Abstract
(Approx 250-350 words summarizing the patent landscape, major synthesis approaches, recurring chemistry, and trends).

### Methodology
(For each patent provided, create a subsection with the Patent Number and Title, and list the extracted parameters in a clean bulleted list).

### Cross-Patent Comparison & Synthesis Trends
(Identify common technical trends across all analyzed patents. Subsections should include: Emulsifier Selection and Loading, Initiator and Chain Transfer Agent Strategies, Monomer Ratio and Reaction Control, Coagulation and Post-Treatment Conditions).

### References
(A markdown table containing: Patent Number, Patent Title, Assignee, Jurisdiction, Publication Year, Google Patents URL).

Constraints:
- DO NOT exceed 5 pages of content.
- Use ONLY the provided structured extraction data. DO NOT hallucinate.
- If a parameter is 'Not disclosed', mention it as such.
- The Google Patents URL in the references MUST be a clickable markdown link using the 'url' field provided.
- Exclude compounding formulations or end-product manufacturing (focus strictly on raw polymer synthesis).
"""

class ReportService:
    def __init__(self):
        # Ensure export directory exists
        self.export_dir = os.path.join(os.getcwd(), "exports")
        os.makedirs(self.export_dir, exist_ok=True)

    async def generate_markdown_report(self, compound_name: str, extractions: List[PatentExtraction]) -> str:
        """Generate the markdown report via Gemini using the aggregated extractions."""
        logger.info("Generating final markdown report for %d patents...", len(extractions))
        
        # Serialize the extractions to JSON-like string for Gemini context
        extractions_data = "\n\n".join(
            [f"--- Patent {i+1} ---\n{ex.model_dump_json(indent=2)}" for i, ex in enumerate(extractions)]
        )
        
        prompt = (
            f"Please generate the report for the compound: {compound_name}\n\n"
            f"Here is the structured extraction data from the relevant patents:\n"
            f"{extractions_data}\n"
        )
        
        sys_prompt = REPORT_SYSTEM_PROMPT.format(compound_name=compound_name)

        try:
            return await llm_client.generate_text(
                prompt=prompt,
                system_prompt=sys_prompt,
                temperature=0.2
            )
        except Exception as e:
            logger.error("Failed to generate markdown report: %s", e)
            return f"# Error generating report\n\nFailed due to API error: {e}"

    async def export_to_pdf(self, markdown_text: str, file_name: str) -> str:
        """Convert Markdown to HTML, then to PDF using xhtml2pdf."""
        logger.info("Exporting report to PDF: %s", file_name)
        
        # Convert Markdown to HTML
        html_content = markdown.markdown(markdown_text, extensions=['tables'])
        
        # Basic APCOTEX CSS styling wrapper
        styled_html = f"""
        <html>
        <head>
            <style>
                @page {{ size: a4 portrait; margin: 2cm; }}
                body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #333; }}
                h1 {{ color: #004080; font-size: 24pt; border-bottom: 2px solid #004080; padding-bottom: 5px; }}
                h2 {{ color: #0059b3; font-size: 18pt; margin-top: 20px; }}
                h3 {{ color: #0073e6; font-size: 14pt; margin-top: 15px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; margin-bottom: 10px; }}
                th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        pdf_path = os.path.join(self.export_dir, file_name)
        
        try:
            with open(pdf_path, "w+b") as result_file:
                pisa_status = pisa.CreatePDF(styled_html, dest=result_file)
                
            if pisa_status.err:
                logger.error("Error creating PDF via xhtml2pdf")
                raise Exception("PDF generation failed.")
                
            return pdf_path
        except Exception as e:
            logger.error("Export to PDF failed: %s", e)
            return ""

    async def export_to_docx(self, markdown_text: str, file_name: str) -> str:
        """
        Convert Markdown to DOCX using python-docx.
        Note: True markdown parsing to DOCX is complex; we'll do a simple line-by-line 
        or chunked parsing based on headings for Phase 1.
        """
        logger.info("Exporting report to DOCX: %s", file_name)
        
        doc = Document()
        
        # Super simple markdown parser for python-docx
        lines = markdown_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('# '):
                doc.add_heading(line[2:].replace('**', ''), level=1)
            elif line.startswith('## '):
                doc.add_heading(line[3:].replace('**', ''), level=2)
            elif line.startswith('### '):
                doc.add_heading(line[4:].replace('**', ''), level=3)
            elif line.startswith('- ') or line.startswith('* '):
                # Simple list item
                doc.add_paragraph(line[2:], style='List Bullet')
            elif line.startswith('|') and '---' not in line:
                # Basic table handling (skip rows that are just formatters like |---|---|)
                # python-docx tables are hard to build line-by-line easily without buffering,
                # so we will just dump table rows as text for this simple parser.
                doc.add_paragraph(line.replace('|', ' | '))
            elif not line.startswith('|---'):
                # Regular paragraph
                doc.add_paragraph(line.replace('**', ''))
                
        docx_path = os.path.join(self.export_dir, file_name)
        try:
            doc.save(docx_path)
            return docx_path
        except Exception as e:
            logger.error("Export to DOCX failed: %s", e)
            return ""
