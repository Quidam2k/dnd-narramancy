"""Utilities for comparing parsed abilities against existing flavor tables."""


def find_missing_abilities(creature, existing_json):
    """Find abilities that don't have existing flavor tables.

    Args:
        creature: ParsedCreature with abilities list
        existing_json: dict with 'tables' key containing existing flavor data

    Returns:
        List of ParsedAbility objects that have no matching table.
    """
    existing = set()
    for table in existing_json.get('tables', []):
        existing.add(table.get('ability', ''))

    return [a for a in creature.abilities if a.name not in existing]
