"""Data models for Narramancy."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class FlavorTextRequest:
    """Request structure for flavor text generation."""
    character_name: str
    character_race: str
    character_class: str
    character_level: int
    ability_name: str
    ability_type: str
    ability_description: Optional[str] = None
    style: str = 'dramatic'  # dramatic|comedic|gritty|heroic
    variations: int = 5
    context_blob: Optional[str] = None  # Per-creature seasoning or character context
    has_outcomes: bool = True  # False = no resolution roll, skip success/failure generation
    pronouns: Optional[str] = None  # e.g. 'he/him' — set for named characters, None = monster ("it")


@dataclass
class FlavorTextResult:
    """Result structure for flavor text generation."""
    attempts: List[str]
    successes: List[str]
    failures: List[str]
    metadata: Dict[str, Any]
    crits: List[str] = field(default_factory=list)
    fumbles: List[str] = field(default_factory=list)
    barely_hits: List[str] = field(default_factory=list)
    barely_misses: List[str] = field(default_factory=list)
    miss_dodge: List[str] = field(default_factory=list)
    miss_armor: List[str] = field(default_factory=list)
    killing_blow: List[str] = field(default_factory=list)
    cast: List[str] = field(default_factory=list)


@dataclass
class ParsedAbility:
    """A single ability/action parsed from a monster stat block."""
    name: str
    ability_type: str  # attack|spell|cantrip|feature|action|reaction|legendary|bonus_action
    description: str
    damage: Optional[str] = None
    attack_bonus: Optional[int] = None
    save_dc: Optional[int] = None
    save_type: Optional[str] = None  # DEX, CON, etc.
    range: Optional[str] = None
    uses: Optional[str] = None
    recharge: Optional[str] = None  # "5-6", "short rest", etc.
    is_multi_phase: bool = False
    activity_types: List[str] = field(default_factory=list)
    # True when the ability comes from a parser with authoritative structured
    # activity data (Foundry's system.activities). For these, an empty
    # activity_types list means "no roll" — do NOT fall back to scanning the
    # description text, which false-positives on passives whose prose mentions
    # "ability check"/"saving throw" incidentally (e.g. Powerful Build).
    from_structured_source: bool = False


# Ability types whose use is itself a roll that can succeed or fail
_ROLL_OUTCOME_TYPES = {'attack', 'save', 'skill', 'death_save'}

# Foundry activity types that involve a resolution roll
_ROLL_ACTIVITY_TYPES = {'attack', 'save', 'check'}

# Fallback for text-block-parsed creatures: descriptions that mention a
# resolution roll mean success/failure flavor is meaningful. Also matches
# D&D Beyond importer enricher syntax like [[/save wis format=long]].
_ROLL_DESCRIPTION_RE = re.compile(
    r'attack roll|spell attack|saving throw|ability check|contested'
    r'|\[\[/(?:save|attack|check)\b',
    re.IGNORECASE,
)

# Reviewed aggressive cuts (by base name, parenthetical suffix stripped): named
# abilities where the *character* makes no meaningful pass/fail roll, even though
# the data or text might suggest one. Embedded-disbelief illusions (the observer
# rolls Investigation, not the caster), Cunning Action (the Hide check is its own
# Stealth entry), and damage-reduction reactions (you reduce damage, you don't
# pass/fail). These get attempts-only flavor regardless of activity/save data.
AGGRESSIVE_NO_OUTCOME = {
    'Minor Illusion',
    'Silent Image',
    'Cunning Action',
    'Deflect Attacks',
    "Stone's Endurance",
}


def _base_ability_name(name: str) -> str:
    """Strip a trailing ' (...)' source/variant suffix for name matching."""
    return re.sub(r'\s*\(.*\)$', '', name).strip()


def has_roll_outcomes(ability: 'ParsedAbility') -> bool:
    """Whether an ability involves a resolution roll (success/failure are meaningful).

    No-roll abilities (Wild Shape, Longstrider, initiative) can't hit or miss —
    generating success/failure tables for them wastes tokens on entries
    nothing ever triggers.
    """
    if _base_ability_name(ability.name) in AGGRESSIVE_NO_OUTCOME:
        return False
    if ability.attack_bonus is not None or ability.save_dc is not None:
        return True
    if ability.ability_type in _ROLL_OUTCOME_TYPES:
        return True
    if ability.activity_types:
        # Foundry activities are authoritative — long feature descriptions
        # mention rolls incidentally (Wild Shape retains save proficiencies)
        return bool(_ROLL_ACTIVITY_TYPES & set(ability.activity_types))
    if ability.from_structured_source:
        # Authoritative structured data with no roll activity = no roll.
        # Don't fall through to the description regex (false-positives on
        # passive features like Powerful Build, Fey Ancestry, War Caster).
        return False
    if ability.description and _ROLL_DESCRIPTION_RE.search(ability.description):
        return True
    return False


@dataclass
class ParsedCreature:
    """A monster/creature parsed from a stat block."""
    name: str
    size: str = ""
    creature_type: str = ""
    challenge_rating: str = ""
    abilities: List['ParsedAbility'] = field(default_factory=list)
    context_blob: Optional[str] = None
    pronouns: Optional[str] = None  # e.g. 'he/him' — set for PCs, None = monster ("it")
    skill_proficiencies: Dict[str, int] = field(default_factory=dict)  # e.g. {"perception": 4, "stealth": 10}
    save_proficiencies: Dict[str, int] = field(default_factory=dict)  # e.g. {"dex": 7, "con": 5}

    @classmethod
    def from_dict(cls, data: dict) -> 'ParsedCreature':
        """Reconstruct a ParsedCreature from a JSON-serializable dict.

        Handles the output format produced by _creature_to_dict() in __main__.py.
        """
        abilities = []
        for a in data.get('abilities', []):
            abilities.append(ParsedAbility(
                name=a['name'],
                ability_type=a['ability_type'],
                description=a.get('description', ''),
                damage=a.get('damage'),
                attack_bonus=a.get('attack_bonus'),
                save_dc=a.get('save_dc'),
                save_type=a.get('save_type'),
                range=a.get('range'),
                uses=a.get('uses'),
                recharge=a.get('recharge'),
                activity_types=a.get('activity_types', []),
                from_structured_source=a.get('from_structured_source', False),
            ))

        return cls(
            name=data['name'],
            size=data.get('size', ''),
            creature_type=data.get('type', ''),
            challenge_rating=data.get('cr', ''),
            abilities=abilities,
            context_blob=data.get('context'),
            pronouns=data.get('pronouns'),
            skill_proficiencies=data.get('skill_proficiencies', {}),
            save_proficiencies=data.get('save_proficiencies', {}),
        )

    def to_flavor_request(self, ability: 'ParsedAbility', style: str = 'dramatic', variations: int = 5) -> 'FlavorTextRequest':
        """Build a FlavorTextRequest from one of this creature's abilities."""
        # Use PC info if set by Foundry parser, otherwise fall back to monster defaults
        char_class = getattr(self, '_pc_class', '') or "Monster"
        char_level = getattr(self, '_pc_level', 0) or _cr_to_level(self.challenge_rating)
        return FlavorTextRequest(
            character_name=self.name,
            character_race=self.creature_type or "creature",
            character_class=char_class,
            character_level=char_level,
            ability_name=ability.name,
            ability_type=ability.ability_type,
            ability_description=ability.description,
            style=style,
            variations=variations,
            context_blob=self.context_blob,
            has_outcomes=has_roll_outcomes(ability),
            pronouns=self.pronouns,
        )


