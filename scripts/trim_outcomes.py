#!/usr/bin/env python3
"""Trim meaningless success/failure tables from existing narramancy JSON.

No-roll abilities (Wild Shape, Longstrider, initiative) can't hit or miss,
but earlier generation runs produced success/failure tables for every ability.
This script re-parses the source Foundry actor through the same pipeline used
for generation, classifies each ability with has_roll_outcomes(), and drops
successes/failures tables for abilities that have no resolution roll.

Usage:
    python scripts/trim_outcomes.py [--dry-run]
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from narramancy.models import (  # noqa: E402
    GENERIC_ACTIONS, SKILL_ID_MAP, ParsedAbility,
    get_save_abilities, has_roll_outcomes,
)
from narramancy.parsers.foundry import parse_foundry_actor  # noqa: E402

FIXTURE = ROOT / "fvtt-Actor-gimbal-starwhisper-fCEZTwnXtpQXOcuH.json"
TARGETS = [
    ROOT / "web" / "demo" / "gimbal-starwhisper.json",
    ROOT / "output" / "gimbal-starwhisper-narramancy.json",
]

TRIM_CATEGORIES = {'successes', 'failures'}


def build_ability_map() -> dict:
    """Parse the fixture + generic-actions pipeline; map ability name -> ParsedAbility."""
    creature = parse_foundry_actor(FIXTURE)
    abilities = {a.name: a for a in creature.abilities}

    # Same generic additions the generation pipeline makes (--generic):
    # all 6 saves, proficient skills, death save, initiative.
    for sa in get_save_abilities():
        abilities.setdefault(sa.name, sa)
    # Generation used per-skill tables; classify any skill name as 'skill'
    # (skills always keep outcomes — you succeed or fail the check)
    for skill_name in SKILL_ID_MAP:
        display = skill_name.title()
        abilities.setdefault(display, ParsedAbility(
            name=display, ability_type='skill',
            description=f'The creature makes a {display} check',
        ))
    for ga in GENERIC_ACTIONS:
        abilities.setdefault(ga.name, ga)
    # Bloodied/Death tables are attempts-only already, but classify them
    # so they don't show up as unknown
    for name, atype in (('Bloodied', 'bloodied'), ('Death', 'death')):
        abilities.setdefault(name, ParsedAbility(
            name=name, ability_type=atype, description='',
        ))
    return abilities


def make_resolver(abilities: dict):
    """Build a name resolver: exact -> case-insensitive -> base name without '(...)' suffix.

    Table names can predate fixture renames ('Druidcraft' vs 'Druidcraft (Legacy)').
    """
    lower = {n.lower(): a for n, a in abilities.items()}
    base = {}
    for n, a in abilities.items():
        b = re.sub(r'\s*\(.*\)$', '', n).lower()
        if b != n.lower():
            base[b] = None if b in base else a  # None = ambiguous, don't guess

    def resolve(name: str):
        a = abilities.get(name) or lower.get(name.lower())
        if a is not None:
            return a
        return base.get(name.lower())

    return resolve


def trim_file(path: Path, resolve, dry_run: bool) -> None:
    data = json.loads(path.read_text(encoding='utf-8'))
    tables = data['tables']

    # Abilities whose outcome tables are trigger-wired (e.g. Shillelagh exported
    # as an attack): roll-resolved in practice — keep BOTH successes and failures,
    # whatever we classified from the source item.
    outcome_hooks = TRIM_CATEGORIES | {
        'crits', 'fumbles', 'barely_hits', 'barely_misses', 'miss_dodge', 'miss_armor',
    }
    wired = set()
    for trig in data.get('triggers', []):
        ref_ability, _, ref_category = trig['table'].rpartition('|')
        if ref_category in outcome_hooks:
            wired.add(ref_ability)

    kept, dropped, unknown = [], [], set()
    for table in tables:
        name, category = table['ability'], table['category']
        if category not in TRIM_CATEGORIES:
            kept.append(table)
            continue
        if name in wired:
            kept.append(table)
            continue
        ability = resolve(name)
        if ability is None:
            unknown.add(name)
            kept.append(table)  # conservative: keep what we can't classify
            continue
        if has_roll_outcomes(ability):
            kept.append(table)
        else:
            dropped.append(table)

    print(f"\n{path.relative_to(ROOT)}")
    print(f"  tables: {len(tables)} -> {len(kept)} (dropped {len(dropped)})")
    by_ability = {}
    for t in dropped:
        by_ability.setdefault(t['ability'], []).append(t['category'])
    for name in sorted(by_ability):
        print(f"    - {name}: dropped {', '.join(sorted(by_ability[name]))}")
    if wired:
        print(f"  kept despite no-roll classification (trigger-wired): {', '.join(sorted(wired))}")
    if unknown:
        print(f"  WARNING: unclassified abilities (kept as-is): {', '.join(sorted(unknown))}")

    if not dry_run:
        data['tables'] = kept
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print("  written")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='report only, do not write')
    args = parser.parse_args()

    abilities = build_ability_map()
    resolve = make_resolver(abilities)
    no_roll = sorted(n for n, a in abilities.items() if not has_roll_outcomes(a))
    print(f"Parsed {len(abilities)} abilities; {len(no_roll)} classified as no-roll:")
    for name in no_roll:
        print(f"  {name}")

    for target in TARGETS:
        if target.exists():
            trim_file(target, resolve, args.dry_run)
        else:
            print(f"\nSKIP (missing): {target}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
