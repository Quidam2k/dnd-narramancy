"""Monster stat block parsers — auto-detect format or use specific parsers."""

import json
from pathlib import Path

from ..models import ParsedCreature
from .text_block import parse_text_block
from .open5e import fetch_creature, search_creatures
from .foundry import parse_foundry_actor
from .html_block import parse_html_block
from .pdf_block import parse_pdf_block, list_pdf_pages

__all__ = [
    'parse_stat_block',
    'parse_text_block',
    'fetch_creature',
    'search_creatures',
    'parse_foundry_actor',
    'parse_html_block',
    'parse_pdf_block',
    'list_pdf_pages',
]


def parse_stat_block(text_or_path: str, *, page: int | None = None) -> ParsedCreature:
    """Auto-detect format and parse a stat block.

    Accepts:
    - File path to a .json, .txt, .html, .htm, or .pdf file
    - Raw JSON string (tries Foundry format)
    - Raw HTML string (starts with < or <!)
    - Plain text stat block
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

    # Fall back to plain text
    return parse_text_block(text)


def _parse_json_data(data: dict) -> ParsedCreature:
    """Route JSON data to the right parser based on structure."""
    # Foundry actor: has 'type' == 'npc' and 'system'/'data' key with items
    if data.get('type') == 'npc' or 'items' in data:
        return parse_foundry_actor(data)

    # Open5e-style: has 'slug' and 'actions' as a list
    if 'slug' in data and isinstance(data.get('actions'), list):
        from .open5e import _parse_open5e_data
        return _parse_open5e_data(data)

    # Unknown JSON — try Foundry as fallback
    return parse_foundry_actor(data)
