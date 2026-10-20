"""Story-thread briefs: a living 5W1H brief per thread, rewritten when new articles join it.

The current brief is replaced on each update; what changed is appended to an update log, and earlier
briefs are kept in `history`. Stored in data/threads/<thread-id>.json, rendered to docs/threads/.

  python -m digest.threads          # write or refresh briefs for threads that have new articles
"""

from __future__ import annotations

import json
from datetime import date
from html import escape
from pathlib import Path

from pydantic import BaseModel, Field

from . import theme_toggle
from .about import md_to_html
from .render import DARK, LIGHT

DETACHED = "detached.json"   # item ids judged not to belong to their thread


class Actor(BaseModel):
    name: str = Field(description="Organization, agency, firm type or group")
    role: str = Field(description="What it does in this story")
    stake: str = Field(description="What it wants or stands to gain or lose")


class Angle(BaseModel):
    question: str = Field(description="A research question this story makes possible")
    shock: str = Field(description="The event or date that could serve as a shock or treatment, if any")
    data: str = Field(description="Data that could be used")


class ThreadBrief(BaseModel):
    title: str = Field(description="Short name for the whole story (4-10 words), not a headline of one article")
    summary: str = Field(description="1-2 sentences: what this story is about and where it stands")
    origin: str = Field(description="How and when it began: key earlier events and decisions with dates")
    causes: str = Field(description="Why it is happening: the underlying drivers")
    actors: list[Actor] = Field(description="3-7 main actors and their stakes")
    status: str = Field(description="Where things stand now: what has been decided and what is still open")
    watch: list[str] = Field(description="2-4 upcoming decisions, deadlines or data releases, with dates when known")
    research: list[Angle] = Field(description="1-3 research angles for an operations management PhD student")
    update_note: str = Field(description="1-2 sentences on what the newest article(s) changed; for a new thread, what opened it")
    off_topic: list[str] = Field(description="Ids of listed articles that are NOT about this same specific story (only the broad topic); usually empty")
    sources: list[str] = Field(description="URLs from the research notes that support the background")


def slug(thread_id: str) -> str:
    return thread_id.replace("#", "-")


def load_detached(threads_dir: Path) -> set[str]:
    p = threads_dir / DETACHED
    return set(json.loads(p.read_text())) if p.exists() else set()


def load_threads(threads_dir: Path) -> dict[str, dict]:
    if not threads_dir.exists():
        return {}
    return {json.loads(p.read_text())["id"]: json.loads(p.read_text())
            for p in sorted(threads_dir.glob("*.json")) if p.name != DETACHED}


def _full_items(issues_dir: Path) -> dict[str, dict]:
    out = {}
    for p in sorted(issues_dir.glob("*.json")):
        for n, it in enumerate(json.loads(p.read_text())["items"], 1):
            out[f"{p.stem}#{n}"] = {**it, "id": f"{p.stem}#{n}", "issue_date": p.stem}
    return out


