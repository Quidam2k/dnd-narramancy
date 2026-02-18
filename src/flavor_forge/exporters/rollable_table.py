"""Foundry VTT RollTable JSON exporter."""

import secrets
from typing import Dict, List

from ..models import FlavorTextResult


def export_rollable_tables(
    creature_name: str,
    results: Dict[str, FlavorTextResult],
) -> List[dict]:
    """Convert generation results to Foundry VTT RollTable JSON objects.

    Produces up to 3 tables per ability (attempts, successes, failures).
    Empty categories are skipped.
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
                    "_id": secrets.token_hex(8),
                    "type": 0,
                    "text": text,
                    "img": "icons/svg/d20-black.svg",
                    "weight": 1,
                    "range": [i, i],
                    "drawn": False,
                })

            ability_type = result.metadata.get('ability_type', 'ability')
            tables.append({
                "name": table_name,
                "img": "icons/svg/d20-black.svg",
                "description": f"Flavor text for {category} a {ability_type}",
                "formula": f"1d{len(texts)}",
                "replacement": True,
                "displayRoll": True,
                "folder": None,
                "sort": 0,
                "ownership": {"default": 0},
                "flags": {},
                "results": table_results,
            })

    return tables
