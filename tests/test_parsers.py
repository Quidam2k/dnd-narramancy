#!/usr/bin/env python3
"""Test suite for monster stat block parsers."""

import json
import subprocess
import sys
import os
from pathlib import Path

# Add src/ to path so narramancy package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from narramancy.models import ParsedCreature, ParsedAbility, FlavorTextRequest
from narramancy.parsers import parse_stat_block, parse_text_block
from narramancy.parsers.foundry import parse_foundry_actor

# ---------------------------------------------------------------------------
# Test data: real stat blocks as string constants
# ---------------------------------------------------------------------------

GOBLIN_TEXT = """Goblin
Small humanoid (goblinoid), neutral evil

Armor Class 15 (leather armor, shield)
Hit Points 7 (2d6)
Speed 30 ft.

STR     DEX     CON     INT     WIS     CHA
8 (-1)  14 (+2) 10 (+0) 10 (+0) 8 (-1)  8 (-1)

Skills Stealth +6
Senses darkvision 60 ft., passive Perception 9
Languages Common, Goblin
Challenge 1/4 (50 XP)

Nimble Escape. The goblin can take the Disengage or Hide action as a bonus action on each of its turns.

Actions

Scimitar. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage.

Shortbow. Ranged Weapon Attack: +4 to hit, range 80/320 ft., one target. Hit: 5 (1d6 + 2) piercing damage."""

DRAGON_TEXT = """Adult Red Dragon
Huge dragon, chaotic evil

Armor Class 19 (natural armor)
Hit Points 256 (19d12 + 133)
Speed 40 ft., climb 40 ft., fly 80 ft.

STR     DEX     CON     INT     WIS     CHA
27 (+8) 10 (+0) 25 (+7) 16 (+3) 13 (+1) 21 (+5)

Saving Throws Dex +6, Con +13, Wis +7, Cha +11
Skills Perception +13, Stealth +6
Damage Immunities fire
Senses blindsight 60 ft., darkvision 120 ft., passive Perception 23
Languages Common, Draconic
Challenge 17 (18,000 XP)

Legendary Resistance (3/Day). If the dragon fails a saving throw, it can choose to succeed instead.

Actions

Multiattack. The dragon can use its Frightful Presence. It then makes three attacks: one with its bite and two with its claws.

Bite. Melee Weapon Attack: +14 to hit, reach 10 ft., one target. Hit: 19 (2d10 + 8) piercing damage plus 7 (2d6) fire damage.

Claw. Melee Weapon Attack: +14 to hit, reach 5 ft., one target. Hit: 15 (2d6 + 8) slashing damage.

Tail. Melee Weapon Attack: +14 to hit, reach 15 ft., one target. Hit: 17 (2d8 + 8) bludgeoning damage.

Frightful Presence. Each creature of the dragon's choice that is within 120 feet of the dragon and aware of it must succeed on a DC 19 Wisdom saving throw or become frightened for 1 minute.

Fire Breath (Recharge 5-6). The dragon exhales fire in a 60-foot cone. Each creature in that area must make a DC 21 Dexterity saving throw, taking 63 (18d6) fire damage on a failed save, or half as much damage on a successful one.

Legendary Actions

The dragon can take 3 legendary actions, choosing from the options below.

Detect. The dragon makes a Wisdom (Perception) check.

Tail Attack. The dragon makes a tail attack.

Wing Attack (Costs 2 Actions). The dragon beats its wings. Each creature within 10 feet of the dragon must succeed on a DC 22 Dexterity saving throw or take 15 (2d6 + 8) bludgeoning damage and be knocked prone."""

