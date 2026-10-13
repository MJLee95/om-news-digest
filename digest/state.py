"""Remember what was already sent, and keep an archive of every issue."""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SEEN = DATA / "seen.json"
ARCHIVE_CSV = DATA / "archive.csv"
KEEP_DAYS = 60


def load_seen() -> dict:
    if SEEN.exists():
        return json.loads(SEEN.read_text())
    return {"items": []}


def seen_sets(seen: dict) -> tuple[set[str], set[str]]:
    return {i["title_key"] for i in seen["items"]}, {i["url"] for i in seen["items"]}


def save_seen(seen: dict, new_items: list[dict], today: date) -> None:
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    items = [i for i in seen["items"] if i["date"] >= cutoff] + new_items
    SEEN.write_text(json.dumps({"items": items}, indent=1, ensure_ascii=False))


ARCHIVE_FIELDS = ["date", "kind", "theme", "headline", "source", "url",
                  "summary", "om_angle", "research_question", "data_identification", "keywords"]


def append_archive(rows: list[dict]) -> None:
    new = not ARCHIVE_CSV.exists()
    with ARCHIVE_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ARCHIVE_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)
