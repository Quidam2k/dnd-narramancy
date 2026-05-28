"""HTML stat block parser — extracts text from HTML and delegates to text_block parser."""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from ..models import ParsedCreature
from .text_block import parse_text_block

# CSS classes commonly used for D&D stat blocks
_STAT_BLOCK_SELECTORS = [
    '.mon-stat-block',
    '.stat-block-content',
    '.stat-block',
    '.monster-stat-block',
    '.ddb-statblock',
    'stat-block',  # custom element used by some sites
]


def parse_html_block(html: str) -> ParsedCreature:
    """Parse an HTML stat block into a ParsedCreature.

    Accepts raw HTML string or a file path to an .html/.htm file.
    Looks for known stat block containers first, falls back to full text extraction.
    """
    # If it looks like a file path (no tags), try reading it
    if not html.strip().startswith('<'):
        path = Path(html)
        if path.exists() and path.suffix.lower() in ('.html', '.htm'):
            html = path.read_text(encoding='utf-8')

    soup = BeautifulSoup(html, 'lxml')

    # Try known stat block containers
    for selector in _STAT_BLOCK_SELECTORS:
        block = soup.select_one(selector)
        if block:
            text = _extract_text(block)
            if text.strip():
                return parse_text_block(text)

    # Fallback: extract all visible text (strip script/style)
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()

    text = _extract_text(soup)
    if not text.strip():
        raise ValueError("No readable text found in HTML")

    return parse_text_block(text)


def _extract_text(element) -> str:
    """Extract clean text from a BeautifulSoup element, preserving line structure."""
    # get_text with separator ensures block elements produce line breaks
    raw = element.get_text(separator='\n')
    # Collapse multiple blank lines, strip trailing whitespace per line
    lines = [line.strip() for line in raw.splitlines()]
    # Remove empty lines that are consecutive
    cleaned = []
    for line in lines:
        if line or (cleaned and cleaned[-1]):
            cleaned.append(line)
    return '\n'.join(cleaned).strip()
