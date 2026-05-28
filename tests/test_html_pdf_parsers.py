"""Tests for HTML and PDF stat block parsers."""

import os
import tempfile

import pytest

from narramancy.parsers import parse_stat_block, parse_html_block, parse_pdf_block, list_pdf_pages


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

GOBLIN_TEXT_BLOCK = """Goblin
Small humanoid (goblinoid), neutral evil

Armor Class 15 (leather armor, shield)
Hit Points 7 (2d6)
Speed 30 ft.

STR 8 (-1) DEX 14 (+2) CON 10 (+0) INT 10 (+0) WIS 8 (-1) CHA 8 (-1)

Skills Stealth +6
Senses darkvision 60 ft., passive Perception 9
Languages Common, Goblin
Challenge 1/4 (50 XP)

Nimble Escape. The goblin can take the Disengage or Hide action as a bonus action on each of its turns.

Actions

Scimitar. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage.

Shortbow. Ranged Weapon Attack: +4 to hit, range 80/320 ft., one target. Hit: 5 (1d6 + 2) piercing damage."""

GOBLIN_HTML_STAT_BLOCK = f"""<div class="stat-block">
<h2>Goblin</h2>
<p>Small humanoid (goblinoid), neutral evil</p>
<p>Armor Class 15 (leather armor, shield)</p>
<p>Hit Points 7 (2d6)</p>
<p>Speed 30 ft.</p>
<p>STR 8 (-1) DEX 14 (+2) CON 10 (+0) INT 10 (+0) WIS 8 (-1) CHA 8 (-1)</p>
<p>Skills Stealth +6</p>
<p>Senses darkvision 60 ft., passive Perception 9</p>
<p>Languages Common, Goblin</p>
<p>Challenge 1/4 (50 XP)</p>
<p>Nimble Escape. The goblin can take the Disengage or Hide action as a bonus action on each of its turns.</p>
<h3>Actions</h3>
<p>Scimitar. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage.</p>
<p>Shortbow. Ranged Weapon Attack: +4 to hit, range 80/320 ft., one target. Hit: 5 (1d6 + 2) piercing damage.</p>
</div>"""

GOBLIN_HTML_FULL_PAGE = f"""<!DOCTYPE html>
<html>
<head><title>Goblin - D&D Beyond</title></head>
<body>
<nav>Navigation stuff</nav>
<main>
{GOBLIN_HTML_STAT_BLOCK}
</main>
<footer>Footer stuff</footer>
</body>
</html>"""

GOBLIN_HTML_NO_CLASS = f"""<html>
<body>
<h2>Goblin</h2>
<p>Small humanoid (goblinoid), neutral evil</p>
<p>Armor Class 15 (leather armor, shield)</p>
<p>Hit Points 7 (2d6)</p>
<p>Speed 30 ft.</p>
<p>STR 8 (-1) DEX 14 (+2) CON 10 (+0) INT 10 (+0) WIS 8 (-1) CHA 8 (-1)</p>
<p>Skills Stealth +6</p>
<p>Senses darkvision 60 ft., passive Perception 9</p>
<p>Languages Common, Goblin</p>
<p>Challenge 1/4 (50 XP)</p>
<p>Nimble Escape. The goblin can take the Disengage or Hide action as a bonus action on each of its turns.</p>
<h3>Actions</h3>
<p>Scimitar. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage.</p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTML Tests
# ---------------------------------------------------------------------------

class TestHTMLParser:
    def test_stat_block_div_extraction(self):
        """Extracts text from a known .stat-block container."""
        creature = parse_html_block(GOBLIN_HTML_STAT_BLOCK)
        assert creature.name == 'Goblin'
        assert creature.challenge_rating == '1/4'
        assert len(creature.abilities) >= 2  # Nimble Escape + at least 1 attack

    def test_full_page_html(self):
        """Extracts stat block from a full HTML page with nav/footer."""
        creature = parse_html_block(GOBLIN_HTML_FULL_PAGE)
        assert creature.name == 'Goblin'
        assert creature.challenge_rating == '1/4'

    def test_html_without_known_class(self):
        """Falls back to full-text extraction when no stat-block class found."""
        creature = parse_html_block(GOBLIN_HTML_NO_CLASS)
        assert creature.name == 'Goblin'
        assert creature.challenge_rating == '1/4'

    def test_html_snippet(self):
        """Handles a minimal HTML snippet (no <html>/<body> tags)."""
        snippet = "<p>Goblin</p><p>Small humanoid (goblinoid), neutral evil</p><p>Challenge 1/4 (50 XP)</p><p>Nimble Escape. The goblin can take the Disengage or Hide action as a bonus action.</p>"
        creature = parse_html_block(snippet)
        assert creature.name == 'Goblin'

    def test_html_file_path(self):
        """Reads from an .html file path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(GOBLIN_HTML_STAT_BLOCK)
            path = f.name
        try:
            creature = parse_html_block(path)
            assert creature.name == 'Goblin'
        finally:
            os.unlink(path)

    def test_empty_html_raises(self):
        """Raises ValueError on empty/script-only HTML."""
        with pytest.raises(ValueError, match="No readable text"):
            parse_html_block("<html><script>var x = 1;</script></html>")


