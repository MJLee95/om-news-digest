"""Render the digest as HTML (email: inline hex colors; web: the same markup with CSS variables
so the archive copy follows light/dark mode) and a plain-text fallback."""

from __future__ import annotations

from html import escape

from . import theme_toggle
from .stars import star_url

LIGHT = {"bg": "#f4f3ef", "card": "#ffffff", "ink": "#1d1d1b", "ink2": "#3a3935", "ink3": "#2f2e2b",
         "muted": "#6b6a65", "faint": "#8f8d86", "line": "#dcdad3", "box": "#1d1d1b", "boxink": "#f4f3ef",
         "gold": "#d9c48f", "accent": "#1f6f5c",
         "t0": "#1f6f5c", "t1": "#8a5a00", "t2": "#2b5ea7", "t3": "#7a3e8f", "t4": "#a8402f", "t5": "#4b6b1f"}
DARK = {"bg": "#161615", "card": "#20201e", "ink": "#ecebe6", "ink2": "#c9c7c0", "ink3": "#d6d4cd",
        "muted": "#9c9a93", "faint": "#7d7b75", "line": "#34332f", "box": "#2b2a27", "boxink": "#ecebe6",
        "gold": "#d9c48f", "accent": "#6fc2a8",
        "t0": "#6fc2a8", "t1": "#e0a845", "t2": "#86aee8", "t3": "#c493d6", "t4": "#e8907c", "t5": "#a3c873"}
N_THEME_COLORS = 6
EMAIL_PALETTE = LIGHT
WEB_PALETTE = {k: f"var(--{k})" for k in LIGHT}


def _color(theme: str, themes: list[str], P: dict) -> str:
    return P[f"t{themes.index(theme) % N_THEME_COLORS}"]


def _related_html(rel: list[dict], color: str, P: dict) -> str:
    if not rel:
        return ""
    rows = "".join(
        f'<div style="margin:6px 0 0;"><a href="{escape(r["url"])}" style="color:{P['ink']};font-weight:bold;">{escape(r["title"])}</a>'
        f' <span style="color:{P['muted']};">({escape(r["journal"])}, {r["year"]})</span><br>'
        f'<span style="color:{P['ink2']};">{escape(r["why"])}</span></div>'
        for r in rel)
    return (f'<div style="margin-top:10px;padding-top:10px;border-top:1px dashed {P['line']};font-family:Helvetica,Arial,sans-serif;font-size:13px;line-height:1.5;">'
            f'<div style="font-size:11px;font-weight:bold;letter-spacing:.06em;text-transform:uppercase;color:{color};">Related research</div>{rows}</div>')


def render_html(title: str, date_str: str, issue: dict, archive_link: str = "", web: bool = False,
                iso: str = "", repo: str = "", starred: frozenset = frozenset()) -> str:
    """web=True: archive copy with CSS-variable colors and the Light/Dark/System toggle.

    archive_link: archive home (absolute URL in email, relative in web copies). iso: the issue date,
    used for item ids ('2026-10-13#2'). repo: GitHub repo for star links.
    """
    def item_href(item_id: str) -> str:
        d, n = item_id.split("#")
        if web:
            return f"{d}.html#item-{n}"
        return f"{archive_link}issues/{d}.html#item-{n}" if archive_link else ""
    themes = list(dict.fromkeys(i["theme"] for i in issue["items"]))
    e = escape
    P = WEB_PALETTE if web else EMAIL_PALETTE
    toggle_vars = {"toggle-bg": "var(--card)", "toggle-ink": "var(--ink)", "toggle-line": "var(--line)"}
    web_head = (f"{theme_toggle.HEAD_JS}<style>{theme_toggle.themed_vars({**LIGHT, **toggle_vars}, {**DARK, **toggle_vars})}"
                f"{theme_toggle.CSS}html{{background:var(--bg)}}</style>") if web else ""
    parts = [f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} — {e(date_str)}</title>{web_head}</head>
