"""Parser for standalone Foundry VTT item exports (weapons, spells, feats, etc.)."""

from ..models import ParsedCreature
from .foundry import _parse_foundry_item, _TYPE_MAP


# Foundry item types we can parse as standalone items
_STANDALONE_ITEM_TYPES = set(_TYPE_MAP.keys())


def is_foundry_item_standalone(data: dict) -> bool:
    """Check if a JSON dict is a standalone Foundry item export."""
    item_type = data.get('type', '')
    has_system = 'system' in data or 'data' in data
    has_items = 'items' in data
    return item_type in _STANDALONE_ITEM_TYPES and has_system and not has_items


def parse_foundry_item_standalone(data: dict) -> ParsedCreature:
    """Parse a standalone Foundry item export into a synthetic ParsedCreature.

    The creature gets _token_pattern = '*' so triggers fire by itemName
    regardless of which token uses the item.

    Raises:
        ValueError: If the item type is unsupported or the item is passive equipment.
    """
    item_type = data.get('type', '')
    if item_type not in _STANDALONE_ITEM_TYPES:
        raise ValueError(f"Unsupported standalone item type: {item_type}")

    ability = _parse_foundry_item(data)
    if ability is None:
        raise ValueError(
            f"Item '{data.get('name', 'Unknown')}' is passive equipment with no activation"
        )

    item_name = data.get('name', 'Unknown Item')
    creature = ParsedCreature(
        name=item_name,
        creature_type=item_type,
    )
    creature._token_pattern = '*'
    creature.abilities.append(ability)
    return creature
