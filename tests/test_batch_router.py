"""Tests for batch_router — input classification, routing, and folder scanning."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from narramancy.batch_router import (
    InputType, classify_json, classify_text, classify_input,
    route_input, scan_batch_folder, SkipFileError,
)


# ── JSON classification ──────────────────────────────────────────────

def test_classify_narramancy_v1():
    data = {'formatVersion': 1, 'creature': {'name': 'Goblin'}, 'tables': [], 'triggers': []}
    assert classify_json(data) == InputType.NARRAMANCY_OUTPUT

def test_classify_narramancy_v2():
    data = {'formatVersion': 2, 'creatures': []}
    assert classify_json(data) == InputType.NARRAMANCY_OUTPUT

def test_classify_foundry_pc():
    data = {'type': 'character', 'name': 'Gimbal', 'items': [], 'system': {}}
    assert classify_json(data) == InputType.FOUNDRY_PC

def test_classify_foundry_npc_by_type():
    data = {'type': 'npc', 'name': 'Goblin', 'system': {}, 'items': []}
    assert classify_json(data) == InputType.FOUNDRY_NPC

def test_classify_foundry_npc_by_items():
    """JSON with items + system but no explicit npc type → FOUNDRY_NPC."""
    data = {'name': 'Goblin', 'items': [{'type': 'weapon'}], 'system': {'details': {}}}
    assert classify_json(data) == InputType.FOUNDRY_NPC

def test_classify_foundry_item_weapon():
    data = {'type': 'weapon', 'name': 'Longsword', 'system': {'damage': {}}}
    assert classify_json(data) == InputType.FOUNDRY_ITEM

def test_classify_foundry_item_spell():
    data = {'type': 'spell', 'name': 'Fireball', 'system': {'level': 3}}
    assert classify_json(data) == InputType.FOUNDRY_ITEM

def test_classify_foundry_item_feat():
    data = {'type': 'feat', 'name': 'Great Weapon Master', 'system': {}}
    assert classify_json(data) == InputType.FOUNDRY_ITEM

def test_classify_open5e():
    data = {'slug': 'goblin', 'name': 'Goblin', 'actions': []}
    assert classify_json(data) == InputType.OPEN5E

def test_classify_parsed_creature():
    data = {'name': 'Goblin', 'abilities': [{'name': 'Bite', 'ability_type': 'attack'}]}
    assert classify_json(data) == InputType.PARSED_CREATURE

def test_no_false_positive_parsed_creature_type_humanoid():
    """A parsed creature with type='humanoid' should NOT match foundry item types."""
    data = {'name': 'Bandit', 'type': 'humanoid', 'abilities': [{'name': 'Scimitar', 'ability_type': 'attack'}]}
    # 'humanoid' is not in _FOUNDRY_ITEM_TYPES, so it should fall to PARSED_CREATURE
    result = classify_json(data)
    assert result == InputType.PARSED_CREATURE, f"Expected PARSED_CREATURE, got {result}"

def test_classify_fallback():
    """Unknown JSON structure falls back to FOUNDRY_NPC."""
    data = {'something': 'else'}
    assert classify_json(data) == InputType.FOUNDRY_NPC


# ── Text classification ──────────────────────────────────────────────

def test_classify_text_stat_block():
    text = "Goblin\nSmall humanoid (goblinoid), neutral evil\n\nArmor Class 15"
    assert classify_text(text) == InputType.TEXT_STAT_BLOCK

def test_classify_text_magic_item():
    text = "Flame Tongue\nWeapon (any sword), rare (requires attunement)\nSome description."
    assert classify_text(text) == InputType.TEXT_ITEM

def test_classify_text_wondrous_item():
    text = "Cloak of Displacement\nWondrous Item, rare (requires attunement)\nSome description."
    assert classify_text(text) == InputType.TEXT_ITEM

def test_classify_text_spell_level():
    text = "Fireball\n3rd-level evocation\nA bright streak flashes..."
    assert classify_text(text) == InputType.TEXT_ITEM

def test_classify_text_cantrip():
    text = "Fire Bolt\nEvocation cantrip\nYou hurl a mote of fire..."
    assert classify_text(text) == InputType.TEXT_ITEM


# ── File-based classification ────────────────────────────────────────

def test_classify_input_json_file():
    data = {'type': 'npc', 'name': 'Goblin', 'system': {}, 'items': []}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(data, f)
        path = f.name
    try:
        assert classify_input(path) == InputType.FOUNDRY_NPC
    finally:
        os.unlink(path)

def test_classify_input_txt_stat_block():
    text = "Goblin\nSmall humanoid (goblinoid), neutral evil\n\nArmor Class 15"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(text)
        path = f.name
    try:
        assert classify_input(path) == InputType.TEXT_STAT_BLOCK
    finally:
        os.unlink(path)

def test_classify_input_html():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write("<html><body>stat block</body></html>")
        path = f.name
    try:
        assert classify_input(path) == InputType.HTML
    finally:
        os.unlink(path)


# ── Routing ──────────────────────────────────────────────────────────

def test_route_standalone_item():
    """Standalone Foundry item → creature with _token_pattern='*'."""
    data = {
        'type': 'weapon',
        'name': 'Flame Tongue',
        'system': {
            'damage': {'parts': [['2d6', 'fire']]},
            'description': {'value': 'A flaming sword'},
        },
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(data, f)
        path = f.name
    try:
        creature = route_input(path)
        assert creature.name == 'Flame Tongue'
        assert creature._token_pattern == '*'
        assert len(creature.abilities) == 1
        assert creature.abilities[0].ability_type == 'attack'
    finally:
        os.unlink(path)

def test_route_narramancy_output_raises_skip():
    """Narramancy output files should raise SkipFileError."""
    data = {'formatVersion': 1, 'creature': {'name': 'Goblin'}, 'tables': [], 'triggers': []}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(data, f)
        path = f.name
    try:
        raised = False
        try:
            route_input(path)
        except SkipFileError:
            raised = True
        assert raised, "Expected SkipFileError for narramancy output"
    finally:
        os.unlink(path)

def test_route_parsed_creature():
    """Pre-parsed creature JSON → ParsedCreature via from_dict."""
    data = {
        'name': 'Test Creature',
        'size': 'Medium',
        'type': 'beast',
        'cr': '2',
        'abilities': [
            {'name': 'Bite', 'ability_type': 'attack', 'description': 'Melee bite attack'}
        ],
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(data, f)
        path = f.name
    try:
        creature = route_input(path)
        assert creature.name == 'Test Creature'
        assert creature.creature_type == 'beast'
        assert len(creature.abilities) == 1
    finally:
        os.unlink(path)

def test_route_text_item():
    """Text spell description → creature with _token_pattern='*'."""
    text = "Fireball\n3rd-level evocation\nA bright streak flashes from your pointing finger."
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(text)
        path = f.name
    try:
        creature = route_input(path)
        assert creature.name == 'Fireball'
        assert creature._token_pattern == '*'
        assert creature.abilities[0].ability_type == 'spell'
    finally:
        os.unlink(path)


# ── Folder scanning ─────────────────────────────────────────────────

def test_scan_mixed_folder():
    """Mixed folder → correct types, flavor.txt excluded, narramancy output marked skip."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # NPC JSON
        npc = {'type': 'npc', 'name': 'Goblin', 'system': {}, 'items': []}
        with open(os.path.join(tmpdir, 'goblin.json'), 'w') as f:
            json.dump(npc, f)

        # Standalone item
        item = {'type': 'weapon', 'name': 'Sword', 'system': {'damage': {}}}
        with open(os.path.join(tmpdir, 'sword.json'), 'w') as f:
            json.dump(item, f)

        # Narramancy output (should be skipped)
        output = {'formatVersion': 1, 'creature': {'name': 'Goblin'}, 'tables': [], 'triggers': []}
        with open(os.path.join(tmpdir, 'goblin-narramancy.json'), 'w') as f:
            json.dump(output, f)

        # Text stat block
        with open(os.path.join(tmpdir, 'orc.txt'), 'w') as f:
            f.write("Orc\nMedium humanoid (orc), chaotic evil\n\nArmor Class 13")

        # flavor.txt (should be excluded entirely)
        with open(os.path.join(tmpdir, 'flavor.txt'), 'w') as f:
            f.write("These creatures guard the dungeon entrance.")

        entries = scan_batch_folder(tmpdir)

        # flavor.txt should not appear at all
        filenames = {e.filename for e in entries}
        assert 'flavor.txt' not in filenames

        # Check types
        by_name = {e.filename: e for e in entries}

        assert by_name['goblin.json'].input_type == InputType.FOUNDRY_NPC
        assert by_name['goblin.json'].skip_reason is None

        assert by_name['sword.json'].input_type == InputType.FOUNDRY_ITEM
        assert by_name['sword.json'].skip_reason is None

        assert by_name['goblin-narramancy.json'].input_type == InputType.NARRAMANCY_OUTPUT
        assert by_name['goblin-narramancy.json'].skip_reason == 'narramancy output file'

        assert by_name['orc.txt'].input_type == InputType.TEXT_STAT_BLOCK
        assert by_name['orc.txt'].skip_reason is None

