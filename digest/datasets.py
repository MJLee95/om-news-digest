"""Dataset registry (datasets.yaml) and the candidate list for datasets not in it yet."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "datasets.yaml"
CANDIDATES = ROOT / "data" / "dataset_candidates.json"
ACCESS_LABELS = {"public": "Public", "university": "University license", "commercial": "Commercial", "request": "On request"}


def load_registry(path: Path = REGISTRY) -> dict:
    reg = yaml.safe_load(path.read_text())
    reg["by_id"] = {d["id"]: d for d in reg["datasets"]}
    return reg


def registry_prompt(reg: dict) -> str:
    """Compact listing for Claude: id: name [category; access]."""
    return "\n".join(f"{d['id']}: {d['name']} [{reg['categories'][d['category']]}; {d['access']}]"
                     for d in reg["datasets"])


def load_candidates() -> dict:
    return json.loads(CANDIDATES.read_text()) if CANDIDATES.exists() else {}


def add_candidates(names_by_item: dict[str, list[str]], iso: str, reg: dict) -> None:
    """Record datasets Claude named that aren't in the registry. Keyed by lowercased name."""
    cands = load_candidates()
    known = {d["name"].lower() for d in reg["datasets"]}
    for item_id, names in names_by_item.items():
        for name in names:
            key = name.strip().lower()
            if not key or key in known:
                continue
            c = cands.setdefault(key, {"name": name.strip(), "first_seen": iso, "items": []})
            if item_id not in c["items"]:
                c["items"].append(item_id)
            c["last_seen"] = iso
    CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES.write_text(json.dumps(cands, indent=1, ensure_ascii=False))


def frequent_candidates(min_mentions: int = 2) -> list[dict]:
    """Candidates mentioned by at least `min_mentions` stories that still aren't in the registry."""
    known = {d["name"].lower() for d in load_registry()["datasets"]}
    out = [{**c, "mentions": len(c["items"])} for k, c in load_candidates().items()
           if len(c["items"]) >= min_mentions and k not in known]
    return sorted(out, key=lambda c: -c["mentions"])
