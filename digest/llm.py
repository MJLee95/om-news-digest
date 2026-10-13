"""Three Claude calls: pick stories -> research them on the web -> write the digest."""

from __future__ import annotations

import anthropic
from pydantic import BaseModel, Field

from .sources import Candidate

FALLBACK = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}


# ---------- schemas ----------

class Pick(BaseModel):
    id: int = Field(description="Candidate id from the list")
    theme: str = Field(description="Exactly one theme from the allowed theme list")
    why: str = Field(description="One sentence on why this matters for OM research")
    lit_queries: list[str] = Field(description="2 short academic search queries (3-6 words each) for finding OM papers related to this story")
    follows: list[str] = Field(description="Ids (e.g. '2026-10-13#2') of earlier archive items about the same ongoing story that this is a new development of; empty if none")


class AlsoPick(BaseModel):
    id: int = Field(description="Candidate id from the news list")
    theme: str = Field(description="Exactly one theme from the allowed theme list")


class Selection(BaseModel):
    news: list[Pick]
    also: list[AlsoPick] = Field(description="Runner-up news worth a headline-only mention")
    papers: list[Pick]


class RelatedPaper(BaseModel):
    paper_id: str = Field(description="Id of a related-paper candidate, e.g. 'R3'")
    why: str = Field(description="One sentence: what the paper does and how it relates to this story")


class NewsItem(BaseModel):
    candidate_id: int
    headline: str = Field(description="Clear, factual headline (rewrite clickbait)")
    theme: str
    original_url: str = Field(description="Publisher URL found during research, copied exactly from the notes; empty string if none")
    summary: str = Field(description="2-3 sentences: what happened, with key numbers, dates, firms")
    om_angle: str = Field(description="1-2 sentences: why an operations researcher should care")
    research_question: str = Field(description="One concrete, researchable question")
    data_identification: str = Field(description="Possible data sources and identification idea (treatment/control, shock timing, unit of analysis)")
    keywords: list[str] = Field(description="3-5 lowercase literature keywords, more specific than the theme")
    datasets: list[str] = Field(description="1-4 short canonical names of datasets mentioned in data_identification, e.g. 'PJM capacity auction results', 'Panjiva bill-of-lading data', 'CDP climate responses'")
    related: list[RelatedPaper] = Field(description="1-2 genuinely related papers from the candidates for this story; empty if none fit")


class PaperItem(BaseModel):
    candidate_id: int
    takeaway: str = Field(description="1-2 sentences: the paper's question and main finding, in plain English")
    connection: str = Field(description="One sentence linking it to today's news or the reader's interests")


class Digest(BaseModel):
    intro: str = Field(description="1-2 sentence overview of today's issue")
    items: list[NewsItem]
    papers: list[PaperItem]
    thread_to_pull: str = Field(description="2-3 sentences proposing one research idea that connects two or more of today's items (or items with the papers)")


# ---------- helpers ----------

def _fmt_candidates(cands: list[Candidate]) -> str:
    lines = []
    for i, c in enumerate(cands):
        date = c.published.strftime("%Y-%m-%d") if c.published else "n/a"
        line = f"[{i}] ({c.source}, {date}) {c.title}"
        if c.snippet:
            line += f" — {c.snippet}"
        lines.append(line)
    return "\n".join(lines)