def _cr_to_level(cr: str) -> int:
    """Convert CR string to an approximate level for prompt purposes."""
    try:
        if '/' in cr:
            num, den = cr.split('/')
            val = int(num) / int(den)
        else:
            val = float(cr)
        return max(1, int(val))
    except (ValueError, ZeroDivisionError):
        return 1


GENERIC_ACTIONS = [
    ParsedAbility(
        name='Death Save',
        ability_type='death_save',
        description='The creature makes a death saving throw, clinging to life',
    ),
    ParsedAbility(
        name='Initiative',
        ability_type='initiative',
        description='The creature rolls for initiative at the start of combat',
    ),
]

SAVE_ABILITIES = {
    'str': 'STR Save',
    'dex': 'DEX Save',
    'con': 'CON Save',
    'int': 'INT Save',
    'wis': 'WIS Save',
    'cha': 'CHA Save',
}

# Map skill names (lowercase) to their dnd5e skill IDs
SKILL_ID_MAP = {
    'acrobatics': 'acr', 'animal handling': 'ani', 'arcana': 'arc',
    'athletics': 'ath', 'deception': 'dec', 'history': 'his',
    'insight': 'ins', 'intimidation': 'itm', 'investigation': 'inv',
    'medicine': 'med', 'nature': 'nat', 'perception': 'prc',
    'performance': 'prf', 'persuasion': 'per', 'religion': 'rel',
    'sleight of hand': 'slt', 'stealth': 'ste', 'survival': 'sur',
}


def get_save_abilities() -> List[ParsedAbility]:
    """Return ParsedAbility entries for all 6 saving throws."""
    return [
        ParsedAbility(
            name=name,
            ability_type='save',
            description=f'The creature makes a {name.split()[0]} saving throw against an effect',
        )
        for name in SAVE_ABILITIES.values()
    ]


def get_skill_abilities(skill_proficiencies: Dict[str, int]) -> List[ParsedAbility]:
    """Return ParsedAbility entries only for skills the creature is proficient in."""
    abilities = []
    for skill_name, bonus in skill_proficiencies.items():
        display_name = skill_name.title()
        abilities.append(ParsedAbility(
            name=display_name,
            ability_type='skill',
            description=f'The creature makes a {display_name} check (+{bonus})',
        ))
    return abilities


@dataclass
class AbilityData:
    """Data structure for character ability information used in flavor text generation."""
    name: str
    ability_type: str
    description: str
    character_name: str
    character_class: str
    character_level: int
    damage: Optional[str] = None
    range: Optional[str] = None
    duration: Optional[str] = None
    uses: Optional[str] = None
    save_dc: Optional[int] = None
