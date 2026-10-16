from __future__ import annotations
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from config import settings as _settings
from llm import LLMClient
from sources import SourceBase
from .state import AgentState
from .types import Reflection
from stages import planner, reranker, reader, reflector, synthesizer

StepCallback = Callable[[dict], None]


class LiteratureAgent:
    """6 阶段编排：planner → retrieve → rerank → read → reflect → synthesize."""

    def __init__(
        self,
        llm: LLMClient | None = None,
        sources: list[SourceBase] | None = None,
        settings=None,
    ):
        self.settings = settings or _settings
        self.llm = llm or LLMClient()
        self.sources = sources or _default_sources()

    def run(self, question: str, on_step: StepCallback | None = None) -> AgentState:
        state = AgentState(question=question)
        ts = lambda: time.time()

        def emit(stage: str, data: dict, status: str = "ok"):
            if on_step:
                on_step({"stage": stage, "data": data, "status": status,
                         "ts": ts()})

        # 1. Planner
        emit("planner", {"question": question}, "start")
        plan = planner.run(state, self.llm, self.settings)
        emit("planner", {
            "subqueries": [{"text": s.text, "sources": s.sources}
                           for s in state.subqueries],
        })

        # 2. Retrieve + Rerank + Read + Reflect loop
        while state.round < self.settings.max_reflect_rounds:
            emit("retrieve", {"round": state.round + 1}, "start")
            new_papers = self._retrieve(state.subqueries)
            state.papers.extend(new_papers)
            state.dedup_papers()
            emit("retrieve", {
                "round": state.round + 1,
                "new": len(new_papers),
                "total": len(state.papers),
            })

            if not state.papers:
                emit("reflector", {"round": state.round + 1,
                                   "sufficient": False, "gaps": ["No papers retrieved"],
                                   "conflicts": [], "summary": "No results from sources"})
                refl = Reflection(evidence_sufficient=False,
                                  gaps=["No papers retrieved"], summary="No results")
                state.reflections.append(refl)
                if state.round + 1 >= self.settings.max_reflect_rounds:
                    break
                state.round += 1
                continue

            emit("reranker", {"candidates": len(state.papers)}, "start")
            reranker.run(state, self.llm, self.settings)
            emit("reranker", {
                "top": [{"id": sp.paper.paper_id, "score": sp.score,
                         "title": sp.paper.title}
                        for sp in state.scored],
            })

            emit("reader", {"papers": len(state.scored)}, "start")
            reader.run(state, self.llm, self.settings)
            emit("reader", {"notes": len(state.notes)})

            emit("reflector", {"round": state.round + 1}, "start")
            refl = reflector.run(state, self.llm, self.settings)
            emit("reflector", {
                "sufficient": refl.evidence_sufficient,
                "gaps": refl.gaps,
                "conflicts": refl.conflicts,
                "summary": refl.summary,
            })

            if refl.evidence_sufficient or state.round + 1 >= self.settings.max_reflect_rounds:
                break
            state.subqueries = refl.new_subqueries or state.subqueries
            state.round += 1

        # 3. Synthesizer
        emit("synthesizer", {}, "start")
        synthesizer.run(state, self.llm, self.settings)
        emit("synthesizer", {"length": len(state.final_output)})

        return state

    def _retrieve(self, subqueries) -> list:
        from collections import defaultdict
        groups: dict[str, list[tuple[SourceBase, str]]] = defaultdict(list)
        for sq in subqueries:
            for src in self.sources:
                if src.name in sq.sources and src.is_available():
                    groups[src.name].append((src, sq.text))

        def run_group(name_tasks):
            name, tasks = name_tasks
            results = []
            for src, q in tasks:
                try:
                    results.extend(src.search(q, self.settings.top_k_per_source))
                except Exception as e:
                    print(f"[retrieve] {src.name} '{q[:40]}' failed: {e}")
            return results

        all_results = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            for grp in pool.map(run_group, groups.items()):
                all_results.extend(grp)
        return all_results


def _default_sources() -> list[SourceBase]:
    from sources import (ArxivSource, PubMedSource, SemanticScholarSource)
    return [ArxivSource(), PubMedSource(), SemanticScholarSource()]
