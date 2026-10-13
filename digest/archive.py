"""Build a static archive site (docs/) from data/issues/*.json.

  python -m digest.archive            # rebuild docs/ from data/issues
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from .render import render_html


def _issues(issues_dir: Path) -> list[tuple[str, dict]]:
    return [(p.stem, json.loads(p.read_text())) for p in sorted(issues_dir.glob("*.json"))]


def known_keywords(issues_dir: Path, limit: int = 200) -> list[str]:
    counts = Counter(k.strip().lower() for _, iss in _issues(issues_dir)
                     for it in iss["items"] for k in it["keywords"])
    return [k for k, _ in counts.most_common(limit)]


def build(issues_dir: Path, out_dir: Path, title: str) -> None:
    issues = _issues(issues_dir)
    (out_dir / "issues").mkdir(parents=True, exist_ok=True)

    records = []
    for iso, iss in issues:
        date_str = date.fromisoformat(iso).strftime("%A, %B %-d, %Y")
        (out_dir / "issues" / f"{iso}.html").write_text(render_html(title, date_str, iss, "../index.html"))
        records.append({
            "date": iso,
            "intro": iss["intro"],
            "items": [{"n": n, "headline": it["headline"], "theme": it["theme"], "source": it["source"],
                       "summary": it["summary"], "rq": it["research_question"],
                       "related": [r["title"] for r in it.get("related", [])],
                       "keywords": [k.strip().lower() for k in it["keywords"]]}
                      for n, it in enumerate(iss["items"], 1)],
            "papers": [{"title": p["title"], "journal": p["journal"], "url": p["url"]} for p in iss["papers"]],
            "also": [{"title": a["title"], "url": a["url"], "source": a["source"]} for a in iss.get("also", [])],
        })
    records.sort(key=lambda r: r["date"], reverse=True)
    data = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    (out_dir / "index.html").write_text(INDEX.replace("__TITLE__", title).replace("__DATA__", data))
    (out_dir / ".nojekyll").touch()


INDEX = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ Archive</title>
<style>
:root{--bg:#f4f3ef;--card:#fff;--ink:#1d1d1b;--muted:#6b6a65;--line:#dcdad3;--accent:#1f6f5c;--chip:#ebe9e2;--chip-on:#1d1d1b;--chip-on-ink:#f4f3ef}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--card:#20201e;--ink:#ecebe6;--muted:#9c9a93;--line:#34332f;--accent:#6fc2a8;--chip:#2b2a27;--chip-on:#ecebe6;--chip-on-ink:#161615}}
:root[data-theme="dark"]{--bg:#161615;--card:#20201e;--ink:#ecebe6;--muted:#9c9a93;--line:#34332f;--accent:#6fc2a8;--chip:#2b2a27;--chip-on:#ecebe6;--chip-on-ink:#161615}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:28px 16px 64px}
h1{font-family:Georgia,"Times New Roman",serif;font-size:30px;margin:0}
.sub{color:var(--muted);margin:4px 0 20px}
a{color:inherit}
.layout{display:grid;grid-template-columns:280px 1fr;gap:28px;align-items:start}
@media (max-width:760px){.layout{grid-template-columns:1fr}}
aside{position:sticky;top:16px}
@media (max-width:760px){aside{position:static}}
input[type=search]{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);font:inherit}
details{margin-top:18px}
summary{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);cursor:pointer;list-style:none;display:flex;align-items:center;gap:6px;padding:4px 0;user-select:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"▸";font-size:11px;transition:transform .15s}
details[open] summary::before{transform:rotate(90deg)}
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
.day{background:var(--card);border-radius:10px;padding:18px 20px;margin-bottom:14px}
.day h3{margin:0 0 4px;font-family:Georgia,serif;font-size:19px}
.day h3 a{text-decoration:none}
.day .intro{color:var(--muted);font-size:14px;margin:0 0 10px}
.row{display:block;padding:9px 0;border-top:1px solid var(--line);text-decoration:none}
.row:hover .hl{text-decoration:underline}
.meta{font-size:12px;color:var(--muted)}
.theme{font-weight:600;color:var(--accent)}
.hl{font-weight:600}
.kw{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}
.kw .chip{font-size:11px;padding:2px 8px}
.snip{font-size:13px;color:var(--muted);margin-top:3px}
.paper{font-size:13px;color:var(--muted);padding-top:8px;border-top:1px dashed var(--line)}
.empty{color:var(--muted);padding:24px 0}
mark{background:#f2dc8a;color:#1d1d1b;border-radius:2px}
</style></head>
<body><div class="wrap">
<h1>__TITLE__</h1>
<div class="sub" id="stats"></div>
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
const DATA = JSON.parse(document.getElementById('data').textContent);
const ITEMS = DATA.flatMap(d => d.items.map(it => ({...it, date: d.date})));
const $ = id => document.getElementById(id);
const esc = s => s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = iso => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric', year:'numeric'});
const link = it => `issues/${it.date}.html#item-${it.n}`;
let state = {kind: null, tag: null, q: ''}, showAllKw = false;
const NARROW = matchMedia('(max-width:760px)'), KW_TOP = () => NARROW.matches ? 12 : 30;

function counts(key) {
  const m = new Map();
  ITEMS.forEach(it => [].concat(it[key]).forEach(v => m.set(v, (m.get(v) || 0) + 1)));
  return [...m].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}
const THEMES = counts('theme'), KEYWORDS = counts('keywords');

function chip(kind, v, n) {
  const on = state.kind === kind && state.tag === v;
  return `<button class="chip${on ? ' on' : ''}" data-kind="${kind}" data-tag="${esc(v)}">${esc(v)}${n ? `<small>${n}</small>` : ''}</button>`;
}

function renderSide() {
  $('themes').innerHTML = THEMES.map(([v, n]) => chip('theme', v, n)).join('');
  const kws = showAllKw ? KEYWORDS : KEYWORDS.slice(0, KW_TOP());
  $('keywords').innerHTML = kws.map(([v, n]) => chip('keywords', v, n)).join('');
  $('moreKw').hidden = KEYWORDS.length <= KW_TOP();
  $('moreKw').textContent = showAllKw ? 'Show fewer' : `Show all ${KEYWORDS.length}`;
}

function hi(s) {
  if (!state.q) return esc(s);
  const re = new RegExp('(' + state.q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
  return esc(s).replace(re, '<mark>$1</mark>');
}

function row(it, withDate) {
  const kw = it.keywords.map(k => chip('keywords', k)).join('');
  return `<div class="row"><a href="${link(it)}" style="text-decoration:none">
    <div class="meta">${withDate ? fmt(it.date) + ' · ' : ''}<span class="theme">${esc(it.theme)}</span> · ${esc(it.source)}</div>
    <div class="hl">${hi(it.headline)}</div>
    ${state.q ? `<div class="snip">${hi(it.summary)}</div>` : ''}</a>
    <div class="kw">${kw}</div></div>`;
}

function renderMain() {
  const q = state.q.toLowerCase();
  if (state.tag || q) {
    const hits = ITEMS.filter(it =>
      (!state.tag || [].concat(it[state.kind]).includes(state.tag)) &&
      (!q || (it.headline + ' ' + it.summary + ' ' + it.rq + ' ' + it.keywords.join(' ') + ' ' + (it.related || []).join(' ')).toLowerCase().includes(q)))
      .sort((a, b) => b.date.localeCompare(a.date) || a.n - b.n);
    const label = [state.tag && `“${esc(state.tag)}”`, q && `search “${esc(state.q)}”`].filter(Boolean).join(' + ');
    $('bar').innerHTML = `<strong>${label}</strong><span class="meta">${hits.length} article${hits.length === 1 ? '' : 's'}</span><button class="clear" id="clear">Clear</button>`;
    $('list').innerHTML = hits.length ? `<div class="day">${hits.map(it => row(it, true)).join('')}</div>` : '<div class="empty">No matching articles.</div>';
    $('clear').onclick = () => { state = {kind: null, tag: null, q: ''}; $('q').value = ''; update(); };
  } else {
    $('bar').innerHTML = `<strong>All issues</strong><span class="meta">newest first</span>`;
    $('list').innerHTML = DATA.length ? DATA.map(d => `<section class="day">
      <h3><a href="issues/${d.date}.html">${fmt(d.date)}</a></h3>
      <p class="intro">${esc(d.intro)}</p>
      ${d.items.map(it => row({...it, date: d.date}, false)).join('')}
      ${d.papers.map(p => `<div class="paper">📄 <a href="${esc(p.url)}">${esc(p.title)}</a> — ${esc(p.journal)}</div>`).join('')}
      ${(d.also || []).length ? `<details class="also"><summary>Also worth noting · ${d.also.length}</summary>${d.also.map(a => `<div class="paper"><a href="${esc(a.url)}">${esc(a.title)}</a> — ${esc(a.source)}</div>`).join('')}</details>` : ''}
    </section>`).join('') : '<div class="empty">No issues yet.</div>';
  }
}

function update() {
  const h = state.tag ? `#${state.kind === 'theme' ? 'theme' : 'tag'}=${encodeURIComponent(state.tag)}` : ' ';
  history.replaceState(null, '', h === ' ' ? location.pathname : h);
  renderSide(); renderMain();
}

document.addEventListener('click', e => {
  const c = e.target.closest('.chip');
  if (!c) return;
  e.preventDefault();
  const {kind, tag} = c.dataset;
  state = state.tag === tag && state.kind === kind ? {...state, kind: null, tag: null} : {...state, kind, tag};
  update(); (NARROW.matches ? $('bar') : document.body).scrollIntoView({behavior: 'smooth'});
});
$('moreKw').onclick = () => { showAllKw = !showAllKw; renderSide(); };
$('q').oninput = e => { state.q = e.target.value.trim(); renderMain(); };

const m = location.hash.match(/^#(tag|theme)=(.+)$/);
if (m) state = {kind: m[1] === 'theme' ? 'theme' : 'keywords', tag: decodeURIComponent(m[2]), q: ''};
$('kwBox').open = !NARROW.matches;
$('nThemes').textContent = THEMES.length; $('nKw').textContent = KEYWORDS.length;
$('stats').textContent = `${DATA.length} issue${DATA.length === 1 ? '' : 's'} · ${ITEMS.length} articles · ${KEYWORDS.length} keywords`;
update();
</script>
</body></html>
"""


if __name__ == "__main__":
    import yaml
    root = Path(__file__).resolve().parent.parent
    title = yaml.safe_load((root / "config.yaml").read_text())["digest"]["title"]
    issues_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "data" / "issues"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "docs"
    build(issues_dir, out_dir, title)
    print(f"Archive built: {out_dir / 'index.html'}")
