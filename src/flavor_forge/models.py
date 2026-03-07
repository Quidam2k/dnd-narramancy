"""Data models for Flavor Forge."""

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


@dataclass
class ParsedCreature:
    """A monster/creature parsed from a stat block."""
    name: str
    size: str = ""
    creature_type: str = ""
    challenge_rating: str = ""
    abilities: List['ParsedAbility'] = field(default_factory=list)
    context_blob: Optional[str] = None
    skill_proficiencies: Dict[str, int] = field(default_factory=dict)  # e.g. {"perception": 4, "stealth": 10}
    save_proficiencies: Dict[str, int] = field(default_factory=dict)  # e.g. {"dex": 7, "con": 5}

    def to_flavor_request(self, ability: 'ParsedAbility', style: str = 'dramatic', variations: int = 5) -> 'FlavorTextRequest':
        """Build a FlavorTextRequest from one of this creature's abilities."""
        return FlavorTextRequest(
            character_name=self.name,
            character_race=self.creature_type or "creature",
            character_class="Monster",
            character_level=_cr_to_level(self.challenge_rating),
            ability_name=ability.name,
            ability_type=ability.ability_type,
            ability_description=ability.description,
            style=style,
            variations=variations,
            context_blob=self.context_blob,
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
