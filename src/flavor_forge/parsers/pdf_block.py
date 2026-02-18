"""PDF stat block parser — extracts text from PDF pages and delegates to text_block parser."""

from ..models import ParsedCreature
from .text_block import parse_text_block


def parse_pdf_block(path: str, page: int | None = None) -> ParsedCreature:
    """Parse a PDF stat block into a ParsedCreature.

    Args:
        path: Path to a .pdf file.
        page: 1-based page number to extract. If None, extracts all pages.
    """
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        if page is not None:
            if page < 1 or page > len(pdf.pages):
                raise ValueError(f"Page {page} out of range (PDF has {len(pdf.pages)} pages)")
            text = pdf.pages[page - 1].extract_text() or ''
        else:
            parts = []
            for p in pdf.pages:
                t = p.extract_text()
                if t:
                    parts.append(t)
            text = '\n\n'.join(parts)

    if not text.strip():
        raise ValueError("No readable text found in PDF")

    return parse_text_block(text)


def list_pdf_pages(path: str) -> list[str]:
    """Return a preview of each page (first ~100 chars) for page selection UI.

    Returns a list where index 0 = page 1 preview, etc.
    """
    import pdfplumber

    previews = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            text = p.extract_text() or ''
            preview = text.strip()[:100]
            if len(text.strip()) > 100:
                preview += '...'
            previews.append(preview)
    return previews
