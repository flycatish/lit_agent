from __future__ import annotations
from pydantic import BaseModel, Field

from core.types import ScoredPaper
from core.state import AgentState
from llm import LLMClient


class _Ranked(BaseModel):
    paper_id: str
    score: float = Field(ge=0, le=10)
    reason: str = ""


class RerankerOutput(BaseModel):
    ranked: list[_Ranked]


SYSTEM = """You are a literature relevance judge.
Given a research question and a list of candidate papers (title+abstract+year),
score each paper 0-10 by relevance to the question, recency, and authority.

Respond with ONLY valid JSON: {"ranked":[{"paper_id":...,"score":...,"reason":...}]}"""


def _format_candidates(state: AgentState) -> str:
    lines = []
    for p in state.papers:
        lines.append(
            f"[{p.paper_id}] ({p.year}) {p.title}\n"
            f"  {p.abstract[:300]}"
        )
    return "\n\n".join(lines)


def run(state: AgentState, llm: LLMClient, settings) -> RerankerOutput:
    if not state.papers:
        return RerankerOutput(ranked=[])

    out = llm.chat_json(
        SYSTEM,
        f"Question:\n{state.question}\n\n"
        f"Candidates:\n{_format_candidates(state)}\n\n"
        f"Score each paper 0-10.",
        RerankerOutput,
    )

    idx = state.paper_index()
    state.scored = []
    for r in out.ranked:
        p = idx.get(r.paper_id)
        if p:
            state.scored.append(ScoredPaper(paper=p, score=r.score, reason=r.reason))
    state.scored.sort(key=lambda x: x.score, reverse=True)
    state.scored = state.scored[: settings.final_top_k]
    return out
