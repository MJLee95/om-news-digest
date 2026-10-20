"""Sunday weekly review: re-read the week's issues and pull out patterns, developing stories and ideas."""

from __future__ import annotations

from datetime import date
from html import escape

from pydantic import BaseModel, Field

from . import theme_toggle
from .render import DARK, EMAIL_PALETTE, LIGHT, WEB_PALETTE


class Pattern(BaseModel):
    title: str = Field(description="Short name for the pattern")
    explanation: str = Field(description="2-3 sentences on what recurred this week and why it matters for OM research")
    item_ids: list[str] = Field(description="Ids of this week's items that show it")


class Developing(BaseModel):
    title: str = Field(description="The ongoing story")
    update: str = Field(description="1-2 sentences: where it stands and what to watch next")
    item_ids: list[str]


class Idea(BaseModel):
    title: str = Field(description="Short working title for a possible paper")
    question: str = Field(description="The research question, stated precisely")
    why_now: str = Field(description="Why this week's events make it timely or identifiable")
    data: str = Field(description="Concrete data sources")
    identification: str = Field(description="Empirical strategy or model setup; name the main threat to identification")
    literature: str = Field(description="How it relates to the related papers listed with the items (cite only those titles); empty if none apply")
    item_ids: list[str]


class WeeklyReview(BaseModel):
    overview: str = Field(description="2-3 sentence summary of the week")
    patterns: list[Pattern] = Field(description="2-4 cross-cutting patterns")
    developing: list[Developing] = Field(description="0-4 stories that are still unfolding")
    ideas: list[Idea] = Field(description="2-3 of the most promising research ideas, more developed than the daily ones")
    watch: list[str] = Field(description="2-4 short items to watch next week (scheduled decisions, deadlines, data releases)")


def compose(curator, week_items: list[dict], also: list[dict], starred_ids: set[str], effort: str = "high") -> WeeklyReview:
    blocks = []
    for it in week_items:
        rel = "; ".join(r["title"] for r in it.get("related", [])) or "none"
        blocks.append(
            f"[{it['id']}]{' ★ STARRED' if it['id'] in starred_ids else ''} ({it['theme']}) {it['headline']}\n"
            f"Summary: {it['summary']}\n" + (
                f"Problem: {it['problem']}\nWhere & why: {it['where_why']}\n"
                f"Stakeholders: {'; '.join(x['name'] + ' (' + x['stake'] + ')' for x in it['stakeholders'])}\n"
                f"Hints: {' | '.join(it['hints'])}\nData leads: {it['data_leads']}\n"
                if "problem" in it else
                f"OM angle: {it['om_angle']}\nResearch Q: {it['research_question']}\nData/ID: {it['data_identification']}\n")
            + f"Related papers: {rel}")
    prompt = f"""Here is everything from this week's daily newsletter. Write the weekly review.

Look across days rather than summarizing each item: what recurred, which stories are developing, and which
ideas are strongest when items are combined. Give extra weight to items the reader starred. Ideas should be
more developed than the daily one-liners: a precise question, why the timing helps identification, concrete
data, and the main threat to identification. Reference items only by the ids given.

THIS WEEK'S ITEMS:
{chr(10).join(blocks)}

HEADLINE-ONLY MENTIONS THIS WEEK:
{chr(10).join(f"- {a['title']} ({a['source']})" for a in also) or "(none)"}
"""
    wk = curator._parse(prompt, WeeklyReview, effort=effort)
    valid = {it["id"] for it in week_items}
    for group in (wk.patterns, wk.developing, wk.ideas):
        for g in group:
            g.item_ids = [i for i in g.item_ids if i in valid]
    return wk


def render_weekly(title: str, iso: str, wk: dict, archive_link: str = "", web: bool = False,
                  items: dict | None = None) -> str:
    """wk is WeeklyReview.model_dump() plus 'items': {id: headline}."""
    P = WEB_PALETTE if web else EMAIL_PALETTE
    e = escape
    items = items or wk.get("items", {})
    end = date.fromisoformat(iso)

    def ref(ids):
        out = []
        for i in ids:
            d, n = i.split("#")
            href = f"../issues/{d}.html#item-{n}" if web else (f"{archive_link}issues/{d}.html#item-{n}" if archive_link else "")
            label = f"{date.fromisoformat(d):%a} · {items.get(i, i)[:70]}"
            out.append(f'<a href="{e(href)}" style="color:{P["accent"]};">{e(label)}</a>' if href else e(label))
        return (f'<div style="font-family:Helvetica,Arial,sans-serif;font-size:12px;color:{P["muted"]};margin-top:6px;line-height:1.6;">'
                + "<br>".join(out) + "</div>") if out else ""

    h3 = f'font-size:16px;margin:28px 0 10px;font-family:Helvetica,Arial,sans-serif;letter-spacing:.04em;text-transform:uppercase;color:{P["muted"]};'
    card = f'background:{P["card"]};border-radius:10px;padding:18px 20px;margin:0 0 14px;'
    sans = "font-family:Helvetica,Arial,sans-serif;"
    toggle_vars = {"toggle-bg": "var(--card)", "toggle-ink": "var(--ink)", "toggle-line": "var(--line)"}
    web_head = (f"{theme_toggle.HEAD_JS}<style>{theme_toggle.themed_vars({**LIGHT, **toggle_vars}, {**DARK, **toggle_vars})}"
                f"{theme_toggle.CSS}html{{background:var(--bg)}}</style>") if web else ""
    home = archive_link
    parts = [f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} — Week ending {end:%b %-d}</title>{web_head}</head>