<body style="margin:0;padding:0;background:{P['bg']};">{theme_toggle.BUTTON if web else ''}
<div style="max-width:640px;margin:0 auto;padding:24px 16px;font-family:Georgia,'Times New Roman',serif;color:{P['ink']};">
{f'<a href="{e(archive_link)}" style="font-family:Helvetica,Arial,sans-serif;font-size:13px;color:{P['accent']};text-decoration:none;">&larr; Archive</a>' if archive_link else ''}
<div style="font-family:Helvetica,Arial,sans-serif;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:{P['muted']};">{e(title)}</div>
<h1 style="margin:4px 0 12px;font-size:28px;line-height:1.2;">{e(date_str)}</h1>
<p style="margin:0 0 24px;font-size:16px;line-height:1.55;color:{P['ink2']};">{e(issue['intro'])}</p>"""]

    for n, it in enumerate(issue["items"], 1):
        c = _color(it["theme"], themes, P)
        kw = " · ".join(e(k) for k in it["keywords"])
        item_id = f"{iso}#{n}"
        star = ""
        if repo and iso:
            on = item_id in starred
            star = (f' · <a href="{e(star_url(repo, item_id, it["headline"]))}" style="color:{c};text-decoration:none;" '
                    f'title="{"Starred" if on else "Star this story (opens GitHub)"}">{"★ Starred" if on else "☆ Star"}</a>')
        follows = ""
        if it.get("follows"):
            links = ", ".join(
                (f'<a href="{e(item_href(f["id"]))}" style="color:{c};">{e(f["label"])}</a>' if item_href(f["id"]) else e(f["label"]))
                for f in it["follows"])
            follows = (f'<div style="font-family:Helvetica,Arial,sans-serif;font-size:12px;color:{P["muted"]};margin:0 0 8px;">'
                       f'↳ Follow-up to {links}</div>')
        parts.append(f"""
<div id="item-{n}" style="background:{P['card']};border-radius:10px;padding:20px 20px 16px;margin:0 0 16px;border-left:4px solid {c};scroll-margin-top:16px;">
  <div style="font-family:Helvetica,Arial,sans-serif;font-size:11px;font-weight:bold;letter-spacing:.06em;text-transform:uppercase;color:{c};">{n:02d} · {e(it['theme'])}</div>
  <h2 style="margin:6px 0 4px;font-size:19px;line-height:1.3;"><a href="{e(it['url'])}" style="color:{P['ink']};text-decoration:none;">{e(it['headline'])}</a></h2>
  <div style="font-family:Helvetica,Arial,sans-serif;font-size:12px;color:{P['muted']};margin-bottom:10px;">{e(it['source'])}{(' · ' + e(it['date'])) if it.get('date') else ''} · <a href="{e(it['url'])}" style="color:{c};">Read</a>{star}</div>
  {follows}<p style="margin:0 0 12px;font-size:15px;line-height:1.55;">{e(it['summary'])}</p>
  <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;font-family:Helvetica,Arial,sans-serif;font-size:13px;line-height:1.5;color:{P['ink3']};">
    <tr><td style="padding:6px 0;vertical-align:top;width:92px;color:{P['muted']};">OM angle</td><td style="padding:6px 0;">{e(it['om_angle'])}</td></tr>
    <tr><td style="padding:6px 0;vertical-align:top;color:{P['muted']};">Research Q</td><td style="padding:6px 0;font-weight:bold;">{e(it['research_question'])}</td></tr>
    <tr><td style="padding:6px 0;vertical-align:top;color:{P['muted']};">Data / ID</td><td style="padding:6px 0;">{e(it['data_identification'])}</td></tr>
    <tr><td style="padding:6px 0;vertical-align:top;color:{P['muted']};">Keywords</td><td style="padding:6px 0;color:{P['muted']};">{kw}</td></tr>
  </table>{_related_html(it.get('related', []), c, P)}
</div>""")

    if issue.get("thread_to_pull"):
        parts.append(f"""
