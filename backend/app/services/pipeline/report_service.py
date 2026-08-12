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

from app.services.llm.llm_client import llm_client
from app.services.pipeline.schemas import ReportPatentEvidence, PatentResearchReport
from app.services.prompts.patent_prompts import (
    REPORT_GENERATION_SYSTEM_PROMPT,
    REPORT_GENERATION_USER_TEMPLATE
)

logger = logging.getLogger(__name__)

class ReportService:
    def __init__(self):
        # Ensure export directory exists
        self.export_dir = os.path.join(os.getcwd(), "exports")
        os.makedirs(self.export_dir, exist_ok=True)

    async def generate_structured_report(self, compound_name: str, extractions: List[ReportPatentEvidence]) -> PatentResearchReport:
        """Generate the structured report via Gemini using the aggregated extractions."""
        logger.info("Generating final structured report for %d patents...", len(extractions))

        from app.services.pipeline.report_evidence_service import ReportEvidenceService
        svc = ReportEvidenceService()
        extractions_data = svc.serialize_evidence(extractions)

        prompt = REPORT_GENERATION_USER_TEMPLATE.format(
            compound_name=compound_name,
            extractions_data=extractions_data
        )

        sys_prompt = REPORT_GENERATION_SYSTEM_PROMPT.format(compound_name=compound_name)

        max_retries = 2
        for attempt in range(max_retries):
            logger.info(f"REPORT GENERATION ATTEMPT {attempt + 1}/{max_retries}")

            try:
                report_obj, _ = await llm_client.generate_structured(
                    prompt=prompt,
                    system_prompt=sys_prompt,
                    schema=PatentResearchReport,
                    temperature=0.2
                )

                # Validate structured response
                logger.info("=" * 60)
                logger.info("REPORT STRUCTURED RESPONSE VALIDATION")
                logger.info("=" * 60)
                logger.info(f"Response received: YES")
                logger.info(f"Title: {'PRESENT' if report_obj.title else 'MISSING'}")
                logger.info(f"Abstract: {'PRESENT' if report_obj.abstract else 'MISSING'}")
                logger.info(f"Methodology patents: {len(report_obj.methodology_patents)}")
                logger.info(f"Cross-patent comparison: {len(report_obj.cross_patent_comparison)}")
                logger.info(f"References: {len(report_obj.references)}")
                logger.info("=" * 60)

                # Apply safe defaults for missing critical fields
                if not report_obj.title:
                    logger.warning("Title missing - applying default fallback")
                    report_obj.title = "PATENT RESEARCH REPORT"
                if not report_obj.abstract:
                    logger.warning("Abstract missing - applying default fallback")
                    report_obj.abstract = "No abstract provided."

                return report_obj

            except Exception as e:
                logger.error(f"REPORT GENERATION ATTEMPT {attempt + 1} FAILED: {e}")
                if attempt < max_retries - 1:
                    logger.info("Retrying report generation...")
                    continue
                else:
                    logger.error("All report generation attempts failed")
                    raise e

    def report_to_markdown(self, report: PatentResearchReport) -> str:
        """Converts the structured report to markdown for PDF/DOCX export."""
        lines = []

        # Title with safe fallback
        title = report.title or "PATENT RESEARCH REPORT"
        lines.append(f"# {title.upper()}")

        # Abstract with safe fallback
        abstract = report.abstract or "No abstract provided."
        lines.append("\n## 1. ABSTRACT")
        lines.append(abstract)

        lines.append("\n## 2. METHODOLOGY")
        lines.append("### POLYMERIZATION RECIPE EXTRACTIONS")

        for idx, patent in enumerate(report.methodology_patents):
            lines.append(f"\n#### Patent {idx + 1}")
            lines.append("\n**Patent Details**")

            pd = patent.patent_details
            lines.append(f"- Patent Number: {pd.patent_number or 'Not disclosed'}")
            lines.append(f"- Patent Title: {pd.patent_title or 'Not disclosed'}")
            lines.append(f"- Assignee: {pd.assignee or 'Not disclosed'}")
            lines.append(f"- Jurisdiction: {pd.jurisdiction or 'Not disclosed'}")
            lines.append(f"- Publication Year: {pd.publication_year or 'Not disclosed'}")
            lines.append(f"- Polymer Type: {pd.polymer_type or 'Not disclosed'}")
            lines.append(f"- Relevance to target: {pd.relevance_to_target or 'Not disclosed'}")

            lines.append("\n**Polymerization / Synthesis Method**")
            p = patent.polymerization_method
            lines.append(f"- Polymerization process: {p.polymerization_process or 'Not disclosed'}")
            lines.append(f"- Monomer system: {p.monomer_system or 'Not disclosed'}")
            lines.append(f"- Monomer ratio: {p.monomer_ratio or 'Not disclosed'}")
            lines.append(f"- Water amount: {p.water_amount or 'Not disclosed'}")
            lines.append(f"- Emulsifier: {p.emulsifier or 'Not disclosed'}")
            lines.append(f"- Emulsifier loading: {p.emulsifier_loading or 'Not disclosed'}")
            lines.append(f"- Initiator: {p.initiator or 'Not disclosed'}")
            lines.append(f"- Initiator loading: {p.initiator_loading or 'Not disclosed'}")
            lines.append(f"- Catalyst / activator: {p.catalyst_activator or 'Not disclosed'}")
            lines.append(f"- Chain-transfer agent: {p.chain_transfer_agent or 'Not disclosed'}")
            lines.append(f"- Chain-transfer dosage: {p.chain_transfer_dosage or 'Not disclosed'}")
            lines.append(f"- Polymerization temperature: {p.polymerization_temperature or 'Not disclosed'}")
            lines.append(f"- Pressure: {p.pressure or 'Not disclosed'}")
            lines.append(f"- pH: {p.ph or 'Not disclosed'}")
            lines.append(f"- Reaction time: {p.reaction_time or 'Not disclosed'}")
            lines.append(f"- Conversion: {p.conversion or 'Not disclosed'}")
            lines.append(f"- Coagulation conditions: {p.coagulation_conditions or 'Not disclosed'}")
            lines.append(f"- Post-treatment: {p.post_treatment or 'Not disclosed'}")
            lines.append(f"- Raw polymer properties: {p.raw_polymer_properties or 'Not disclosed'}")

            lines.append("\n**Relevant Experimental Evidence**")
            if patent.experimental_evidence:
                for ev in patent.experimental_evidence:
                    lines.append(f"- {ev}")
            else:
                lines.append("- No experimental evidence provided.")

            lines.append("\n**Technical Relevance**")
            lines.append(patent.technical_relevance or "No technical relevance provided.")

        lines.append("\n## 3. CROSS-PATENT COMPARISON & SYNTHESIS TRENDS")
        if report.cross_patent_comparison:
            for point in report.cross_patent_comparison:
                lines.append(f"- {point}")
        else:
            lines.append("- No cross-patent comparison provided.")

        lines.append("\n## 4. REFERENCES")
        if report.references:
            for ref in report.references:
                lines.append(f"- {ref}")
        else:
            lines.append("- No references provided.")

        return "\n".join(lines)

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
