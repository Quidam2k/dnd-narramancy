"""D&D Beyond character sheet PDF parser.

Extracts character data from D&D Beyond PDF exports, which use PDF form fields
(annotations) rather than text. Produces a ParsedCreature matching the same shape
as the Foundry PC parser.

Limitation: D&D Beyond PDFs do not distinguish prepared from unprepared spells —
all show 'O'. Only cantrips and always-prepared ('P') spells are imported.
"""

import re

from ..models import ParsedCreature, ParsedAbility

# Map form field skill names to standard lowercase skill names
_SKILL_FIELDS = {
    'Acrobatics': 'acrobatics',
    'Animal': 'animal handling',  # field is "Animal" not "AnimalHandling"
    'Arcana': 'arcana',
    'Athletics': 'athletics',
    'Deception': 'deception',
    'History': 'history',
    'Insight': 'insight',
    'Intimidation': 'intimidation',
    'Investigation': 'investigation',
    'Medicine': 'medicine',
    'Nature': 'nature',
    'Perception': 'perception',
    'Performance': 'performance',
    'Persuasion': 'persuasion',
    'Religion': 'religion',
    'SleightofHand': 'sleight of hand',
    'Stealth': 'stealth',  # field is "Stealth " (with trailing space)
    'Survival': 'survival',
}

# Map save field prefixes to abbreviations
_SAVE_FIELDS = {
    'Str': 'str', 'Dex': 'dex', 'Con': 'con',
    'Int': 'int', 'Wis': 'wis', 'Cha': 'cha',
}

# Features that are purely passive (no action, no combat relevance)
_PASSIVE_FEATURES = {
    'lucky', 'brave', 'halfling nimbleness', 'darkvision', 'stonecunning',
    'trance', 'fey ancestry', 'keen senses', 'mask of the wild',
    'dwarven resilience', 'dwarven toughness', 'relentless endurance',
    'savage attacks', 'spellcasting', 'core druid traits', 'primal order',
    'druid subclass', 'ability score improvement', 'timberwalk',
    'star map', 'druidic', 'musician',
    'wayfarer ability score improvements',
}

# Casting time codes that indicate reaction/bonus action
_BONUS_ACTION_TIMES = {'1BA', 'BA', '1 Bonus Action', 'Bonus'}
_REACTION_TIMES = {'1R', 'R', '1 Reaction', 'Reaction'}


