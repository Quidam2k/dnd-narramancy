"""Foundry VTT RollTable text exporter.

Produces plain text compatible with the Roll Table Importer module:
  https://foundryvtt.com/packages/roll-table-importer

Uses the multi-table text format where each table starts with a dice
formula line (e.g. "d5 Table Name"), followed by one entry per line.
Multiple tables are separated by blank lines in a single file.
"""

from typing import Dict, List

from ..models import FlavorTextResult


def export_rollable_tables(
    creature_name: str,
    results: Dict[str, FlavorTextResult],
) -> str:
    """Convert generation results to Roll Table Importer plain text format.

    Produces up to 3 tables per ability (attempts, successes, failures).
    Empty categories are skipped.

    Returns a single string with all tables, ready to paste or save as .txt.
    Format per table:
        d5 Vampire - Bite - Attempts
        ### Flavor text for attempts an attack
        Your fangs glisten...
        The air chills...
    """
    blocks = [creature_name]

    for ability_name, result in results.items():
        for category in ('attempts', 'successes', 'failures'):
            texts = getattr(result, category)
            if not texts:
                continue

            category_label = category.capitalize()
            table_name = f"{creature_name} - {ability_name} - {category_label}"
            n = len(texts)

            ability_type = result.metadata.get('ability_type', 'ability')
            description = f"Flavor text for {category} a {ability_type}"

            lines = [f"d{n} {table_name}"]
            lines.append(f"### {description}")
            for text in texts:
                lines.append(text)

            blocks.append('\n'.join(lines))

    return '\n\n'.join(blocks)
