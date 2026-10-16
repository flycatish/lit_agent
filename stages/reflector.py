from __future__ import annotations
from pydantic import BaseModel, Field, field_validator

from core.types import Reflection, SubQuery
from core.state import AgentState
from llm import LLMClient


class _SubQ(BaseModel):
    text: str
    sources: list[str] = Field(default_factory=lambda: ["arxiv", "pubmed", "s2"])
    rationale: str = ""


class ReflectorOutput(BaseModel):
    evidence_sufficient: bool
    gaps: list[str] = Field(default_factory=list)
    new_subqueries: list[_SubQ] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    summary: str = ""

    @field_validator("new_subqueries", mode="before")
    @classmethod
    def _coerce(cls, v):
        if isinstance(v, list):
            out = []
            for item in v:
                if isinstance(item, str):
                    out.append({"text": item})
                elif isinstance(item, dict):
                    out.append(item)
            return out
        return v


SYSTEM = """You are a research evidence assessor.
Given the research question and reading notes from retrieved papers, assess:
1. Is the evidence sufficient to write a comprehensive review?
2. What gaps remain (aspects not covered)?
3. Are there conflicts between papers?
4. If insufficient, propose 1-3 new sub-queries to fill gaps.

Respond with ONLY valid JSON:
{"evidence_sufficient":bool,"gaps":[...],"new_subqueries":[...],
 "conflicts":[...],"summary":"..."}"""


def _format_notes(state: AgentState) -> str:
    lines = []
    for n in state.notes:
        p = state.paper_index().get(n.paper_id)
        title = p.title if p else n.paper_id
        lines.append(
            f"[{n.paper_id}] {title}\n"
            f"  Findings: {'; '.join(n.key_findings)}"
        )
    return "\n\n".join(lines) or "(no notes yet)"


def run(state: AgentState, llm: LLMClient, settings) -> ReflectorOutput:
    out = llm.chat_json(
        SYSTEM,
        f"Question:\n{state.question}\n\n"
        f"Round: {state.round + 1}/{settings.max_reflect_rounds}\n\n"
        f"Notes:\n{_format_notes(state)}\n\n"
        f"Assess evidence sufficiency.",
        ReflectorOutput,
    )
    refl = Reflection(
        evidence_sufficient=out.evidence_sufficient,
        gaps=out.gaps,
        new_subqueries=[SubQuery(text=s.text, sources=s.sources, rationale=s.rationale)
                        for s in out.new_subqueries],
        conflicts=out.conflicts,
        summary=out.summary,
    )
    state.reflections.append(refl)
    return out