def test_scan_spell_text():
    """Text spell file is classified as TEXT_ITEM."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, 'fireball.txt'), 'w') as f:
            f.write("Fireball\n3rd-level evocation\nBoom.")

        entries = scan_batch_folder(tmpdir)
        assert len(entries) == 1
        assert entries[0].input_type == InputType.TEXT_ITEM


# ── Run ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [
        # JSON classification
        test_classify_narramancy_v1,
        test_classify_narramancy_v2,
        test_classify_foundry_pc,
        test_classify_foundry_npc_by_type,
        test_classify_foundry_npc_by_items,
        test_classify_foundry_item_weapon,
        test_classify_foundry_item_spell,
        test_classify_foundry_item_feat,
        test_classify_open5e,
        test_classify_parsed_creature,
        test_no_false_positive_parsed_creature_type_humanoid,
        test_classify_fallback,
        # Text classification
        test_classify_text_stat_block,
        test_classify_text_magic_item,
        test_classify_text_wondrous_item,
        test_classify_text_spell_level,
        test_classify_text_cantrip,
        # File-based classification
        test_classify_input_json_file,
        test_classify_input_txt_stat_block,
        test_classify_input_html,
        # Routing
        test_route_standalone_item,
        test_route_narramancy_output_raises_skip,
        test_route_parsed_creature,
        test_route_text_item,
        # Folder scanning
        test_scan_mixed_folder,
        test_scan_spell_text,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
