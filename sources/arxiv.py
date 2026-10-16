from __future__ import annotations
import time
import urllib.parse

import feedparser
import httpx

from .base import SourceBase
from core.types import Paper


class ArxivSource(SourceBase):
    name = "arxiv"
    _endpoint = "http://export.arxiv.org/api/query"
    _headers = {"User-Agent": "lit-agent/1.0 (research demo; mailto:user@example.com)"}

    def search(self, query: str, limit: int = 5) -> list[Paper]:
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
        }
        resp = None
        for attempt in range(3):
            try:
                resp = httpx.get(self._endpoint, params=params,
                                 timeout=40, follow_redirects=True,
                                 verify=False,
                                 headers=self._headers)
                resp.raise_for_status()
                break
            except httpx.HTTPError as e:
                if resp is not None and resp.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                elif attempt < 2:
                    time.sleep(3)
                else:
                    print(f"[arxiv] error: {e}")
                    return []
        if resp is None:
            return []

        feed = feedparser.parse(resp.text)
        papers: list[Paper] = []
        for entry in feed.entries:
            arxiv_url = entry.get("id", "")
            arxiv_id = arxiv_url.rsplit("/", 1)[-1]
            authors = [a.get("name", "") for a in entry.get("authors", [])]
            year = None
            if "published" in entry:
                try:
                    year = int(entry["published"][:4])
                except (ValueError, TypeError):
                    pass
            papers.append(Paper(
                paper_id=f"arxiv:{arxiv_id}",
                title=entry.get("title", "").strip().replace("\n", " "),
                authors=authors,
                abstract=entry.get("summary", "").strip(),
                year=year,
                url=arxiv_url,
                source=self.name,
                doi=entry.get("arxiv_doi", ""),
                raw={"arxiv_id": arxiv_id},
            ))
        return papers
