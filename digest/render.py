"""Render the digest as an email-safe HTML page (inline styles) and a plain-text fallback."""

from __future__ import annotations

from html import escape

THEME_COLORS = ["#1f6f5c", "#8a5a00", "#2b5ea7", "#7a3e8f", "#a8402f", "#4b6b1f"]


def _color(theme: str, themes: list[str]) -> str:
    return THEME_COLORS[themes.index(theme) % len(THEME_COLORS)]


def _related_html(rel: list[dict], color: str) -> str:
    if not rel:
        return ""
    rows = "".join(
        f'<div style="margin:6px 0 0;"><a href="{escape(r["url"])}" style="color:#1d1d1b;font-weight:bold;">{escape(r["title"])}</a>'
        f' <span style="color:#6b6a65;">({escape(r["journal"])}, {r["year"]})</span><br>'
        f'<span style="color:#3a3935;">{escape(r["why"])}</span></div>'
        for r in rel)
    return (f'<div style="margin-top:10px;padding-top:10px;border-top:1px dashed #dcdad3;font-family:Helvetica,Arial,sans-serif;font-size:13px;line-height:1.5;">'
            f'<div style="font-size:11px;font-weight:bold;letter-spacing:.06em;text-transform:uppercase;color:{color};">Related research</div>{rows}</div>')


def render_html(title: str, date_str: str, issue: dict, archive_link: str = "") -> str:
    themes = list(dict.fromkeys(i["theme"] for i in issue["items"]))
    e = escape
    parts = [f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} — {e(date_str)}</title></head>
<body style="margin:0;padding:0;background:#f4f3ef;">
<div style="max-width:640px;margin:0 auto;padding:24px 16px;font-family:Georgia,'Times New Roman',serif;color:#1d1d1b;">
{f'<a href="{e(archive_link)}" style="font-family:Helvetica,Arial,sans-serif;font-size:13px;color:#1f6f5c;text-decoration:none;">&larr; Archive</a>' if archive_link else ''}
<div style="font-family:Helvetica,Arial,sans-serif;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#6b6a65;">{e(date_str)}</div>
<h1 style="margin:4px 0 12px;font-size:28px;line-height:1.2;">{e(title)}</h1>
<p style="margin:0 0 24px;font-size:16px;line-height:1.55;color:#3a3935;">{e(issue['intro'])}</p>"""]

    for n, it in enumerate(issue["items"], 1):
        c = _color(it["theme"], themes)
        kw = " · ".join(e(k) for k in it["keywords"])
        parts.append(f"""
<div id="item-{n}" style="background:#ffffff;border-radius:10px;padding:20px 20px 16px;margin:0 0 16px;border-left:4px solid {c};scroll-margin-top:16px;">
  <div style="font-family:Helvetica,Arial,sans-serif;font-size:11px;font-weight:bold;letter-spacing:.06em;text-transform:uppercase;color:{c};">{n:02d} · {e(it['theme'])}</div>
  <h2 style="margin:6px 0 4px;font-size:19px;line-height:1.3;"><a href="{e(it['url'])}" style="color:#1d1d1b;text-decoration:none;">{e(it['headline'])}</a></h2>
  <div style="font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#6b6a65;margin-bottom:10px;">{e(it['source'])}{(' · ' + e(it['date'])) if it.get('date') else ''} · <a href="{e(it['url'])}" style="color:{c};">Read</a></div>
  <p style="margin:0 0 12px;font-size:15px;line-height:1.55;">{e(it['summary'])}</p>
  <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;font-family:Helvetica,Arial,sans-serif;font-size:13px;line-height:1.5;color:#2f2e2b;">
    <tr><td style="padding:6px 0;vertical-align:top;width:92px;color:#6b6a65;">OM angle</td><td style="padding:6px 0;">{e(it['om_angle'])}</td></tr>
    <tr><td style="padding:6px 0;vertical-align:top;color:#6b6a65;">Research Q</td><td style="padding:6px 0;font-weight:bold;">{e(it['research_question'])}</td></tr>
    <tr><td style="padding:6px 0;vertical-align:top;color:#6b6a65;">Data / ID</td><td style="padding:6px 0;">{e(it['data_identification'])}</td></tr>
    <tr><td style="padding:6px 0;vertical-align:top;color:#6b6a65;">Keywords</td><td style="padding:6px 0;color:#6b6a65;">{kw}</td></tr>
  </table>{_related_html(it.get('related', []), c)}
</div>""")

    if issue.get("thread_to_pull"):
        parts.append(f"""
<div style="background:#1d1d1b;color:#f4f3ef;border-radius:10px;padding:20px;margin:24px 0 16px;">
  <div style="font-family:Helvetica,Arial,sans-serif;font-size:11px;font-weight:bold;letter-spacing:.06em;text-transform:uppercase;color:#d9c48f;">Thread to pull</div>
  <p style="margin:8px 0 0;font-size:15px;line-height:1.55;">{e(issue['thread_to_pull'])}</p>
</div>""")

    if issue["papers"]:
        parts.append("""<h3 style="font-size:16px;margin:28px 0 8px;font-family:Helvetica,Arial,sans-serif;letter-spacing:.04em;text-transform:uppercase;color:#6b6a65;">New in the journals</h3>""")
        for p in issue["papers"]:
            parts.append(f"""
<div style="border-top:1px solid #dcdad3;padding:12px 0;">
  <a href="{e(p['url'])}" style="font-size:16px;color:#1d1d1b;font-weight:bold;text-decoration:none;">{e(p['title'])}</a>
  <div style="font-family:Helvetica,Arial,sans-serif;font-size:12px;color:#6b6a65;margin:2px 0 6px;">{e(p['journal'])}</div>
  <p style="margin:0 0 4px;font-size:14px;line-height:1.5;">{e(p['takeaway'])}</p>
  <p style="margin:0;font-size:13px;line-height:1.5;color:#3a3935;font-style:italic;">{e(p['connection'])}</p>
</div>""")

    parts.append("""
<p style="font-family:Helvetica,Arial,sans-serif;font-size:11px;color:#8f8d86;margin-top:28px;line-height:1.5;">
Curated and summarized automatically with Claude from public news feeds and Crossref. Verify facts in the linked sources before citing.{(' <a href="' + e(archive_link) + '" style="color:#8f8d86;">Browse the archive</a>.') if archive_link else ''}</p>
</div></body></html>""")
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
    return "\n".join(out)
