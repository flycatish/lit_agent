from __future__ import annotations
import time

import httpx

from .base import SourceBase
from core.types import Paper

_ENDPOINT = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,authors,abstract,year,externalIds,url"


class SemanticScholarSource(SourceBase):
    name = "s2"

    def search(self, query: str, limit: int = 5) -> list[Paper]:
        time.sleep(1.0)  # 无 key 限流 ~1 req/s
        data = None
        r = None
        for attempt in range(3):
            try:
                r = httpx.get(_ENDPOINT, params={
                    "query": query, "limit": limit, "fields": _FIELDS,
                }, timeout=20, verify=False)
                r.raise_for_status()
                data = r.json()
                break
            except (httpx.HTTPError, ValueError) as e:
                if r is not None and r.status_code == 429 and attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
                print(f"[s2] error: {e}")
                return []
        if data is None:
            return []

        papers: list[Paper] = []
        for item in data.get("data", []):
            pid = item.get("paperId", "")
            ext = item.get("externalIds", {}) or {}
            doi = ext.get("DOI", "")
            authors = [a.get("name", "") for a in item.get("authors", [])]
            papers.append(Paper(
                paper_id=f"s2:{pid}",
                title=item.get("title", "").strip(),
                authors=authors,
                abstract=item.get("abstract", "") or "",
                year=item.get("year"),
                url=item.get("url", "") or f"https://www.semanticscholar.org/paper/{pid}",
                source=self.name,
                doi=doi,
                raw={"s2_id": pid},
            ))
        return papers
