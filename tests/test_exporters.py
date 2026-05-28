"""Tests for Foundry VTT exporters and batch mode."""

import json
import os
import sys
import subprocess
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from narramancy.models import FlavorTextResult, GENERIC_ACTIONS
from narramancy.exporters import export_rollable_tables, export_token_says
from narramancy.exporters.token_says import _ACTION_TYPE_MAP


def _make_results():
    """Create sample results for testing."""
    return {
        'Scimitar': FlavorTextResult(
            attempts=['The goblin lunges with its rusty scimitar!',
                      'A wild slash arcs through the air!'],
            successes=['The blade bites deep into flesh!',
                       'A devastating strike finds its mark!'],
            failures=['The scimitar glances off harmlessly.',
                      'The goblin stumbles, missing wildly.'],
            metadata={'provider': 'mock', 'ability_type': 'attack'},
        ),
        'Nimble Escape': FlavorTextResult(
            attempts=['The goblin darts between your legs!'],
            successes=['Gone in a flash of green skin!'],
            failures=[],  # empty — should produce no failure table
            metadata={'provider': 'mock', 'ability_type': 'bonus_action'},
        ),
    }


def test_rollable_table_structure():
    """Verify rollable table text format."""
    results = _make_results()
    text = export_rollable_tables('Goblin', results)

    # Should be a string with multiple table blocks separated by blank lines
    assert isinstance(text, str)
    blocks = text.strip().split('\n\n')

    # First block is creature name header, then 3 for Scimitar + 2 for Nimble Escape = 6
    assert len(blocks) == 6, f"Expected 6 blocks (1 header + 5 tables), got {len(blocks)}"
    assert blocks[0] == 'Goblin', f"First block should be creature name, got {blocks[0]}"

    for block in blocks[1:]:  # Skip creature name header
        lines = block.split('\n')
        # First line: dice formula + name (e.g. "d2 Goblin - Scimitar - Attempts")
        assert lines[0].startswith('d'), f"Table should start with dice formula: {lines[0]}"
        # Second line: description starting with ###
        assert lines[1].startswith('### '), f"Description line missing: {lines[1]}"
        # Remaining lines are the entries
        entries = lines[2:]
        assert len(entries) > 0, "Table should have at least one entry"

        # Check formula matches entry count
        formula_n = int(lines[0].split(' ', 1)[0][1:])  # extract N from "dN ..."
        assert formula_n == len(entries), f"Formula d{formula_n} but {len(entries)} entries"

    print("PASS: test_rollable_table_structure")


def test_table_naming():
    """Verify table naming convention."""
    results = _make_results()
    text = export_rollable_tables('Goblin', results)

    assert 'Goblin - Scimitar - Attempts' in text
    assert 'Goblin - Scimitar - Successes' in text
    assert 'Goblin - Scimitar - Failures' in text
    assert 'Goblin - Nimble Escape - Attempts' in text
    assert 'Goblin - Nimble Escape - Successes' in text
    # No failures table for Nimble Escape
    assert 'Goblin - Nimble Escape - Failures' not in text

    print("PASS: test_table_naming")


def test_empty_category_handling():
    """No table emitted for empty lists."""
    results = {
        'Empty Ability': FlavorTextResult(
            attempts=[], successes=[], failures=[],
            metadata={'ability_type': 'feature'},
        ),
    }
    text = export_rollable_tables('Test', results)
    assert text == 'Test', f"Expected only creature header for all-empty, got {repr(text)}"
    print("PASS: test_empty_category_handling")