# ---------------------------------------------------------------------------
# PDF Tests
# ---------------------------------------------------------------------------

def _make_test_pdf(text: str, num_pages: int = 1) -> str:
    """Create a minimal test PDF with the given text. Returns path."""
    # Use pdfplumber's dependency (pdfminer) doesn't create PDFs,
    # so we use reportlab if available, otherwise fpdf2, otherwise skip
    try:
        from fpdf import FPDF
    except ImportError:
        pytest.skip("fpdf2 not installed — needed to create test PDFs")

    pdf = FPDF()
    for i in range(num_pages):
        pdf.add_page()
        pdf.set_font('Helvetica', size=10)
        if i == 0:
            for line in text.split('\n'):
                pdf.cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.cell(0, 5, f"Page {i + 1} filler content", new_x="LMARGIN", new_y="NEXT")

    path = tempfile.mktemp(suffix='.pdf')
    pdf.output(path)
    return path


class TestPDFParser:
    def test_parse_single_page_pdf(self):
        path = _make_test_pdf(GOBLIN_TEXT_BLOCK)
        try:
            creature = parse_pdf_block(path)
            assert creature.name == 'Goblin'
            assert creature.challenge_rating == '1/4'
        finally:
            os.unlink(path)

    def test_parse_specific_page(self):
        path = _make_test_pdf(GOBLIN_TEXT_BLOCK, num_pages=3)
        try:
            creature = parse_pdf_block(path, page=1)
            assert creature.name == 'Goblin'
        finally:
            os.unlink(path)

    def test_page_out_of_range(self):
        path = _make_test_pdf(GOBLIN_TEXT_BLOCK, num_pages=1)
        try:
            with pytest.raises(ValueError, match="out of range"):
                parse_pdf_block(path, page=5)
        finally:
            os.unlink(path)

    def test_list_pdf_pages(self):
        path = _make_test_pdf(GOBLIN_TEXT_BLOCK, num_pages=3)
        try:
            previews = list_pdf_pages(path)
            assert len(previews) == 3
            assert 'Goblin' in previews[0]
            assert 'filler' in previews[1].lower() or 'Page' in previews[1]
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Auto-detect Tests
# ---------------------------------------------------------------------------

class TestAutoDetect:
    def test_html_file_extension_routes_to_html_parser(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(GOBLIN_HTML_STAT_BLOCK)
            path = f.name
        try:
            creature = parse_stat_block(path)
            assert creature.name == 'Goblin'
        finally:
            os.unlink(path)

    def test_htm_file_extension_routes_to_html_parser(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.htm', delete=False, encoding='utf-8') as f:
            f.write(GOBLIN_HTML_STAT_BLOCK)
            path = f.name
        try:
            creature = parse_stat_block(path)
            assert creature.name == 'Goblin'
        finally:
            os.unlink(path)

    def test_pdf_file_extension_routes_to_pdf_parser(self):
        path = _make_test_pdf(GOBLIN_TEXT_BLOCK)
        try:
            creature = parse_stat_block(path)
            assert creature.name == 'Goblin'
        finally:
            os.unlink(path)

    def test_raw_html_string_autodetected(self):
        """A raw HTML string starting with < is auto-detected as HTML."""
        creature = parse_stat_block(GOBLIN_HTML_STAT_BLOCK)
        assert creature.name == 'Goblin'

    def test_doctype_html_string_autodetected(self):
        """A raw HTML string starting with <! is auto-detected as HTML."""
        creature = parse_stat_block(GOBLIN_HTML_FULL_PAGE)
        assert creature.name == 'Goblin'
