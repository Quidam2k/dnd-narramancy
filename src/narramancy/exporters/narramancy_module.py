"""Narramancy module exporter.

Produces a single JSON file per creature containing:
- Creature metadata (name, type, CR, token pattern, pronouns)
- All rollable table data (entries grouped by ability + category)
- Trigger configuration (which hooks fire which tables)

This JSON is consumed by the Narramancy Foundry VTT module.
"""

from typing import Dict, List, Optional, Tuple

from ..models import FlavorTextResult, ParsedCreature, SAVE_ABILITIES, SKILL_ID_MAP


def export_narramancy(
    creature: ParsedCreature,
    results: Dict[str, FlavorTextResult],
    whisper: str = "gm",
) -> dict:
    """Build the combined Narramancy JSON for a creature.

    Args:
        creature: Parsed creature with metadata and proficiencies.
        results: Dict mapping ability name to FlavorTextResult.
        whisper: Default whisper target ("gm", "owner", "gm+owner", "public").

    Returns:
        Dict ready for json.dump — the full Narramancy import format.
    """
    # PCs carry explicit pronouns from their sheet; monsters fall back by type
    pronouns = getattr(creature, 'pronouns', None)
    if not pronouns:
        creature_type = (creature.creature_type or '').lower()
        pronouns = 'they' if 'humanoid' in creature_type else 'it'

    tables = []
    triggers = []

    for ability_name, result in results.items():
        ability_type = result.metadata.get('ability_type', 'action')

        for category in ('attempts', 'successes', 'failures'):
            entries = getattr(result, category)
            if not entries:
                continue

            tables.append({
                'ability': ability_name,
                'category': category,
                'description': f'Flavor text for {category} a {ability_type}',
                'entries': entries,
            })

        # Cast table (multi-phase spells)
        if result.cast:
            tables.append({
                'ability': ability_name,
                'category': 'cast',
                'description': f'Flavor text for casting {ability_name}',
                'entries': result.cast,
            })

        # Conditional tables (crits, fumbles, barely_hits, barely_misses, miss_dodge, miss_armor, killing_blow)
        for cond_category in ('crits', 'fumbles', 'barely_hits', 'barely_misses', 'miss_dodge', 'miss_armor', 'killing_blow'):
            entries = getattr(result, cond_category, [])
            if not entries:
                continue

            tables.append({
                'ability': ability_name,
                'category': cond_category,
                'description': f'Flavor text for {cond_category} with {ability_name}',
                'entries': entries,
            })

        # Build triggers based on ability type
        triggers.extend(_build_triggers(ability_name, ability_type, result))

    return {
        'formatVersion': 1,
        'creature': {
            'name': creature.name,
            'tokenPattern': getattr(creature, '_token_pattern', f'*{creature.name}*'),
            'cr': creature.challenge_rating,
            'type': creature.creature_type,
            'pronouns': pronouns,
        },
        'whisper': whisper,
        'tables': tables,
        'triggers': triggers,
    }