class Curator:
    def __init__(self, cfg: dict, profile: str):
        self.client = anthropic.Anthropic()
        self.model = cfg["model"]
        self.effort = cfg.get("effort", "medium")
        self.cfg = cfg
        self.profile = profile.strip()
        self.tokens = {"input": 0, "output": 0, "searches": 0}

    def _track(self, resp):
        u = resp.usage
        self.tokens["input"] += (u.input_tokens or 0) + (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0)
        self.tokens["output"] += u.output_tokens or 0
        if u.server_tool_use:
            self.tokens["searches"] += u.server_tool_use.web_search_requests or 0

    def cost_report(self) -> str:
        t = self.tokens
        usd = t["input"] * 4 / 1e6 + t["output"] * 20 / 1e6 + t["searches"] * 0.01
        return f"Usage: {t['input']:,} in / {t['output']:,} out tokens, {t['searches']} searches ≈ ${usd:.2f} (Opus 5.5 list price)"

    def _parse(self, prompt: str, schema, effort: str | None = None):
        resp = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            output_config={"effort": effort or self.effort},
            system=f"You curate a daily research newsletter.\n\n{self.profile}",
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
            **FALLBACK,
        )
        self._track(resp)
        if resp.stop_reason == "refusal" or resp.parsed_output is None:
            raise RuntimeError(f"No structured output (stop_reason={resp.stop_reason}, request_id={resp._request_id})")
        return resp.parsed_output

    # Step 1: choose stories from headlines/snippets
    def select(self, news: list[Candidate], papers: list[Candidate], n_news: int, n_papers: int,
               themes: list[str], n_also: int = 5, recent: list[dict] = (), starred: list[dict] = ()) -> Selection:
        prompt = f"""Below are today's candidate news items. Choose exactly {n_news} for the newsletter.

Allowed themes (use these exact labels): {"; ".join(themes)}

Rules:
- Diversify across themes; at most 2 per theme.
- Never pick two items about the same underlying event.
- Prefer concrete events with a research hook over generic commentary or marketing.
- Skip law-firm/consultancy client briefings, evergreen explainers, and anything that looks like old news resurfacing.

Also choose up to {n_also} runner-up stories for an "Also worth noting" list (headline + link only).
They must cover different events from the main picks and from each other; favor themes the main picks don't cover.

NEWS CANDIDATES:
{_fmt_candidates(news)}
"""
        if recent:
            prompt += ("\nRECENTLY COVERED (id: headline). Don't pick stories that merely repeat these. A genuinely new "
                       "development of one of these stories is welcome: pick it and list the earlier ids in 'follows'.\n"
                       + "\n".join(f"{r['id']}: {r['headline']}" for r in recent) + "\n")
        if starred:
            prompt += ("\nSTARRED BY THE READER (stories they found most useful; lean toward similar topics and kinds of "
                       "research hooks, without narrowing the mix too much):\n"
                       + "\n".join(f"- [{s['theme']}] {s['headline']}" + (f" (note: {s['note']})" if s.get('note') else "")
                                    for s in starred) + "\n")
        if n_papers and papers:
            prompt += f"""
Also choose up to {n_papers} recent journal papers most relevant to the reader's interests
(return an empty list if none are relevant). Paper ids refer to this separate list:

PAPER CANDIDATES:
{_fmt_candidates(papers)}
"""
        else:
            prompt += "\nReturn an empty list for papers.\n"
        sel = self._parse(prompt, Selection)
        sel.news = [p for p in sel.news if 0 <= p.id < len(news)][:n_news]
        recent_ids = {r["id"] for r in recent}
        for p in sel.news:
            p.follows = [f for f in p.follows if f in recent_ids]
        main_ids = {p.id for p in sel.news}
        sel.also = [a for a in sel.also if 0 <= a.id < len(news) and a.id not in main_ids][:n_also]
        sel.papers = [p for p in sel.papers if 0 <= p.id < len(papers)][:n_papers]
        return sel

    # Step 2: verify facts and find the original reporting on the web
    def research(self, picks: list[tuple[int, Candidate, Pick]]) -> str:
        stories = "\n\n".join(
            f"[{cid}] {c.title}\nSource: {c.source}\nLink: {c.url}\nSnippet: {c.snippet or '(none)'}"
            for cid, c, _ in picks
        )
        user = f"""Research each story below so a newsletter can be written about it accurately.
For each one, use web search (and web fetch when a page is readable) to find the original
publisher article and the key facts: what happened, who, when, numbers, and what is still uncertain.
Some links are Google News redirects; search for the headline to find the real article.

Then write research notes, one section per story, headed with its [id]. In each section include
the best original article URL you actually visited or saw in search results (write 'URL: <url>'),
and only facts supported by sources. If something can't be verified, say so.

STORIES:
{stories}"""
        tools = [
            {"type": "web_search_20260209", "name": "web_search", "max_uses": self.cfg.get("web_search_max_uses", 8)},
            {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": self.cfg.get("web_fetch_max_uses", 6),
             "max_content_tokens": self.cfg.get("web_fetch_max_content_tokens", 5000)},
        ]
        messages = [{"role": "user", "content": user}]
        for _ in range(6):  # cap pause_turn continuations
            resp = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                output_config={"effort": self.effort},
                tools=tools,
                messages=messages,
                **FALLBACK,
            )
            self._track(resp)
            if resp.stop_reason != "pause_turn":
                break
            messages = [{"role": "user", "content": user}, {"role": "assistant", "content": resp.content}]
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"Research step refused (request_id={resp._request_id})")
        return "\n".join(b.text for b in resp.content if b.type == "text")

    # Step 3: write the structured digest
    def compose(self, picks, paper_picks, notes: str, known_keywords: list[str] = (),
                related: dict[int, list[tuple[str, dict]]] | None = None, themes: list[str] = (),
                known_datasets: list[str] = ()) -> Digest:
        stories = "\n".join(f"[{cid}] {c.title} ({c.source}) — selection note: {p.why} — theme: {p.theme}"
                            for cid, c, p in picks)
        papers = "\n".join(f"[{cid}] {c.title} ({c.source})\nAbstract: {c.snippet or '(not available)'}"
                           for cid, c, _ in paper_picks) or "(none today)"
        prompt = f"""Write today's newsletter in English for the reader described in the system prompt.
Write one item per story, in the order given, using only facts in the research notes. Be specific
and concise; research questions should be ones a PhD student could actually pursue
(name plausible datasets such as SEC filings, CDP, EIA, EPA GHGRP/TRI, bill-of-lading data,
FactSet Revere supply chain links, RepRisk, Compustat, where relevant).

STORIES:
{stories}

RESEARCH NOTES:
{notes}

PAPERS (use the same ids in candidate_id):
{papers}
"""
        if themes:
            prompt += f"\nUse exactly one of these theme labels per item: {'; '.join(themes)}\n"
        if related:
            blocks = []
            for cid, cands in related.items():
                lines = [f"  {rid}: {r['title']} ({r['journal']}, {r['year']}) — {r['abstract'] or 'no abstract'}"
                         for rid, r in cands]
                blocks.append(f"Story [{cid}]:\n" + "\n".join(lines))
            prompt += ("\nRELATED-PAPER CANDIDATES (from an academic search; many are only loosely related). "
                       "For each story, choose 1-2 papers that a researcher would actually cite or read next, "
                       "using only ids listed under that story; leave 'related' empty if none fit:\n"
                       + "\n".join(blocks) + "\n")
        if known_keywords:
            prompt += ("\nKeywords are used as archive tags. Reuse these existing tags (exact spelling) whenever "
                       "they fit, and add a new lowercase tag only when none fits:\n" + ", ".join(known_keywords) + "\n")
        if known_datasets:
            prompt += ("\nDataset names are used for a data-source index. Reuse these existing names (exact spelling) "
                       "for the same dataset:\n" + "; ".join(known_datasets) + "\n")
        return self._parse(prompt, Digest)