<div style="background:{P['box']};color:{P['boxink']};border-radius:10px;padding:20px;margin:24px 0 16px;">
  <div style="font-family:Helvetica,Arial,sans-serif;font-size:11px;font-weight:bold;letter-spacing:.06em;text-transform:uppercase;color:{P['gold']};">Thread to pull</div>
  <p style="margin:8px 0 0;font-size:15px;line-height:1.55;">{e(issue['thread_to_pull'])}</p>
</div>""")

    if issue["papers"]:
        parts.append(f"""<h3 style="font-size:16px;margin:28px 0 8px;font-family:Helvetica,Arial,sans-serif;letter-spacing:.04em;text-transform:uppercase;color:{P['muted']};">New in the journals</h3>""")
        for p in issue["papers"]:
            parts.append(f"""
<div style="border-top:1px solid {P['line']};padding:12px 0;">
  <a href="{e(p['url'])}" style="font-size:16px;color:{P['ink']};font-weight:bold;text-decoration:none;">{e(p['title'])}</a>
  <div style="font-family:Helvetica,Arial,sans-serif;font-size:12px;color:{P['muted']};margin:2px 0 6px;">{e(p['journal'])}</div>
  <p style="margin:0 0 4px;font-size:14px;line-height:1.5;">{e(p['takeaway'])}</p>
  <p style="margin:0;font-size:13px;line-height:1.5;color:{P['ink2']};font-style:italic;">{e(p['connection'])}</p>
</div>""")

    if issue.get("also"):
        rows = "".join(
            f'<div style="padding:7px 0;border-top:1px solid {P['line']};">'
            f'<a href="{e(a["url"])}" style="color:{P['ink']};text-decoration:none;font-size:14px;">{e(a["title"])}</a>'
            f'<div style="font-size:12px;color:{P['muted']};">{e(a["source"])} · {e(a["theme"])}</div></div>'
            for a in issue["also"])
        parts.append(f"""
<h3 style="font-size:16px;margin:28px 0 8px;font-family:Helvetica,Arial,sans-serif;letter-spacing:.04em;text-transform:uppercase;color:{P['muted']};">Also worth noting</h3>
<div style="font-family:Helvetica,Arial,sans-serif;">{rows}</div>""")

    archive = (f' <a href="{e(archive_link)}" style="color:{P['faint']};">Browse the archive</a>.' if archive_link else "")
    parts.append(f"""
<p style="font-family:Helvetica,Arial,sans-serif;font-size:11px;color:{P['faint']};margin-top:28px;line-height:1.5;">
Selected and summarized by Claude from news feeds, Crossref and OpenAlex. Check the original sources before citing.{archive}</p>
</div>{theme_toggle.BODY_JS if web else ''}</body></html>""")
    return "".join(parts)


def render_text(title: str, date_str: str, issue: dict) -> str:
    out = [f"{title} — {date_str}", "", issue["intro"], ""]
    for n, it in enumerate(issue["items"], 1):
        out += [f"{n}. [{it['theme']}] {it['headline']}", f"   {it['source']} — {it['url']}",
                f"   {it['summary']}", f"   OM angle: {it['om_angle']}",
                f"   Research Q: {it['research_question']}", f"   Data/ID: {it['data_identification']}",
                f"   Keywords: {', '.join(it['keywords'])}"]
        out += [f"   Related: {r['title']} ({r['journal']}, {r['year']}) {r['url']}" for r in it.get("related", [])]
        out.append("")
    if issue.get("thread_to_pull"):
        out += ["THREAD TO PULL", issue["thread_to_pull"], ""]
    for p in issue["papers"]:
        out += [f"* {p['title']} ({p['journal']}) {p['url']}", f"  {p['takeaway']}", f"  {p['connection']}", ""]
    if issue.get("also"):
        out += ["ALSO WORTH NOTING"] + [f"- {x['title']} ({x['source']}) {x['url']}" for x in issue["also"]]
    return "\n".join(out)
