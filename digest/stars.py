"""Stars live as GitHub issues labeled 'star' in the repo (the site is static, so GitHub is the store).

The archive's ☆/★ buttons create and close those issues through the GitHub API (see star_client.py);
email links send you to the archive to do it. Only issues opened by the repo owner count.
"""

from __future__ import annotations

import os
import re
from urllib.parse import quote

import requests

ID_RE = re.compile(r"item:\s*(\d{4}-\d{2}-\d{2}#\d+)")


def star_link(archive_url: str, item_id: str) -> str:
    """Email link: opens the archive, which stars the item (asking to connect GitHub the first time)."""
    return f"{archive_url}#star={quote(item_id, safe='')}"


def fetch_stars(repo: str) -> dict[str, dict]:
    """Return {item_id: {"number", "note", "url", "created"}} for open 'star' issues opened by the repo owner."""
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
            stars[m.group(1)] = {"number": iss["number"], "note": note[:500], "url": iss["html_url"],
                                 "created": iss["created_at"][:10]}
        if len(batch) < 100:
            return stars
        page += 1
