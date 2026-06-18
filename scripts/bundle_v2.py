#!/usr/bin/env python3
"""Combine per-creature v1 Narramancy JSON files into one v2 import bundle.

The Narramancy Foundry module's importer accepts a formatVersion-2 file with a
`creatures` array and imports every creature in one action (folder + RollTables
+ triggers per creature). This stitches the individual v1 exports the generation
CLI produces into that single bundle.

Usage:
    python scripts/bundle_v2.py -o output/undermountain/undermountain-bundle.json \
        output/undermountain/bueller-von-ferris-2024-narramancy.json \
        output/undermountain/grumph-narramancy.json ...
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--output", required=True, help="bundle output path")
    ap.add_argument("inputs", nargs="+", help="per-creature v1 narramancy JSON files")
    args = ap.parse_args()

    creatures = []
    for path in args.inputs:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("formatVersion") == 2:
            # already a bundle — fold its creatures in
            creatures.extend(data.get("creatures", []))
            continue
        # v1: strip formatVersion, keep {creature, whisper, tables, triggers}
        entry = {k: v for k, v in data.items() if k != "formatVersion"}
        if "creature" not in entry or "tables" not in entry:
            print(f"WARNING: {path} doesn't look like a v1 export, skipping", file=sys.stderr)
            continue
        creatures.append(entry)

    bundle = {"formatVersion": 2, "creatures": creatures}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    total_tables = sum(len(c.get("tables", [])) for c in creatures)
    total_trig = sum(len(c.get("triggers", [])) for c in creatures)
    print(f"Bundle: {len(creatures)} creatures, {total_tables} tables, "
          f"{total_trig} triggers -> {out} ({out.stat().st_size // 1024} KB)")
    for c in creatures:
        cr = c["creature"]
        print(f"  - {cr['name']:28} {len(c.get('tables', [])):>4} tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