def _build_triggers(
    ability_name: str,
    ability_type: str,
    result: FlavorTextResult,
) -> List[dict]:
    """Build trigger entries for a single ability based on its type."""
    triggers = []

    if ability_type == 'attack':
        # Attack roll -> attempts, damage roll -> successes
        if result.attempts:
            triggers.append({
                'hookType': 'attackRoll',
                'itemName': ability_name,
                'table': f'{ability_name}|attempts',
            })
        if result.successes:
            triggers.append({
                'hookType': 'damageRoll',
                'itemName': ability_name,
                'table': f'{ability_name}|successes',
            })
        # Conditional attack triggers
        if result.crits:
            triggers.append({
                'hookType': 'attackRoll_crit',
                'itemName': ability_name,
                'table': f'{ability_name}|crits',
            })
        if result.fumbles:
            triggers.append({
                'hookType': 'attackRoll_fumble',
                'itemName': ability_name,
                'table': f'{ability_name}|fumbles',
            })
        if result.barely_hits:
            triggers.append({
                'hookType': 'attackRoll_barely_hits',
                'itemName': ability_name,
                'table': f'{ability_name}|barely_hits',
            })
        if result.barely_misses:
            triggers.append({
                'hookType': 'attackRoll_barely_misses',
                'itemName': ability_name,
                'table': f'{ability_name}|barely_misses',
            })
        if result.miss_dodge:
            triggers.append({
                'hookType': 'attackRoll_miss_dodge',
                'itemName': ability_name,
                'table': f'{ability_name}|miss_dodge',
            })
        if result.miss_armor:
            triggers.append({
                'hookType': 'attackRoll_miss_armor',
                'itemName': ability_name,
                'table': f'{ability_name}|miss_armor',
            })
        if result.killing_blow:
            triggers.append({
                'hookType': 'killingBlow',
                'itemName': ability_name,
                'table': f'{ability_name}|killing_blow',
            })

    elif ability_type == 'save':
        # Per-save abilities: "STR Save", "DEX Save", etc.
        save_abbrev = _save_name_to_id(ability_name)
        if save_abbrev and result.attempts:
            triggers.append({
                'hookType': 'savingThrow',
                'saveId': save_abbrev,
                'table': f'{ability_name}|attempts',
            })

    elif ability_type == 'skill':
        # Per-skill abilities: "Perception", "Stealth", etc.
        skill_id = SKILL_ID_MAP.get(ability_name.lower())
        if skill_id and result.attempts:
            triggers.append({
                'hookType': 'skill',
                'skillId': skill_id,
                'table': f'{ability_name}|attempts',
            })

    elif ability_type == 'death_save':
        if result.attempts:
            triggers.append({
                'hookType': 'deathSave',
                'table': f'{ability_name}|attempts',
            })

    elif ability_type == 'initiative':
        if result.attempts:
            triggers.append({
                'hookType': 'initiative',
                'table': f'{ability_name}|attempts',
            })

    elif ability_type == 'bloodied':
        if result.attempts:
            triggers.append({
                'hookType': 'bloodied',
                'table': f'{ability_name}|attempts',
            })

    elif ability_type == 'death':
        if result.attempts:
            triggers.append({
                'hookType': 'death',
                'table': f'{ability_name}|attempts',
            })

    else:
        # Spells, features, actions, etc.
        # Multi-phase: cast table gets spellCast, attempts get spellEffect
        is_multi_phase = bool(result.cast)
        if is_multi_phase:
            if result.cast:
                triggers.append({
                    'hookType': 'spellCast',
                    'itemName': ability_name,
                    'table': f'{ability_name}|cast',
                })
            if result.attempts:
                triggers.append({
                    'hookType': 'spellEffect',
                    'itemName': ability_name,
                    'table': f'{ability_name}|attempts',
                })
        else:
            # Single-phase: itemUse for attempts (backwards compat)
            if result.attempts:
                triggers.append({
                    'hookType': 'itemUse',
                    'itemName': ability_name,
                    'table': f'{ability_name}|attempts',
                })

    # Killing blow for any non-attack ability that has one
    if ability_type != 'attack' and result.killing_blow:
        triggers.append({
            'hookType': 'killingBlow',
            'itemName': ability_name,
            'table': f'{ability_name}|killing_blow',
        })

    return triggers


def export_narramancy_v2(
    creature_results_pairs: List[Tuple[ParsedCreature, Dict[str, FlavorTextResult]]],
    whisper: str = "gm",
) -> dict:
    """Build a v2 multi-creature Narramancy JSON bundle.

    Args:
        creature_results_pairs: List of (creature, results) tuples.
        whisper: Default whisper target for all creatures.

    Returns:
        Dict with formatVersion 2 and a creatures array.
    """
    creatures = []
    for creature, results in creature_results_pairs:
        v1 = export_narramancy(creature, results, whisper=whisper)
        # Strip formatVersion from the v1 output to make a creature entry
        entry = {
            'creature': v1['creature'],
            'tables': v1['tables'],
            'triggers': v1['triggers'],
            'whisper': v1['whisper'],
        }
        creatures.append(entry)
    return {'formatVersion': 2, 'creatures': creatures}


def _save_name_to_id(name: str) -> Optional[str]:
    """Convert 'STR Save' to 'str', 'DEX Save' to 'dex', etc."""
    # Reverse lookup from SAVE_ABILITIES values to keys
    for abbrev, save_name in SAVE_ABILITIES.items():
        if save_name == name:
            return abbrev
    return None
