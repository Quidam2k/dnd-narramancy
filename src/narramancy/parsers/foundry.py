"""Foundry VTT Actor JSON parser."""

import json
from pathlib import Path
from typing import Union

from ..models import ParsedCreature, ParsedAbility


# Foundry item types that map to abilities
_TYPE_MAP = {
    'weapon': 'attack',
    'spell': 'spell',
    'feat': 'feature',
    'equipment': 'feature',
    'tool': 'feature',
}


def parse_foundry_actor(data: Union[str, dict, Path]) -> ParsedCreature:
    """Parse a Foundry VTT actor export into a ParsedCreature.

    Args:
        data: JSON string, dict, or Path to a .json file
    """
    if isinstance(data, (str, Path)):
        path = Path(data)
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
        elif isinstance(data, str):
            data = json.loads(data)

    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object for Foundry actor data")

    actor_type = data.get('type', '')  # 'character' or 'npc'
    system = data.get('system', data.get('data', {}))
    details = system.get('details', {})
    traits = system.get('traits', {})
    items = data.get('items', [])

    # Extract race/class/level from item entries (PC actors)
    race = ''
    char_class = ''
    char_level = 0
    if actor_type == 'character':
        for item in items:
            if item.get('type') == 'race':
                race = item.get('name', '')
            elif item.get('type') == 'class':
                char_class = item.get('name', '')
                char_level = item.get('system', {}).get('levels', 0)

    creature = ParsedCreature(
        name=data.get('name', 'Unknown'),
        size=_foundry_size(traits.get('size', system.get('traits', {}).get('size', ''))),
        creature_type=race or _foundry_type(details.get('type', {})),
        challenge_rating=str(details.get('cr', details.get('challenge', {}).get('value', ''))),
    )

    # Store PC info for to_flavor_request
    if actor_type == 'character':
        creature._pc_class = char_class
        creature._pc_level = char_level

    # Parse items into abilities
    for item in items:
        ability = _parse_foundry_item(item)
        if ability:
            creature.abilities.append(ability)

    return creature


def _foundry_size(size_val) -> str:
    """Convert Foundry size code to readable string."""
    size_map = {
        'tiny': 'Tiny', 'sm': 'Small', 'med': 'Medium',
        'lg': 'Large', 'huge': 'Huge', 'grg': 'Gargantuan',
    }
    if isinstance(size_val, str):
        return size_map.get(size_val.lower(), size_val.capitalize())
    return ''


def _foundry_type(type_val) -> str:
    """Extract creature type from Foundry type field (can be string or object)."""
    if isinstance(type_val, str):
        return type_val
    if isinstance(type_val, dict):
        return type_val.get('value', '')
    return ''


def _parse_foundry_item(item: dict):
    """Parse a single Foundry item into a ParsedAbility, or None if not relevant."""
    item_type = item.get('type', '')
    ability_type = _TYPE_MAP.get(item_type)
    if not ability_type:
        return None

    # Skip passive equipment with no activation (armor, shields, mundane gear)
    if item_type == 'equipment':
        activation = item.get('system', {}).get('activation', {})
        act_type = activation.get('type', '') if isinstance(activation, dict) else ''
        if not act_type:
            return None

    name = item.get('name', 'Unknown')
    system = item.get('system', item.get('data', {}))
    description = ''
    desc_data = system.get('description', {})
    if isinstance(desc_data, dict):
        description = desc_data.get('value', '')
    elif isinstance(desc_data, str):
        description = desc_data

    # Strip HTML tags from description
    import re
    description = re.sub(r'<[^>]+>', '', description).strip()

    # Extract attack bonus
    attack_bonus = None
    attack_data = system.get('attackBonus', system.get('attack', {}).get('bonus', None))
    if attack_data:
        try:
            attack_bonus = int(attack_data)
        except (ValueError, TypeError):
            pass

    # Extract damage
    damage = None
    dmg = system.get('damage', {})
    if isinstance(dmg, dict):
        parts = dmg.get('parts', [])
        if parts and isinstance(parts[0], (list, tuple)):
            damage = parts[0][0]  # First damage formula

    # Extract save
    save_dc = None
    save_type = None
    save = system.get('save', {})
    if isinstance(save, dict) and save.get('ability'):
        save_type = save['ability'].upper()[:3]
        save_dc = save.get('dc')

    # Detect spells
    if item_type == 'spell':
        level = system.get('level', 1)
        ability_type = 'cantrip' if level == 0 else 'spell'

    # Extract activation type for action classification
    activation = system.get('activation', {})
    if isinstance(activation, dict):
        act_type = activation.get('type', '')
        if act_type == 'reaction':
            ability_type = 'reaction'
        elif act_type == 'bonus':
            ability_type = 'bonus_action'
        elif act_type == 'legendary':
            ability_type = 'legendary'

    # Detect multi-phase from activities
    activities = system.get('activities', {})
    activity_types = list({
        act.get('type', '')
        for act in activities.values()
        if act.get('type', '')
    })
    is_multi_phase = len(activity_types) > 1

    return ParsedAbility(
        name=name,
        ability_type=ability_type,
        description=description,
        damage=damage,
        attack_bonus=attack_bonus,
        save_dc=save_dc,
        save_type=save_type,
        is_multi_phase=is_multi_phase,
        activity_types=activity_types,
        from_structured_source=True,
    )
