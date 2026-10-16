from __future__ import annotations
from pydantic import BaseModel, Field

from core.types import ReadingNote
from core.state import AgentState
from llm import LLMClient


class _NoteSchema(BaseModel):
    paper_id: str
    key_findings: list[str] = Field(default_factory=list)
    method: str = ""
    limitations: str = ""
    citations: list[str] = Field(default_factory=list)


class ReaderOutput(BaseModel):
    notes: list[_NoteSchema]


SYSTEM = """You are a research paper reader.
For each paper, extract key findings, method, limitations, and 1-3 direct
verbatim quotes from the abstract that support the findings.

Rules:
- `citations` MUST be verbatim substrings of the abstract (<= 200 chars each).
- If the abstract is empty, note "No abstract available".
- Respond with ONLY valid JSON: {"notes":[{"paper_id":...,"key_findings":[...],
  "method":...,"limitations":...,"citations":[...]}]}"""

_BATCH = 5


def _format_batch(papers: list) -> str:
    lines = []
    for p in papers:
        lines.append(
            f"[{p.paper_id}] {p.title}\n"
            f"Abstract: {p.abstract[:600]}"
        )
    return "\n\n".join(lines)


def run(state: AgentState, llm: LLMClient, settings) -> ReaderOutput:
    top_papers = [sp.paper for sp in state.scored] or state.papers
    all_notes: list[ReadingNote] = []

    for i in range(0, len(top_papers), _BATCH):
        batch = top_papers[i : i + _BATCH]
        out = llm.chat_json(
            SYSTEM,
            f"Extract notes for these papers:\n\n{_format_batch(batch)}",
            ReaderOutput,
        )
        for n in out.notes:
            all_notes.append(ReadingNote(
                paper_id=n.paper_id,
                key_findings=n.key_findings,
                method=n.method,
                limitations=n.limitations,
                citations=n.citations,
            ))
    state.notes = all_notes
    return ReaderOutput(notes=[])
