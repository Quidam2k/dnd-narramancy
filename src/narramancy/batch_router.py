"""Input classification and routing for batch processing.

Detects the type of each input file (Foundry actor, standalone item, Open5e JSON,
pre-parsed creature JSON, narramancy output, text stat block, text item/spell, etc.)
and routes it to the appropriate parser.
"""

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from .models import ParsedCreature
from .parsers.foundry import _TYPE_MAP


class InputType(Enum):
    """Classification of input file types."""
    FOUNDRY_PC = 'foundry_pc'
    FOUNDRY_NPC = 'foundry_npc'
    FOUNDRY_ITEM = 'foundry_item'
    OPEN5E = 'open5e'
    PARSED_CREATURE = 'parsed_creature'
    NARRAMANCY_OUTPUT = 'narramancy_output'
    TEXT_STAT_BLOCK = 'text_stat_block'
    TEXT_ITEM = 'text_item'
    HTML = 'html'
    PDF = 'pdf'
    UNKNOWN = 'unknown'


class SkipFileError(Exception):
    """Raised for files that should be skipped during batch processing (not errors)."""
    pass


@dataclass
class BatchEntry:
    """A file in a batch folder with its classification."""
    path: str
    filename: str
    input_type: InputType
    skip_reason: Optional[str] = None


# Foundry item types that can appear as standalone exports
_FOUNDRY_ITEM_TYPES = set(_TYPE_MAP.keys())


def classify_json(data: dict) -> InputType:
    """Classify a JSON dict by its structure.

    Detection priority:
    1. formatVersion present → NARRAMANCY_OUTPUT
    2. type == 'character' + items → FOUNDRY_PC
    3. type == 'npc' or (items + system) → FOUNDRY_NPC
    4. type in item types + system + no items → FOUNDRY_ITEM
    5. slug + actions list → OPEN5E
    6. name + abilities list → PARSED_CREATURE
    7. Fallback → FOUNDRY_NPC
    """
    # 1. Narramancy output (v1 or v2)
    if 'formatVersion' in data:
        return InputType.NARRAMANCY_OUTPUT

    # 2. Foundry PC actor
    if data.get('type') == 'character' and 'items' in data:
        return InputType.FOUNDRY_PC

    # 3. Foundry NPC actor
    if data.get('type') == 'npc':
        return InputType.FOUNDRY_NPC
    if 'items' in data and ('system' in data or 'data' in data):
        return InputType.FOUNDRY_NPC

    # 4. Standalone Foundry item
    item_type = data.get('type', '')
    if item_type in _FOUNDRY_ITEM_TYPES and ('system' in data or 'data' in data) and 'items' not in data:
        return InputType.FOUNDRY_ITEM

    # 5. Open5e
    if 'slug' in data and isinstance(data.get('actions'), list):
        return InputType.OPEN5E

    # 6. Pre-parsed creature JSON
    if 'name' in data and isinstance(data.get('abilities'), list):
        return InputType.PARSED_CREATURE

    # 7. Fallback
    return InputType.FOUNDRY_NPC


def classify_text(text: str) -> InputType:
    """Classify a plain text file as item/spell or stat block."""
    from .parsers.text_item import is_text_item
    if is_text_item(text):
        return InputType.TEXT_ITEM
    return InputType.TEXT_STAT_BLOCK


def classify_input(path: str) -> InputType:
    """Classify an input file by extension and content."""
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix == '.json':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return classify_json(data)

    if suffix in ('.html', '.htm'):
        return InputType.HTML

    if suffix == '.pdf':
        return InputType.PDF

    if suffix == '.txt':
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        return classify_text(text)

    return InputType.UNKNOWN


def route_input(path: str) -> ParsedCreature:
    """Classify a file and parse it with the appropriate parser.

    Raises:
        SkipFileError: For files that should be skipped (narramancy output).
        ValueError: For unsupported or unrecognized file types.
    """
    input_type = classify_input(path)

    if input_type == InputType.NARRAMANCY_OUTPUT:
        raise SkipFileError(f"Skipping narramancy output file: {path}")

    if input_type == InputType.UNKNOWN:
        raise ValueError(f"Unrecognized file type: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        if path.lower().endswith('.json'):
            data = json.load(f)
        else:
            text = f.read()

    if input_type == InputType.FOUNDRY_PC:
        from .pc_parser import parse_foundry_pc
        return parse_foundry_pc(data)

    if input_type == InputType.FOUNDRY_NPC:
        from .parsers.foundry import parse_foundry_actor
        return parse_foundry_actor(data)

    if input_type == InputType.FOUNDRY_ITEM:
        from .parsers.foundry_item import parse_foundry_item_standalone
        return parse_foundry_item_standalone(data)

    if input_type == InputType.OPEN5E:
        from .parsers.open5e import _parse_open5e_data
        return _parse_open5e_data(data)

    if input_type == InputType.PARSED_CREATURE:
        return ParsedCreature.from_dict(data)

    if input_type == InputType.TEXT_ITEM:
        from .parsers.text_item import parse_text_item
        return parse_text_item(text)

    if input_type == InputType.TEXT_STAT_BLOCK:
        from .parsers.text_block import parse_text_block
        return parse_text_block(text)

    if input_type == InputType.HTML:
        from .parsers.html_block import parse_html_block
        return parse_html_block(text)

    if input_type == InputType.PDF:
        from .parsers.pdf_block import parse_pdf_block
        return parse_pdf_block(path)

    raise ValueError(f"No parser for input type: {input_type}")


def scan_batch_folder(folder: str) -> List[BatchEntry]:
    """Scan a folder and classify each file for batch processing.

    Returns a list of BatchEntry objects sorted by filename.
    Skips flavor.txt (folder-level context file).
    """
    entries = []
    for fn in sorted(os.listdir(folder)):
        # Skip flavor.txt (folder-level context)
        if fn.lower() == 'flavor.txt':
            continue

        # Only process supported extensions
        suffix = Path(fn).suffix.lower()
        if suffix not in ('.json', '.txt', '.html', '.htm', '.pdf'):
            continue

        filepath = os.path.join(folder, fn)
        if not os.path.isfile(filepath):
            continue

        try:
            input_type = classify_input(filepath)
            skip_reason = None
            if input_type == InputType.NARRAMANCY_OUTPUT:
                skip_reason = 'narramancy output file'
            elif input_type == InputType.UNKNOWN:
                skip_reason = 'unrecognized format'
            entries.append(BatchEntry(
                path=filepath,
                filename=fn,
                input_type=input_type,
                skip_reason=skip_reason,
            ))
        except Exception as e:
            entries.append(BatchEntry(
                path=filepath,
                filename=fn,
                input_type=InputType.UNKNOWN,
                skip_reason=str(e),
            ))

    return entries