def update_threads(issues_dir: Path, threads_dir: Path, curator, today: str, research_cfg: dict | None = None) -> list[str]:
    """Write or refresh briefs for threads that gained articles. Returns the updated thread ids."""
    from .archive import all_items, threads as group_threads
    threads_dir.mkdir(parents=True, exist_ok=True)
    detached = load_detached(threads_dir)
    groups: dict[str, list[str]] = {}
    for item_id, tid in group_threads(all_items(issues_dir), detached).items():
        groups.setdefault(tid, []).append(item_id)
    full = _full_items(issues_dir)
    existing = load_threads(threads_dir)
    updated = []

    for tid, ids in groups.items():
        ids = sorted(ids)
        prev = existing.get(tid)
        new_ids = [i for i in ids if not prev or i not in prev["items"]]
        if not new_ids:
            continue
        articles = "\n\n".join(
            f"[{i}] {full[i]['issue_date']} · {full[i]['source']} · {full[i]['headline']}\n"
            f"URL: {full[i]['url']}\nSummary: {full[i]['summary']}" + ("   (NEW)" if prev and i in new_ids else "")
            for i in ids)
        prev_brief = json.dumps(prev["brief"], ensure_ascii=False) if prev else "(none: this is a new thread)"

        notes = curator.web_notes(
            f"""These newsletter articles were linked as one ongoing story. Research its background so a
brief can explain it: how and when it began (earlier decisions, filings, events, with dates), why it is
happening, who the main actors are and what each wants, and where things stand today. Use web search; prefer
primary sources (agency orders, filings, official statements) and reputable reporting. Write concise notes
with the URL of every source you rely on. Say clearly when something is uncertain.

ARTICLES:
{articles}""",
            searches=(research_cfg or {}).get("thread_search_max_uses", 5),
            fetches=(research_cfg or {}).get("thread_fetch_max_uses", 3))

        brief = curator._parse(f"""Write the current brief for this story thread, for an operations management PhD student.
Use the research notes and the articles; do not add facts that are in neither. If a previous brief exists,
produce an updated version reflecting everything known now (it replaces the old one), and describe in
update_note what the NEW articles changed.
If an article is about the same broad topic but not this specific story, list its id in off_topic.

ARTICLES:
{articles}

PREVIOUS BRIEF:
{prev_brief}

RESEARCH NOTES:
{notes}""", ThreadBrief)

        off = [i for i in brief.off_topic if i in ids and i != tid]
        if off:
            detached |= set(off)
            (threads_dir / DETACHED).write_text(json.dumps(sorted(detached), indent=1))
        b = brief.model_dump(exclude={"off_topic", "update_note", "sources"})
        record = prev or {"id": tid, "created": today, "updates": [], "history": []}
        if prev:
            record["history"].append({"date": prev["updated"], "brief": prev["brief"]})
        record.update(
            brief=b, updated=today, items=[i for i in ids if i not in off],
            sources=[u for u in dict.fromkeys(brief.sources) if u in notes][:12])
        record["updates"].append({"date": today, "items": [i for i in new_ids if i not in off], "note": brief.update_note})
        (threads_dir / f"{slug(tid)}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False))
        updated.append(tid)
        print(f"Thread brief {'updated' if prev else 'created'}: {b['title']} ({len(ids)} articles)")
    return updated


def render_thread(site_title: str, t: dict, items: dict[str, dict]) -> str:
    """Web page for one thread. `items` maps item id -> {headline, source, issue_date}."""
    e = escape
    b = t["brief"]
    fmt = lambda iso: date.fromisoformat(iso).strftime("%b %-d, %Y")
    link = lambda i: f"../issues/{i.split('#')[0]}.html#item-{i.split('#')[1]}"
    its = [i for i in t["items"] if i in items]
    span = f"{fmt(its[0].split('#')[0])} → {fmt(its[-1].split('#')[0])}" if its else ""

    actors = "".join(f"<tr><td><b>{e(a['name'])}</b><div class='role'>{e(a['role'])}</div></td><td>{e(a['stake'])}</td></tr>"
                     for a in b["actors"])
    angles = "".join(f"<div class='angle'><div class='q'>{e(a['question'])}</div>"
                     f"<div class='kv'><span>Shock / timing</span>{e(a['shock'])}</div>"
                     f"<div class='kv'><span>Data</span>{e(a['data'])}</div></div>" for a in b["research"])
    updates = "".join(
        f"<li><span class='d'>{fmt(u['date'])}</span>{e(u['note'])}"
        + "".join(f"<br><a href='{link(i)}'>{e(items[i]['headline'])}</a>" for i in u["items"] if i in items) + "</li>"
        for u in reversed(t["updates"]))
    timeline = "".join(f"<li><span class='d'>{fmt(i.split('#')[0])}</span><a href='{link(i)}'>{e(items[i]['headline'])}</a>"
                       f" <span class='src'>· {e(items[i]['source'])}</span></li>" for i in its)
    sources = "".join(f"<li><a href='{e(u)}' target='_blank' rel='noopener'>{e(u)}</a></li>" for u in t.get("sources", []))
    history = "".join(f"<details><summary>Brief as of {fmt(h['date'])}: {e(h['brief']['title'])}</summary>"
                      f"<p>{e(h['brief']['summary'])}</p><p><b>Status then:</b> {e(h['brief']['status'])}</p></details>"
                      for h in reversed(t.get("history", [])))
    tv = {"toggle-bg": "var(--card)", "toggle-ink": "var(--ink)", "toggle-line": "var(--line)"}
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(b['title'])} · {e(site_title)}</title>
{theme_toggle.HEAD_JS}<style>{theme_toggle.themed_vars({**LIGHT, **tv}, {**DARK, **tv})}{theme_toggle.CSS}
html,body{{background:var(--bg)}}
body{{margin:0;color:var(--ink);font:16px/1.6 Georgia,"Times New Roman",serif}}
.wrap{{max-width:720px;margin:0 auto;padding:24px 16px 64px}}
.back{{font:13px Helvetica,Arial,sans-serif;color:var(--accent);text-decoration:none}}
.kicker{{font:600 12px/1.4 Helvetica,Arial,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-top:14px}}
h1{{font-size:30px;line-height:1.2;margin:4px 0 10px}}
.meta{{font:13px Helvetica,Arial,sans-serif;color:var(--muted);margin-bottom:18px}}
.lede{{font-size:18px;color:var(--ink2);margin:0 0 8px}}
h2{{font:600 13px/1.4 Helvetica,Arial,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:32px 0 8px;padding-top:14px;border-top:1px solid var(--line)}}
p{{margin:0 0 10px;color:var(--ink2)}}
a{{color:var(--accent)}}
table{{width:100%;border-collapse:collapse;font:14px/1.5 Helvetica,Arial,sans-serif;color:var(--ink3)}}
td{{padding:9px 8px 9px 0;border-bottom:1px solid var(--line);vertical-align:top}}
td:first-child{{width:34%}}
.role{{color:var(--muted);font-size:13px}}
ul{{padding-left:20px;margin:0}} li{{margin:8px 0;color:var(--ink2)}}
.log,.tl{{list-style:none;padding:0;font:14px/1.55 Helvetica,Arial,sans-serif}}
.log li,.tl li{{padding:6px 0 6px 12px;border-left:3px solid var(--line)}}
.d{{display:block;font-size:12px;font-weight:600;color:var(--muted)}}
.src{{color:var(--muted);font-size:12px}}
.angle{{background:var(--card);border-radius:10px;padding:14px 16px;margin:10px 0;font:14px/1.5 Helvetica,Arial,sans-serif;border-left:4px solid var(--gold)}}
.angle .q{{font-weight:600;color:var(--ink);margin-bottom:6px}}
.kv{{color:var(--ink3);margin:3px 0}} .kv span{{display:inline-block;min-width:110px;color:var(--muted)}}
.sources{{font:12px/1.5 Helvetica,Arial,sans-serif;word-break:break-all}}
details{{font:14px/1.5 Helvetica,Arial,sans-serif;margin:6px 0}} summary{{cursor:pointer;color:var(--ink2)}}
.note{{font:12px/1.5 Helvetica,Arial,sans-serif;color:var(--faint);margin-top:28px}}
</style></head>
<body>{theme_toggle.BUTTON}<div class="wrap">
<a class="back" href="../index.html#tab=threads">&larr; Story threads</a>
<div class="kicker">Story brief · {len(its)} articles · {span}</div>
<h1>{e(b['title'])}</h1>
<div class="meta">Last updated {fmt(t['updated'])} · first opened {fmt(t['created'])}</div>
<p class="lede">{e(b['summary'])}</p>

