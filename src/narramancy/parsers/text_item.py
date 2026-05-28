"""Parser for plain-text magic item and spell descriptions."""

import re

from ..models import ParsedCreature, ParsedAbility
from .text_block import parse_text_block


# Magic item type lines (typically line 2 of a magic item description)
_MAGIC_ITEM_RE = re.compile(
    r'^(?:Wondrous [Ii]tem|Weapon\s*\(|Armor\s*\(|Potion,|Ring,|Rod,|Staff,|Scroll,|Wand,)',
    re.IGNORECASE,
)

# Spell level line: "3rd-level evocation" or "Evocation cantrip"
_SPELL_LEVEL_RE = re.compile(
    r'^(?:(\d+)\w{2}-level\s+(\w+)|(\w+)\s+cantrip)',
    re.IGNORECASE,
)

# Save DC in description text
_SAVE_DC_RE = re.compile(r'DC\s+(\d+)\s+(\w+)\s+saving\s+throw', re.IGNORECASE)

# Damage in description text
_DAMAGE_RE = re.compile(r'(\d+d\d+(?:\s*[+-]\s*\d+)?)\s+(\w+)\s+damage', re.IGNORECASE)


def is_text_item(text: str) -> bool:
    """Check if text looks like a magic item or spell description."""
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return False
    # Check second line for item/spell pattern
    second = lines[1].strip()
    if _MAGIC_ITEM_RE.match(second):
        return True
    if _SPELL_LEVEL_RE.match(second):
        return True
    return False


def parse_text_item(text: str) -> ParsedCreature:
    """Parse a text magic item or spell description into a synthetic ParsedCreature.

    Falls back to parse_text_block() if no item/spell pattern is detected.
    """
    if not is_text_item(text):
        return parse_text_block(text)

    lines = text.strip().splitlines()
    name = lines[0].strip()
    second = lines[1].strip()

    # Determine ability type
    ability_type = 'feature'
    if _SPELL_LEVEL_RE.match(second):
        m = _SPELL_LEVEL_RE.match(second)
        if m.group(3):  # cantrip form
            ability_type = 'cantrip'
        else:
            ability_type = 'spell'

    # Build description from remaining lines
    description = '\n'.join(lines[2:]).strip()

    # Extract combat-relevant data
    save_dc = None
    save_type = None
    damage = None

    m = _SAVE_DC_RE.search(description)
    if m:
        save_dc = int(m.group(1))
        save_type = m.group(2).upper()[:3]

    m = _DAMAGE_RE.search(description)
    if m:
        damage = m.group(0)

    ability = ParsedAbility(
        name=name,
        ability_type=ability_type,
        description=description,
        save_dc=save_dc,
        save_type=save_type,
        damage=damage,
    )

    creature = ParsedCreature(name=name)
    creature._token_pattern = '*'
    creature.abilities.append(ability)
    return creature
