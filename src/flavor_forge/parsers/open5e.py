"""Open5e API client for fetching monster stat blocks."""

import json
import urllib.request
import urllib.parse
from typing import List, Optional

from ..models import ParsedCreature, ParsedAbility

BASE_URL = "https://api.open5e.com/v1/monsters/"


def fetch_creature(slug: str) -> ParsedCreature:
    """Fetch a creature by slug from Open5e API.

    Args:
        slug: URL slug like "goblin" or "adult-red-dragon"
    """
    url = f"{BASE_URL}{urllib.parse.quote(slug)}/"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FlavorForge/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"Creature '{slug}' not found on Open5e. Try search_creatures() for fuzzy lookup.")
        raise

    return _parse_open5e_data(data)


def search_creatures(query: str, limit: int = 10) -> List[dict]:
    """Search Open5e for creatures matching a query.

    Returns list of dicts with 'slug', 'name', 'cr', 'type'.
    """
    params = urllib.parse.urlencode({'search': query, 'limit': limit})
    url = f"{BASE_URL}?{params}"

    req = urllib.request.Request(url, headers={'User-Agent': 'FlavorForge/1.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    return [
        {
            'slug': r['slug'],
            'name': r['name'],
            'cr': r.get('challenge_rating', '?'),
            'type': r.get('type', ''),
        }
        for r in data.get('results', [])
    ]


def _parse_open5e_data(data: dict) -> ParsedCreature:
    """Convert Open5e JSON response to ParsedCreature."""
    creature = ParsedCreature(
        name=data.get('name', 'Unknown'),
        size=data.get('size', ''),
        creature_type=data.get('type', ''),
        challenge_rating=str(data.get('challenge_rating', '')),
    )

    # Map Open5e sections to ability types
    section_map = {
        'actions': 'action',
        'special_abilities': 'feature',
        'reactions': 'reaction',
        'legendary_actions': 'legendary',
        'bonus_actions': 'bonus_action',
    }

    for section_key, ability_type in section_map.items():
        section = data.get(section_key)
        if not section:
            continue
        for item in section:
            ability = _parse_open5e_ability(item, ability_type)
            creature.abilities.append(ability)

    return creature


def _parse_open5e_ability(item: dict, default_type: str) -> ParsedAbility:
    """Parse a single Open5e ability/action entry."""
    name = item.get('name', 'Unknown')
    desc = item.get('desc', '')

    # Detect if it's an attack from the description
    ability_type = default_type
    attack_bonus = None
    if item.get('attack_bonus'):
        ability_type = 'attack'
        attack_bonus = item['attack_bonus']
    elif 'attack:' in desc.lower() and 'to hit' in desc.lower():
        ability_type = 'attack'
        # Try to extract attack bonus from description
        import re
        m = re.search(r'\+(\d+)\s+to\s+hit', desc)
        if m:
            attack_bonus = int(m.group(1))

    # Extract damage
    damage = None
    damage_dice = item.get('damage_dice')
    damage_bonus = item.get('damage_bonus')
    if damage_dice:
        damage = damage_dice
        if damage_bonus:
            damage = f"{damage_dice}+{damage_bonus}"

    # Extract save DC from description
    save_dc = None
    save_type = None
    import re
    m = re.search(r'DC\s+(\d+)\s+(\w+)\s+saving\s+throw', desc, re.IGNORECASE)
    if m:
        save_dc = int(m.group(1))
        save_type = m.group(2).upper()[:3]

    # Extract recharge
    recharge = None
    m = re.search(r'\(Recharge\s+(\d+(?:[–-]\d+)?)\)', name + ' ' + desc, re.IGNORECASE)
    if m:
        recharge = m.group(1)
        name = re.sub(r'\s*\(Recharge\s+\d+(?:[–-]\d+)?\)', '', name).strip()

    return ParsedAbility(
        name=name,
        ability_type=ability_type,
        description=desc,
        damage=damage,
        attack_bonus=attack_bonus,
        save_dc=save_dc,
        save_type=save_type,
        recharge=recharge,
    )