SAMPLE_FOUNDRY_ACTOR = {
    "name": "Bandit",
    "type": "npc",
    "system": {
        "details": {
            "cr": 0.125,
            "type": {"value": "humanoid"},
        },
        "traits": {
            "size": "med",
        },
    },
    "items": [
        {
            "name": "Scimitar",
            "type": "weapon",
            "system": {
                "description": {"value": "<p>A curved blade favored by pirates.</p>"},
                "attackBonus": "3",
                "damage": {"parts": [["1d6 + 1", "slashing"]]},
                "activation": {"type": "action"},
            },
        },
        {
            "name": "Light Crossbow",
            "type": "weapon",
            "system": {
                "description": {"value": "A simple ranged weapon."},
                "attackBonus": "3",
                "damage": {"parts": [["1d8 + 1", "piercing"]]},
                "activation": {"type": "action"},
            },
        },
        {
            "name": "Leather Armor",
            "type": "equipment",
            "system": {
                "description": {"value": "Light armor."},
                "activation": {},
            },
        },
    ],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_text_block_goblin():
    """Parse a goblin stat block and verify basic fields."""
    print("\nTest: text_block_goblin")
    print("-" * 40)

    creature = parse_text_block(GOBLIN_TEXT)

    assert creature.name == "Goblin", f"Name: {creature.name}"
    assert creature.size == "Small", f"Size: {creature.size}"
    assert "humanoid" in creature.creature_type.lower(), f"Type: {creature.creature_type}"
    assert creature.challenge_rating == "1/4", f"CR: {creature.challenge_rating}"

    # Should have: Nimble Escape (feature) + Scimitar (attack) + Shortbow (attack)
    assert len(creature.abilities) >= 3, f"Abilities: {len(creature.abilities)} - {[a.name for a in creature.abilities]}"

    attacks = [a for a in creature.abilities if a.ability_type == 'attack']
    assert len(attacks) >= 2, f"Attacks: {[a.name for a in attacks]}"

    scimitar = next((a for a in attacks if 'scimitar' in a.name.lower()), None)
    assert scimitar is not None, "No scimitar found"
    assert scimitar.attack_bonus == 4, f"Scimitar bonus: {scimitar.attack_bonus}"

    print(f"  {creature.name}: {len(creature.abilities)} abilities parsed")
    print("  PASS")
    return True


def test_text_block_dragon():
    """Parse adult red dragon — verify legendary actions and recharge."""
    print("\nTest: text_block_dragon")
    print("-" * 40)

    creature = parse_text_block(DRAGON_TEXT)

    assert creature.name == "Adult Red Dragon", f"Name: {creature.name}"
    assert creature.challenge_rating == "17", f"CR: {creature.challenge_rating}"

    legendary = [a for a in creature.abilities if a.ability_type == 'legendary']
    assert len(legendary) >= 2, f"Legendary: {[a.name for a in legendary]}"

    fire_breath = next((a for a in creature.abilities if 'fire breath' in a.name.lower()), None)
    assert fire_breath is not None, "No Fire Breath found"
    assert fire_breath.recharge == "5-6", f"Recharge: {fire_breath.recharge}"
    assert fire_breath.save_dc == 21, f"Save DC: {fire_breath.save_dc}"
    assert fire_breath.save_type == "DEX", f"Save type: {fire_breath.save_type}"

    print(f"  {creature.name}: {len(creature.abilities)} abilities parsed")
    print(f"  Legendary actions: {[a.name for a in legendary]}")
    print("  PASS")
    return True


def test_foundry_parser():
    """Parse a Foundry VTT actor export."""
    print("\nTest: foundry_parser")
    print("-" * 40)

    creature = parse_foundry_actor(SAMPLE_FOUNDRY_ACTOR)

    assert creature.name == "Bandit", f"Name: {creature.name}"
    assert creature.size == "Medium", f"Size: {creature.size}"
    assert creature.creature_type == "humanoid", f"Type: {creature.creature_type}"

    # Should have scimitar + crossbow + leather armor
    assert len(creature.abilities) >= 2, f"Abilities: {len(creature.abilities)}"

    scimitar = next((a for a in creature.abilities if 'scimitar' in a.name.lower()), None)
    assert scimitar is not None
    assert scimitar.ability_type == 'attack'
    assert scimitar.attack_bonus == 3
    assert scimitar.damage == "1d6 + 1"

    print(f"  {creature.name}: {len(creature.abilities)} abilities parsed")
    print("  PASS")
    return True


def test_auto_detect_json():
    """Test parse_stat_block auto-detection with JSON string."""
    print("\nTest: auto_detect_json")
    print("-" * 40)

    json_str = json.dumps(SAMPLE_FOUNDRY_ACTOR)
    creature = parse_stat_block(json_str)

    assert creature.name == "Bandit"
    print(f"  Auto-detected Foundry JSON: {creature.name}")
    print("  PASS")
    return True


def test_to_flavor_request():
    """Test ParsedCreature.to_flavor_request() produces valid FlavorTextRequest."""
    print("\nTest: to_flavor_request")
    print("-" * 40)

    creature = parse_text_block(GOBLIN_TEXT)
    creature.context_blob = "These goblins serve a hobgoblin warlord"

    attack = next(a for a in creature.abilities if a.ability_type == 'attack')
    req = creature.to_flavor_request(attack, style='gritty', variations=3)

    assert isinstance(req, FlavorTextRequest)
    assert req.character_name == "Goblin"
    assert req.ability_name == attack.name
    assert req.style == 'gritty'
    assert req.variations == 3
    assert req.context_blob == "These goblins serve a hobgoblin warlord"
    assert req.character_level >= 1

    print(f"  FlavorTextRequest: {req.character_name}'s {req.ability_name}")
    print("  PASS")
    return True


def test_open5e_fetch():
    """Fetch goblin from Open5e API (skipped if no network)."""
    print("\nTest: open5e_fetch")
    print("-" * 40)

    try:
        from narramancy.parsers.open5e import fetch_creature, search_creatures

        creature = fetch_creature("goblin")
        assert creature.name.lower() == "goblin", f"Name: {creature.name}"
        assert len(creature.abilities) > 0, "No abilities parsed"
        assert creature.challenge_rating, "No CR"

        # Test search
        results = search_creatures("dragon", limit=3)
        assert len(results) > 0, "Search returned no results"

        print(f"  Fetched: {creature.name} (CR {creature.challenge_rating}, {len(creature.abilities)} abilities)")
        print(f"  Search 'dragon': {[r['name'] for r in results]}")
        print("  PASS")
        return True

    except Exception as e:
        err_type = type(e).__name__
        err_str = str(e).lower()
        if 'URLError' in err_type or 'HTTPError' in err_type or 'timeout' in err_str:
            print(f"  SKIP: Network issue ({e})")
            return None
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


MULTI_PHASE_FOUNDRY_ACTOR = {
    "name": "Gimbal",
    "type": "character",
    "system": {
        "details": {"type": {"value": "humanoid"}},
        "traits": {"size": "sm"},
    },
    "items": [
        {
            "name": "Produce Flame",
            "type": "spell",
            "system": {
                "description": {"value": "A flame appears in your hand."},
                "level": 0,
                "activation": {"type": "bonus"},
                "activities": {
                    "attackProdFlame": {"type": "attack", "_id": "attackProdFlame"},
                    "ddbmacroProdFl": {"type": "ddbmacro", "_id": "ddbmacroProdFl"},
                },
            },
        },
        {
            "name": "Call Lightning",
            "type": "spell",
            "system": {
                "description": {"value": "Storm cloud appears, call bolts."},
                "level": 3,
                "activation": {"type": "action"},
                "activities": {
                    "utilityCallLig": {"type": "utility", "_id": "utilityCallLig"},
                    "saveCallLig1": {"type": "save", "_id": "saveCallLig1"},
                    "saveCallLig2": {"type": "save", "_id": "saveCallLig2"},
                },
            },
        },
        {
            "name": "Thunderwave",
            "type": "spell",
            "system": {
                "description": {"value": "A wave of thunderous force."},
                "level": 1,
                "activation": {"type": "action"},
                "activities": {
                    "saveThunder": {"type": "save", "_id": "saveThunder"},
                },
            },
        },
        {
            "name": "Starry Form",
            "type": "feat",
            "system": {
                "description": {"value": "Assume a starry form."},
                "activation": {"type": "bonus"},
                "activities": {
                    "enchantStarry": {"type": "enchant", "_id": "enchantStarry"},
                    "attackArcher": {"type": "attack", "_id": "attackArcher"},
                },
            },
        },
    ],
}


def test_foundry_multi_phase_detection():
    """Foundry parser detects multi-phase abilities from activity types."""
    print("\nTest: foundry_multi_phase_detection")
    print("-" * 40)

    creature = parse_foundry_actor(MULTI_PHASE_FOUNDRY_ACTOR)

    # Produce Flame: attack + ddbmacro = multi-phase
    pf = next(a for a in creature.abilities if a.name == 'Produce Flame')
    assert pf.is_multi_phase, "Produce Flame should be multi-phase"
    assert set(pf.activity_types) == {'attack', 'ddbmacro'}, f"Got {pf.activity_types}"

    # Call Lightning: utility + save = multi-phase
    cl = next(a for a in creature.abilities if a.name == 'Call Lightning')
    assert cl.is_multi_phase, "Call Lightning should be multi-phase"
    assert 'utility' in cl.activity_types
    assert 'save' in cl.activity_types

    # Thunderwave: only save = single-phase
    tw = next(a for a in creature.abilities if a.name == 'Thunderwave')
    assert not tw.is_multi_phase, f"Thunderwave should be single-phase, got activity_types={tw.activity_types}"

    # Starry Form: enchant + attack = multi-phase
    sf = next(a for a in creature.abilities if a.name == 'Starry Form')
    assert sf.is_multi_phase, "Starry Form should be multi-phase"

    print("  Produce Flame: multi-phase OK")
    print("  Call Lightning: multi-phase OK")
    print("  Thunderwave: single-phase OK")
    print("  Starry Form: multi-phase OK")
    print("  PASS")
    return True


def test_cli_smoke():
    """Smoke test the CLI with --help and a piped stat block."""
    print("\nTest: cli_smoke")
    print("-" * 40)

    src_dir = str(Path(__file__).parent.parent / "src")

    # Test --help
    result = subprocess.run(
        [sys.executable, "-m", "narramancy", "--help"],
        capture_output=True, text=True, cwd=src_dir,
    )
    assert result.returncode == 0, f"--help failed: {result.stderr}"
    assert "narramancy" in result.stdout.lower() or "flavor" in result.stdout.lower()

    # Test parse subcommand with piped text
    result = subprocess.run(
        [sys.executable, "-m", "narramancy", "parse", "--json"],
        input=GOBLIN_TEXT, capture_output=True, text=True, cwd=src_dir,
    )
    assert result.returncode == 0, f"parse failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert data['name'] == 'Goblin'
    assert len(data['abilities']) >= 3

    print(f"  CLI help: OK")
    print(f"  CLI parse (piped): {data['name']} with {len(data['abilities'])} abilities")
    print("  PASS")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Narramancy Parser Test Suite")
    print("=" * 60)

    results = {}
    results['text_block_goblin'] = test_text_block_goblin()
    results['text_block_dragon'] = test_text_block_dragon()
    results['foundry_parser'] = test_foundry_parser()
    results['auto_detect_json'] = test_auto_detect_json()
    results['to_flavor_request'] = test_to_flavor_request()
    results['open5e_fetch'] = test_open5e_fetch()
    results['foundry_multi_phase'] = test_foundry_multi_phase_detection()
    results['cli_smoke'] = test_cli_smoke()

    print(f"\n{'=' * 60}")
    print("Results:")
    for name, result in results.items():
        if result is None:
            status = "SKIP"
        elif result:
            status = "PASS"
        else:
            status = "FAIL"
        print(f"  {name}: {status}")

    failures = [k for k, v in results.items() if v is False]
    if failures:
        print(f"\nFailed: {', '.join(failures)}")
        return False
    else:
        print("\nAll tests passed (or skipped).")
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