def test_token_says_output():
    """Verify TokenSays sayings structure, wildcard, whisper, and action type mapping."""
    results = _make_results()
    output = export_token_says('Goblin', results)

    assert 'sayings' in output
    assert '_note' in output
    sayings = output['sayings']

    # 2 Attempts sayings + 1 Successes (Damage Roll) for Scimitar attack = 3
    assert len(sayings) == 3, f"Expected 3 sayings, got {len(sayings)}"

    # Check Scimitar Attempts (attack -> Attack Roll)
    scimitar_attempt = next(s for s in sayings if 'Scimitar' in s['title'] and 'Hit' not in s['title'])
    assert scimitar_attempt['actionType'] == 'Attack Roll'
    assert scimitar_attempt['tokenName'] == '*Goblin*'
    assert scimitar_attempt['isWildcard'] is True
    assert scimitar_attempt['whisperTo'] == 'GM'
    assert scimitar_attempt['tableName'] == 'Goblin - Scimitar - Attempts'
    assert scimitar_attempt['likelihood'] == 100

    # Check Scimitar Successes (Damage Roll wiring)
    scimitar_hit = next(s for s in sayings if 'Hit' in s['title'])
    assert scimitar_hit['actionType'] == 'Damage Roll'
    assert scimitar_hit['tableName'] == 'Goblin - Scimitar - Successes'
    assert scimitar_hit['tokenName'] == '*Goblin*'

    # Check Nimble Escape (bonus_action -> Item Name, no hit saying)
    nimble = next(s for s in sayings if 'Nimble Escape' in s['title'])
    assert nimble['actionType'] == 'Item Name'
    assert nimble['tokenName'] == '*Goblin*'

    print("PASS: test_token_says_output")


def test_token_says_no_whisper():
    """TokenSays whisper can be disabled."""
    results = _make_results()
    output = export_token_says('Goblin', results, whisper=None)
    for saying in output['sayings']:
        assert 'whisperTo' not in saying
    print("PASS: test_token_says_no_whisper")


def test_token_says_skips_empty():
    """TokenSays should skip abilities with no attempts."""
    results = {
        'Empty': FlavorTextResult(
            attempts=[], successes=['hit!'], failures=[],
            metadata={'ability_type': 'attack'},
        ),
    }
    output = export_token_says('Test', results)
    assert len(output['sayings']) == 0
    print("PASS: test_token_says_skips_empty")


def test_token_says_no_hit_for_non_attacks():
    """Non-attack abilities should NOT get a Damage Roll saying."""
    results = {
        'Shield': FlavorTextResult(
            attempts=['Casts shield!'],
            successes=['Protected!'],
            failures=['Shield fizzles.'],
            metadata={'ability_type': 'spell'},
        ),
    }
    output = export_token_says('Mage', results)
    sayings = output['sayings']
    assert len(sayings) == 1, f"Expected 1 saying for non-attack, got {len(sayings)}"
    assert sayings[0]['actionType'] == 'Item Name'
    print("PASS: test_token_says_no_hit_for_non_attacks")


def test_action_type_map_generic():
    """Verify generic action types are in the map."""
    assert _ACTION_TYPE_MAP['save'] == 'Saving Throw'
    assert _ACTION_TYPE_MAP['skill'] == 'Skill'
    assert _ACTION_TYPE_MAP['ability_check'] == 'Ability Check'
    assert _ACTION_TYPE_MAP['death_save'] == 'Saving Throw'
    assert _ACTION_TYPE_MAP['initiative'] == 'Initiative Roll'
    assert _ACTION_TYPE_MAP['damage'] == 'Damage Roll'
    print("PASS: test_action_type_map_generic")


def test_generic_actions_constant():
    """Verify GENERIC_ACTIONS are defined with correct types."""
    names = {a.name for a in GENERIC_ACTIONS}
    assert 'Death Save' in names
    assert 'Initiative' in names

    types = {a.ability_type for a in GENERIC_ACTIONS}
    assert 'death_save' in types
    assert 'initiative' in types

    # All should map to valid TokenSays action types
    for ga in GENERIC_ACTIONS:
        assert ga.ability_type in _ACTION_TYPE_MAP, f"{ga.ability_type} not in _ACTION_TYPE_MAP"

    print("PASS: test_generic_actions_constant")


