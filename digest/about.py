"""About page (docs/about.html) from about.md — a tiny Markdown subset: # / ## headings, paragraphs,
'- ' lists, **bold** and [links](https://...)."""

from __future__ import annotations

import re
from html import escape

from . import theme_toggle
from .render import DARK, LIGHT


def _inline(text: str) -> str:
    s = escape(text)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)


def md_to_html(md: str) -> str:
    out, para, items = [], [], []

    def flush():
        if para:
            out.append(f"<p>{_inline(' '.join(para))}</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + "</ul>")
            items.clear()

    for line in md.splitlines():
        line = line.rstrip()
        if not line:
            flush()
        elif line.startswith("## "):
            flush(); out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            flush(); out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("- "):
            if para:
                flush()
            items.append(line[2:])
        elif items:
            items[-1] += " " + line.strip()
        else:
            para.append(line.strip())
    flush()
    return "\n".join(out)


def render_about(title: str, md: str) -> str:
    toggle_vars = {"toggle-bg": "var(--card)", "toggle-ink": "var(--ink)", "toggle-line": "var(--line)"}
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>About · {escape(title)}</title>
{theme_toggle.HEAD_JS}<style>{theme_toggle.themed_vars({**LIGHT, **toggle_vars}, {**DARK, **toggle_vars})}{theme_toggle.CSS}
html,body{{background:var(--bg)}}
body{{margin:0;color:var(--ink);font:16px/1.65 Georgia,"Times New Roman",serif}}
.wrap{{max-width:640px;margin:0 auto;padding:24px 16px 64px}}
.back{{font:13px Helvetica,Arial,sans-serif;color:var(--accent);text-decoration:none}}
h1{{font-size:30px;margin:10px 0 16px;line-height:1.2}}
h2{{font:600 13px/1.4 Helvetica,Arial,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:30px 0 8px}}
p,li{{color:var(--ink2)}}
ul{{padding-left:20px}} li{{margin:6px 0}}
a{{color:var(--accent)}}
</style></head>
<body>{theme_toggle.BUTTON}<div class="wrap"><a class="back" href="index.html">&larr; Archive</a>
{md_to_html(md)}
</div>{theme_toggle.BODY_JS}</body></html>"""
