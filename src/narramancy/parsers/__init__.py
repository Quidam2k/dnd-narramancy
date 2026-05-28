"""Monster stat block parsers — auto-detect format or use specific parsers."""

import json
from pathlib import Path

from ..models import ParsedCreature
from .text_block import parse_text_block
from .open5e import fetch_creature, search_creatures
from .foundry import parse_foundry_actor
from ..pc_parser import parse_foundry_pc
from .html_block import parse_html_block
from .pdf_block import parse_pdf_block, list_pdf_pages
from .foundry_item import parse_foundry_item_standalone, is_foundry_item_standalone
from .text_item import parse_text_item, is_text_item

__all__ = [
    'parse_stat_block',
    'parse_text_block',
    'fetch_creature',
    'search_creatures',
    'parse_foundry_actor',
    'parse_foundry_pc',
    'parse_html_block',
    'parse_pdf_block',
    'list_pdf_pages',
    'parse_foundry_item_standalone',
    'parse_text_item',
]


def parse_stat_block(text_or_path: str, *, page: int | None = None) -> ParsedCreature:
    """Auto-detect format and parse a stat block.

    Accepts:
    - File path to a .json, .txt, .html, .htm, or .pdf file
    - Raw JSON string (tries Foundry format)
    - Raw HTML string (starts with < or <!)
    - Plain text stat block or item/spell description
    """
    # Check if it's a file path
    path = Path(text_or_path)
    if path.exists():
        suffix = path.suffix.lower()
        if suffix == '.json':
            content = path.read_text(encoding='utf-8')
            data = json.loads(content)
            return _parse_json_data(data)
        if suffix in ('.html', '.htm'):
            content = path.read_text(encoding='utf-8')
            return parse_html_block(content)
        if suffix == '.pdf':
            return parse_pdf_block(str(path), page=page)
        content = path.read_text(encoding='utf-8')
        if is_text_item(content):
            return parse_text_item(content)
        return parse_text_block(content)

    # Try parsing as JSON
    text = text_or_path.strip()
    if text.startswith('{'):
        try:
            data = json.loads(text)
            return _parse_json_data(data)
        except json.JSONDecodeError:
            pass

    # Try parsing as HTML (starts with < or <!)
    if text.startswith('<') or text.startswith('<!'):
        try:
            return parse_html_block(text)
        except (ValueError, Exception):
            pass

    # Try text item/spell before falling back to stat block
    if is_text_item(text):
        return parse_text_item(text)

    # Fall back to plain text
    return parse_text_block(text)


def _parse_json_data(data: dict) -> ParsedCreature:
    """Route JSON data to the right parser based on structure."""
    # Narramancy output — not a creature, raise error
    if 'formatVersion' in data:
        raise ValueError("This is a narramancy output file, not a creature input")

    # Foundry PC actor: type == 'character'
    if data.get('type') == 'character':
        from ..pc_parser import parse_foundry_pc
        return parse_foundry_pc(data)

    # Foundry NPC actor: has 'type' == 'npc' and 'system'/'data' key with items
    if data.get('type') == 'npc' or 'items' in data:
        return parse_foundry_actor(data)

    # Standalone Foundry item (weapon, spell, feat, etc.)
    if is_foundry_item_standalone(data):
        return parse_foundry_item_standalone(data)

    # Open5e-style: has 'slug' and 'actions' as a list
    if 'slug' in data and isinstance(data.get('actions'), list):
        from .open5e import _parse_open5e_data
        return _parse_open5e_data(data)

    # Pre-parsed creature JSON (has name + abilities list)
    if 'name' in data and isinstance(data.get('abilities'), list):
        return ParsedCreature.from_dict(data)

    # Unknown JSON — try Foundry as fallback
    return parse_foundry_actor(data)
