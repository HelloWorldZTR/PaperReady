"""Deterministic academic metadata lookup helpers."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import httpx

from .models import PaperRecord


def lookup_doi(doi: str) -> PaperRecord | None:
    """Resolve DOI metadata from Crossref, returning None on failure."""
    try:
        response = httpx.get(f"https://api.crossref.org/works/{doi}", timeout=6.0)
        response.raise_for_status()
        item = response.json()["message"]
        return _crossref_item_to_paper(item, 0.9)
    except Exception:
        return None


def search_title(title: str) -> list[PaperRecord]:
    """Search Crossref by title and return plausible candidates."""
    try:
        response = httpx.get(
            "https://api.crossref.org/works",
            params={"query.title": title, "rows": 5},
            timeout=6.0,
        )
        response.raise_for_status()
        items = response.json()["message"].get("items", [])
        return [_crossref_item_to_paper(item, _score_to_confidence(item)) for item in items]
    except Exception:
        return []


def lookup_arxiv(arxiv_id: str) -> PaperRecord | None:
    """Resolve arXiv metadata from the public Atom API."""
    try:
        response = httpx.get(
            "https://export.arxiv.org/api/query",
            params={"id_list": arxiv_id},
            timeout=6.0,
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        entry = root.find("atom:entry", namespace)
        if entry is None:
            return None
        title = _text(entry, "atom:title", namespace)
        abstract = _text(entry, "atom:summary", namespace)
        authors = [
            _text(author, "atom:name", namespace)
            for author in entry.findall("atom:author", namespace)
        ]
        return PaperRecord(
            title=" ".join(title.split()),
            authors=[author for author in authors if author],
            arxiv_id=arxiv_id,
            urls=[f"https://arxiv.org/abs/{arxiv_id}"],
            abstract=" ".join(abstract.split()) if abstract else None,
            source_confidence=0.95,
            resolution_source="arxiv",
        )
    except Exception:
        return None


def _crossref_item_to_paper(item: dict[str, Any], confidence: float) -> PaperRecord:
    """Convert one Crossref work item into PaperRecord."""
    authors = [
        " ".join(part for part in [author.get("given"), author.get("family")] if part)
        for author in item.get("author", [])
    ]
    year_parts = item.get("published-print") or item.get("published-online") or {}
    date_parts = year_parts.get("date-parts") or [[]]
    title = (item.get("title") or ["Untitled paper"])[0]
    return PaperRecord(
        title=title,
        authors=[author for author in authors if author],
        year=(date_parts[0][0] if date_parts and date_parts[0] else None),
        venue=(item.get("container-title") or [None])[0],
        doi=item.get("DOI"),
        urls=[item.get("URL")] if item.get("URL") else [],
        abstract=item.get("abstract"),
        source_confidence=confidence,
        resolution_source="crossref",
    )


def _score_to_confidence(item: dict[str, Any]) -> float:
    """Convert Crossref score to a bounded confidence estimate."""
    score = float(item.get("score") or 0.0)
    return min(0.88, max(0.45, score / 100.0))


def _text(node, path: str, namespace: dict[str, str]) -> str:
    """Read text from one Atom element child."""
    found = node.find(path, namespace)
    return found.text.strip() if found is not None and found.text else ""
