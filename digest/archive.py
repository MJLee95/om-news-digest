"""Build a static archive site (docs/) from data/issues/*.json and data/weekly/*.json.

  python -m digest.archive            # rebuild docs/ (fetches stars from GitHub)
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path

from . import theme_toggle
from .datasets import ACCESS_LABELS, load_candidates, load_registry
from .star_client import STARS_JS
from .render import render_html


def _issues(issues_dir: Path) -> list[tuple[str, dict]]:
    return [(p.stem, json.loads(p.read_text())) for p in sorted(issues_dir.glob("*.json"))]


def all_items(issues_dir: Path) -> list[dict]:
    """Every news item in the archive, oldest first, with a stable id like '2026-10-13#2'."""
    out = []
    for iso, iss in _issues(issues_dir):
        for n, it in enumerate(iss["items"], 1):
            out.append({"id": f"{iso}#{n}", "date": iso, "n": n, "headline": it["headline"], "theme": it["theme"],
                        "keywords": it["keywords"], "datasets": it.get("datasets", []),
                        "follows": [f["id"] for f in it.get("follows", [])]})
    return out


def known_keywords(issues_dir: Path, limit: int = 200) -> list[str]:
    counts = Counter(k.strip().lower() for i in all_items(issues_dir) for k in i["keywords"])
    return [k for k, _ in counts.most_common(limit)]


def threads(items: list[dict]) -> dict[str, str]:
    """Group items linked by 'follows' into story threads. Returns {item_id: thread_id} for threads of 2+."""
    parent = {i["id"]: i["id"] for i in items}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in items:
        for f in i["follows"]:
            if f in parent:
                parent[find(i["id"])] = find(f)
    groups = Counter(find(x) for x in parent)
    return {x: find(x) for x in parent if groups[find(x)] > 1}


def _byline_html(text: str) -> str:
    """Escape the byline and turn [label](https://...) into links."""
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                  lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener">{m.group(1)}</a>', escape(text))


def analytics_snippet(cfg: dict | None) -> str:
    """Page-view counting for the web pages (never the email).

    GoatCounter: our own few lines send a 1-pixel request with the path, title and referrer, so no third-party
    script runs next to the GitHub token used for stars. GA4: Google's gtag script (runs in the page).
    """
    cfg = cfg or {}
    gc = (cfg.get("goatcounter") or "").strip()
    if gc:
        return rf"""<script>(function(){{
  if (/^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname)) return;
  try {{
    // same opt-out as GoatCounter's own script: Settings → "disable for this browser" opens #toggle-goatcounter
    if (location.hash === '#toggle-goatcounter') {{
      var off = localStorage.getItem('skipgc') === 't';
      off ? localStorage.removeItem('skipgc') : localStorage.setItem('skipgc', 't');
      alert(off ? 'GoatCounter: counting this browser again.' : 'GoatCounter: visits from this browser will no longer be counted.');
      history.replaceState(null, '', location.pathname);
      return;
    }}
    if (localStorage.getItem('skipgc') === 't') return;
  }} catch (e) {{}}
  var q = new URLSearchParams({{p: location.pathname, t: document.title, r: document.referrer, s: screen.width, rnd: Math.random()}});
  new Image().src = 'https://{gc}.goatcounter.com/count?' + q;
}})();</script>"""
    ga = (cfg.get("ga4") or "").strip()
    if ga:
        return f"""<script async src="https://www.googletagmanager.com/gtag/js?id={ga}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{ga}');</script>"""
    return ""


def _inject(html: str, snippet: str) -> str:
    # in <head> so it sees the URL before the page's own scripts rewrite the #hash
    return html.replace("</head>", snippet + "</head>", 1) if snippet else html


def build(issues_dir: Path, out_dir: Path, title: str, repo: str = "", stars: dict | None = None, byline: str = "",
          analytics: dict | None = None) -> None:
    track = analytics_snippet(analytics)
    if stars is None:
        from .stars import fetch_stars
        stars = fetch_stars(repo)
    issues = _issues(issues_dir)
    (out_dir / "issues").mkdir(parents=True, exist_ok=True)
    thread_of = threads(all_items(issues_dir))

    records = []
    for iso, iss in issues:
        date_str = date.fromisoformat(iso).strftime("%A, %B %-d, %Y")
        (out_dir / "issues" / f"{iso}.html").write_text(_inject(
            render_html(title, date_str, iss, "../index.html", web=True, iso=iso, repo=repo, stars=stars), track))
        records.append({
            "date": iso,
            "intro": iss["intro"],
            "items": [{"n": n, "id": f"{iso}#{n}", "headline": it["headline"], "theme": it["theme"],
                       "source": it["source"], "summary": it["summary"], "rq": it["research_question"],
                       "related": [r["title"] for r in it.get("related", [])],
                       "keywords": [k.strip().lower() for k in it["keywords"]],
                       "datasets": [d.strip() for d in it.get("datasets", [])],
                       "thread": thread_of.get(f"{iso}#{n}")}
                      for n, it in enumerate(iss["items"], 1)],
            "papers": [{"title": p["title"], "journal": p["journal"], "url": p["url"]} for p in iss["papers"]],
            "also": [{"title": a["title"], "url": a["url"], "source": a["source"]} for a in iss.get("also", [])],
        })
    records.sort(key=lambda r: r["date"], reverse=True)

    weekly = []
    weekly_dir = issues_dir.parent / "weekly"
    if weekly_dir.exists():
        from .weekly import render_weekly
        (out_dir / "weekly").mkdir(exist_ok=True)
        for p in sorted(weekly_dir.glob("*.json"), reverse=True):
            wk = json.loads(p.read_text())
            (out_dir / "weekly" / f"{p.stem}.html").write_text(_inject(render_weekly(title, p.stem, wk, "../index.html", web=True), track))
            weekly.append({"date": p.stem, "overview": wk["overview"], "ideas": [i["title"] for i in wk["ideas"]]})

    reg = load_registry()
    payload = {
        "issues": records,
        "registry": {"categories": reg["categories"], "access": ACCESS_LABELS,
                     "datasets": [{k: d.get(k) for k in ("id", "name", "category", "access", "url", "alt")} for d in reg["datasets"]]},
        "candidates": sorted(({"name": c["name"], "mentions": len(c["items"]), "last": c.get("last_seen", "")}
                              for c in load_candidates().values()), key=lambda c: -c["mentions"]),
        "stars": {k: {"number": v.get("number"), "note": v.get("note", "")} for k, v in stars.items()},
        "weekly": weekly,
        "repo": repo,
    }
    (out_dir / "stars.js").write_text(STARS_JS)
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    page = (INDEX.replace("__TOGGLE_HEAD__", theme_toggle.HEAD_JS).replace("__TOGGLE_CSS__", theme_toggle.CSS)
            .replace("__TOGGLE_BUTTON__", theme_toggle.BUTTON).replace("__TOGGLE_JS__", theme_toggle.BODY_JS)
            .replace("__TITLE__", title).replace("__BYLINE__", _byline_html(byline)).replace("__DATA__", data))
    about_md = Path(__file__).resolve().parent.parent / "about.md"
    if about_md.exists():
        from .about import render_about
        (out_dir / "about.html").write_text(_inject(render_about(title, about_md.read_text()), track))
        page = page.replace("<!--ABOUT-->", ' · <a href="about.html">About</a>', 1)
    (out_dir / "index.html").write_text(_inject(page, track))
    (out_dir / ".nojekyll").touch()


INDEX = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ Archive</title>
__TOGGLE_HEAD__
<style>
:root{--bg:#f4f3ef;--card:#fff;--ink:#1d1d1b;--muted:#6b6a65;--line:#dcdad3;--accent:#1f6f5c;--chip:#ebe9e2;--chip-on:#1d1d1b;--chip-on-ink:#f4f3ef;--star:#b7791f}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--card:#20201e;--ink:#ecebe6;--muted:#9c9a93;--line:#34332f;--accent:#6fc2a8;--chip:#2b2a27;--chip-on:#ecebe6;--chip-on-ink:#161615;--star:#e6b450}}
:root[data-theme="dark"]{--bg:#161615;--card:#20201e;--ink:#ecebe6;--muted:#9c9a93;--line:#34332f;--accent:#6fc2a8;--chip:#2b2a27;--chip-on:#ecebe6;--chip-on-ink:#161615;--star:#e6b450}
:root{--toggle-bg:var(--card);--toggle-ink:var(--ink);--toggle-line:var(--line)}
__TOGGLE_CSS__
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:28px 16px 64px}
h1{font-family:Georgia,"Times New Roman",serif;font-size:30px;margin:0;padding-right:120px}
.sub{color:var(--muted);margin:4px 0 16px}
a{color:inherit}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin-bottom:20px;overflow-x:auto}
.tab{background:none;border:0;border-bottom:2px solid transparent;color:var(--muted);font:600 14px/1 inherit;padding:10px 12px;cursor:pointer;white-space:nowrap}
.tab.on{color:var(--ink);border-bottom-color:var(--ink)}
.tab small{font-weight:400;margin-left:4px}
.layout{display:grid;grid-template-columns:280px 1fr;gap:28px;align-items:start}
@media (max-width:760px){.layout{grid-template-columns:1fr}}
aside{position:sticky;top:16px}
@media (max-width:760px){aside{position:static}}
input[type=search]{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);font:inherit}
details{margin-top:18px}
summary{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);cursor:pointer;list-style:none;display:flex;align-items:center;gap:6px;padding:4px 0;user-select:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"▸";font-size:11px;transition:transform .15s}
details[open]>summary::before{transform:rotate(90deg)}
summary .n{margin-left:auto;letter-spacing:0;text-transform:none}
details .chips{margin-top:8px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{border:0;border-radius:999px;padding:4px 10px;background:var(--chip);color:var(--ink);font:13px/1.4 inherit;cursor:pointer}
.chip:hover{outline:1px solid var(--muted)}
.chip.on{background:var(--chip-on);color:var(--chip-on-ink)}
.chip small{color:var(--muted);margin-left:3px}
.chip.on small{color:inherit;opacity:.7}
.more{background:none;border:0;color:var(--accent);cursor:pointer;padding:6px 0;font:inherit;font-size:13px}
.bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px;min-height:28px}
.bar strong{font-size:17px}
.clear{background:none;border:1px solid var(--line);border-radius:6px;color:var(--muted);cursor:pointer;padding:3px 8px;font:inherit;font-size:13px}
.card{background:var(--card);border-radius:10px;padding:18px 20px;margin-bottom:14px}
.card h3{margin:0 0 4px;font-family:Georgia,serif;font-size:19px}
.card h3 a{text-decoration:none}
.card .intro{color:var(--muted);font-size:14px;margin:0 0 10px}
.row{padding:9px 0;border-top:1px solid var(--line);display:flex;gap:10px;align-items:flex-start}
.row .body{flex:1;min-width:0}
.row a.go{text-decoration:none;display:block}
.row a.go:hover .hl{text-decoration:underline}
.star{flex:none;text-decoration:none;color:var(--muted);font-size:17px;line-height:1.2;padding:2px 2px 0}
.star.on{color:var(--star)}
.star:hover{color:var(--star)}
.meta{font-size:12px;color:var(--muted)}
.theme{font-weight:600;color:var(--accent)}
.hl{font-weight:600}
.kw{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}
.kw .chip{font-size:11px;padding:2px 8px}
.chip.thread{background:none;border:1px solid var(--line);color:var(--accent)}
.snip{font-size:13px;color:var(--muted);margin-top:3px}
.note{font-size:13px;margin-top:4px;padding:6px 10px;border-left:3px solid var(--star);background:var(--chip);border-radius:4px}
.paper{font-size:13px;color:var(--muted);padding-top:8px;border-top:1px dashed var(--line)}
.card details{margin-top:8px}
details.card{margin:0 0 8px;padding:12px 18px}
details.card>summary{padding:2px 0}
details.card[open]>summary{margin-bottom:6px}
.empty{color:var(--muted);padding:24px 0;line-height:1.6}
.help{font-size:13px;color:var(--muted);margin:0 0 14px;line-height:1.55}
mark{background:#f2dc8a;color:#1d1d1b;border-radius:2px}
.badge{display:inline-block;font-size:11px;font-weight:600;border-radius:4px;padding:1px 6px;margin-left:6px;vertical-align:1px;white-space:nowrap}
.badge.public{background:#dcefe6;color:#1f5f4c}.badge.university{background:#dfe7f6;color:#28497f}
.badge.commercial{background:#f6e3d6;color:#8a4a1c}.badge.request{background:#efe3f3;color:#6a3a7a}
:root[data-theme="dark"] .badge{filter:brightness(.85) saturate(1.2)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .badge{filter:brightness(.85) saturate(1.2)}}
.ds{border-top:1px solid var(--line);padding:8px 0}
.ds>summary{font-size:14px;letter-spacing:0;text-transform:none;color:var(--ink);font-weight:600;padding:2px 0}
.ds .alt{font-size:12px;color:var(--muted);margin:2px 0 4px 17px}
.ds.unused>summary{color:var(--muted);font-weight:400}
.cal{background:var(--card);border-radius:10px;padding:12px 12px 10px;margin-bottom:14px}
.cal-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
.cal-head button{background:none;border:0;color:var(--ink);font:600 14px/1 inherit;cursor:pointer;padding:6px 8px;border-radius:6px}
.cal-head button:hover{background:var(--chip)}
.cal-head .mon.on{background:var(--chip-on);color:var(--chip-on-ink)}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center}
.cal-grid .dow{font-size:11px;color:var(--muted);padding:2px 0 4px}
.cal-grid .d{font:13px/1 inherit;padding:7px 0;border-radius:6px;color:var(--muted);opacity:.45;border:0;background:none}
.cal-grid button.d{opacity:1;color:var(--ink);font-weight:600;cursor:pointer;position:relative}
.cal-grid button.d::after{content:"";position:absolute;left:50%;bottom:2px;width:4px;height:4px;margin-left:-2px;border-radius:50%;background:var(--accent)}
.cal-grid button.d:hover{background:var(--chip)}
.cal-grid button.d.on{background:var(--chip-on);color:var(--chip-on-ink)}
.cal-grid button.d.on::after{background:var(--chip-on-ink)}
.cal-foot{display:flex;justify-content:space-between;align-items:center;margin-top:8px;font-size:12px;color:var(--muted)}
.cal-foot button{background:none;border:0;color:var(--accent);cursor:pointer;font:inherit;padding:0}
.pager{display:flex;align-items:center;justify-content:center;gap:6px;flex-wrap:wrap;margin:6px 0 20px;font-size:13px;color:var(--muted)}
.pager button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:6px;padding:5px 10px;font:inherit;cursor:pointer;min-width:34px}
.pager button.on{background:var(--chip-on);color:var(--chip-on-ink);border-color:transparent}
.pager button:disabled{opacity:.4;cursor:default}
.pager select{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:6px;padding:4px 6px;font:inherit}
.filters{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:-4px 0 14px}
</style></head>
<body><div class="wrap">
__TOGGLE_BUTTON__
<h1>__TITLE__</h1>
<div class="sub">__BYLINE__<!--ABOUT--></div>
<nav class="tabs" id="tabs"></nav>
<div class="layout">
<aside>
  <div class="cal" id="cal"></div>
  <input type="search" id="q" placeholder="Search headlines, summaries, questions" aria-label="Search">
  <details id="themeBox" open><summary>Themes<span class="n" id="nThemes"></span></summary><div class="chips" id="themes"></div></details>
  <details id="kwBox"><summary>Keywords<span class="n" id="nKw"></span></summary><div class="chips" id="keywords"></div>
  <button class="more" id="moreKw" hidden></button></details>
</aside>
<main>
  <div class="bar" id="bar"></div>
  <div id="list"></div>
</main>
</div></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
window.STAR_CFG = {repo: D.repo, initial: D.stars,
  headlines: Object.fromEntries(D.issues.flatMap(d => d.items.map(it => [it.id, it.headline])))};
</script>
<script src="stars.js"></script>
<script>
const ISSUES = D.issues;
const ITEMS = ISSUES.flatMap(d => d.items.map(it => ({...it, date: d.date})));
const BY_ID = Object.fromEntries(ITEMS.map(it => [it.id, it]));
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric', year:'numeric'});
const short = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', {month:'short', day:'numeric'});
const link = it => `issues/${it.date}.html#item-${it.n}`;
const NARROW = matchMedia('(max-width:760px)'), KW_TOP = () => NARROW.matches ? 12 : 30;

// threads
const THREADS = {};
ITEMS.forEach(it => { if (it.thread) (THREADS[it.thread] ||= []).push(it); });
Object.values(THREADS).forEach(list => list.sort((a, b) => a.date.localeCompare(b.date) || a.n - b.n));
const THREAD_LIST = Object.entries(THREADS).sort((a, b) => b[1].at(-1).date.localeCompare(a[1].at(-1).date));

// datasets: registry entries (datasets.yaml) with the stories that used them
const REG = D.registry, DS_BY_ID = Object.fromEntries(REG.datasets.map(d => [d.id, d]));
const DATASETS = {};
ITEMS.forEach(it => (it.datasets || []).forEach(id => { if (DS_BY_ID[id]) (DATASETS[id] ||= []).push(it); }));
const DATASET_LIST = Object.keys(DATASETS);
let dsAccess = null, dsShowAll = false;

// filters: one theme + any number of keywords (an article must have all of them) + search text
let state = {tab: 'issues', theme: null, kws: [], q: '', open: null, day: null, month: null, page: 1}, showAllKw = false;

// calendar + paging
const ISSUE_DATES = new Set(ISSUES.map(d => d.date));
const NEWEST = ISSUES[0]?.date || new Date().toISOString().slice(0, 10);
let calView = NEWEST.slice(0, 7);   // 'YYYY-MM' shown in the calendar
let perPage = 7;
try { perPage = +localStorage.getItem('perPage') || 7; } catch (e) {}
const inRange = date => (!state.day || date === state.day) && (!state.month || date.startsWith(state.month));
const monthName = ym => new Date(ym + '-15T12:00:00').toLocaleDateString('en-US', {month: 'long', year: 'numeric'});
const shiftMonth = (ym, k) => { const d = new Date(ym + '-15T12:00:00'); d.setMonth(d.getMonth() + k); return d.toISOString().slice(0, 7); };

function renderCal() {
  const [y, m] = calView.split('-').map(Number);
  const first = new Date(y, m - 1, 1).getDay(), days = new Date(y, m, 0).getDate();
  const cells = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map(d => `<div class="dow">${d}</div>`);
  for (let i = 0; i < first; i++) cells.push('<div></div>');
  for (let d = 1; d <= days; d++) {
    const iso = `${calView}-${String(d).padStart(2, '0')}`;
    cells.push(ISSUE_DATES.has(iso)
      ? `<button class="d${state.day === iso ? ' on' : ''}" data-calday="${iso}" title="${fmt(iso)}">${d}</button>`
      : `<div class="d">${d}</div>`);
  }
  const n = ISSUES.filter(x => x.date.startsWith(calView)).length;
  const sel = state.day ? fmt(state.day) : state.month ? monthName(state.month) : 'All issues';
  $('cal').innerHTML = `<div class="cal-head"><button data-calnav="-1" aria-label="Previous month">‹</button>
    <button class="mon${state.month === calView ? ' on' : ''}" data-calmonth="${calView}" title="Show this month">${monthName(calView)}</button>
    <button data-calnav="1" aria-label="Next month">›</button></div>
    <div class="cal-grid">${cells.join('')}</div>
    <div class="cal-foot"><span>${n} issue${n === 1 ? '' : 's'} this month · showing ${esc(sel)}</span>
    ${state.day || state.month ? '<button data-calall>Show all</button>' : ''}</div>`;
}

function pager(total, size) {
  const pages = Math.max(1, Math.ceil(total / size));
  state.page = Math.min(Math.max(1, state.page), pages);
  const nums = [];
  for (let i = 1; i <= pages; i++)
    if (i === 1 || i === pages || Math.abs(i - state.page) <= 1) nums.push(i);
    else if (nums.at(-1) !== '…') nums.push('…');
  const btns = pages > 1 ? `<button data-page="${state.page - 1}" ${state.page === 1 ? 'disabled' : ''}>‹ Newer</button>
    ${nums.map(i => i === '…' ? '<span>…</span>' : `<button data-page="${i}" class="${i === state.page ? 'on' : ''}">${i}</button>`).join('')}
    <button data-page="${state.page + 1}" ${state.page === pages ? 'disabled' : ''}>Older ›</button>` : '';
  return {slice: arr => arr.slice((state.page - 1) * size, state.page * size),
          html: `<div class="pager">${btns}<span style="margin-left:8px">Per page</span>
            <select id="perPage">${[5, 7, 10].map(k => `<option ${k === perPage ? 'selected' : ''}>${k}</option>`).join('')}</select></div>`};
}
const filtering = () => !!(state.theme || state.kws.length || state.q);

const matchQ = it => !state.q || (it.headline + ' ' + it.summary + ' ' + it.rq + ' ' + it.keywords.join(' ') + ' ' +
  (it.related || []).join(' ') + ' ' + (it.datasets || []).join(' ')).toLowerCase().includes(state.q.toLowerCase());
const matches = (it, {ignoreTheme = false} = {}) =>
  (ignoreTheme || !state.theme || it.theme === state.theme) && state.kws.every(k => it.keywords.includes(k)) && matchQ(it);

function tally(items, key) {
  const m = new Map();
  items.forEach(it => [].concat(it[key]).forEach(v => m.set(v, (m.get(v) || 0) + 1)));
  return [...m].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}
const ALL_KW = tally(ITEMS, 'keywords');

const TABS = [
  ['issues', 'Issues', ISSUES.length],
  ['threads', 'Story threads', THREAD_LIST.length],
  ['datasets', 'Datasets', DATASET_LIST.length],
  ['starred', '★ Starred', null],
  ['weekly', 'Weekly reviews', D.weekly.length],
];

function chip(kind, v, n) {
  const on = kind === 'theme' ? state.theme === v : state.kws.includes(v);
  return `<button class="chip${on ? ' on' : ''}" data-kind="${kind}" data-tag="${esc(v)}" aria-pressed="${on}">${esc(v)}${n ? `<small>${n}</small>` : ''}</button>`;
}

function hi(s) {
  if (!state.q) return esc(s);
  const re = new RegExp('(' + state.q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
  return esc(s).replace(re, '<mark>$1</mark>');
}

const starBtn = it => D.repo ? `<a class="star${Stars.isStarred(it.id) ? ' on' : ''}" href="#" data-star="${esc(it.id)}">${Stars.isStarred(it.id) ? '★' : '☆'}</a>` : '';

function row(it, {withDate = false, showRq = false, note = null} = {}) {
  const thread = it.thread && THREADS[it.thread].length > 1
    ? `<button class="chip thread" data-thread="${esc(it.thread)}">🧵 ${THREADS[it.thread].length} in thread</button>` : '';
  const kw = it.keywords.map(k => chip('keywords', k)).join('');
  const noteHtml = note === null ? '' : `<div class="note">${note ? esc(note) : '<span class="meta">No note yet.</span>'}
    <button class="clear" data-note="${esc(it.id)}" style="margin-left:6px">${note ? 'Edit note' : 'Add note'}</button></div>`;
  return `<div class="row">${starBtn(it)}<div class="body"><a class="go" href="${link(it)}">
    <div class="meta">${withDate ? fmt(it.date) + ' · ' : ''}<span class="theme">${esc(it.theme)}</span> · ${esc(it.source)}</div>
    <div class="hl">${hi(it.headline)}</div>
    ${state.q ? `<div class="snip">${hi(it.summary)}</div>` : ''}
    ${showRq ? `<div class="snip"><b>Q:</b> ${hi(it.rq)}</div>` : ''}</a>
    ${noteHtml}
    <div class="kw">${thread}${kw}</div></div></div>`;
}

function renderSide() {
  // themes still possible with the chosen keywords/search; keywords present in the current results
  const themes = tally(ITEMS.filter(it => matches(it, {ignoreTheme: true})), 'theme');
  if (state.theme && !themes.some(([t]) => t === state.theme)) themes.unshift([state.theme, 0]);
  $('themes').innerHTML = themes.map(([v, n]) => chip('theme', v, n)).join('') || '<span class="meta">No themes match.</span>';
  const pool = filtering() ? tally(ITEMS.filter(it => matches(it)), 'keywords') : ALL_KW;
  const chosen = state.kws.map(k => [k, (pool.find(([v]) => v === k) || [k, 0])[1]]);
  const rest = pool.filter(([v]) => !state.kws.includes(v));
  const kws = [...chosen, ...(showAllKw ? rest : rest.slice(0, Math.max(0, KW_TOP() - chosen.length)))];
  $('keywords').innerHTML = kws.map(([v, n]) => chip('keywords', v, n)).join('') || '<span class="meta">No keywords match.</span>';
  $('moreKw').hidden = chosen.length + rest.length <= KW_TOP();
  $('moreKw').textContent = showAllKw ? 'Show fewer' : `Show all ${chosen.length + rest.length}`;
  $('nThemes').textContent = themes.length; $('nKw').textContent = chosen.length + rest.length;
  const nStar = ITEMS.filter(it => Stars.isStarred(it.id)).length;
  $('tabs').innerHTML = TABS.map(([k, label, n]) =>
    `<button class="tab${state.tab === k ? ' on' : ''}" data-tab="${k}">${label}<small>${k === 'starred' ? nStar : n}</small></button>`).join('');
}

function bar(title, sub, clear) {
  $('bar').innerHTML = `<strong>${title}</strong>${sub ? `<span class="meta">${sub}</span>` : ''}${clear ? '<button class="clear" id="clear">Clear</button>' : ''}`;
  if (clear) $('clear').onclick = () => { state = {...state, theme: null, kws: [], q: '', open: null, day: null, month: null, page: 1}; $('q').value = ''; update(); };
}

function filterBar(n) {
  const tags = [
    ...(state.theme ? [`<button class="chip on" data-kind="theme" data-tag="${esc(state.theme)}">${esc(state.theme)} ✕</button>`] : []),
    ...state.kws.map(k => `<button class="chip on" data-kind="keywords" data-tag="${esc(k)}">${esc(k)} ✕</button>`),
    ...(state.q ? [`<span class="meta">search “${esc(state.q)}”</span>`] : []),
  ].join('');
  $('bar').innerHTML = `<div class="chips">${tags}</div><span class="meta">${n} article${n === 1 ? '' : 's'}${state.kws.length > 1 ? ' with all selected keywords' : ''}</span>
    <button class="clear" id="clear">Clear all</button>`;
  $('clear').onclick = () => { state = {...state, theme: null, kws: [], q: '', open: null}; $('q').value = ''; update(); };
}

const VIEWS = {
  issues() {
    if (filtering()) {
      const hits = ITEMS.filter(it => matches(it) && inRange(it.date)).sort((a, b) => b.date.localeCompare(a.date) || a.n - b.n);
      filterBar(hits.length);
      const pg = pager(hits.length, perPage * 5);
      return hits.length ? `<div class="card">${pg.slice(hits).map(it => row(it, {withDate: true})).join('')}</div>${pg.html}` : '<div class="empty">No articles match all of these filters.</div>';
    }
    const issues = ISSUES.filter(d => inRange(d.date));
    const pg = pager(issues.length, perPage);
    if (state.day) bar(fmt(state.day), '', true);
    else if (state.month) bar(monthName(state.month), `${issues.length} issue${issues.length === 1 ? '' : 's'}`, true);
    else bar('All issues', `newest first · ${issues.length} issue${issues.length === 1 ? '' : 's'}`);
    return issues.length ? pg.slice(issues).map(d => `<section class="card">
      <h3><a href="issues/${d.date}.html">${fmt(d.date)}</a></h3>
      <p class="intro">${esc(d.intro)}</p>
      ${d.items.map(it => row({...it, date: d.date})).join('')}
      ${d.papers.map(p => `<div class="paper">📄 <a href="${esc(p.url)}">${esc(p.title)}</a> — ${esc(p.journal)}</div>`).join('')}
      ${(d.also || []).length ? `<details><summary>Also worth noting · ${d.also.length}</summary>${d.also.map(a => `<div class="paper"><a href="${esc(a.url)}">${esc(a.title)}</a> — ${esc(a.source)}</div>`).join('')}</details>` : ''}
    </section>`).join('') + pg.html : `<div class="empty">${ISSUES.length ? 'No issue on this date.' : 'No issues yet.'}</div>`;
  },
  threads() {
    let list = THREAD_LIST.filter(([, its]) => its.some(matchQ));
    if (state.open) list = list.filter(([id]) => id === state.open);
    bar(state.open ? 'Story thread' : 'Story threads', state.open ? '' : 'ongoing stories covered more than once', !!state.open || !!state.q);
    if (!list.length) return `<div class="empty">${THREAD_LIST.length ? 'No matching threads.' :
      'No story threads yet. When a new story is a follow-up to something covered earlier, the two are linked here as a timeline.'}</div>`;
    return list.map(([id, its]) => `<section class="card">
      <h3>${esc(its.at(-1).headline)}</h3>
      <p class="intro">${its.length} updates · ${short(its[0].date)} → ${short(its.at(-1).date)}</p>
      ${its.map(it => row(it, {withDate: true})).join('')}</section>`).join('');
  },
  datasets() {
    const q = state.q.toLowerCase();
    const used = id => (DATASETS[id] || []).filter(matchQ);
    const visible = REG.datasets.filter(d => (!dsAccess || d.access === dsAccess) &&
      (dsShowAll || used(d.id).length) &&
      (!q || used(d.id).length || (d.name + ' ' + (d.alt || '')).toLowerCase().includes(q)));
    bar('Datasets', `${DATASET_LIST.length} of ${REG.datasets.length} in your list used so far`, !!state.q);
    const accessChip = (k, label) => `<button class="chip${dsAccess === k ? ' on' : ''}" data-dsaccess="${k || ''}">${label}</button>`;
    const filters = `<div class="filters">${accessChip(null, 'All')}${Object.entries(REG.access).map(([k, l]) => accessChip(k, l)).join('')}
      <button class="clear" data-dsall>${dsShowAll ? 'Hide unused' : 'Show full list'}</button></div>
      <p class="help">The list lives in <code>datasets.yaml</code>. Each story links to at most two entries; datasets outside the list are kept as candidates below. Access tiers are general guidance — check what UMD actually licenses.</p>`;
    const groups = Object.entries(REG.categories).map(([cat, label]) => [label, visible.filter(d => d.category === cat)]).filter(([, ds]) => ds.length);
    const dsRow = d => {
      const its = used(d.id).sort((a, b) => b.date.localeCompare(a.date));
      const name = d.url ? `<a href="${esc(d.url)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${hi(d.name)}</a>` : hi(d.name);
      return `<details class="ds${its.length ? '' : ' unused'}" ${q && its.length ? 'open' : ''}>
        <summary>${name}<span class="badge ${d.access}">${esc(REG.access[d.access])}</span><span class="n">${its.length || ''}</span></summary>
        ${d.alt ? `<div class="alt">Alternative / note: ${esc(d.alt)}</div>` : ''}
        ${its.map(it => row(it, {withDate: true, showRq: true})).join('')}</details>`;
    };
    const body = groups.length ? groups.map(([label, ds]) => `<section class="card"><h3 style="font-size:16px">${esc(label)}</h3>
      ${ds.map(dsRow).join('')}</section>`).join('') : '<div class="empty">No datasets match.</div>';
    const cands = D.candidates.filter(c => !q || c.name.toLowerCase().includes(q));
    const candHtml = cands.length ? `<details class="card"><summary>Candidates not in your list · ${cands.length}</summary>
      <p class="help" style="margin-top:8px">Named in stories but not in <code>datasets.yaml</code>. Ones mentioned 2+ times also appear in the weekly review; add the useful ones to the list.</p>
      ${cands.map(c => `<div class="paper">${esc(c.name)} <span class="meta">· ${c.mentions} mention${c.mentions === 1 ? '' : 's'}</span></div>`).join('')}</details>` : '';
    return filters + body + candHtml;
  },
  starred() {
    const its = ITEMS.filter(it => Stars.isStarred(it.id) && matchQ(it)).sort((a, b) => b.date.localeCompare(a.date));
    bar('★ Starred', `${its.length} stor${its.length === 1 ? 'y' : 'ies'}`, !!state.q);
    const conn = Stars.connected()
      ? `GitHub connected in this browser · <button class="clear" data-act="disconnect">Disconnect</button>`
      : `<button class="clear" data-act="connect">Connect GitHub</button> (one-time, needed to star from this browser)`;
    const help = `<p class="help">Click ☆ to star a story and ★ to un-star it. Starred stories and their notes steer future picks
      and the weekly review.<br>${conn}</p>`;
    return help + (its.length ? `<div class="card">${its.map(it => row(it, {withDate: true, showRq: true, note: Stars.note(it.id)})).join('')}</div>`
      : '<div class="empty">Nothing starred yet.</div>');
  },
  weekly() {
    bar('Weekly reviews', 'every Sunday');
    return D.weekly.length ? D.weekly.map(w => `<section class="card">
      <h3><a href="weekly/${w.date}.html">Week ending ${fmt(w.date)}</a></h3>
      <p class="intro">${esc(w.overview)}</p>
      ${w.ideas.map(t => `<div class="paper">💡 ${esc(t)}</div>`).join('')}</section>`).join('')
      : '<div class="empty">The first weekly review arrives on Sunday.</div>';
  },
};

function toHash() {
  const p = new URLSearchParams();
  if (state.open) p.set('thread', state.open);
  else if (state.tab !== 'issues') p.set('tab', state.tab);
  if (state.theme) p.set('theme', state.theme);
  state.kws.forEach(k => p.append('kw', k));
  if (state.day) p.set('day', state.day);
  else if (state.month) p.set('month', state.month);
  if (state.page > 1) p.set('page', state.page);
  return p.toString();
}
function fromHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  const tab = p.get('tab');
  state = {...state, tab: VIEWS[tab] ? tab : 'issues', theme: p.get('theme'), kws: [...p.getAll('kw'), ...p.getAll('tag')], open: p.get('thread'),
           day: p.get('day'), month: p.get('month'), page: +p.get('page') || 1};
  if (state.day || state.month) calView = (state.day || state.month).slice(0, 7);
  if (state.open) state.tab = 'threads';
}

function update() {
  const h = toHash();
  history.replaceState(null, '', h ? '#' + h : location.pathname);
  renderSide();
  renderCal();
  $('list').innerHTML = VIEWS[state.tab]();
}

document.addEventListener('click', e => {
  const tab = e.target.closest('.tab');
  if (tab) { state = {...state, tab: tab.dataset.tab, open: null}; return update(); }
  const th = e.target.closest('[data-thread]');
  if (th) { e.preventDefault(); state = {...state, tab: 'threads', open: th.dataset.thread}; update(); return window.scrollTo({top: 0, behavior: 'smooth'}); }
  const nt = e.target.closest('[data-note]');
  if (nt) {
    const id = nt.dataset.note, v = prompt('Why is this story interesting? (used to guide future picks)', Stars.note(id));
    if (v !== null) Stars.setNote(id, v.trim());
    return;
  }
  const cal = e.target.closest('[data-calnav],[data-calmonth],[data-calday],[data-calall],[data-page]');
  if (cal) {
    const ds = cal.dataset;
    if (ds.calnav) { calView = shiftMonth(calView, +ds.calnav); return renderCal(); }
    if (ds.page) { state.page = +ds.page; update(); return $('bar').scrollIntoView({behavior: 'smooth'}); }
    if (ds.calall !== undefined) state = {...state, day: null, month: null};
    else if (ds.calmonth) state = {...state, day: null, month: state.month === ds.calmonth ? null : ds.calmonth};
    else state = {...state, month: null, day: state.day === ds.calday ? null : ds.calday};
    state = {...state, tab: 'issues', open: null, page: 1};
    update(); return (NARROW.matches ? $('bar') : document.body).scrollIntoView({behavior: 'smooth'});
  }
  const dsa = e.target.closest('[data-dsaccess]');
  if (dsa) { dsAccess = dsa.dataset.dsaccess || null; return update(); }
  if (e.target.closest('[data-dsall]')) { dsShowAll = !dsShowAll; return update(); }
  const act = e.target.closest('[data-act]');
  if (act && act.dataset.act === 'connect') return Stars.connect(update);
  if (act && act.dataset.act === 'disconnect') { Stars.disconnect(); return update(); }
  const c = e.target.closest('.chip[data-kind]');
  if (!c) return;
  e.preventDefault();
  const {kind, tag} = c.dataset;
  if (kind === 'theme') state.theme = state.theme === tag ? null : tag;
  else state.kws = state.kws.includes(tag) ? state.kws.filter(k => k !== tag) : [...state.kws, tag];
  state = {...state, tab: 'issues', open: null, page: 1};
  update(); (NARROW.matches ? $('bar') : document.body).scrollIntoView({behavior: 'smooth'});
});
$('moreKw').onclick = () => { showAllKw = !showAllKw; renderSide(); };
$('q').oninput = e => { state.q = e.target.value.trim(); state.page = 1; renderSide(); $('list').innerHTML = VIEWS[state.tab](); };
document.addEventListener('change', e => {
  if (e.target.id !== 'perPage') return;
  perPage = +e.target.value; state.page = 1;
  try { localStorage.setItem('perPage', perPage); } catch (err) {}
  update();
});
window.addEventListener('hashchange', () => { fromHash(); update(); });
Stars.onChange(update);

fromHash();
$('kwBox').open = !NARROW.matches;
update();
</script>
__TOGGLE_JS__
</body></html>
"""


if __name__ == "__main__":
    import yaml
    root = Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load((root / "config.yaml").read_text())
    issues_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "data" / "issues"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "docs"
    build(issues_dir, out_dir, cfg["digest"]["title"], cfg.get("github_repo", ""), byline=cfg["digest"].get("byline", ""),
          analytics=cfg.get("analytics"))
    print(f"Archive built: {out_dir / 'index.html'}")
