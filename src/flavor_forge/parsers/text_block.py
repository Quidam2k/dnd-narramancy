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
    'villain actions': 'villain_action',
    'mythic actions': 'legendary',
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

# CR line: "Challenge 5 (1,800 XP)" or "Challenge 1/4 (50 XP)" or "CR 11" or "CR 11 Solo"
_CR_RE = re.compile(r'(?:Challenge|CR)\s+([\d/]+)', re.IGNORECASE)

# Creature header line 2: "Medium humanoid (goblinoid), neutral evil"
_HEADER_RE = re.compile(
    r'^(Tiny|Small|Medium|Large|Huge|Gargantuan)\s+(.+?)(?:,\s*.+)?$',
    re.IGNORECASE,
)

# Feature line: "Name. Description..." or "Name (Recharge 5-6). Description..."
_FEATURE_RE = re.compile(r'^(?P<name>[A-Z][^.]*?(?:\s*\([^)]*\))?)\.\s+(?P<desc>.+)')

# MCDM-style numbered action: "Action 1: Name. Description" or "Action 1: Name! Description"
_NUMBERED_ACTION_RE = re.compile(
    r'^Action\s+\d+:\s*(?P<name>[^.!]+)[.!]\s*(?P<desc>.+)',
    re.IGNORECASE,
)

# Preamble lines that describe section mechanics, not actual abilities
_PREAMBLE_RE = re.compile(
    r'has\s+(?:three|two|one|four|five)\s+(?:villain|mythic|legendary)\s+actions?',
    re.IGNORECASE,
)


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

    # Scan for CR, saves, and skills before parsing abilities
    for line in lines:
        m = _CR_RE.search(line)
        if m:
            creature.challenge_rating = m.group(1)
        if line.startswith('Saving Throws'):
            creature.save_proficiencies = _parse_save_line(line)
        if line.startswith('Skills'):
            creature.skill_proficiencies = _parse_skill_line(line)

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
        if re.match(r'^CR\s+[\d/]', line, re.IGNORECASE):
            continue
        if re.match(r'^[\d,]+\s*XP\b', line):
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

        # Try MCDM-style numbered action: "Action 1: Name. Description..."
        m = _NUMBERED_ACTION_RE.match(line)
        if m:
            name = m.group('name').strip()
            desc = m.group('desc').strip()
            while i < len(lines):
                if lines[i] and not _is_new_entry(lines[i]):
                    desc += ' ' + lines[i]
                    i += 1
                elif not lines[i]:
                    peek = i + 1
                    while peek < len(lines) and not lines[peek]:
                        peek += 1
                    if peek < len(lines) and not _is_new_entry(lines[peek]):
                        desc += ' ' + lines[peek]
                        i = peek + 1
                    else:
                        break
                else:
                    break
            ability = ParsedAbility(
                name=name,
                ability_type=current_section,
                description=desc,
            )
            _extract_save_dc(desc, ability)
            _extract_damage_from_desc(desc, ability)
            creature.abilities.append(ability)
            continue

        # Try feature/action pattern
        m = _FEATURE_RE.match(line)
        if m:
            name = m.group('name').strip()
            desc = m.group('desc').strip()

            # Skip preamble paragraphs (e.g. "Emer has three villain actions...")
            if _PREAMBLE_RE.search(line):
                # Consume any continuation lines too
                while i < len(lines) and lines[i] and not _is_new_entry(lines[i]):
                    i += 1
                continue

            # Collect continuation lines — also peek past blank lines for
            # multi-paragraph ability descriptions (e.g. Stone Gaze)
            while i < len(lines):
                if lines[i] and not _is_new_entry(lines[i]):
                    desc += ' ' + lines[i]
                    i += 1
                elif not lines[i]:
                    # Blank line — peek ahead to see if next content is a continuation
                    peek = i + 1
                    while peek < len(lines) and not lines[peek]:
                        peek += 1
                    if peek < len(lines) and not _is_new_entry(lines[peek]):
                        desc += ' ' + lines[peek]
                        i = peek + 1
                    else:
                        break
                else:
                    break

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
    """Check if a line looks like a new entry (starts with capitalized name followed by period).

    Distinguishes "Snake Bite. Melee Weapon Attack..." (new entry) from
    "If a creature who is turning to stone..." (continuation paragraph).
    """
    lower = line.lower().rstrip('.')
    if lower in _SECTION_HEADERS:
        return True
    if _ATTACK_RE.match(line):
        return True
    m = _FEATURE_RE.match(line)
    if m:
        name = m.group('name').strip()
        # Continuation paragraphs start with common sentence words, not ability names.
        # Ability names are short (1-5 words) and often contain parentheticals.
        # "If a creature", "While turning", "A creature" etc. are continuations.
        first_word = name.split()[0] if name.split() else ''
        continuation_starters = {
            'if', 'while', 'when', 'a', 'an', 'the', 'each', 'any', 'at',
            'on', 'for', 'this', 'that', 'these', 'those', 'once', 'until',
            'after', 'before', 'as', 'alternatively', 'in', 'additionally',
        }
        if first_word.lower() in continuation_starters:
            return False
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


# "Saving Throws DEX +7, CON +5, WIS +4"
_SAVE_ENTRY_RE = re.compile(r'(STR|DEX|CON|INT|WIS|CHA)\s*([+-]\d+)', re.IGNORECASE)

def _parse_save_line(line: str) -> dict:
    """Parse a 'Saving Throws' line into {abbrev: bonus}."""
    return {m.group(1).lower(): int(m.group(2)) for m in _SAVE_ENTRY_RE.finditer(line)}


# "Skills Perception +4, Stealth +10"
_SKILL_ENTRY_RE = re.compile(r'([A-Za-z ]+?)\s*([+-]\d+)')

def _parse_skill_line(line: str) -> dict:
    """Parse a 'Skills' line into {skill_name: bonus}."""
    # Remove the "Skills" prefix
    rest = line.split('Skills', 1)[-1].strip()
    result = {}
    for m in _SKILL_ENTRY_RE.finditer(rest):
        skill = m.group(1).strip().lower()
        if skill:
            result[skill] = int(m.group(2))
    return result
