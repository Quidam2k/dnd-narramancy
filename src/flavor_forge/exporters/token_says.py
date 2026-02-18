"""TokenSays config exporter for Foundry VTT."""

from typing import Dict, Optional

from ..models import FlavorTextResult


# Maps ability_type to TokenSays actionType
_ACTION_TYPE_MAP = {
    'attack': 'Attack Roll',
    'spell': 'Item Name',
    'cantrip': 'Item Name',
    'feature': 'Item Name',
    'action': 'Item Name',
    'legendary': 'Item Name',
    'bonus_action': 'Item Name',
    'reaction': 'Item Name',
    'save': 'Saving Throw',
    'skill': 'Skill',
    'ability_check': 'Ability Check',
    'death_save': 'Saving Throw',
    'initiative': 'Initiative Roll',
    'damage': 'Damage Roll',
}


def _make_saying(
    creature_name: str,
    ability_name: str,
    action_type: str,
    table_name: str,
    whisper: Optional[str] = "GM",
) -> dict:
    """Build a single TokenSays saying entry."""
    saying = {
        "title": f"{creature_name} - {ability_name}",
        "tokenName": f"*{creature_name}*",
        "isWildcard": True,
        "actorName": creature_name,
        "actionType": action_type,
        "actionName": ability_name,
        "tableName": table_name,
        "likelihood": 100,
    }
    if whisper:
        saying["whisperTo"] = whisper
    return saying


def export_token_says(
    creature_name: str,
    results: Dict[str, FlavorTextResult],
    whisper: Optional[str] = "GM",
) -> dict:
    """Generate TokenSays sayings config.

    Wires each ability's Attempts table to trigger on use.
    For attacks, also wires Successes to Damage Roll (fires on hit).
    Success/failure for non-attacks require macro integration.

    Args:
        creature_name: Name of the creature.
        results: Dict mapping ability name to FlavorTextResult.
        whisper: Whisper target ("GM", "Token Owner", etc.) or None to disable.
    """
    sayings = []

    for ability_name, result in results.items():
        if not result.attempts:
            continue

        ability_type = result.metadata.get('ability_type', 'action')
        action_type = _ACTION_TYPE_MAP.get(ability_type, 'Item Name')

        # Attempts saying — triggers on the action
        sayings.append(_make_saying(
            creature_name, ability_name, action_type,
            f"{creature_name} - {ability_name} - Attempts",
            whisper=whisper,
        ))

        # Successes saying — for attacks, wire to Damage Roll (fires on hit)
        if result.successes and ability_type == 'attack':
            saying = _make_saying(
                creature_name, ability_name, "Damage Roll",
                f"{creature_name} - {ability_name} - Successes",
                whisper=whisper,
            )
            saying["title"] = f"{creature_name} - {ability_name} (Hit)"
            sayings.append(saying)

    return {
        "sayings": sayings,
        "_note": (
            "Attempts tables trigger on ability use. "
            "For attacks, Successes tables trigger on Damage Roll (hit). "
            "Failure tables and non-attack success/failure require Foundry macros. "
            "tokenName uses wildcard matching (*Name*) to catch variants. "
            "Import these sayings via TokenSays module settings."
        ),
    }
