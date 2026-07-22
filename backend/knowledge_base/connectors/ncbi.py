"""
NCBI Bookshelf + OpenStax + WHO/MoHFW/ICMR/NHM/UPSC connector.

Strategy:
- We never crawl paywalled / copyrighted material.
- We pull from explicit, public APIs / static URLs that are
  guaranteed-public-domain or CC BY.

NCBI Entrez E-utilities (esearch + efetch) returns public-domain text
records. We support:
  - StatPearls (NCBI Bookshelf IDs NBK####)
  - Bookshelf whole-book collections via the eBooks API
  - PubMed Central OA subset via the PMC OA service

We deliberately fetch only the OA/CC-marked records. The connector
sets `license=public_domain` for any NCBI record by default — NCBI
Bookshelf and PMC OA content are US Federal Government works or
explicitly CC-licensed.

Usage from a management command:
    python manage.py ingest_source ncbi-bookshelf \
        --query "hypertension pathophysiology" --max 50
"""

import json
import logging
import re
import time
import urllib.parse
from pathlib import Path
from typing import Iterable, Optional

from django.conf import settings

from .base import ConnectorBase, RawChunk

logger = logging.getLogger(__name__)


class NCBIBookshelfConnector(ConnectorBase):
    """
    Connector for NCBI Bookshelf / StatPearls / PubMed Central OA.

    Uses Entrez E-utilities (public, no auth required for moderate
    rates). A free NCBI API key increases rate limits — set
    `NCBI_API_KEY` env var.
    """

    source_slug = "ncbi-bookshelf"

    ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def __init__(self, api_key: Optional[str] = None,
                 tool: str = "cracklabs", email: str = "ops@cracklabs.app"):
        super().__init__()
        self.api_key = api_key or getattr(settings, "NCBI_API_KEY", "")
        self.tool = tool
        self.email = email

    def _rate_limit(self):
        if self.api_key:
            time.sleep(0.11)  # 10/s with key
        else:
            time.sleep(0.34)  # 3/s without key

    def _esearch(self, db: str, term: str, retmax: int = 20) -> list[str]:
        import requests
        params = {
            "db": db, "term": term, "retmax": retmax, "retmode": "json",
            "tool": self.tool, "email": self.email,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        try:
            r = requests.get(self.ESEARCH, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
            return data.get("esearchresult", {}).get("idlist", [])
        except Exception as e:
            logger.warning(f"NCBI esearch failed for '{term}': {e}")
            return []

    def _efetch_text(self, db: str, id_: str) -> tuple[str, str, str]:
        """Returns (title, full_text, source_url)."""
        import requests
        params = {
            "db": db, "id": id_, "rettype": "docsum", "retmode": "xml",
            "tool": self.tool, "email": self.email,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        try:
            r = requests.get(self.EFETCH, params=params, timeout=30)
            r.raise_for_status()
            xml = r.text
        except Exception as e:
            logger.warning(f"NCBI efetch failed for {db}/{id_}: {e}")
            return "", "", ""

        # Strip XML tags crudely to keep prose
        text = re.sub(r"<[^>]+>", " ", xml)
        text = re.sub(r"\s+", " ", text).strip()

        # Title extraction (best-effort)
        title_match = re.search(r"<ArticleTitle>(.*?)</ArticleTitle>", xml)
        title = title_match.group(1) if title_match else ""
        title = re.sub(r"<[^>]+>", "", title).strip()

        url = f"https://www.ncbi.nlm.nih.gov/{db}/?term={id_}"
        return title, text[:20000], url  # cap per record

    def fetch(self, query: str = "", max_records: int = 25,
              db: str = "books", **kwargs) -> Iterable[RawChunk]:
        """
        Fetch public-domain medical reference text from NCBI.

        Args:
            query: search term (medical concept, disease, drug)
            max_records: cap records (default 25 to stay polite)
            db: 'books' (NCBI Bookshelf/StatPearls), 'pmc' (PubMed Central)
        """
        if not query:
            logger.warning("NCBI fetch requires a non-empty query")
            return

        # Filter to free full text subset
        if db == "pmc":
            term = f'({query}) AND "open access"[Filter]'
        else:
            # Bookshelf ids start with NBK; restrict by prefix
            term = f'({query}) AND (NBK*[Book] OR StatPearls[Book])'

        ids = self._esearch(db=db, term=term, retmax=max_records)
        self._rate_limit()
        if not ids:
            logger.info(f"NCBI: no results for '{query}'")
            return

        for id_ in ids:
            self._rate_limit()
            title, text, url = self._efetch_text(db=db, id_=id_)
            if not text:
                continue
            for chunk in self._make_chunks(
                raw_text=text,
                locator=f"{db}/{id_}",
                source_url=url,
                subject="medicine",
                topic=query,
                title=title,
                quality_score=0.8,
            ):
                yield chunk
            logger.info(f"[ncbi-bookshelf] ingested {db}/{id_} — {title[:60]}")


class OpenStaxConnector(ConnectorBase):
    """
    OpenStax (CC BY 4.0) textbook connector.

    Uses the OpenStax CNX archive API for the canonical, attribution-
    friendly version of each book. Books are CC BY 4.0 — commercial
    use OK with attribution (we carry attribution in KnowledgeSource).
    """

    source_slug = "openstax-anatomy"  # default; subclasses override

    CNX_API = "https://archive.cnx.org/contents/"

    # Map subject -> canonical collection UUID (these are stable OpenStax IDs)
    COLLECTIONS = {
        "openstax-anatomy": (
            "14fb4ad7-39a1-4eee-ab6e-3ef2482e3e22",  # Anatomy & Physiology
            "Anatomy and Physiology",
        ),
        "openstax-microbiology": (
            "e42bd376-624b-4c0f-972d-e4c01a30149d",  # Microbiology
            "Microbiology",
        ),
        "openstax-psychology": (
            "4abf04bf-93a0-45c3-9cbc-2cefd46e0cc8",  # Psychology 2e
            "Psychology 2e",
        ),
    }

    def __init__(self, collection_id: Optional[str] = None,
                 book_title: Optional[str] = None):
        super().__init__()
        if self.source_slug not in self.COLLECTIONS:
            raise RuntimeError(
                f"OpenStaxConnector source_slug '{self.source_slug}' "
                f"must be one of {list(self.COLLECTIONS)}"
            )
        default_id, default_title = self.COLLECTIONS[self.source_slug]
        self.collection_id = collection_id or default_id
        self.book_title = book_title or default_title

    def fetch(self, max_chapters: int = 50, **kwargs) -> Iterable[RawChunk]:
        import requests
        # Get the tree of the book
        try:
            r = requests.get(f"{self.CNX_API}{self.collection_id}.json",
                             timeout=30)
            r.raise_for_status()
            tree = r.json()
        except Exception as e:
            logger.warning(f"OpenStax tree fetch failed: {e}")
            return

        # Walk the tree, fetching each leaf
        leaves = []
        def walk(node):
            if isinstance(node, dict):
                if node.get("id") and node["id"] != self.collection_id:
                    leaves.append(node["id"])
                for child in node.get("children", []) or []:
                    walk(child)
            elif isinstance(node, list):
                for x in node:
                    walk(x)
        walk(tree.get("tree", {}))

        for i, leaf_id in enumerate(leaves[:max_chapters]):
            try:
                resp = requests.get(f"{self.CNX_API}{leaf_id}.json",
                                    timeout=30)
                resp.raise_for_status()
                doc = resp.json()
            except Exception as e:
                logger.debug(f"OpenStax leaf fetch failed: {e}")
                continue

            content = doc.get("content", "")
            if not content:
                continue
            # Strip HTML
            text = re.sub(r"<[^>]+>", " ", content)
            text = re.sub(r"\s+", " ", text).strip()

            title = doc.get("title", "OpenStax chapter")
            url = f"https://openstax.org/books/{self.book_title.lower().replace(' ', '-')}/pages/{leaf_id}"
            for chunk in self._make_chunks(
                raw_text=text,
                locator=f"chapter/{leaf_id[:12]}",
                source_url=url,
                subject=self._subject_for_source(),
                topic=title,
                title=f"{self.book_title} — {title}",
                quality_score=0.85,
            ):
                yield chunk
            logger.info(f"[{self.source_slug}] chapter {title[:50]}")

    def _subject_for_source(self) -> str:
        return {
            "openstax-anatomy": "anatomy",
            "openstax-microbiology": "microbiology",
            "openstax-psychology": "psychiatry",
        }.get(self.source_slug, "")


class OpenStaxMicrobiologyConnector(OpenStaxConnector):
    source_slug = "openstax-microbiology"


class OpenStaxPsychologyConnector(OpenStaxConnector):
    source_slug = "openstax-psychology"


class GovernmentGuidelinesConnector(ConnectorBase):
    """
    Generic connector for the Indian + WHO public-domain guideline PDFs
    we already keep in `Medura_Train/` (UPSC CMS notification, syllabus,
    form notices, growth & immunization notes, etc).

    These are Government of India / WHO public-domain documents.
    """

    source_slug = "mohfw-india"  # default; subclasses override

    def __init__(self, base_dir: Optional[str] = None,
                 max_size_mb: float = 50.0):
        super().__init__()
        from django.conf import settings as _s
        # Bulletproof path: explicit arg → MEDURA_TRAIN_DIR → BASE_DIR/Medura_Train.
        # Never pass None to Path() — that's a TypeError on fresh checkouts.
        chosen = (
            base_dir
            or str(getattr(_s, "MEDURA_TRAIN_DIR", None) or "")
        ) or str(_s.BASE_DIR / "Medura_Train")
        self.base_dir = Path(chosen)
        self.max_size_mb = max_size_mb

    def fetch(self, **kwargs) -> Iterable[RawChunk]:
        from ai_engine.document_processor import DocumentProcessor

        # Skip the giant textbook PDFs (220MB+ Ghai/Nelson)
        # — those are copyrighted and we will never ingest them.
        for path in sorted(self.base_dir.glob("*.pdf")):
            try:
                size_mb = path.stat().st_size / (1024 * 1024)
            except OSError:
                continue
            if size_mb > self.max_size_mb:
                logger.info(f"[{self.source_slug}] skipping {path.name} — {size_mb:.1f} MB")
                continue

            n = path.name.lower()
            # Only allow clearly public-domain / govt documents
            allowed_markers = ["upsc", "exam", "syllabus", "notice",
                               "form", "certificate", "proforma",
                               "allowance", "immunization", "growth"]
            if not any(m in n for m in allowed_markers):
                logger.info(f"[{self.source_slug}] skipping non-govt file {path.name}")
                continue

            processor = DocumentProcessor()
            try:
                pages = processor.extract_text(str(path))
            except Exception as e:
                logger.warning(f"Failed to extract {path}: {e}")
                continue
            full_text = "\n\n".join(p["text"] for p in pages if p.get("text"))
            full_text = self._normalize_text(full_text)
            full_text = self._guard_text(full_text)
            if not full_text:
                continue
            for chunk in self._make_chunks(
                raw_text=full_text,
                locator=path.name,
                source_url="",
                subject="psm",
                topic=path.stem.replace("_", " "),
                title=path.stem,
                quality_score=0.9,
            ):
                yield chunk
            logger.info(f"[{self.source_slug}] ingested {path.name}")


class UPSCConnector(GovernmentGuidelinesConnector):
    source_slug = "upsc"


class NHMConnector(GovernmentGuidelinesConnector):
    source_slug = "nhm-india"


class MoHFWConnector(GovernmentGuidelinesConnector):
    source_slug = "mohfw-india"


class ICMRConnector(GovernmentGuidelinesConnector):
    source_slug = "icmr"


class NMCConnector(GovernmentGuidelinesConnector):
    source_slug = "nmc-india"