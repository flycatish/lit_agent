from __future__ import annotations
from core.state import AgentState
from llm import LLMClient


SYSTEM = """You are a research literature synthesizer.
Write a structured Markdown literature review based on the provided reading notes.

Structure (use Chinese headings as shown):
1. **综述概述** (Overview) — 1-2 paragraph summary
2. **核心发现** (Key Findings) — bullet list, each with [paper_id] citation
3. **方法对比表** (Comparison Table) — Markdown table comparing methods/approaches across papers
4. **冲突与空白** (Conflicts & Gaps) — note disagreements and uncovered aspects
5. **参考文献** (References) — numbered list: [n] paper_id, title, year, url

Rules:
- Every factual claim MUST cite a [paper_id].
- Do NOT fabricate findings not present in the notes.
- Write the review body in **Chinese (简体中文)**.
  Exception: keep paper_id, title, author names, and URLs in their original form.
- Keep it concise (300-600 words excluding references)."""


def _format_notes(state: AgentState) -> str:
    lines = []
    for n in state.notes:
        p = state.paper_index().get(n.paper_id)
        if p:
            lines.append(
                f"[{n.paper_id}] ({p.year}) {p.title}\n"
                f"  URL: {p.url}\n"
                f"  Findings: {'; '.join(n.key_findings)}\n"
                f"  Method: {n.method}\n"
                f"  Limitations: {n.limitations}\n"
                f"  Quotes: {' | '.join(n.citations)}"
            )
    return "\n\n".join(lines) or "(no notes)"


def _format_conflicts(state: AgentState) -> str:
    if not state.reflections:
        return "(none)"
    r = state.reflections[-1]
    parts = []
    if r.conflicts:
        parts.append("Conflicts:\n" + "\n".join(f"- {c}" for c in r.conflicts))
    if r.gaps:
        parts.append("Gaps:\n" + "\n".join(f"- {g}" for g in r.gaps))
    return "\n\n".join(parts) or "(none)"


def run(state: AgentState, llm: LLMClient, settings) -> str:
    md = llm.chat(
        SYSTEM,
        f"Research question:\n{state.question}\n\n"
        f"Reading notes:\n{_format_notes(state)}\n\n"
        f"Conflicts & gaps:\n{_format_conflicts(state)}\n\n"
        f"Write the literature review in Markdown.",
    )
    state.final_output = md
    return md