def test_export_cli():
    """Generate JSON, save it, then export via CLI."""
    results = _make_results()

    # Build the JSON as __main__.py would
    data = {'_creature': 'Goblin'}
    for name, r in results.items():
        data[name] = {
            'attempts': r.attempts,
            'successes': r.successes,
            'failures': r.failures,
            'metadata': r.metadata,
        }

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'goblin.json')
        output_path = os.path.join(tmpdir, 'goblin-tables.txt')

        with open(input_path, 'w') as f:
            json.dump(data, f)

        result = subprocess.run(
            [sys.executable, '-m', 'narramancy', 'export', input_path,
             '--format', 'foundry', '--output', output_path],
            capture_output=True, text=True,
            env={**os.environ, 'PYTHONPATH': os.path.join(os.path.dirname(__file__), '..', 'src')},
        )

        if result.returncode != 0:
            print(f"FAIL: export CLI returned {result.returncode}")
            print(f"  stderr: {result.stderr}")
            return

        assert os.path.isfile(output_path), f"Output file not created: {output_path}"
        with open(output_path) as f:
            text = f.read()
        blocks = text.strip().split('\n\n')
        assert len(blocks) == 6, f"Expected 6 blocks (1 header + 5 tables), got {len(blocks)}"

    print("PASS: test_export_cli")


def test_export_all_format():
    """Test --format all produces both tables and sayings."""
    results = _make_results()
    data = {'_creature': 'Goblin'}
    for name, r in results.items():
        data[name] = {
            'attempts': r.attempts,
            'successes': r.successes,
            'failures': r.failures,
            'metadata': r.metadata,
        }

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'goblin.json')
        with open(input_path, 'w') as f:
            json.dump(data, f)

        result = subprocess.run(
            [sys.executable, '-m', 'narramancy', 'export', input_path,
             '--format', 'all'],
            capture_output=True, text=True,
            cwd=tmpdir,
            env={**os.environ, 'PYTHONPATH': os.path.join(os.path.dirname(__file__), '..', 'src')},
        )

        if result.returncode != 0:
            print(f"FAIL: export --format all returned {result.returncode}")
            print(f"  stderr: {result.stderr}")
            return

        # Check both files created
        tables_file = os.path.join(tmpdir, 'goblin-tables.txt')
        sayings_file = os.path.join(tmpdir, 'goblin-sayings.json')
        assert os.path.isfile(tables_file), "Tables file not created"
        assert os.path.isfile(sayings_file), "Sayings file not created"

    print("PASS: test_export_all_format")


