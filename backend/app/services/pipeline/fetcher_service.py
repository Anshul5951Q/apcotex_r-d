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

logger = logging.getLogger(__name__)


class FetcherService:
    async def fetch_patent_text(self, url: str) -> Optional[str]:
        """
        Download the patent and extract raw text.
        Supports HTML (Google Patents) and PDF.
        """
        logger.info("Fetching patent from %s...", url)
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                
                content_type = response.headers.get("Content-Type", "")
                
                if "application/pdf" in content_type.lower() or url.lower().endswith(".pdf"):
                    return self._parse_pdf(response.content)
                else:
                    return self._parse_google_patents_html(response.text)
        except Exception as e:
            logger.error("Failed to fetch patent from %s: %s", url, e)
            return None

    def _parse_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text from a PDF file using pdfplumber."""
        logger.info("Parsing PDF content...")
        text_pages = []
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_pages.append(text)
            return "\n".join(text_pages)
        except Exception as e:
            logger.error("PDF parsing failed: %s", e)
            return ""

    def _parse_google_patents_html(self, html: str) -> str:
        """
        Extract meaningful text from Google Patents HTML.
        Removes legal boilerplate, scripts, styles, and priority history.
        """
        logger.info("Parsing Google Patents HTML...")
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove noisy elements
        for tag in soup(["script", "style", "nav", "footer", "meta", "link", "noscript"]):
            tag.decompose()
            
        # Google Patents specific: remove citation lists, patent classifications
        for tag in soup.find_all(class_=re.compile("classification|citation|legal|history", re.IGNORECASE)):
            tag.decompose()

        # Extract abstract, description, and claims
        sections = []
        
        abstract = soup.find("section", {"itemprop": "abstract"})
        if abstract:
            sections.append("ABSTRACT:\n" + abstract.get_text(separator="\n", strip=True))
            
        description = soup.find("section", {"itemprop": "description"})
        if description:
            sections.append("DESCRIPTION:\n" + description.get_text(separator="\n", strip=True))
            
        claims = soup.find("section", {"itemprop": "claims"})
        if claims:
            sections.append("CLAIMS:\n" + claims.get_text(separator="\n", strip=True))
            
        # If we didn't find specific tags, just dump the body text
        if not sections:
            logger.warning("Could not find specific patent sections. Dumping entire body text.")
            body = soup.find("body")
            if body:
                return body.get_text(separator="\n", strip=True)
            return soup.get_text(separator="\n", strip=True)
            
        return "\n\n".join(sections)
