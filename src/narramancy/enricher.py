"""Ability description enrichment for better flavor text generation.

Fetches real ability descriptions from Open5e and provides built-in
descriptions for saves and skills, so the LLM generates flavor text
that matches what the ability actually does.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level cache: name_slug -> description (None = known 404)
_spell_cache: dict[str, Optional[str]] = {}


def _slugify(name: str) -> str:
    """Convert an ability name to an Open5e API slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[''']", "", slug)  # Remove apostrophes
    slug = re.sub(r"[^a-z0-9]+", "-", slug)  # Non-alnum to hyphens
    slug = slug.strip("-")
    return slug


def fetch_spell_description(name: str) -> Optional[str]:
    """Fetch a spell description from Open5e. Returns None on miss."""
    import urllib.request
    import json

    slug = _slugify(name)
    if slug in _spell_cache:
        return _spell_cache[slug]

    headers = {"Accept": "application/json", "User-Agent": "narramancy/1.0"}

    # Try exact slug via v1 API
    url = f"https://api.open5e.com/v1/spells/{slug}/"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            desc = data.get("desc", "")
            if desc:
                _spell_cache[slug] = desc
                logger.debug(f"Open5e hit for '{name}' via slug '{slug}'")
                return desc
    except Exception:
        pass

    # Try search endpoint
    search_url = f"https://api.open5e.com/v1/spells/?search={slug.replace('-', '+')}&limit=1"
    try:
        req = urllib.request.Request(search_url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("results", [])
            if results:
                desc = results[0].get("desc", "")
                if desc:
                    _spell_cache[slug] = desc
                    logger.debug(f"Open5e search hit for '{name}'")
                    return desc
    except Exception as e:
        logger.debug(f"Open5e search failed for '{name}': {e}")

    _spell_cache[slug] = None
    return None


# ── Built-in Descriptions ────────────────────────────────────────

SAVE_DESCRIPTIONS = {
    "STR": "resisting through raw physical power — holding ground, breaking free, bracing against force",
    "DEX": "dodging, diving, twisting away — reflexive evasion, split-second agility",
    "CON": "enduring through sheer toughness — weathering poison, shrugging off pain, refusing to fall",
    "INT": "seeing through illusions, resisting psychic intrusion — mental clarity under pressure",
    "WIS": "willpower against charm, fear, compulsion — inner resolve, spiritual fortitude",
    "CHA": "force of personality against banishment, possession — refusing to be unmade or displaced",
}

SKILL_DESCRIPTIONS = {
    "Acrobatics": "balance, tumbling, aerial maneuvers — fluid movement through difficult space",
    "Animal Handling": "calming beasts, reading animal behavior, commanding mounts",
    "Arcana": "recalling arcane lore, identifying magical effects, deciphering mystical symbols",
    "Athletics": "climbing, swimming, jumping, grappling — raw physical prowess applied to a task",
    "Deception": "lying convincingly, disguising intent, misleading with half-truths",
    "History": "recalling historical events, recognizing heraldry, placing artifacts in context",
    "Insight": "reading body language and intent, sensing hidden motives, detecting lies",
    "Intimidation": "projecting menace, coercing through presence, breaking will with a look",
    "Investigation": "searching for clues, deducing from evidence, piecing together puzzles",
    "Medicine": "stabilizing the wounded, diagnosing ailments, recalling anatomy",
    "Nature": "identifying plants and animals, reading weather, recalling natural lore",
    "Perception": "noticing hidden details, spotting danger, hearing faint sounds — passive awareness",
    "Performance": "entertaining, oration, musical skill — commanding an audience",
    "Persuasion": "diplomatic speech, winning trust, negotiating with charm and reason",
    "Religion": "recalling divine lore, recognizing holy symbols, understanding planar cosmology",
    "Sleight of Hand": "pickpocketing, palming objects, subtle gestures — deft fingers",
    "Stealth": "moving unseen, blending with shadows, controlling sound and presence",
    "Survival": "tracking, foraging, navigating wilderness, reading terrain",
}


def enrich_ability_description(ability) -> None:
    """Enrich a single ParsedAbility with a real description if possible.

    For spells/cantrips, always fetches from Open5e and combines with
    existing mechanical stats. For other types, skips if there's already
    a substantial non-mechanical description.
    """
    existing = ability.description or ""
    atype = ability.ability_type

    if atype in ("spell", "cantrip"):
        desc = fetch_spell_description(ability.name)
        if desc:
            if len(desc) > 400:
                desc = desc[:397] + "..."
            # Combine: Open5e description + existing mechanical stats
            if existing and existing.strip() != desc.strip():
                ability.description = f"{desc}\n{existing}"
            else:
                ability.description = desc
            return

    if atype == "save":
        # Extract save type from name (e.g., "STR Save" -> "STR")
        save_abbr = ability.name.split()[0].upper() if ability.name else ""
        if save_abbr in SAVE_DESCRIPTIONS:
            ability.description = SAVE_DESCRIPTIONS[save_abbr]
            return

    if atype == "skill":
        # Match skill name (e.g., "Perception", "Sleight of Hand")
        skill_name = ability.name.strip()
        if skill_name in SKILL_DESCRIPTIONS:
            ability.description = SKILL_DESCRIPTIONS[skill_name]
            return

    # For feature/action/bonus_action/reaction/legendary, try Open5e
    if atype in ("feature", "action", "bonus_action", "reaction", "legendary"):
        desc = fetch_spell_description(ability.name)
        if desc:
            if len(desc) > 400:
                desc = desc[:397] + "..."
            if existing and existing.strip() != desc.strip():
                ability.description = f"{desc}\n{existing}"
            else:
                ability.description = desc


def enrich_creature(creature) -> None:
    """Enrich all abilities on a ParsedCreature in-place."""
    for ability in creature.abilities:
        enrich_ability_description(ability)
    enriched = sum(1 for a in creature.abilities if a.description and len(a.description) > 40)
    logger.info(f"Enriched {enriched}/{len(creature.abilities)} abilities for {creature.name}")
