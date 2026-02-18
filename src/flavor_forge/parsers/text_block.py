"""Plain text stat block parser for standard WotC format."""

import re
from typing import List, Optional

from ..models import ParsedCreature, ParsedAbility


# Section headers that divide a stat block
_SECTION_HEADERS = {
    'actions': 'action',
    'reactions': 'reaction',
    'legendary actions': 'legendary',
    'bonus actions': 'bonus_action',
    'lair actions': 'legendary',
}

# Attack line pattern: "Name. Melee/Ranged Weapon Attack: +N to hit, reach/range X, one target. Hit: N (dice) damage."
_ATTACK_RE = re.compile(
    r'^(?P<name>.+?)\.\s*'
    r'(?P<attack_type>Melee|Ranged|Melee or Ranged)\s+(?:Weapon|Spell)\s+Attack:\s*'
    r'\+(?P<bonus>\d+)\s+to\s+hit,\s*'
    r'(?P<range>.+?)\.\s*'
    r'Hit:\s*(?P<damage>.+)',
    re.IGNORECASE,
)

# Recharge pattern: "(Recharge 5-6)" or "(Recharge 6)"
_RECHARGE_RE = re.compile(r'\(Recharge\s+(\d+(?:[–-]\d+)?)\)', re.IGNORECASE)

# Save DC pattern: "DC 15 Dexterity saving throw"
_SAVE_DC_RE = re.compile(r'DC\s+(\d+)\s+(\w+)\s+saving\s+throw', re.IGNORECASE)

# Uses pattern: "(1/Day)" or "(3/Day Each)"
_USES_RE = re.compile(r'\((\d+/(?:Day|Short Rest|Long Rest)(?:\s+Each)?)\)', re.IGNORECASE)

# CR line: "Challenge 5 (1,800 XP)" or "Challenge 1/4 (50 XP)"
_CR_RE = re.compile(r'Challenge\s+([\d/]+)\s*\(', re.IGNORECASE)

# Creature header line 2: "Medium humanoid (goblinoid), neutral evil"
_HEADER_RE = re.compile(
    r'^(Tiny|Small|Medium|Large|Huge|Gargantuan)\s+(.+?)(?:,\s*.+)?$',
    re.IGNORECASE,
)

# Feature line: "Name. Description..." or "Name (Recharge 5-6). Description..."
_FEATURE_RE = re.compile(r'^(?P<name>[A-Z][^.]*?(?:\s*\([^)]*\))?)\.\s+(?P<desc>.+)')


def parse_text_block(text: str) -> ParsedCreature:
    """Parse a plain-text WotC-style stat block into a ParsedCreature."""
    lines = [l.strip() for l in text.strip().splitlines()]
    if not lines:
        raise ValueError("Empty stat block")

    creature = ParsedCreature(name=lines[0])
    current_section = 'feature'  # default for traits above Actions

    i = 1
    # Parse header line (size/type)
    if i < len(lines):
        m = _HEADER_RE.match(lines[i])
        if m:
            creature.size = m.group(1).capitalize()
            creature.creature_type = m.group(2).strip()
            i += 1

    # Scan for CR before parsing abilities
    for line in lines:
        m = _CR_RE.search(line)
        if m:
            creature.challenge_rating = m.group(1)
            break

    # Parse the rest of the block
    while i < len(lines):
        line = lines[i]
        i += 1

        # Check for section header
        lower = line.lower().rstrip('.')
        if lower in _SECTION_HEADERS:
            current_section = _SECTION_HEADERS[lower]
            continue

        # Skip blank lines and stat lines (STR, DEX, etc.)
        if not line or line.startswith('STR') or line.startswith('Armor Class'):
            continue
        if line.startswith('Hit Points') or line.startswith('Speed'):
            continue
        if line.startswith('Saving Throws') or line.startswith('Skills'):
            continue
        if line.startswith('Damage') or line.startswith('Condition'):
            continue
        if line.startswith('Senses') or line.startswith('Languages'):
            continue
        if line.startswith('Challenge') or line.startswith('Proficiency'):
            continue
        # Skip ability score rows (e.g. "16 (+3)  12 (+1) ...")
        if re.match(r'^\d+\s*\([+-]?\d+\)', line):
            continue

        # Try attack pattern first
        m = _ATTACK_RE.match(line)
        if m:
            ability = ParsedAbility(
                name=m.group('name').strip(),
                ability_type='attack',
                description=line,
                attack_bonus=int(m.group('bonus')),
                range=m.group('range').strip(),
                damage=m.group('damage').strip(),
            )
            _extract_recharge(line, ability)
            creature.abilities.append(ability)
            continue

        # Try feature/action pattern
        m = _FEATURE_RE.match(line)
        if m:
            name = m.group('name').strip()
            desc = m.group('desc').strip()

            # Collect continuation lines (indented or lowercase start)
            while i < len(lines) and lines[i] and not _is_new_entry(lines[i]):
                desc += ' ' + lines[i]
                i += 1

            ability = ParsedAbility(
                name=_clean_name(name),
                ability_type=current_section,
                description=desc,
            )
            _extract_recharge(name + '. ' + desc, ability)
            _extract_save_dc(desc, ability)
            _extract_uses(name + '. ' + desc, ability)
            _extract_damage_from_desc(desc, ability)
            creature.abilities.append(ability)
            continue

    return creature


def _is_new_entry(line: str) -> bool:
    """Check if a line looks like a new entry (starts with capitalized name followed by period)."""
    lower = line.lower().rstrip('.')
    if lower in _SECTION_HEADERS:
        return True
    if _ATTACK_RE.match(line):
        return True
    if _FEATURE_RE.match(line):
        return True
    return False


def _clean_name(name: str) -> str:
    """Remove recharge/uses annotations from ability name."""
    name = _RECHARGE_RE.sub('', name).strip()
    name = _USES_RE.sub('', name).strip()
    return name


def _extract_recharge(text: str, ability: ParsedAbility):
    m = _RECHARGE_RE.search(text)
    if m:
        ability.recharge = m.group(1)


def _extract_save_dc(text: str, ability: ParsedAbility):
    m = _SAVE_DC_RE.search(text)
    if m:
        ability.save_dc = int(m.group(1))
        ability.save_type = m.group(2).upper()[:3]


def _extract_uses(text: str, ability: ParsedAbility):
    m = _USES_RE.search(text)
    if m:
        ability.uses = m.group(1)


def _extract_damage_from_desc(text: str, ability: ParsedAbility):
    """Extract damage from description if not already an attack line."""
    if ability.damage:
        return
    m = re.search(r'(\d+d\d+(?:\s*[+-]\s*\d+)?)\s+(\w+)\s+damage', text, re.IGNORECASE)
    if m:
        ability.damage = m.group(0)
