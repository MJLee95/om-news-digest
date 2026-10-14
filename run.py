"""Daily OM research news digest.

  python run.py                    # full run: collect -> curate -> email -> save archive
  python run.py --dry-run          # everything except email and state updates; writes output/preview.html
  python run.py --candidates-only  # just list today's candidates (no API calls, free)
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

import sys

from digest import archive, datasets as ds_registry, sources, stars as star_store, state
from digest.render import render_html, render_text

ROOT = Path(__file__).resolve().parent


def load_dotenv() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                if v.strip():
                    os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--candidates-only", action="store_true")
    ap.add_argument("--papers", action="store_true", help="force the journal section today")
    ap.add_argument("--force", action="store_true", help="send even if today's issue was already sent")
    args = ap.parse_args()

    load_dotenv()
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    d = cfg["digest"]
    now_local = datetime.now(ZoneInfo(d["timezone"]))
    today = now_local.date()
    since = datetime.now(timezone.utc) - timedelta(hours=d["lookback_hours"])
    if not (args.dry_run or args.candidates_only or args.force) and (state.DATA / "issues" / f"{today.isoformat()}.json").exists():
        print(f"Today's issue ({today}) was already sent; skipping. Use --force to send again.")
        return

    # 1. collect
    seen = state.load_seen()
    seen_titles, seen_urls = state.seen_sets(seen)
    raw = (sources.fetch_rss(cfg["rss_feeds"], since)
           + sources.fetch_google_news(cfg["google_news_queries"], since))
    news = sources.dedupe(raw, seen_titles, seen_urls)

    want_papers = args.papers or today.weekday() in d["academic_weekdays"]
    papers = []
    if want_papers:
        papers = sources.dedupe(
            sources.fetch_papers(cfg["journals"], d["paper_lookback_days"], cfg.get("crossref_mailto", "")),
            seen_titles, seen_urls)
    print(f"Candidates: {len(news)} news (from {len(raw)} raw), {len(papers)} papers")

    if args.candidates_only:
        for c in news:
            print(f"- ({c.source}) {c.title}")
        for c in papers:
            print(f"* ({c.source}) {c.title}")
        return
    if not news:
        # Usually means every feed failed; exit non-zero so the workflow's failure alert fires.
        sys.exit("No new candidates today (all feeds empty or failing); nothing sent.")

    # 2. curate with Claude
    from digest.llm import Curator
    cur = Curator(cfg["llm"], cfg["research_profile"])
    themes = cfg["themes"]
    repo = cfg.get("github_repo", "")
    issues_dir = state.DATA / "issues"
    all_items = archive.all_items(issues_dir)
    recent = [i for i in all_items if i["date"] >= (today - timedelta(days=21)).isoformat()]
    stars = star_store.fetch_stars(repo)
    starred = [{**i, "note": stars[i["id"]]["note"]} for i in all_items if i["id"] in stars][-30:]
    sel = cur.select(news, papers, d["num_news"], d["num_papers"] if want_papers else 0, themes,
                     d.get("num_also", 5), recent, starred)
    picks = [(p.id, news[p.id], p) for p in sel.news]
    paper_picks = [(p.id, papers[p.id], p) for p in sel.papers]
    print("Selected:", *[f"  [{p.theme}] {c.title}" for _, c, p in picks], sep="\n")

    # related academic papers per story (real search results; Claude only chooses among them)
    related, rel_by_id, n = {}, {}, 0
    for cid, _, p in picks:
        found = sources.search_related(p.lit_queries[:2], cfg["related_journal_issns"],
                                       mailto=cfg.get("crossref_mailto", ""))
        related[cid] = []
        for r in found:
            n += 1
            related[cid].append((f"R{n}", r))
            rel_by_id[f"R{n}"] = (cid, r)

    notes = cur.research(picks)
    registry = ds_registry.load_registry()
    dg = cur.compose(picks, paper_picks, notes, archive.known_keywords(issues_dir),
                     related, themes, ds_registry.registry_prompt(registry))
    print(cur.cost_report())

    # 3. assemble (never trust a URL that didn't appear in the research notes)
    by_id = {cid: c for cid, c, _ in picks}
    pick_by_id = {cid: p for cid, _, p in picks}
    item_lookup = {i["id"]: i for i in all_items}
    items = []
    for it in dg.items:
        c = by_id.get(it.candidate_id)
        if c is None:
            continue
        url = it.original_url if it.original_url and it.original_url in notes else c.url
        theme = next((t for t in themes if t.lower() == it.theme.strip().lower()), it.theme)
        rel = [{**rel_by_id[r.paper_id][1], "why": r.why} for r in it.related[:2]
               if r.paper_id in rel_by_id and rel_by_id[r.paper_id][0] == it.candidate_id]
        for r in rel:
            r.pop("abstract", None)
        follows = [{"id": f, "label": f"{datetime.fromisoformat(f.split('#')[0]):%b %-d} · {item_lookup[f]['headline'][:80]}"}
                   for f in pick_by_id[it.candidate_id].follows if f in item_lookup]
        dsets = [x for x in dict.fromkeys(it.datasets) if x in registry["by_id"]][:2]
        items.append({**it.model_dump(exclude={"related", "datasets"}), "datasets": dsets,
                      "theme": theme, "related": rel, "url": url, "follows": follows,
                      "source": c.source, "date": c.published.strftime("%b %d") if c.published else ""})
    paper_by_id = {cid: c for cid, c, _ in paper_picks}
    issue_papers = [{**p.model_dump(), "title": paper_by_id[p.candidate_id].title,
                     "journal": paper_by_id[p.candidate_id].source, "url": paper_by_id[p.candidate_id].url}
                    for p in dg.papers if p.candidate_id in paper_by_id]
    norm_theme = lambda t: next((x for x in themes if x.lower() == t.strip().lower()), t)
    also = [{"title": news[a.id].title, "url": news[a.id].url, "source": news[a.id].source,
             "theme": norm_theme(a.theme)} for a in sel.also]
    issue = {"intro": dg.intro, "items": items, "papers": issue_papers, "thread_to_pull": dg.thread_to_pull,
             "also": also}

    if not items:
        sys.exit("Claude returned no usable items; nothing sent.")
    iso = today.isoformat()
    date_str = now_local.strftime("%A, %B %-d, %Y")
    html = render_html(d["title"], date_str, issue, d.get("archive_url", ""), iso=iso, repo=repo)
    text = render_text(d["title"], date_str, issue)
    subject = f"{now_local:%a, %b %-d} — {items[0]['headline']}"[:150]

    if args.dry_run:
        out = ROOT / "output"
        out.mkdir(exist_ok=True)
        (out / "preview.html").write_text(html)
        (out / "notes.md").write_text(notes)
        (out / "issue.json").write_text(json.dumps(issue, indent=1, ensure_ascii=False))
        print(f"Dry run: wrote {out / 'preview.html'}")
        return

    # 4. send, then record
    from digest.mailer import send
    send(subject, text, html)
    print("Email sent.")

    (state.DATA / "issues").mkdir(parents=True, exist_ok=True)
    (state.DATA / "issues" / f"{iso}.html").write_text(html)
    (state.DATA / "issues" / f"{iso}.json").write_text(json.dumps(issue, indent=1, ensure_ascii=False))
    state.append_archive(
        [{**i, "date": iso, "kind": "news", "keywords": "; ".join(i["keywords"])} for i in items]
        + [{"date": iso, "kind": "paper", "theme": "", "headline": p["title"], "source": p["journal"],
            "url": p["url"], "summary": p["takeaway"]} for p in issue_papers])
    sent = [c for _, c, _ in picks] + [c for _, c, _ in paper_picks] + [news[a.id] for a in sel.also]
    ds_registry.add_candidates({f"{iso}#{n}": i.get("dataset_candidates", [])[:2] for n, i in enumerate(items, 1)},
                               iso, registry)
    state.save_seen(seen, [{"date": iso, "url": c.url, "title_key": sources.norm_title(c.title)} for c in sent], today)
    archive.build(issues_dir, ROOT / "docs", d["title"], repo, stars, d.get("byline", ""), cfg.get("analytics"))


if __name__ == "__main__":
    main()
