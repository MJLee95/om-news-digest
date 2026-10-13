"""Collect candidate news items (RSS + Google News) and recent papers (Crossref)."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import requests

UA = {"User-Agent": "Mozilla/5.0 (om-news-digest; personal research newsletter)"}


@dataclass
class Candidate:
    kind: str  # "news" | "paper"
    title: str
    url: str
    source: str
    published: datetime | None
    snippet: str = ""
    extra: dict = field(default_factory=dict)


def clean_text(s: str, limit: int = 300) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def norm_title(title: str) -> str:
    # Google News appends " - Publisher"; drop it so the same story dedups across feeds.
    t = re.sub(r"\s+-\s+[^-]{2,60}$", "", title)
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def _entry_time(e) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = e.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def _fetch_feed(url: str):
    r = requests.get(url, timeout=20, headers=UA)
    r.raise_for_status()
    return feedparser.parse(r.content)


def fetch_rss(feeds: list[dict], since: datetime) -> list[Candidate]:
    out = []
    for f in feeds:
        try:
            parsed = _fetch_feed(f["url"])
        except Exception as ex:
            print(f"[warn] RSS failed: {f['name']}: {ex}")
            continue
        for e in parsed.entries:
            ts = _entry_time(e)
            if ts and ts < since:
                continue
            out.append(Candidate(
                kind="news",
                title=clean_text(e.get("title", ""), 200),
                url=e.get("link", ""),
                source=f["name"],
                published=ts,
                snippet=clean_text(e.get("summary", "")),
            ))
    return out


def fetch_google_news(queries: list[str], since: datetime, per_query: int = 15) -> list[Candidate]:
    out = []
    for q in queries:
        url = ("https://news.google.com/rss/search?q=" + quote_plus(f"{q} when:2d")
               + "&hl=en-US&gl=US&ceid=US:en")
        try:
            parsed = _fetch_feed(url)
        except Exception as ex:
            print(f"[warn] Google News failed: {q}: {ex}")
            continue
        for e in parsed.entries[:per_query]:
            ts = _entry_time(e)
            if ts and ts < since:
                continue
            publisher = (e.get("source") or {}).get("title", "Google News")
            title = clean_text(e.get("title", ""), 200)
            title = re.sub(r"\s+-\s+" + re.escape(publisher) + r"$", "", title)
            out.append(Candidate(
                kind="news",
                title=title,
                url=e.get("link", ""),
                source=publisher,
                published=ts,
                extra={"query": q},
            ))
    return out


def fetch_papers(journals: list[dict], days: int, mailto: str = "") -> list[Candidate]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    out = []
    for j in journals:
        params = {
            "filter": f"from-created-date:{since},type:journal-article",
            "rows": 40,
            "select": "title,DOI,created,abstract,URL",
        }
        if mailto:
            params["mailto"] = mailto
        try:
            r = requests.get(f"https://api.crossref.org/journals/{j['issn']}/works",
                             params=params, headers=UA, timeout=30)
            r.raise_for_status()
            items = r.json()["message"]["items"]
        except Exception as ex:
            print(f"[warn] Crossref failed: {j['name']}: {ex}")
            continue
        for it in items:
            title = clean_text((it.get("title") or [""])[0], 250)
            if not title or re.search(r"\b(retraction|erratum|corrigendum)\b", title, re.I):
                continue
            created = it.get("created", {}).get("date-time")
            out.append(Candidate(
                kind="paper",
                title=title,
                url=it.get("URL") or f"https://doi.org/{it['DOI']}",
                source=j["name"],
                published=datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None,
                snippet=clean_text(it.get("abstract", ""), 600),
            ))
    return out


def dedupe(cands: list[Candidate], seen_titles: set[str], seen_urls: set[str]) -> list[Candidate]:
    out, titles = [], set()
    # Prefer specialist RSS entries (direct links + snippets) over Google News duplicates.
    for c in sorted(cands, key=lambda c: "query" in c.extra):
        key = norm_title(c.title)
        if not key or key in titles or key in seen_titles or c.url in seen_urls:
            continue
        titles.add(key)
        out.append(c)
    return out


def _abstract(inv: dict | None, limit: int = 450) -> str:
    if not inv:
        return ""
    words = sorted((pos, w) for w, positions in inv.items() for pos in positions)
    return clean_text(" ".join(w for _, w in words), limit)


def search_related(queries: list[str], issns: list[str], per_query: int = 6, mailto: str = "") -> list[dict]:
    """Search OpenAlex for papers in the given journals matching each query (deduped by DOI)."""
    out, dois = [], set()
    for q in queries:
        params = {
            "search": q,
            "filter": f"primary_location.source.issn:{'|'.join(issns)},publication_year:>2004,type:article",
            "per_page": per_query,
            "select": "title,doi,publication_year,primary_location,abstract_inverted_index,cited_by_count",
        }
        if mailto:
            params["mailto"] = mailto
        try:
            r = requests.get("https://api.openalex.org/works", params=params, headers=UA, timeout=30)
            r.raise_for_status()
            results = r.json()["results"]
        except Exception as ex:
            print(f"[warn] OpenAlex failed: {q}: {ex}")
            continue
        for w in results:
            doi = w.get("doi")
            if not doi or doi in dois or not w.get("title"):
                continue
            dois.add(doi)
            out.append({
                "title": clean_text(w["title"], 250),
                "journal": ((w.get("primary_location") or {}).get("source") or {}).get("display_name", ""),
                "year": w.get("publication_year"),
                "url": doi,
                "cites": w.get("cited_by_count", 0),
                "abstract": _abstract(w.get("abstract_inverted_index")),
            })
    return out
