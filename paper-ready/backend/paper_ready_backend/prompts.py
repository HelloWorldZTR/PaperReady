"""Prompt templates used by pipeline modules."""

from __future__ import annotations

import json
from typing import Any

LOCATOR_PROMPT = (
    "Resolve one paper input into metadata using web search. Search the web for "
    "the exact paper identity, prioritizing arXiv. If any credible arXiv page "
    "matches the input, treat the paper as successfully matched and return its "
    "arxiv_id. Return only JSON with title, authors, year, venue, doi, arxiv_id, "
    "urls, abstract, source_confidence, match_status, rationale, and "
    "candidate_records. Use match_status='matched' only when you found a "
    "specific paper; use 'ambiguous' with candidate_records when multiple "
    "papers plausibly match; use 'not_found' when web search cannot identify "
    "the paper. Do not invent metadata."
)
EVALUATION_PROMPT = """
You are PaperReady's research-paper triage evaluator.

Evaluate whether this paper is worth reading for the user. Base the decision on
three dimensions:

1. Paper value: novelty, technical depth, clarity of contribution, empirical or
   theoretical evidence, reproducibility signals, and usefulness to future work.
2. Publisher importance: author or lab reputation when available, venue quality,
   release source credibility, citation-worthy positioning, and whether the work
   is likely to influence the field. Do not invent missing affiliations, venues,
   or reputation facts.
3. Relevance to our research: compare the paper against the supplied research
   interests, tags, and prior evaluation context. The research direction may be
   empty. If it is empty, do not penalize the paper for weak relevance; instead
   judge intrinsic value and say that user-specific relevance is unknown.

Rendered input variables:
- Title: {{title}}
- Authors: {{authors}}
- Venue: {{venue}}
- Year: {{year}}
- DOI: {{doi}}
- arXiv ID: {{arxiv_id}}
- Abstract: {{abstract}}
- Parsed PDF text: {{pdf_text}}
- Parsed sections: {{sections}}
- References: {{references}}
- User research context: {{user_research_context}}
- Existing value recommendation: {{value_recommendation}}

Use the parsed sections when available. If only metadata is available, be
conservative about confidence and explain the uncertainty.

Return only a JSON object with these keys:
- value_recommendation: one of "Very Important", "Brief Reading",
  "Unrelated", or "Needs Review".
- confidence: a number from 0 to 1.
- rationale: a concise but evidence-grounded explanation covering paper value,
  publisher importance, and research relevance.
- suggested_next_action: a practical next step, such as "Generate report",
  "Skim abstract and conclusion", or "Review manually".
- suggested_report_type: "Detailed Report", "Standard Report", "Quick Brief",
  or null.

Recommendation policy:
- Use "Very Important" when the paper is high-value and either strongly related
  to the user's research or important enough to inspect despite unknown/weak
  relevance. Prefer "Detailed Report" or "Standard Report".
- Use "Brief Reading" for moderately useful, adjacent, or uncertain papers that
  deserve a short pass. Prefer "Quick Brief".
- Use "Unrelated" only when the paper is clearly outside the user's interests
  and lacks enough standalone importance to justify reading.
- Use "Needs Review" when metadata is ambiguous, parse quality is too low, or
  the decision depends on missing facts.
""".strip()
SUMMARY_PROMPT = """
You are PaperReady's academic report writer.

Write a high-quality, evidence-grounded academic reading report for one paper.
Use the requested report type and requested section keys exactly. Return only a
JSON object with one top-level key, "sections", whose value is an object keyed by
the requested section names.

General requirements:
- Be specific to the paper. Do not write generic filler.
- Ground claims in the provided title, abstract, parsed sections, references,
  and evaluation notes. Mark uncertainty when the source text is incomplete.
- Prioritize technical substance: problem framing, contribution, method,
  evidence, assumptions, limitations, and how the paper can inform our work.
- If research interests are empty, write a field-level report and state that
  user-specific relevance cannot be determined.
- Keep prose concise, scholarly, and usable as a Zotero note.

Rendered input variables:
- Title: {{title}}
- Authors: {{authors}}
- Venue: {{venue}}
- Year: {{year}}
- DOI: {{doi}}
- arXiv ID: {{arxiv_id}}
- Abstract: {{abstract}}
- Parsed PDF text: {{pdf_text}}
- Parsed sections: {{sections}}
- References: {{references}}
- User research context: {{user_research_context}}
- Value recommendation: {{value_recommendation}}

Section requirements:
- summary: 1-2 paragraphs covering the paper's question, core idea, result, and
  why it matters.
- main_contribution: identify the central contribution and separate it from
  engineering details or incremental variants.
- relevance: connect the work to the user's research interests when provided;
  otherwise discuss likely audience and field relevance.
- problem: describe the research problem, why existing approaches are
  insufficient, and what success means.
- method: explain the technical approach, assumptions, inputs/outputs, model or
  algorithm design, and key implementation choices.
- evidence: summarize experiments, datasets, baselines, metrics, ablations, and
  whether the evidence supports the claims.
- section_summary: summarize major parsed sections in order, preserving the
  paper's argument structure.
- experiments: detail experimental setup, evaluation protocol, results,
  comparisons, and threats to validity.
- limitations: list concrete limitations, missing evidence, failure modes,
  scalability concerns, and reproducibility risks.

For unknown custom section names, infer the expected content from the section
name and keep the answer evidence-grounded.
""".strip()

DEFAULT_PROMPT_TEMPLATES = {
    "Locator prompt": LOCATOR_PROMPT,
    "Evaluator prompt": EVALUATION_PROMPT,
    "Quick Brief prompt": SUMMARY_PROMPT,
    "Standard Report prompt": SUMMARY_PROMPT,
    "Detailed Report prompt": SUMMARY_PROMPT,
    "Zotero note prompt": (
        "Convert generated report sections for {{title}} into a concise Zotero "
        "note. Preserve section headings, keep claims tied to the paper, include "
        "the reading recommendation {{value_recommendation}} when useful, and "
        "omit empty fields. Research context: {{user_research_context}}."
    ),
}


def prompt_template(settings, key: str, fallback: str) -> str:
    """Return the saved prompt template for a key or the provided default."""
    configured = (settings.prompt_templates or {}).get(key)
    return configured.strip() if configured and configured.strip() else fallback


def render_prompt(template: str, variables: dict[str, Any]) -> str:
    """Replace supported {{variable}} tokens in an editable prompt template."""
    rendered = template
    for key, value in variables.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", _prompt_value(value))
    return rendered


def report_prompt_key(report_type: str) -> str:
    """Return the settings key used for a report-type prompt."""
    return f"{report_type} prompt"


def _prompt_value(value: Any) -> str:
    """Serialize prompt variables predictably for model input."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=True, indent=2)