<body style="margin:0;padding:0;background:{P['bg']};">{theme_toggle.BUTTON if web else ''}
<div style="max-width:640px;margin:0 auto;padding:24px 16px;font-family:Georgia,'Times New Roman',serif;color:{P['ink']};">
{f'<a href="{e(home)}" style="{sans}font-size:13px;color:{P["accent"]};text-decoration:none;">&larr; Archive</a>' if home else ''}
<div style="{sans}font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:{P['muted']};">{e(title)} · Weekly review</div>
<h1 style="margin:4px 0 12px;font-size:28px;line-height:1.2;">Week ending {end:%B %-d}</h1>
<p style="margin:0 0 8px;font-size:16px;line-height:1.55;color:{P['ink2']};">{e(wk['overview'])}</p>"""]

    parts.append(f'<h3 style="{h3}">Research ideas</h3>')
    for k, idea in enumerate(wk["ideas"], 1):
        row = lambda label, text, bold=False: (
            f'<tr><td style="padding:5px 0;vertical-align:top;width:96px;color:{P["muted"]};">{label}</td>'
            f'<td style="padding:5px 0;{"font-weight:bold;" if bold else ""}">{e(text)}</td></tr>') if text else ""
        parts.append(f"""<div style="{card}border-left:4px solid {P['gold']};">
  <div style="{sans}font-size:11px;font-weight:bold;letter-spacing:.06em;text-transform:uppercase;color:{P['muted']};">Idea {k}</div>
  <h2 style="margin:4px 0 8px;font-size:19px;line-height:1.3;">{e(idea['title'])}</h2>
  <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;{sans}font-size:13px;line-height:1.5;color:{P['ink3']};">
    {row('Question', idea['question'], True)}{row('Why now', idea['why_now'])}{row('Data', idea['data'])}
    {row('Identification', idea['identification'])}{row('Literature', idea['literature'])}
  </table>{ref(idea['item_ids'])}
</div>""")

    if wk["patterns"]:
        parts.append(f'<h3 style="{h3}">Patterns this week</h3>')
        for pt in wk["patterns"]:
            parts.append(f'<div style="{card}"><div style="font-size:17px;font-weight:bold;">{e(pt["title"])}</div>'
                         f'<p style="margin:6px 0 0;font-size:15px;line-height:1.55;">{e(pt["explanation"])}</p>{ref(pt["item_ids"])}</div>')

    if wk["developing"]:
        parts.append(f'<h3 style="{h3}">Developing stories</h3>')
        for dv in wk["developing"]:
            parts.append(f'<div style="border-top:1px solid {P["line"]};padding:10px 0;"><div style="font-weight:bold;">{e(dv["title"])}</div>'
                         f'<div style="font-size:14px;line-height:1.5;color:{P["ink2"]};">{e(dv["update"])}</div>{ref(dv["item_ids"])}</div>')

    if wk["watch"]:
        parts.append(f'<h3 style="{h3}">Watch next week</h3><ul style="margin:0;padding-left:20px;font-size:15px;line-height:1.6;">'
                     + "".join(f"<li>{e(w)}</li>" for w in wk["watch"]) + "</ul>")

    if wk.get("dataset_candidates"):
        parts.append(f'<h3 style="{h3}">Dataset candidates</h3>'
                     f'<p style="{sans}font-size:13px;color:{P["muted"]};margin:0 0 6px;">Named in several stories but not in your '
                     f'datasets.yaml list. Add the useful ones to the list.</p><ul style="margin:0;padding-left:20px;font-size:14px;line-height:1.6;">'
                     + "".join(f"<li>{e(c['name'])} <span style=\"color:{P['muted']};\">· {c['mentions']} mentions</span></li>"
                               for c in wk["dataset_candidates"]) + "</ul>")

    archive = (f' <a href="{e(home)}" style="color:{P["faint"]};">Browse the archive</a>.' if home else "")
    parts.append(f"""<p style="{sans}font-size:11px;color:{P['faint']};margin-top:28px;line-height:1.5;">
Written by Claude from this week's issues. Check the original sources before citing.{archive}</p>
</div>{theme_toggle.BODY_JS if web else ''}</body></html>""")
    return "".join(parts)


def render_weekly_text(iso: str, wk: dict) -> str:
    out = [f"Weekly review — week ending {iso}", "", wk["overview"], "", "RESEARCH IDEAS"]
    for k, i in enumerate(wk["ideas"], 1):
        out += [f"{k}. {i['title']}", f"   Q: {i['question']}", f"   Why now: {i['why_now']}",
                f"   Data: {i['data']}", f"   Identification: {i['identification']}", ""]
    out += ["PATTERNS"] + [f"- {p['title']}: {p['explanation']}" for p in wk["patterns"]]
    out += ["", "DEVELOPING"] + [f"- {d['title']}: {d['update']}" for d in wk["developing"]]
    out += ["", "WATCH"] + [f"- {w}" for w in wk["watch"]]
    return "\n".join(out)
