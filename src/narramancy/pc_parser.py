"""Foundry VTT PC (character) actor JSON parser."""

import re

from .models import ParsedCreature, ParsedAbility

# Reverse map: skill abbreviation -> full name
_SKILL_ABBR_TO_NAME = {
    'acr': 'acrobatics', 'ani': 'animal handling', 'arc': 'arcana',
    'ath': 'athletics', 'dec': 'deception', 'his': 'history',
    'ins': 'insight', 'itm': 'intimidation', 'inv': 'investigation',
    'med': 'medicine', 'nat': 'nature', 'prc': 'perception',
    'prf': 'performance', 'per': 'persuasion', 'rel': 'religion',
    'slt': 'sleight of hand', 'ste': 'stealth', 'sur': 'survival',
}


def parse_foundry_pc(data: dict) -> ParsedCreature:
    """Parse a Foundry VTT character actor export into a ParsedCreature.

    Extracts equipped weapons, prepared spells, class/race/feat features,
    and save/skill proficiencies.
    """
    system = data.get('system', {})

    # --- Character metadata ---
    name = data.get('name', 'Unknown')
    race = ''
    class_name = ''
    class_level = 0
    subclass_name = ''

    items = data.get('items', [])
    for item in items:
        itype = item.get('type', '')
        if itype == 'race':
            race = item.get('name', '')
        elif itype == 'class':
            class_name = item.get('name', '')
            class_level = item.get('system', {}).get('levels', 0)
        elif itype == 'subclass':
            subclass_name = item.get('name', '')

    creature_type = class_name or 'Adventurer'
    if race:
        creature_type = f"{race} {creature_type}"
    if class_level:
        creature_type += f" {class_level}"
    if subclass_name:
        creature_type += f" ({subclass_name})"

    context_blob = f"{name} is a level {class_level} {race} {class_name}"
    if subclass_name:
        context_blob += f" ({subclass_name})"

    creature = ParsedCreature(
        name=name,
        creature_type=creature_type,
        challenge_rating=str(class_level),
        context_blob=context_blob,
    )
    creature._pc_class = class_name or 'Adventurer'
    creature._pc_level = class_level

    # --- Proficiencies ---
    abilities_data = system.get('abilities', {})
    for ab_key in ('str', 'dex', 'con', 'int', 'wis', 'cha'):
        ab = abilities_data.get(ab_key, {})
        if ab.get('proficient', 0) > 0:
            creature.save_proficiencies[ab_key] = ab.get('proficient', 1)

    skills_data = system.get('skills', {})
    for sk_key, sk_info in skills_data.items():
        if sk_info.get('value', 0) > 0:
            full_name = _SKILL_ABBR_TO_NAME.get(sk_key, sk_key)
            creature.skill_proficiencies[full_name] = sk_info['value']

    # --- Parse items into abilities (deduplicate by name) ---
    seen_names = set()
    for item in items:
        itype = item.get('type', '')
        if itype == 'weapon':
            _parse_weapon(item, creature, seen_names)
        elif itype == 'spell':
            _parse_spell(item, creature, seen_names)
        elif itype == 'feat':
            _parse_feat(item, creature, seen_names)
        # Skip: equipment, consumable, loot, tool, container, background, class, subclass, race

    return creature


def _parse_weapon(item: dict, creature: ParsedCreature, seen: set):
    """Add equipped weapons as attack abilities."""
    sys = item.get('system', {})
    if not sys.get('equipped', False):
        return

    name = item.get('name', 'Unknown')
    if name in seen:
        return
    seen.add(name)
    ability = _extract_ability(item, default_type='attack')
    creature.abilities.append(ability)


def _parse_spell(item: dict, creature: ParsedCreature, seen: set):
    """Add cantrips and prepared/at-will spells."""
    sys = item.get('system', {})
    level = sys.get('level', 0)
    prepared = sys.get('prepared', 0)
    method = sys.get('method', '')

    include = False
    if level == 0:
        include = True
    elif prepared or method in ('atwill', 'innate'):
        include = True

    if not include:
        return

    name = item.get('name', 'Unknown')
    if name in seen:
        return
    seen.add(name)

    default_type = 'cantrip' if level == 0 else 'spell'
    ability = _extract_ability(item, default_type=default_type)
    creature.abilities.append(ability)


def _parse_feat(item: dict, creature: ParsedCreature, seen: set):
    """Add class features, racial features, and feats. Skip generic actions."""
    sys = item.get('system', {})
    feat_type = sys.get('type', {})
    if isinstance(feat_type, dict):
        feat_type = feat_type.get('value', '')

    # Skip generic D&D actions (Dash, Dodge, Help, etc.)
    if not feat_type:
        return

    if feat_type not in ('class', 'race', 'feat'):
        return

    name = item.get('name', 'Unknown')
    if name in seen:
        return
    seen.add(name)
    ability = _extract_ability(item, default_type='feature')
    creature.abilities.append(ability)


def _extract_ability(item: dict, default_type: str) -> ParsedAbility:
    """Extract a ParsedAbility from a Foundry item, reusing logic from foundry.py."""
    name = item.get('name', 'Unknown')
    sys = item.get('system', {})

    # Description
    description = ''
    desc_data = sys.get('description', {})
    if isinstance(desc_data, dict):
        description = desc_data.get('value', '')
    elif isinstance(desc_data, str):
        description = desc_data
    description = re.sub(r'<[^>]+>', '', description).strip()

    # Attack bonus
    attack_bonus = None
    attack_data = sys.get('attackBonus', sys.get('attack', {}).get('bonus', None))
    if attack_data:
        try:
            attack_bonus = int(attack_data)
        except (ValueError, TypeError):
            pass

    # Damage
    damage = None
    dmg = sys.get('damage', {})
    if isinstance(dmg, dict):
        parts = dmg.get('parts', [])
        if parts and isinstance(parts[0], (list, tuple)):
            damage = parts[0][0]

    # Save
    save_dc = None
    save_type = None
    save = sys.get('save', {})
    if isinstance(save, dict) and save.get('ability'):
        save_type = save['ability'].upper()[:3]
        save_dc = save.get('dc')

    # Determine ability type
    ability_type = default_type
    item_type = item.get('type', '')
    if item_type == 'spell':
        level = sys.get('level', 1)
        ability_type = 'cantrip' if level == 0 else 'spell'

    # Override with activation type (reaction, bonus)
    activation = sys.get('activation', {})
    if isinstance(activation, dict):
        act_type = activation.get('type', '')
        if act_type == 'reaction':
            ability_type = 'reaction'
        elif act_type == 'bonus':
            ability_type = 'bonus_action'

    return ParsedAbility(
        name=name,
        ability_type=ability_type,
        description=description,
        damage=damage,
        attack_bonus=attack_bonus,
        save_dc=save_dc,
        save_type=save_type,
    )
