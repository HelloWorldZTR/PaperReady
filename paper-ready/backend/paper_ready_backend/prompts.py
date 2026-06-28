"""Prompt templates used by pipeline modules."""

LOCATOR_PROMPT = (
    "Resolve one paper input into metadata. Prefer arXiv when available. "
    "Return JSON with title, authors, year, venue, doi, arxiv_id, urls, "
    "abstract, source_confidence, and candidate_records."
)
EVALUATION_PROMPT = (
    "Judge reading value using research interests, metadata, parse quality, "
    "and semantic sections. Return JSON with value_recommendation, confidence, "
    "rationale, suggested_next_action, and suggested_report_type."
)
SUMMARY_PROMPT = (
    "Generate the requested report sections for one paper. Return JSON with a "
    "sections object keyed by report section name."
)
