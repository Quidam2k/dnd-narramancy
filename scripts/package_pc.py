#!/usr/bin/env python3
"""Package each AoA PC's narramancy JSON into a self-contained roller HTML + zip.

Inlines the creature JSON into web/roller.html (replacing the EMBEDDED sentinel)
so the result opens straight from disk (file://) with no picker and no fetch —
one file per player. Each HTML is also zipped for handoff.

Usage:
    python scripts/package_pc.py
"""

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROLLER = ROOT / "web" / "roller.html"
OUT_DIR = ROOT / "output" / "aoa"
DIST = ROOT / "dist" / "aoa"
SENTINEL = "const EMBEDDED = null; /*__EMBED__*/"

SLUGS = ["ayak", "bael", "eldrin-adquinal", "homura", "young-modos"]


def creature_name(data: dict) -> str:
    if data.get("creatures"):
        return data["creatures"][0]["creature"]["name"]
    return data["creature"]["name"]


def embed(template: str, data: dict) -> str:
    if SENTINEL not in template:
        raise SystemExit(f"Embed sentinel not found in {ROLLER} — was the hook added?")
    # Compact JSON; escape </ so a stray '</script>' in flavor text can't close
    # the <script> block early. Inside a JS object literal's string values, \/
    # is a valid escape for '/'.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return template.replace(SENTINEL, f"const EMBEDDED = {payload}; /*__EMBED__*/")


def main() -> int:
    template = ROLLER.read_text(encoding="utf-8")
    DIST.mkdir(parents=True, exist_ok=True)
    results = []
    for slug in SLUGS:
        src = OUT_DIR / f"{slug}-narramancy.json"
        if not src.exists():
            print(f"SKIP (missing): {src}")
            continue
        data = json.loads(src.read_text(encoding="utf-8"))
        name = creature_name(data)
        html = embed(template, data)

        html_path = DIST / f"{name}.html"
        html_path.write_text(html, encoding="utf-8")
        zip_path = DIST / f"{name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(html_path, arcname=f"{name}.html")

        n_tables = len(data.get("tables", []))
        kb = html_path.stat().st_size // 1024
        results.append((name, n_tables, kb, html_path, zip_path))
        print(f"{name}: {n_tables} tables -> {html_path.relative_to(ROOT)} "
              f"({kb} KB) + {zip_path.name}")

    print(f"\nPackaged {len(results)} PCs into {DIST.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
