"""
app/services/pipeline/fetcher_service.py

Downloads and parses patents from Google Patents or standard PDFs.
"""
import io
import logging
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup
import pdfplumber

from app.services.pipeline.schemas import ParsedPatent

logger = logging.getLogger(__name__)


class FetcherService:
    async def fetch_patent(self, url: str) -> Optional[ParsedPatent]:
        """
        Download the patent and extract sections into a ParsedPatent.
        Supports HTML (Google Patents) and PDF.
        """
        logger.info("Fetching patent from %s...", url)
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                
                content_type = response.headers.get("Content-Type", "")
                
                if "application/pdf" in content_type.lower() or url.lower().endswith(".pdf"):
                    parsed = self._parse_pdf(response.content)
                else:
                    parsed = self._parse_google_patents_html(response.text)
                
                parsed.url = url
                return parsed
        except Exception as e:
            logger.error("Failed to fetch patent from %s: %s", url, e)
            return None

    def _parse_pdf(self, pdf_bytes: bytes) -> ParsedPatent:
        """Extract text from a PDF file using pdfplumber."""
        logger.info("Parsing PDF content...")
        text_pages = []
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_pages.append(text)
            
            # For PDF, we just dump everything into detailed_description since we lack HTML tags
            # Rule-based extraction will still run on it, but it's less structured.
            return ParsedPatent(detailed_description="\n".join(text_pages))
        except Exception as e:
            logger.error("PDF parsing failed: %s", e)
            return ""

    def _parse_google_patents_html(self, html: str) -> ParsedPatent:
        """
        Extract meaningful sections from Google Patents HTML.
        """
        logger.info("Parsing Google Patents HTML...")
        soup = BeautifulSoup(html, "html.parser")
        
        parsed = ParsedPatent()
        
        # 1. Extract metadata from meta tags
        meta_tags = soup.find_all("meta")
        for meta in meta_tags:
            name = meta.get("name") or meta.get("property")
            content = meta.get("content")
            if name and content and (name.startswith("DC.") or name.startswith("citation_")):
                parsed.metadata[name] = content

        # Remove noisy elements
        for tag in soup(["script", "style", "nav", "footer", "meta", "link", "noscript"]):
            tag.decompose()
            
        # Google Patents specific: remove citation lists, patent classifications
        for tag in soup.find_all(class_=re.compile("classification|citation|legal|history", re.IGNORECASE)):
            tag.decompose()

        # Extract abstract
        abstract_node = soup.find("section", {"itemprop": "abstract"})
        if abstract_node:
            parsed.abstract = abstract_node.get_text(separator="\n", strip=True)
            
        # Extract claims
        claims_node = soup.find("section", {"itemprop": "claims"})
        if claims_node:
            parsed.claims = claims_node.get_text(separator="\n", strip=True)
            
        # Extract tables from description BEFORE pulling text
        description_node = soup.find("section", {"itemprop": "description"})
        
        if description_node:
            # We want to segment description into Summary, Examples, Detailed Desc.
            # Google Patents doesn't strictly tag these, but often uses headers or bold text.
            # We'll just grab the full description and let the ParserService split it if needed,
            # or we can do a naive split here.
            # A common approach is to look for "Example", "Summary", etc in headings.
            
            # Pull tables first so they don't just become garbled text
            tables = description_node.find_all("table")
            for t in tables:
                # We'll pass the raw HTML of the table to the rule-based extractor
                parsed.tables.append({"html": str(t)})
                # We optionally remove them from text to reduce token count, but sometimes text refers to them.
                # Let's keep them in the text as plain text just in case, but they will be processed natively.
                
            desc_text = description_node.get_text(separator="\n", strip=True)
            
            # Naive splitting based on common headers
            # Find the index of "EXAMPLES" or "Example 1"
            ex_match = re.search(r'\n(EXAMPLES?|Examples?|EXAMPLE 1)\n', desc_text, re.IGNORECASE)
            if ex_match:
                idx = ex_match.start()
                parsed.detailed_description = desc_text[:idx].strip()
                parsed.examples = desc_text[idx:].strip()
            else:
                parsed.detailed_description = desc_text
                
        else:
            # Fallback
            body = soup.find("body")
            if body:
                parsed.detailed_description = body.get_text(separator="\n", strip=True)
            else:
                parsed.detailed_description = soup.get_text(separator="\n", strip=True)
                
        return parsed
