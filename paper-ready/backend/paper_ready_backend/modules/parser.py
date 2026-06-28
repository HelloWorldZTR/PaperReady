"""PDF semantic parsing module."""

from __future__ import annotations

from ..models import PaperTask, ParsedPaper


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

