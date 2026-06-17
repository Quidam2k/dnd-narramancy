#!/usr/bin/env python3
"""Sign-off dry-run: print the per-PC keep/cut outcome classification.

Mirrors the generation pipeline's ability set (Foundry items + --generic saves,
proficient skills, death save, initiative) and runs the same has_roll_outcomes()
classifier used to decide whether each ability gets success/failure tables.

Lets Todd eyeball exactly what each PC will get BEFORE any tokens are spent —
the "thorough check on all the tables".

Usage:
    python scripts/signoff_outcomes.py
    python scripts/signoff_outcomes.py "input-pcs/Absence of Alternatives/fvtt-Actor-ayak-...json"
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from narramancy.models import (  # noqa: E402
    GENERIC_ACTIONS, get_save_abilities, get_skill_abilities, has_roll_outcomes,
)
# Use the SAME dispatch the generation pipeline uses (parse_stat_block routes
# PC actors to pc_parser, NPCs to foundry) — calling parse_foundry_actor
# directly would take the wrong path for PCs and mask classifier bugs.
from narramancy.parsers import parse_stat_block  # noqa: E402
from narramancy.enricher import enrich_creature  # noqa: E402

PC_DIR = ROOT / "input-pcs" / "Absence of Alternatives"


def build_abilities(actor_path: Path):
    """Reproduce the generation pipeline's ability list (with --generic)."""
    creature = parse_stat_block(str(actor_path))
    existing = {a.name for a in creature.abilities}
    for sa in get_save_abilities():
        if sa.name not in existing:
            creature.abilities.append(sa)
    for ska in get_skill_abilities(creature.skill_proficiencies):
        if ska.name not in existing:
            creature.abilities.append(ska)
    for ga in GENERIC_ACTIONS:
        if ga.name not in existing:
            creature.abilities.append(ga)
    enrich_creature(creature)  # matches generation (description-only; no class change)
    return creature


def report(actor_path: Path) -> tuple[int, int]:
    creature = build_abilities(actor_path)
    keep, cut = [], []
    for a in creature.abilities:
        (keep if has_roll_outcomes(a) else cut).append(a)

    print(f"\n=== {creature.name} ===  ({len(creature.abilities)} abilities: "
          f"{len(keep)} with success/fail, {len(cut)} attempts-only)")
    print(f"  KEEP success/failure ({len(keep)}):")
    for a in sorted(keep, key=lambda x: x.name.lower()):
        print(f"    + {a.name}  [{a.ability_type}]")
    print(f"  CUT to attempts-only ({len(cut)}):")
    for a in sorted(cut, key=lambda x: x.name.lower()):
        print(f"    - {a.name}  [{a.ability_type}]")
    return len(keep), len(cut)


def main() -> int:
    if len(sys.argv) > 1:
        actors = [Path(p) for p in sys.argv[1:]]
    else:
        actors = sorted(PC_DIR.glob("*.json"))
    if not actors:
        print(f"No actor JSON found in {PC_DIR}")
        return 1
    tot_keep = tot_cut = 0
    for actor in actors:
        k, c = report(actor)
        tot_keep += k
        tot_cut += c
    print(f"\nTOTAL across {len(actors)} PCs: {tot_keep} keep / {tot_cut} cut")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
