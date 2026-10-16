from __future__ import annotations
import time
import xml.etree.ElementTree as ET

import httpx

from .base import SourceBase
from core.types import Paper

_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class PubMedSource(SourceBase):
    name = "pubmed"

    def search(self, query: str, limit: int = 5) -> list[Paper]:
        try:
            r = httpx.get(_ESEARCH, params={
                "db": "pubmed", "term": query,
                "retmax": limit, "retmode": "json",
            }, timeout=20, verify=False)
            r.raise_for_status()
            ids = r.json().get("esearchresult", {}).get("idlist", [])
        except (httpx.HTTPError, ValueError) as e:
            print(f"[pubmed] esearch error: {e}")
            return []

        if not ids:
            return []
        time.sleep(0.35)  # 3 req/s 限流

        try:
            r = httpx.get(_EFETCH, params={
                "db": "pubmed", "id": ",".join(ids),
                "rettype": "abstract", "retmode": "xml",
            }, timeout=30, verify=False)
            r.raise_for_status()
        except httpx.HTTPError as e:
            print(f"[pubmed] efetch error: {e}")
            return []

        return self._parse(r.text)

    def _parse(self, xml_text: str) -> list[Paper]:
        papers: list[Paper] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            print(f"[pubmed] xml parse error: {e}")
            return []

        for art in root.findall(".//PubmedArticle"):
            pmid_el = art.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""
            title_el = art.find(".//ArticleTitle")
            title = "".join(title_el.itertext()).strip() if title_el is not None else ""
            abs_parts = art.findall(".//Abstract/AbstractText")
            abstract = " ".join("".join(p.itertext()) for p in abs_parts).strip()
            authors = []
            for au in art.findall(".//Author")[:10]:
                ln = au.find("LastName")
                fn = au.find("ForeName")
                if ln is not None:
                    name = ln.text or ""
                    if fn is not None:
                        name = f"{ln.text} {fn.text[0]}"
                    authors.append(name)
            year = None
            yd = art.find(".//ArticleDate/Year")
            if yd is None:
                yd = art.find(".//Journal/JournalIssue/PubDate/Year")
            if yd is not None and yd.text:
                try:
                    year = int(yd.text)
                except ValueError:
                    pass
            doi_el = art.find(".//ArticleId[@IdType='doi']")
            doi = doi_el.text if doi_el is not None else ""
            papers.append(Paper(
                paper_id=f"pubmed:{pmid}",
                title=title,
                authors=authors,
                abstract=abstract,
                year=year,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                source=self.name,
                doi=doi,
                raw={"pmid": pmid},
            ))
        return papers
