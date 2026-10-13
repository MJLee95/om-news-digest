"""Build a static archive site (docs/) from data/issues/*.json and data/weekly/*.json.

  python -m digest.archive            # rebuild docs/ (fetches stars from GitHub)
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from . import theme_toggle
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


def known_datasets(issues_dir: Path, limit: int = 150) -> list[str]:
    counts = Counter(ds.strip() for i in all_items(issues_dir) for ds in i["datasets"])
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


def build(issues_dir: Path, out_dir: Path, title: str, repo: str = "", stars: dict | None = None) -> None:
    if stars is None:
        from .stars import fetch_stars
        stars = fetch_stars(repo)
    issues = _issues(issues_dir)
    (out_dir / "issues").mkdir(parents=True, exist_ok=True)
    thread_of = threads(all_items(issues_dir))
    starred = frozenset(stars)

    records = []
    for iso, iss in issues:
        date_str = date.fromisoformat(iso).strftime("%A, %B %-d, %Y")
        (out_dir / "issues" / f"{iso}.html").write_text(
            render_html(title, date_str, iss, "../index.html", web=True, iso=iso, repo=repo, starred=starred))
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
            (out_dir / "weekly" / f"{p.stem}.html").write_text(render_weekly(title, p.stem, wk, "../index.html", web=True))
            weekly.append({"date": p.stem, "overview": wk["overview"], "ideas": [i["title"] for i in wk["ideas"]]})

    from .stars import star_url
    payload = {
        "issues": records,
        "stars": {k: {"note": v["note"], "url": v["url"]} for k, v in stars.items()},
        "starUrls": {it["id"]: star_url(repo, it["id"], it["headline"]) for r in records for it in r["items"]} if repo else {},
        "weekly": weekly,
        "repo": repo,
    }
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    page = (INDEX.replace("__TOGGLE_HEAD__", theme_toggle.HEAD_JS).replace("__TOGGLE_CSS__", theme_toggle.CSS)
            .replace("__TOGGLE_BUTTON__", theme_toggle.BUTTON).replace("__TOGGLE_JS__", theme_toggle.BODY_JS)
            .replace("__TITLE__", title).replace("__DATA__", data))
    (out_dir / "index.html").write_text(page)
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
</style></head>
<body><div class="wrap">
__TOGGLE_BUTTON__
<h1>__TITLE__</h1>
<div class="sub" id="stats"></div>
<nav class="tabs" id="tabs"></nav>
<div class="layout">
<aside>
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
const ISSUES = D.issues;
const ITEMS = ISSUES.flatMap(d => d.items.map(it => ({...it, date: d.date})));
const BY_ID = Object.fromEntries(ITEMS.map(it => [it.id, it]));
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric', year:'numeric'});
const short = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', {month:'short', day:'numeric'});
const link = it => `issues/${it.date}.html#item-${it.n}`;
const NARROW = matchMedia('(max-width:760px)'), KW_TOP = () => NARROW.matches ? 12 : 30;

// stars: GitHub issues (synced at build) + ones clicked since then (kept in this browser until the next build)
let pending = [];
try { pending = JSON.parse(localStorage.getItem('pendingStars') || '[]').filter(id => !D.stars[id]); } catch (e) {}
const isStarred = id => !!D.stars[id] || pending.includes(id);
function addPending(id) {
  if (isStarred(id)) return;
  pending.push(id);
  try { localStorage.setItem('pendingStars', JSON.stringify(pending)); } catch (e) {}
}

// threads
const THREADS = {};
ITEMS.forEach(it => { if (it.thread) (THREADS[it.thread] ||= []).push(it); });
Object.values(THREADS).forEach(list => list.sort((a, b) => a.date.localeCompare(b.date) || a.n - b.n));
const THREAD_LIST = Object.entries(THREADS).sort((a, b) => b[1].at(-1).date.localeCompare(a[1].at(-1).date));

// datasets
const DATASETS = {};
ITEMS.forEach(it => (it.datasets || []).forEach(ds => (DATASETS[ds] ||= []).push(it)));
const DATASET_LIST = Object.entries(DATASETS).sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]));

let state = {tab: 'issues', kind: null, tag: null, q: '', open: null}, showAllKw = false;

function counts(key) {
  const m = new Map();
  ITEMS.forEach(it => [].concat(it[key]).forEach(v => m.set(v, (m.get(v) || 0) + 1)));
  return [...m].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}
const THEMES = counts('theme'), KEYWORDS = counts('keywords');

const TABS = [
  ['issues', 'Issues', ISSUES.length],
  ['threads', 'Story threads', THREAD_LIST.length],
  ['datasets', 'Datasets', DATASET_LIST.length],
  ['starred', '★ Starred', null],
  ['weekly', 'Weekly reviews', D.weekly.length],
];

function chip(kind, v, n) {
  const on = state.kind === kind && state.tag === v;
  return `<button class="chip${on ? ' on' : ''}" data-kind="${kind}" data-tag="${esc(v)}">${esc(v)}${n ? `<small>${n}</small>` : ''}</button>`;
}

function hi(s) {
  if (!state.q) return esc(s);
  const re = new RegExp('(' + state.q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
  return esc(s).replace(re, '<mark>$1</mark>');
}

function starLink(it) {
  const on = isStarred(it.id), url = D.stars[it.id]?.url || D.starUrls[it.id];
  if (!url) return '';
  return `<a class="star${on ? ' on' : ''}" data-star="${esc(it.id)}" href="${esc(url)}" target="_blank" rel="noopener"
    title="${on ? 'Starred' : 'Star this story (opens a prefilled GitHub issue)'}">${on ? '★' : '☆'}</a>`;
}

function row(it, {withDate = false, showRq = false, note = ''} = {}) {
  const thread = it.thread && THREADS[it.thread].length > 1
    ? `<button class="chip thread" data-thread="${esc(it.thread)}">🧵 ${THREADS[it.thread].length} in thread</button>` : '';
  const kw = it.keywords.map(k => chip('keywords', k)).join('');
  return `<div class="row">${starLink(it)}<div class="body"><a class="go" href="${link(it)}">
    <div class="meta">${withDate ? fmt(it.date) + ' · ' : ''}<span class="theme">${esc(it.theme)}</span> · ${esc(it.source)}</div>
    <div class="hl">${hi(it.headline)}</div>
    ${state.q ? `<div class="snip">${hi(it.summary)}</div>` : ''}
    ${showRq ? `<div class="snip"><b>Q:</b> ${hi(it.rq)}</div>` : ''}</a>
    ${note ? `<div class="note">${esc(note)}</div>` : ''}
    <div class="kw">${thread}${kw}</div></div></div>`;
}

const matchQ = it => !state.q || (it.headline + ' ' + it.summary + ' ' + it.rq + ' ' + it.keywords.join(' ') + ' ' +
  (it.related || []).join(' ') + ' ' + (it.datasets || []).join(' ')).toLowerCase().includes(state.q.toLowerCase());

function renderSide() {
  $('themes').innerHTML = THEMES.map(([v, n]) => chip('theme', v, n)).join('');
  const kws = showAllKw ? KEYWORDS : KEYWORDS.slice(0, KW_TOP());
  $('keywords').innerHTML = kws.map(([v, n]) => chip('keywords', v, n)).join('');
  $('moreKw').hidden = KEYWORDS.length <= KW_TOP();
  $('moreKw').textContent = showAllKw ? 'Show fewer' : `Show all ${KEYWORDS.length}`;
  const nStar = ITEMS.filter(it => isStarred(it.id)).length;
  $('tabs').innerHTML = TABS.map(([k, label, n]) =>
    `<button class="tab${state.tab === k ? ' on' : ''}" data-tab="${k}">${label}<small>${k === 'starred' ? nStar : n}</small></button>`).join('');
}

function bar(title, sub, clear) {
  $('bar').innerHTML = `<strong>${title}</strong>${sub ? `<span class="meta">${sub}</span>` : ''}${clear ? '<button class="clear" id="clear">Clear</button>' : ''}`;
  if (clear) $('clear').onclick = () => { state = {...state, kind: null, tag: null, q: '', open: null}; $('q').value = ''; update(); };
}

const VIEWS = {
  issues() {
    if (state.tag || state.q) {
      const hits = ITEMS.filter(it => (!state.tag || [].concat(it[state.kind]).includes(state.tag)) && matchQ(it))
        .sort((a, b) => b.date.localeCompare(a.date) || a.n - b.n);
      const label = [state.tag && `“${esc(state.tag)}”`, state.q && `search “${esc(state.q)}”`].filter(Boolean).join(' + ');
      bar(label, `${hits.length} article${hits.length === 1 ? '' : 's'}`, true);
      return hits.length ? `<div class="card">${hits.map(it => row(it, {withDate: true})).join('')}</div>` : '<div class="empty">No matching articles.</div>';
    }
    bar('All issues', 'newest first');
    return ISSUES.length ? ISSUES.map(d => `<section class="card">
      <h3><a href="issues/${d.date}.html">${fmt(d.date)}</a></h3>
      <p class="intro">${esc(d.intro)}</p>
      ${d.items.map(it => row({...it, date: d.date})).join('')}
      ${d.papers.map(p => `<div class="paper">📄 <a href="${esc(p.url)}">${esc(p.title)}</a> — ${esc(p.journal)}</div>`).join('')}
      ${(d.also || []).length ? `<details><summary>Also worth noting · ${d.also.length}</summary>${d.also.map(a => `<div class="paper"><a href="${esc(a.url)}">${esc(a.title)}</a> — ${esc(a.source)}</div>`).join('')}</details>` : ''}
    </section>`).join('') : '<div class="empty">No issues yet.</div>';
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
    const list = DATASET_LIST.map(([ds, its]) => [ds, its.filter(matchQ)])
      .filter(([ds, its]) => its.length || (state.q && ds.toLowerCase().includes(state.q.toLowerCase())));
    bar('Datasets', 'data sources suggested so far, with the questions they could answer', !!state.q);
    if (!list.length) return `<div class="empty">${DATASET_LIST.length ? 'No matching datasets.' : 'No datasets recorded yet. They are collected from each story\'s “Data / ID” suggestions starting with the next issue.'}</div>`;
    return list.map(([ds, its]) => `<details class="card" ${state.q ? 'open' : ''}>
      <summary style="font-size:15px;letter-spacing:0;text-transform:none;color:var(--ink);font-weight:600">${hi(ds)}<span class="n">${its.length}</span></summary>
      ${its.slice().sort((a, b) => b.date.localeCompare(a.date)).map(it => row(it, {withDate: true, showRq: true})).join('')}</details>`).join('');
  },
  starred() {
    const its = ITEMS.filter(it => isStarred(it.id) && matchQ(it)).sort((a, b) => b.date.localeCompare(a.date));
    bar('★ Starred', `${its.length} stor${its.length === 1 ? 'y' : 'ies'}`, !!state.q);
    const help = `<p class="help">Click ☆ next to any story. GitHub opens a prefilled issue; add a note if you like and press <b>Create</b>.
      Starred stories steer future picks and the weekly review. To un-star, close that issue on GitHub.
      New stars show here right away in this browser and sync for everyone at the next daily run.</p>`;
    return help + (its.length ? `<div class="card">${its.map(it => row(it, {withDate: true, showRq: true,
      note: D.stars[it.id]?.note || (pending.includes(it.id) ? 'Pending — syncs at the next daily run.' : '')})).join('')}</div>`
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

function update() {
  const h = state.tag ? `#${state.kind === 'theme' ? 'theme' : 'tag'}=${encodeURIComponent(state.tag)}`
    : state.open ? `#thread=${encodeURIComponent(state.open)}` : state.tab !== 'issues' ? `#tab=${state.tab}` : '';
  history.replaceState(null, '', h || location.pathname);
  renderSide();
  $('list').innerHTML = VIEWS[state.tab]();
}

document.addEventListener('click', e => {
  const tab = e.target.closest('.tab');
  if (tab) { state = {...state, tab: tab.dataset.tab, kind: null, tag: null, open: null}; return update(); }
  const th = e.target.closest('[data-thread]');
  if (th) { e.preventDefault(); state = {...state, tab: 'threads', kind: null, tag: null, open: th.dataset.thread}; update(); return window.scrollTo({top: 0, behavior: 'smooth'}); }
  const st = e.target.closest('[data-star]');
  if (st) { addPending(st.dataset.star); setTimeout(update, 50); return; }
  const c = e.target.closest('.chip[data-kind]');
  if (!c) return;
  e.preventDefault();
  const {kind, tag} = c.dataset;
  state = state.tag === tag && state.kind === kind ? {...state, kind: null, tag: null} : {...state, tab: 'issues', kind, tag, open: null};
  update(); (NARROW.matches ? $('bar') : document.body).scrollIntoView({behavior: 'smooth'});
});
$('moreKw').onclick = () => { showAllKw = !showAllKw; renderSide(); };
$('q').oninput = e => { state.q = e.target.value.trim(); $('list').innerHTML = VIEWS[state.tab](); };

function fromHash() {
  const m = location.hash.match(/^#(tag|theme|thread|tab)=(.+)$/);
  if (!m) return;
  const v = decodeURIComponent(m[2]);
  state = {...state, kind: null, tag: null, open: null};
  if (m[1] === 'tab' && VIEWS[v]) state.tab = v;
  else if (m[1] === 'thread') state = {...state, tab: 'threads', open: v};
  else if (m[1] !== 'tab') state = {...state, tab: 'issues', kind: m[1] === 'theme' ? 'theme' : 'keywords', tag: v};
}
fromHash();
window.addEventListener('hashchange', () => { fromHash(); update(); });
$('kwBox').open = !NARROW.matches;
$('nThemes').textContent = THEMES.length; $('nKw').textContent = KEYWORDS.length;
$('stats').textContent = `${ISSUES.length} issue${ISSUES.length === 1 ? '' : 's'} · ${ITEMS.length} articles · ${KEYWORDS.length} keywords`;
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
    build(issues_dir, out_dir, cfg["digest"]["title"], cfg.get("github_repo", ""))
    print(f"Archive built: {out_dir / 'index.html'}")
