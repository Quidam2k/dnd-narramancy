"""Foundry VTT RollTable JSON exporter.

Produces JSON compatible with the Roll Table Importer module:
  https://foundryvtt.com/packages/roll-table-importer

Each table uses the "FoundryTable" format (has formula + range/text results).
Tables are written as individual files for single import, or as a collection
dict keyed by table name for batch import via macro.
"""

from typing import Dict, List

from ..models import FlavorTextResult


def export_rollable_tables(
    creature_name: str,
    results: Dict[str, FlavorTextResult],
) -> List[dict]:
    """Convert generation results to Roll Table Importer-compatible JSON.

    Produces up to 3 tables per ability (attempts, successes, failures).
    Empty categories are skipped.

    Each table matches the Roll Table Importer "FoundryTable" format:
        {"name": "...", "formula": "1dN", "description": "...",
         "results": [{"range": [1,1], "text": "..."}]}
    """
    tables = []

    for ability_name, result in results.items():
        for category in ('attempts', 'successes', 'failures'):
            texts = getattr(result, category)
            if not texts:
                continue

            category_label = category.capitalize()
            table_name = f"{creature_name} - {ability_name} - {category_label}"

            table_results = []
            for i, text in enumerate(texts, 1):
                table_results.append({
                    "range": [i, i],
                    "text": text,
                })

            ability_type = result.metadata.get('ability_type', 'ability')
            tables.append({
                "name": table_name,
                "formula": f"1d{len(texts)}",
                "description": f"Flavor text for {category} a {ability_type}",
                "results": table_results,
            })

    return tables
