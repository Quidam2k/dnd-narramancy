#!/usr/bin/env python3
"""Trim bogus success/failure tables from AoA PC narramancy JSON.

Re-classifies each PC's abilities through the SAME pipeline generation uses
(parse_stat_block -> pc_parser, +generic, enrich) and drops successes/failures
tables for abilities the fixed has_roll_outcomes() classifier says have no
resolution roll. Also removes triggers that referenced a dropped table.

This cleans up output produced before the pc_parser from_structured_source fix,
without regenerating the (good) attempts content.

Usage:
    python scripts/trim_pc_outcomes.py [--dry-run]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from narramancy.parsers import parse_stat_block  # noqa: E402
from narramancy.models import (  # noqa: E402
    GENERIC_ACTIONS, get_save_abilities, get_skill_abilities, has_roll_outcomes,
)
from narramancy.enricher import enrich_creature  # noqa: E402

PC_DIR = ROOT / "input-pcs" / "Absence of Alternatives"
OUT_DIR = ROOT / "output" / "aoa"
TRIM_CATEGORIES = {"successes", "failures"}

PCS = {
    "ayak": "fvtt-Actor-ayak-bi46d8bWdFGq84Nt.json",
    "bael": "fvtt-Actor-bael-r7hZLrcmaNbpu5V7.json",
    "eldrin-adquinal": "fvtt-Actor-eldrin-adquinal-HmfHOwywxNnD1dAH.json",
    "homura": "fvtt-Actor-homura-YVuTSTTiEkZE19yI.json",
    "young-modos": "fvtt-Actor-young-modos-mROc8BBOKkM8UrnW.json",
}


def base(n: str) -> str:
    return re.sub(r"\s*\(.*\)$", "", n).strip()


def classify(actor_path: Path) -> dict:
    """name -> has_roll_outcomes, mirroring the generation ability set."""
    cr = parse_stat_block(str(actor_path))
    existing = {a.name for a in cr.abilities}
    for sa in get_save_abilities():
        if sa.name not in existing:
            cr.abilities.append(sa)
    for ska in get_skill_abilities(cr.skill_proficiencies):
        if ska.name not in existing:
            cr.abilities.append(ska)
    for ga in GENERIC_ACTIONS:
        if ga.name not in existing:
            cr.abilities.append(ga)
    enrich_creature(cr)
    return {a.name: has_roll_outcomes(a) for a in cr.abilities}


def keeps(name: str, cls: dict):
    """Resolve a table's ability name to a keep/cut verdict (None if unknown)."""
    if name in cls:
        return cls[name]
    cands = [v for n, v in cls.items() if base(n) == base(name)]
    return cands[0] if cands else None


def trim_pc(slug: str, fn: str, dry_run: bool) -> None:
    json_path = OUT_DIR / f"{slug}-narramancy.json"
    if not json_path.exists():
        print(f"SKIP (missing): {json_path}")
        return
    cls = classify(PC_DIR / fn)
    data = json.loads(json_path.read_text(encoding="utf-8"))

    dropped = {}  # ability -> [categories]
    kept_tables = []
    for t in data["tables"]:
        if t["category"] in TRIM_CATEGORIES:
            verdict = keeps(t["ability"], cls)
            if verdict is False:
                dropped.setdefault(t["ability"], []).append(t["category"])
                continue
        kept_tables.append(t)

    # Drop triggers that referenced a now-removed table
    dropped_refs = {f"{ab}|{cat}" for ab, cats in dropped.items() for cat in cats}
    kept_triggers = [
        tr for tr in data.get("triggers", [])
        if tr.get("table") not in dropped_refs
    ]
    trig_removed = len(data.get("triggers", [])) - len(kept_triggers)

    print(f"\n{slug}: tables {len(data['tables'])} -> {len(kept_tables)} "
          f"(dropped {len(data['tables']) - len(kept_tables)}); "
          f"triggers removed {trig_removed}")
    for ab in sorted(dropped):
        print(f"    - {ab}: {', '.join(sorted(dropped[ab]))}")

    if not dry_run:
        data["tables"] = kept_tables
        if "triggers" in data:
            data["triggers"] = kept_triggers
        json_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print("    written")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    for slug, fn in PCS.items():
        trim_pc(slug, fn, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
