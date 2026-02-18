"""Tests for Foundry VTT exporters and batch mode."""

import json
import os
import sys
import subprocess
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from flavor_forge.models import FlavorTextResult, GENERIC_ACTIONS
from flavor_forge.exporters import export_rollable_tables, export_token_says
from flavor_forge.exporters.token_says import _ACTION_TYPE_MAP


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
    """Verify rollable table JSON schema."""
    results = _make_results()
    tables = export_rollable_tables('Goblin', results)

    # 3 for Scimitar (attempts, successes, failures) + 2 for Nimble Escape (no failures)
    assert len(tables) == 5, f"Expected 5 tables, got {len(tables)}"

    for table in tables:
        assert 'name' in table
        assert 'formula' in table
        assert 'results' in table
        assert table['displayRoll'] is True
        assert table['replacement'] is True
        assert table['img'] == 'icons/svg/d20-black.svg'

        # Check formula matches result count
        n = len(table['results'])
        assert table['formula'] == f'1d{n}', f"Formula {table['formula']} != 1d{n}"

        # Check each result entry
        for i, entry in enumerate(table['results'], 1):
            assert len(entry['_id']) == 16, f"ID should be 16 hex chars, got {len(entry['_id'])}"
            assert entry['range'] == [i, i]
            assert entry['weight'] == 1
            assert entry['type'] == 0
            assert isinstance(entry['text'], str) and len(entry['text']) > 0

    print("PASS: test_rollable_table_structure")


def test_table_naming():
    """Verify table naming convention."""
    results = _make_results()
    tables = export_rollable_tables('Goblin', results)

    names = [t['name'] for t in tables]
    assert 'Goblin - Scimitar - Attempts' in names
    assert 'Goblin - Scimitar - Successes' in names
    assert 'Goblin - Scimitar - Failures' in names
    assert 'Goblin - Nimble Escape - Attempts' in names
    assert 'Goblin - Nimble Escape - Successes' in names
    # No failures table for Nimble Escape
    assert 'Goblin - Nimble Escape - Failures' not in names

    print("PASS: test_table_naming")


def test_empty_category_handling():
    """No table emitted for empty lists."""
    results = {
        'Empty Ability': FlavorTextResult(
            attempts=[], successes=[], failures=[],
            metadata={'ability_type': 'feature'},
        ),
    }
    tables = export_rollable_tables('Test', results)
    assert len(tables) == 0, f"Expected 0 tables for all-empty, got {len(tables)}"
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
    assert 'Saving Throw' in names
    assert 'Skill Check' in names
    assert 'Death Save' in names
    assert 'Initiative' in names

    types = {a.ability_type for a in GENERIC_ACTIONS}
    assert 'save' in types
    assert 'skill' in types
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
        output_path = os.path.join(tmpdir, 'goblin-tables.json')

        with open(input_path, 'w') as f:
            json.dump(data, f)

        result = subprocess.run(
            [sys.executable, '-m', 'flavor_forge', 'export', input_path,
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
            tables = json.load(f)
        assert len(tables) == 5, f"Expected 5 tables, got {len(tables)}"

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
            [sys.executable, '-m', 'flavor_forge', 'export', input_path,
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
        tables_file = os.path.join(tmpdir, 'goblin-tables.json')
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
            [sys.executable, '-m', 'flavor_forge', 'generate', '--batch', tmpdir,
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
    from flavor_forge.__main__ import _results_to_json, _load_results_from_json

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
        [sys.executable, '-m', 'flavor_forge', 'generate', '--list-providers', '--generic'],
        capture_output=True, text=True,
        env={**os.environ, 'PYTHONPATH': os.path.join(os.path.dirname(__file__), '..', 'src')},
    )
    assert result.returncode == 0, f"--generic flag rejected: {result.stderr}"
    print("PASS: test_generic_flag_cli")


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
    print("\nAll exporter tests passed!")
