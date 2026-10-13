"""Sunday weekly review.

  python run_weekly.py            # compose from the last 7 days, email it, save to the archive
  python run_weekly.py --dry-run  # write output/weekly-preview.html only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import yaml

from digest import archive, datasets as ds_registry, state, stars as star_store
from digest.weekly import compose, render_weekly, render_weekly_text
from run import ROOT, load_dotenv


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    load_dotenv()
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    d = cfg["digest"]
    today = datetime.now(ZoneInfo(d["timezone"])).date()
    start = (today - timedelta(days=6)).isoformat()

    week_items, also = [], []
    for p in sorted((state.DATA / "issues").glob("*.json")):
        if p.stem < start:
            continue
        iss = json.loads(p.read_text())
        week_items += [{**it, "id": f"{p.stem}#{n}"} for n, it in enumerate(iss["items"], 1)]
        also += iss.get("also", [])
    if not week_items:
        sys.exit("No issues in the last 7 days; daily runs may be failing. Weekly review not sent.")

    stars = star_store.fetch_stars(cfg.get("github_repo", ""))
    from digest.llm import Curator
    cur = Curator(cfg["llm"], cfg["research_profile"])
    wk = compose(cur, week_items, also, set(stars), cfg["llm"].get("weekly_effort", "high"))
    print(cur.cost_report())

    iso = today.isoformat()
    data = {**wk.model_dump(), "items": {it["id"]: it["headline"] for it in week_items},
            "dataset_candidates": [{"name": c["name"], "mentions": c["mentions"]} for c in ds_registry.frequent_candidates(2)]}
    html = render_weekly(d["title"], iso, data, d.get("archive_url", ""))
    subject = f"Weekly review · {today:%b %-d} — {wk.ideas[0].title if wk.ideas else wk.overview[:80]}"[:150]

    if args.dry_run:
        (ROOT / "output").mkdir(exist_ok=True)
        (ROOT / "output" / "weekly-preview.html").write_text(html)
        print("Dry run: wrote output/weekly-preview.html")
        return

    from digest.mailer import send
    send(subject, render_weekly_text(iso, data), html)
    print("Weekly review sent.")
    (state.DATA / "weekly").mkdir(parents=True, exist_ok=True)
    (state.DATA / "weekly" / f"{iso}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    archive.build(state.DATA / "issues", ROOT / "docs", d["title"], cfg.get("github_repo", ""), stars)


if __name__ == "__main__":
    main()
