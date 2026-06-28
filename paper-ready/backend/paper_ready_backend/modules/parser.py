"""PDF semantic parsing module."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from ..models import PaperTask, ParsedPaper

SECTION_ALIASES = {
    "abstract": ("abstract",),
    "introduction": ("introduction", "background"),
    "method": ("method", "methods", "approach", "methodology"),
    "experiments": ("experiment", "experiments", "evaluation", "results"),
    "conclusion": ("conclusion", "conclusions", "discussion"),
    "references": ("references", "bibliography"),
}


def parse_pdf(task: PaperTask) -> PaperTask:
    """Create a semantic parsed-paper representation for downstream steps."""
    if not task.paper:
        return task
    task.status = "Parsing"
    task.parser_status = "Parsing"
    if not task.pdf or task.pdf.status != "PDF ready":
        task.parsed = ParsedPaper(paper_id=task.paper.paper_id)
        task.parser_status = "Metadata only"
        task.next_action = "Evaluate paper"
        return task

    extracted_text = _extract_pdf_text(task.pdf.local_path)
    if extracted_text:
        sections = parse_text_sections(extracted_text)
        task.parsed = ParsedPaper(
            paper_id=task.paper.paper_id,
            sections={"abstract": task.paper.abstract or "", **sections},
            references=_split_references(sections.get("references", "")),
            parse_quality="text_sections" if sections else "raw_text",
        )
        task.status = "Evaluating"
        task.parser_status = "Parsed"
        task.next_action = "Evaluate paper"
        return task

    title = task.paper.title
    task.parsed = ParsedPaper(
        paper_id=task.paper.paper_id,
        sections={
            "abstract": task.paper.abstract or "",
            "introduction": f"Placeholder introduction for {title}.",
            "method": "Demo parser has not extracted method details yet.",
            "experiments": "Demo parser has not extracted experiments yet.",
            "conclusion": "Demo parser has not extracted conclusion yet.",
        },
        parse_quality="demo_sections",
    )
    task.status = "Evaluating"
    task.parser_status = "Parsed"
    task.next_action = "Evaluate paper"
    return task


def parse_text_sections(text: str) -> dict[str, str]:
    """Extract coarse semantic sections from plain PDF text."""
    normalized = re.sub(r"\n{2,}", "\n", text)
    heading_pattern = re.compile(
        r"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?"
        r"(abstract|introduction|background|method|methods|approach|"
        r"methodology|experiment|experiments|evaluation|results|discussion|"
        r"conclusion|conclusions|references|bibliography)\s*$"
    )
    matches = list(heading_pattern.finditer(normalized))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        heading = match.group(1).lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        key = _canonical_section(heading)
        content = normalized[start:end].strip()
        if key and content:
            sections[key] = content[:8000]
    return sections


def _canonical_section(heading: str) -> str | None:
    """Map a raw heading to the parser's canonical section names."""
    for canonical, aliases in SECTION_ALIASES.items():
        if heading in aliases:
            return canonical
    return None


def _extract_pdf_text(local_path: str | None) -> str:
    """Extract text from a local PDF path, returning empty text on failure."""
    if not local_path or not Path(local_path).exists():
        return ""
    try:
        reader = PdfReader(local_path)
        pages = [page.extract_text() or "" for page in reader.pages[:40]]
        return "\n".join(pages).strip()
    except Exception:
        return ""


def _split_references(text: str) -> list[str]:
    """Split a references section into compact reference strings."""
    if not text:
        return []
    chunks = re.split(r"\n\s*(?:\[\d+\]|\d+\.)\s*", text)
    return [chunk.strip()[:1000] for chunk in chunks if chunk.strip()][:80]