def is_dndbeyond_pdf(path: str) -> bool:
    """Check if a PDF is a D&D Beyond character sheet by looking for form fields."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        if not pdf.pages:
            return False
        annots = pdf.pages[0].annots or []
        field_names = {a.get('title', '') for a in annots}
        # D&D Beyond sheets have these distinctive field names
        return 'CharacterName' in field_names and 'CLASS  LEVEL' in field_names


def parse_dndbeyond_pdf(path: str) -> ParsedCreature:
    """Parse a D&D Beyond character sheet PDF into a ParsedCreature."""
    import pdfplumber

    # Extract all form fields from all pages, plus ordered spell annotations.
    # Don't overwrite non-empty values with empty ones (duplicate field names across pages).
    fields = {}
    spell_annots_ordered = []  # (title, value) in document order for spells
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for a in (page.annots or []):
                title = a.get('title', '').strip()
                if not title:
                    continue
                raw = a.get('data', {}).get('V', b'')
                val = _decode_value(raw)
                # Only overwrite if new value is non-empty or field not yet seen
                if val or title not in fields:
                    fields[title] = val
                # Collect spell-related annotations in page order
                if title.startswith('spell'):
                    spell_annots_ordered.append((title, val))

    # --- Header ---
    name = fields.get('CharacterName', 'Unknown')
    class_level_str = fields.get('CLASS  LEVEL', '')
    race = fields.get('RACE', '')
    background = fields.get('BACKGROUND', '')

    class_name, level = _parse_class_level(class_level_str)

    creature_type = f"{race} {class_name} {level}".strip()
    context_blob = f"{name} is a level {level} {race} {class_name}"

    creature = ParsedCreature(
        name=name,
        size=fields.get('SIZE', ''),
        creature_type=creature_type,
        challenge_rating=str(level),
        context_blob=context_blob,
    )

    # --- Save proficiencies ---
    for prefix, abbr in _SAVE_FIELDS.items():
        prof_val = fields.get(f'{prefix}Prof', '')
        if prof_val:  # Non-empty = proficient (could be bullet char or 'P')
            creature.save_proficiencies[abbr] = 1

    # --- Skill proficiencies ---
    for field_name, skill_name in _SKILL_FIELDS.items():
        prof_key = f'{field_name}Prof'
        # Handle the trailing space issue: "Stealth " vs "StealthProf"
        prof_val = fields.get(prof_key, '')
        if prof_val:  # 'P' or non-empty = proficient
            # Get the bonus value
            bonus_val = fields.get(field_name, '') or fields.get(field_name + ' ', '')
            bonus = _parse_bonus(bonus_val)
            creature.skill_proficiencies[skill_name] = bonus if bonus else 1

    # --- Weapon attacks ---
    seen_names = set()
    _extract_weapon_attacks(fields, creature, seen_names)

    # --- Features from FeaturesTraits and Actions fields ---
    _extract_features(fields, creature, seen_names)

    # --- Spells: all spells ---
    _extract_spells(fields, spell_annots_ordered, creature, seen_names)

    # --- All 6 saves and all 18 skills as abilities (PCs use them all) ---
    _add_save_abilities(creature)
    _add_skill_abilities(creature)

    return creature


def _add_save_abilities(creature: ParsedCreature):
    """Add all 6 saving throw abilities. PCs make all saves, not just proficient ones."""
    for abbr, name in [
        ('str', 'STR Save'), ('dex', 'DEX Save'), ('con', 'CON Save'),
        ('int', 'INT Save'), ('wis', 'WIS Save'), ('cha', 'CHA Save'),
    ]:
        creature.abilities.append(ParsedAbility(
            name=name,
            ability_type='save',
            description=f'{creature.name} makes a {name.split()[0]} saving throw',
        ))


def _add_skill_abilities(creature: ParsedCreature):
    """Add all 18 skill abilities. PCs use all skills, not just proficient ones."""
    all_skills = [
        'Acrobatics', 'Animal Handling', 'Arcana', 'Athletics',
        'Deception', 'History', 'Insight', 'Intimidation',
        'Investigation', 'Medicine', 'Nature', 'Perception',
        'Performance', 'Persuasion', 'Religion', 'Sleight of Hand',
        'Stealth', 'Survival',
    ]
    for skill in all_skills:
        bonus = creature.skill_proficiencies.get(skill.lower(), 0)
        desc = f'{creature.name} makes a {skill} check'
        if bonus:
            desc += f' (+{bonus})'
        creature.abilities.append(ParsedAbility(
            name=skill,
            ability_type='skill',
            description=desc,
        ))


def _decode_value(raw) -> str:
    """Decode a PDF form field value, handling UTF-16BE BOM."""
    if isinstance(raw, str):
        return raw
    if not isinstance(raw, bytes) or not raw:
        return ''
    # UTF-16BE with BOM
    if raw[:2] == b'\xfe\xff':
        try:
            return raw.decode('utf-16')
        except UnicodeDecodeError:
            pass
    # Plain ASCII/UTF-8
    try:
        return raw.decode('utf-8', errors='replace')
    except Exception:
        return ''


def _parse_class_level(text: str) -> tuple:
    """Parse 'Druid 5' into ('Druid', 5)."""
    m = re.match(r'(.+?)\s+(\d+)', text.strip())
    if m:
        return m.group(1).strip(), int(m.group(2))
    return text.strip(), 0


def _parse_bonus(text: str) -> int:
    """Parse '+8' or '-1' into an integer."""
    m = re.match(r'[+-]?\d+', text.strip())
    return int(m.group()) if m else 0


def _extract_weapon_attacks(fields: dict, creature: ParsedCreature, seen: set):
    """Extract weapon attacks from Wpn Name / Wpn{N} AtkBonus / Wpn{N} Damage fields."""
    # Fields follow an inconsistent naming pattern:
    # Wpn Name, Wpn1 AtkBonus, Wpn1 Damage, Wpn Notes 1
    # Wpn Name 2, Wpn2 AtkBonus , Wpn2 Damage , Wpn Notes 2
    for i in range(1, 20):
        if i == 1:
            name_key = 'Wpn Name'
        else:
            name_key = f'Wpn Name {i}'

        name = fields.get(name_key, '').strip()
        if not name:
            continue

        if name.lower() in seen:
            continue
        seen.add(name.lower())

        # Try various key patterns for atk bonus and damage (fields have inconsistent spacing)
        atk_bonus = None
        damage = None
        for suffix in ('', ' ', '  '):
            atk_val = fields.get(f'Wpn{i} AtkBonus{suffix}', '')
            if atk_val:
                atk_bonus = _parse_bonus(atk_val)
                break
        for suffix in ('', ' '):
            dmg_val = fields.get(f'Wpn{i} Damage{suffix}', '')
            if dmg_val:
                damage = dmg_val.strip()
                break

        notes = fields.get(f'Wpn Notes {i}', '').strip()

        # Determine ability type
        ability_type = 'attack'
        if notes:
            casting_time = notes.split(',')[0].strip() if ',' in notes else ''
            # Cantrips appearing in weapon table are still attacks

        creature.abilities.append(ParsedAbility(
            name=name,
            ability_type=ability_type,
            description=notes or f'{name} attack',
            damage=damage,
            attack_bonus=atk_bonus,
        ))


def _extract_features(fields: dict, creature: ParsedCreature, seen: set):
    """Extract features from FeaturesTraits{N} and Actions{N} fields.

    FeaturesTraits and Actions use different formatting so are processed separately.
    FeaturesTraits: "* Feature Name • Source Page#" with descriptions below.
    Actions: Section headers (=== ACTIONS ===) with named entries below.
    """
    # --- Process FeaturesTraits fields (class/race/feat features) ---
    feat_blocks = []
    for i in range(1, 20):
        val = fields.get(f'FeaturesTraits{i}', '')
        if val:
            feat_blocks.append(val)

    feat_text = '\n\n'.join(feat_blocks)
    current_section = 'feature'

    for block in re.split(r'\n\*\s+', feat_text):
        block = block.strip()
        if not block:
            continue

        # Check for section headers (=== DRUID FEATURES ===, === FEATS ===, etc.)
        # A header may appear at the start, end, or middle of a block.
        # Parse feature text BEFORE the header, then update section for text after.
        section_match = re.search(r'===\s*(.+?)\s*===', block)
        if section_match:
            # Parse any feature text before the header
            before = block[:section_match.start()].strip()
            if before:
                _parse_feature_block(before, current_section, creature, seen)

            section_name = section_match.group(1).upper()
            if 'BONUS' in section_name:
                current_section = 'bonus_action'
            elif 'REACTION' in section_name:
                current_section = 'reaction'
            elif 'ACTION' in section_name:
                current_section = 'action'
            else:
                current_section = 'feature'
            remaining = block[section_match.end():].strip()
            if not remaining:
                continue
            block = remaining

        _parse_feature_block(block, current_section, creature, seen)

    # --- Process Actions fields (action-formatted abilities) ---
    action_blocks = []
    for i in range(1, 20):
        val = fields.get(f'Actions{i}', '')
        if val:
            action_blocks.append(val)

    action_text = '\n\n'.join(action_blocks)
    current_section = 'action'

    # Split Actions text by section headers
    for section in re.split(r'===\s*(.+?)\s*===', action_text):
        section = section.strip()
        if not section:
            continue
        # Check if this part is a header name
        section_upper = section.upper()
        if section_upper in ('ACTIONS', 'BONUS ACTIONS', 'REACTIONS'):
            if 'BONUS' in section_upper:
                current_section = 'bonus_action'
            elif 'REACTION' in section_upper:
                current_section = 'reaction'
            else:
                current_section = 'action'
            continue

        # Parse entries within this action section
        # Entries: "Name\n     description" or just continuation text
        for entry in re.split(r'\n(?=[A-Z])', section):
            entry = entry.strip()
            if not entry:
                continue
            lines = entry.split('\n')
            first_line = lines[0].strip()

            # Skip generic actions list
            if first_line.lower().startswith('standard actions'):
                continue

            # Skip if it looks like a description continuation (starts with lowercase)
            if first_line and first_line[0].islower():
                continue

            # Extract name (before colon if present, e.g. "Archer: Luminous Arrow")
            name = first_line.split('\n')[0].strip()
            if not name or len(name) > 60:
                continue

            # Normalize for dedup: strip "Assume " prefix and " • ..." suffix
            normalized = name.lower()
            normalized = re.sub(r'\s*\u2022.*$', '', normalized).strip()
            if normalized.startswith('assume '):
                normalized = normalized[7:]

            if normalized in _PASSIVE_FEATURES or normalized in seen:
                continue
            seen.add(normalized)

            desc_lines = [l.strip() for l in lines[1:] if l.strip()]
            description = ' '.join(desc_lines)[:500]

            ability_type = current_section
            desc_lower = description.lower()
            if 'bonus action' in desc_lower and ability_type != 'bonus_action':
                ability_type = 'bonus_action'

            creature.abilities.append(ParsedAbility(
                name=name,
                ability_type=ability_type,
                description=description,
            ))


def _parse_feature_block(block: str, section_type: str, creature: ParsedCreature, seen: set):
    """Parse a single feature block (text after a * marker)."""
    lines = block.split('\n')
    first_line = lines[0].strip()

    # Match "Feature Name • Source Page#" or "Feature Name"
    name_match = re.match(r'^([^\u2022\n]+?)(?:\s*\u2022\s*.*)?$', first_line)
    if not name_match:
        return

    feat_name = name_match.group(1).strip()
    if not feat_name:
        return

    if feat_name.lower() in _PASSIVE_FEATURES:
        return

    if feat_name.lower() in seen:
        return
    seen.add(feat_name.lower())

    # Collect description from remaining lines (skip sub-features starting with |)
    desc_lines = []
    for line in lines[1:]:
        line = line.strip()
        if line.startswith('|'):
            sub_name = line.lstrip('| ').strip()
            if sub_name and ':' in sub_name:
                desc_lines.append(sub_name)
        elif line and not line.startswith('==='):
            desc_lines.append(line)

    description = ' '.join(desc_lines)[:500]

    # Determine type based on description keywords
    ability_type = section_type
    desc_lower = description.lower()
    if 'bonus action' in desc_lower and ability_type == 'feature':
        ability_type = 'bonus_action'
    elif 'reaction' in desc_lower and ability_type == 'feature':
        ability_type = 'reaction'

    creature.abilities.append(ParsedAbility(
        name=feat_name,
        ability_type=ability_type,
        description=description,
    ))


def _extract_spells(fields: dict, spell_annots: list, creature: ParsedCreature, seen: set):
    """Extract all spells from spell form fields.

    Includes all spells — cantrips, always-prepared, and known/prepared.
    D&D Beyond PDFs can't distinguish prepared from unprepared (all show 'O'),
    so we include everything and let the user curate in the Web UI.

    Uses annotation ordering (spell_annots) to correctly track level transitions,
    since spellHeader indices (0,1,2,3) are separate from spellName indices (0-114).
    """
    # Build spell-level map by walking annotations in document order.
    # When we see a spellHeader, update the current level.
    # When we see a spellName, record its index and the current level.
    current_level = None
    spell_levels = {}  # spell index -> level

    for title, val in spell_annots:
        header_match = re.match(r'^spellHeader(\d+)$', title)
        name_match = re.match(r'^spellName(\d+)$', title)
        if header_match:
            if 'CANTRIP' in val.upper():
                current_level = 0
            else:
                m = re.search(r'(\d+)\w*\s+LEVEL', val, re.IGNORECASE)
                current_level = int(m.group(1)) if m else None
        elif name_match:
            spell_levels[int(name_match.group(1))] = current_level

    # Now iterate by spell index with correct level info
    for i in sorted(spell_levels.keys()):
        name = fields.get(f'spellName{i}', '').strip()
        if not name:
            continue

        level = spell_levels.get(i)
        is_cantrip = level == 0

        # Clean spell name: remove [R] ritual marker
        clean_name = re.sub(r'\s*\[R\]\s*$', '', name).strip()

        if clean_name.lower() in seen:
            continue
        seen.add(clean_name.lower())

        # Parse spell details
        save_hit = fields.get(f'spellSaveHit{i}', '').strip()
        casting_time = fields.get(f'spellCastingTime{i}', '').strip()
        spell_range = fields.get(f'spellRange{i}', '').strip()
        duration = fields.get(f'spellDuration{i}', '').strip()
        components = fields.get(f'spellComponents{i}', '').strip()

        # Parse attack bonus / save DC
        attack_bonus = None
        save_dc = None
        save_type = None
        if save_hit and save_hit != '--':
            atk_match = re.search(r'\+(\d+)', save_hit)
            if atk_match:
                attack_bonus = int(atk_match.group(1))
            save_match = re.match(r'([A-Z]{3})\s+(\d+)', save_hit)
            if save_match:
                save_type = save_match.group(1)
                save_dc = int(save_match.group(2))

        # Determine ability type
        ability_type = 'cantrip' if is_cantrip else 'spell'
        if casting_time in _REACTION_TIMES:
            ability_type = 'reaction'
        elif casting_time in _BONUS_ACTION_TIMES:
            ability_type = 'bonus_action'

        # Build description
        desc_parts = []
        if spell_range and spell_range != 'Self':
            desc_parts.append(f'Range: {spell_range}')
        if duration and duration != 'Instantaneous':
            desc_parts.append(f'Duration: {duration}')
        if components:
            desc_parts.append(f'Components: {components}')
        description = '. '.join(desc_parts) if desc_parts else clean_name

        creature.abilities.append(ParsedAbility(
            name=clean_name,
            ability_type=ability_type,
            description=description,
            attack_bonus=attack_bonus,
            save_dc=save_dc,
            save_type=save_type,
            range=spell_range if spell_range else None,
        ))