<h2>Background</h2>{md_to_html(b['origin'])}
<h2>Why it is happening</h2>{md_to_html(b['causes'])}
<h2>Who is involved</h2><table>{actors}</table>
<h2>Where things stand</h2>{md_to_html(b['status'])}
<h2>What to watch</h2><ul>{''.join(f'<li>{e(w)}</li>' for w in b['watch'])}</ul>
<h2>Research angles</h2>{angles}
<h2>Update log</h2><ul class="log">{updates}</ul>
<h2>Articles in this thread</h2><ul class="tl">{timeline}</ul>
{f'<h2>Sources</h2><ul class="sources">{sources}</ul>' if sources else ''}
{f'<h2>Earlier versions of this brief</h2>{history}' if history else ''}
<p class="note">Written by Claude from the linked articles and web sources, and rewritten when new articles join the thread. Check the sources before citing.</p>
</div>{theme_toggle.BODY_JS}</body></html>"""


if __name__ == "__main__":
    import yaml
    from run import ROOT, load_dotenv
    load_dotenv()
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    from .llm import Curator
    cur = Curator(cfg["llm"], cfg["research_profile"])
    done = update_threads(ROOT / "data" / "issues", ROOT / "data" / "threads", cur, date.today().isoformat(), cfg["llm"])
    print(f"{len(done)} thread(s) updated.", cur.cost_report())
