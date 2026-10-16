from __future__ import annotations
from dataclasses import dataclass, field

from .types import SubQuery, Paper, ScoredPaper, ReadingNote, Reflection


@dataclass
class AgentState:
    question: str
    subqueries: list[SubQuery] = field(default_factory=list)
    papers: list[Paper] = field(default_factory=list)
    scored: list[ScoredPaper] = field(default_factory=list)
    notes: list[ReadingNote] = field(default_factory=list)
    reflections: list[Reflection] = field(default_factory=list)
    final_output: str = ""
    round: int = 0

    def dedup_papers(self) -> None:
        seen: dict[str, Paper] = {}
        for p in self.papers:
            key = (p.doi or p.title.lower().strip())[:200]
            if key and key not in seen:
                seen[key] = p
            elif key in seen and not seen[key].abstract and p.abstract:
                seen[key] = p
        self.papers = list(seen.values())

    def paper_index(self) -> dict[str, Paper]:
        return {p.paper_id: p for p in self.papers}
