from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class SubQuery:
    text: str
    sources: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class Paper:
    paper_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    year: int | None = None
    url: str = ""
    source: str = ""
    doi: str = ""
    raw: dict = field(default_factory=dict)

    def short(self, max_abs: int = 400) -> str:
        abs_ = self.abstract[:max_abs]
        if len(self.abstract) > max_abs:
            abs_ += "..."
        return f"[{self.year}] {self.title}\nAuthors: {', '.join(self.authors[:5])}\n{abs_}"


@dataclass
class ScoredPaper:
    paper: Paper
    score: float
    reason: str = ""


@dataclass
class ReadingNote:
    paper_id: str
    key_findings: list[str] = field(default_factory=list)
    method: str = ""
    limitations: str = ""
    citations: list[str] = field(default_factory=list)


@dataclass
class Reflection:
    evidence_sufficient: bool
    gaps: list[str] = field(default_factory=list)
    new_subqueries: list[SubQuery] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    summary: str = ""
