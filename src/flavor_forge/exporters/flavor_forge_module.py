"""Flavor Forge module exporter.

Produces a single JSON file per creature containing:
- Creature metadata (name, type, CR, token pattern, pronouns)
- All rollable table data (entries grouped by ability + category)
- Trigger configuration (which hooks fire which tables)

This JSON is consumed by the Flavor Forge Foundry VTT module.
"""

from typing import Dict, List, Optional

from ..models import FlavorTextResult, ParsedCreature, SAVE_ABILITIES, SKILL_ID_MAP


def export_flavor_forge(
    creature: ParsedCreature,
    results: Dict[str, FlavorTextResult],
    whisper: str = "gm",
) -> dict:
    """Build the combined Flavor Forge JSON for a creature.

    Args:
        creature: Parsed creature with metadata and proficiencies.
        results: Dict mapping ability name to FlavorTextResult.
        whisper: Default whisper target ("gm", "owner", "gm+owner", "public").

    Returns:
        Dict ready for json.dump — the full Flavor Forge import format.
    """
    # Determine pronouns from creature type
    creature_type = (creature.creature_type or '').lower()
    if 'humanoid' in creature_type:
        pronouns = 'they'
    else:
        pronouns = 'it'

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

        # Conditional tables (crits, fumbles, barely_hits, barely_misses, miss_dodge, miss_armor)
        for cond_category in ('crits', 'fumbles', 'barely_hits', 'barely_misses', 'miss_dodge', 'miss_armor'):
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
            'tokenPattern': f'*{creature.name}*',
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
        # Spells, features, actions, etc. -> itemUse for attempts
        if result.attempts:
            triggers.append({
                'hookType': 'itemUse',
                'itemName': ability_name,
                'table': f'{ability_name}|attempts',
            })

    return triggers


def _save_name_to_id(name: str) -> Optional[str]:
    """Convert 'STR Save' to 'str', 'DEX Save' to 'dex', etc."""
    # Reverse lookup from SAVE_ABILITIES values to keys
    for abbrev, save_name in SAVE_ABILITIES.items():
        if save_name == name:
            return abbrev
    return None
