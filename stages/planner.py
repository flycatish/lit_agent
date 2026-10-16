from __future__ import annotations
from pydantic import BaseModel, Field

from core.types import SubQuery
from core.state import AgentState
from llm import LLMClient


class _SubQuerySchema(BaseModel):
    text: str
    sources: list[str] = Field(default_factory=lambda: ["arxiv", "pubmed", "s2"])
    rationale: str = ""


class PlannerOutput(BaseModel):
    subqueries: list[_SubQuerySchema]


SYSTEM = """You are a research question decomposer.
Given a research question, break it into 3-6 concrete sub-queries suitable
for academic database search (arXiv / PubMed / Semantic Scholar).

Rules:
- Each sub-query should be a concise English search phrase (not a full sentence).
- Cover different aspects: methods, datasets, theory, applications, recent advances.
- Assign `sources` from: ["arxiv","pubmed","s2"]. Choose by relevance
  (e.g. biomedical → pubmed+s2; CS → arxiv+s2).
- Respond with ONLY valid JSON: {"subqueries":[{"text":...,"sources":[...]," rationale":...}]}"""


def run(state: AgentState, llm: LLMClient, settings) -> PlannerOutput:
    out = llm.chat_json(
        SYSTEM,
        f"Research question:\n{state.question}\n\n"
        f"Decompose into 3-6 sub-queries.",
        PlannerOutput,
    )
    state.subqueries = [
        SubQuery(text=s.text, sources=s.sources, rationale=s.rationale)
        for s in out.subqueries
    ]
    return out
