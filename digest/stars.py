"""Stars live as GitHub issues labeled 'star' in the repo (the site is static, so GitHub is the store).

Clicking ☆ on the site or in an email opens a prefilled 'new issue' form; submitting it stars the item,
closing the issue un-stars it. Only issues opened by the repo owner count.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlencode

import requests

ID_RE = re.compile(r"item:\s*(\d{4}-\d{2}-\d{2}#\d+)")


def star_url(repo: str, item_id: str, headline: str) -> str:
    body = (f"item: {item_id}\n\n"
            "<!-- Optional: write a note below on why this is interesting (it helps future curation). -->\n")
    return f"https://github.com/{repo}/issues/new?" + urlencode(
        {"labels": "star", "title": f"★ {headline}"[:200], "body": body})


def fetch_stars(repo: str) -> dict[str, dict]:
    """Return {item_id: {"note", "url", "created"}} for open 'star' issues opened by the repo owner."""
    if not repo:
        return {}
    owner = repo.split("/")[0].lower()
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    stars, page = {}, 1
    while True:
        try:
            r = requests.get(f"https://api.github.com/repos/{repo}/issues", headers=headers, timeout=20,
                             params={"labels": "star", "state": "open", "per_page": 100, "page": page})
            r.raise_for_status()
        except Exception as ex:
            print(f"[warn] could not load stars: {ex}")
            return stars
        batch = r.json()
        for iss in batch:
            if (iss.get("user") or {}).get("login", "").lower() != owner:
                continue
            m = ID_RE.search(iss.get("body") or "")
            if not m:
                continue
            note = re.sub(r"<!--.*?-->", "", ID_RE.sub("", iss["body"]), flags=re.S).strip()
            stars[m.group(1)] = {"note": note[:500], "url": iss["html_url"], "created": iss["created_at"][:10]}
        if len(batch) < 100:
            return stars
        page += 1