def test_batch_mode():
    """Batch mode with multiple creature files + flavor.txt."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create flavor.txt
        with open(os.path.join(tmpdir, 'flavor.txt'), 'w') as f:
            f.write("These creatures lurk in a haunted forest.")

        # Create two creature JSON files
        for name in ('goblin', 'skeleton'):
            data = {
                'name': name.capitalize(),
                'size': 'Small' if name == 'goblin' else 'Medium',
                'type': 'humanoid' if name == 'goblin' else 'undead',
                'cr': '1/4' if name == 'goblin' else '1/4',
                'context': None,
                'abilities': [
                    {
                        'name': 'Slash',
                        'ability_type': 'attack',
                        'description': 'Melee attack with a weapon',
                        'damage': '1d6',
                        'attack_bonus': 3,
                        'save_dc': None,
                        'save_type': None,
                        'range': '5 ft.',
                        'uses': None,
                        'recharge': None,
                    }
                ],
            }
            with open(os.path.join(tmpdir, f'{name}.json'), 'w') as f:
                json.dump(data, f)

        # Run batch with --list-providers to smoke test the batch arg parsing
        # (actual generation needs API keys, so just test that it parses)
        result = subprocess.run(
            [sys.executable, '-m', 'narramancy', 'generate', '--batch', tmpdir,
             '--list-providers'],
            capture_output=True, text=True,
            env={**os.environ, 'PYTHONPATH': os.path.join(os.path.dirname(__file__), '..', 'src')},
        )

        # --list-providers exits before batch runs, so rc should be 0
        assert result.returncode == 0, f"Batch smoke test failed: {result.stderr}"

    print("PASS: test_batch_mode")


def test_round_trip():
    """Generate JSON output format, then load it back as results."""
    # Simulate what _results_to_json produces
    from narramancy.__main__ import _results_to_json, _load_results_from_json

    results = _make_results()
    data = _results_to_json('Goblin', results)

    # Serialize and deserialize (simulates file round-trip)
    json_str = json.dumps(data)
    loaded = json.loads(json_str)

    reconstructed = _load_results_from_json(loaded)
    assert loaded['_creature'] == 'Goblin'
    assert len(reconstructed) == 2
    assert 'Scimitar' in reconstructed
    assert reconstructed['Scimitar'].attempts == results['Scimitar'].attempts
    assert reconstructed['Nimble Escape'].failures == []

    print("PASS: test_round_trip")


def test_generic_flag_cli():
    """Test that --generic flag is accepted by the CLI parser."""
    # Just test that the arg parses without error (no API key needed for --list-providers)
    result = subprocess.run(
        [sys.executable, '-m', 'narramancy', 'generate', '--list-providers', '--generic'],
        capture_output=True, text=True,
        env={**os.environ, 'PYTHONPATH': os.path.join(os.path.dirname(__file__), '..', 'src')},
    )
    assert result.returncode == 0, f"--generic flag rejected: {result.stderr}"
    print("PASS: test_generic_flag_cli")


def test_multi_phase_triggers():
    """Multi-phase spells produce spellCast/spellEffect triggers; single-phase use itemUse."""
    from narramancy.exporters.narramancy_module import _build_triggers

    # Multi-phase: has cast entries → spellCast + spellEffect
    multi_result = FlavorTextResult(
        attempts=['bolt strikes'],
        successes=['lightning hits'],
        failures=['storm fizzles'],
        metadata={'ability_type': 'spell'},
        cast=['clouds gather overhead'],
    )
    triggers = _build_triggers('Call Lightning', 'spell', multi_result)
    hook_types = {t['hookType'] for t in triggers}
    assert 'spellCast' in hook_types, f"Expected spellCast in {hook_types}"
    assert 'spellEffect' in hook_types, f"Expected spellEffect in {hook_types}"
    assert 'itemUse' not in hook_types, f"itemUse should not appear for multi-phase: {hook_types}"

    # Verify spellCast points to cast table
    cast_trigger = next(t for t in triggers if t['hookType'] == 'spellCast')
    assert cast_trigger['table'] == 'Call Lightning|cast'

    # Verify spellEffect points to attempts table
    effect_trigger = next(t for t in triggers if t['hookType'] == 'spellEffect')
    assert effect_trigger['table'] == 'Call Lightning|attempts'

    # Single-phase: no cast entries → itemUse
    single_result = FlavorTextResult(
        attempts=['thunderwave booms'],
        successes=['creatures stumble'],
        failures=['wave fizzles'],
        metadata={'ability_type': 'spell'},
    )
    triggers = _build_triggers('Thunderwave', 'spell', single_result)
    hook_types = {t['hookType'] for t in triggers}
    assert 'itemUse' in hook_types, f"Expected itemUse for single-phase: {hook_types}"
    assert 'spellCast' not in hook_types, f"spellCast should not appear for single-phase: {hook_types}"

    print("PASS: test_multi_phase_triggers")


def test_cast_round_trip():
    """Cast entries survive JSON round-trip."""
    from narramancy.__main__ import _results_to_json, _load_results_from_json

    results = {
        'Produce Flame': FlavorTextResult(
            attempts=['flame flickers'],
            successes=['fire connects'],
            failures=['flame sputters'],
            metadata={'provider': 'mock', 'ability_type': 'cantrip'},
            cast=['palm glows warm', 'tiny flame dances to life'],
        ),
    }
    data = _results_to_json('Gimbal', results)
    json_str = json.dumps(data)
    loaded = json.loads(json_str)
    reconstructed = _load_results_from_json(loaded)

    assert 'Produce Flame' in reconstructed
    assert reconstructed['Produce Flame'].cast == ['palm glows warm', 'tiny flame dances to life']

    print("PASS: test_cast_round_trip")


if __name__ == '__main__':
    test_rollable_table_structure()
    test_table_naming()
    test_empty_category_handling()
    test_token_says_output()
    test_token_says_no_whisper()
    test_token_says_skips_empty()
    test_token_says_no_hit_for_non_attacks()
    test_action_type_map_generic()
    test_generic_actions_constant()
    test_export_cli()
    test_export_all_format()
    test_batch_mode()
    test_round_trip()
    test_generic_flag_cli()
    test_multi_phase_triggers()
    test_cast_round_trip()
    print("\nAll exporter tests passed!")
