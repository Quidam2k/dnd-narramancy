"""Tests for multi-creature format merge/split/upgrade utilities."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from narramancy.merger import (
    detect_format_version,
    upgrade_v1_to_v2,
    split_v2_to_v1,
    merge_creature_results,
    add_creature_to_bundle,
)


def _make_v1(name='Goblin', table_count=1, whisper='gm'):
    """Create a minimal v1 creature bundle."""
    tables = [
        {
            'ability': 'Slash',
            'category': 'attempts',
            'description': 'Flavor text for attempts an attack',
            'entries': ['blade swings wild'],
        }
        for _ in range(table_count)
    ]
    return {
        'formatVersion': 1,
        'creature': {
            'name': name,
            'tokenPattern': f'*{name}*',
            'cr': '1/4',
            'type': 'humanoid',
            'pronouns': 'it',
        },
        'whisper': whisper,
        'tables': tables,
        'triggers': [
            {'hookType': 'attackRoll', 'itemName': 'Slash', 'table': 'Slash|attempts'},
        ],
    }


def test_detect_format_version():
    """v1 returns 1, v2 returns 2, missing key raises ValueError."""
    assert detect_format_version({'formatVersion': 1}) == 1
    assert detect_format_version({'formatVersion': 2}) == 2

    try:
        detect_format_version({})
        assert False, "Should have raised ValueError for missing key"
    except ValueError as e:
        assert 'Missing' in str(e)

    try:
        detect_format_version({'formatVersion': 99})
        assert False, "Should have raised ValueError for unknown version"
    except ValueError as e:
        assert 'Unrecognized' in str(e)

    print("PASS: test_detect_format_version")


def test_upgrade_v1_to_v2():
    """Single creature wraps correctly into v2."""
    v1 = _make_v1('Goblin')
    v2 = upgrade_v1_to_v2(v1)

    assert v2['formatVersion'] == 2
    assert len(v2['creatures']) == 1

    entry = v2['creatures'][0]
    assert 'formatVersion' not in entry
    assert entry['creature']['name'] == 'Goblin'
    assert entry['tables'] == v1['tables']
    assert entry['triggers'] == v1['triggers']
    assert entry['whisper'] == 'gm'

    print("PASS: test_upgrade_v1_to_v2")


def test_split_v2_to_v1():
    """Round-trips with upgrade — split produces valid v1 entries."""
    v1_original = _make_v1('Skeleton')
    v2 = upgrade_v1_to_v2(v1_original)
    v1_list = split_v2_to_v1(v2)

    assert len(v1_list) == 1
    v1_back = v1_list[0]
    assert v1_back['formatVersion'] == 1
    assert v1_back['creature']['name'] == 'Skeleton'
    assert v1_back['tables'] == v1_original['tables']
    assert v1_back['triggers'] == v1_original['triggers']

    print("PASS: test_split_v2_to_v1")


def test_merge_two_v1():
    """Merges two v1 files into v2 with 2 creatures."""
    v1a = _make_v1('Goblin')
    v1b = _make_v1('Skeleton')
    merged = merge_creature_results(v1a, v1b)

    assert merged['formatVersion'] == 2
    assert len(merged['creatures']) == 2
    names = [c['creature']['name'] for c in merged['creatures']]
    assert 'Goblin' in names
    assert 'Skeleton' in names

    print("PASS: test_merge_two_v1")


def test_merge_dedup():
    """Same creature name in two inputs -> last wins, only 1 in output."""
    v1a = _make_v1('Goblin', whisper='gm')
    v1b = _make_v1('Goblin', whisper='owner')
    merged = merge_creature_results(v1a, v1b)

    assert merged['formatVersion'] == 2
    assert len(merged['creatures']) == 1
    assert merged['creatures'][0]['whisper'] == 'owner'

    print("PASS: test_merge_dedup")


def test_add_creature_to_bundle():
    """Add new creature + replace existing creature."""
    v2 = upgrade_v1_to_v2(_make_v1('Goblin'))

    # Add a new creature
    skeleton_entry = {
        'creature': {'name': 'Skeleton', 'tokenPattern': '*Skeleton*', 'cr': '1/4', 'type': 'undead', 'pronouns': 'it'},
        'tables': [],
        'triggers': [],
        'whisper': 'gm',
    }
    result = add_creature_to_bundle(v2, skeleton_entry)
    assert len(result['creatures']) == 2
    names = [c['creature']['name'] for c in result['creatures']]
    assert 'Goblin' in names
    assert 'Skeleton' in names

    # Replace existing creature (Goblin with different whisper)
    goblin_updated = {
        'creature': {'name': 'Goblin', 'tokenPattern': '*Goblin*', 'cr': '1/4', 'type': 'humanoid', 'pronouns': 'it'},
        'tables': [{'ability': 'Bite', 'category': 'attempts', 'entries': ['chomps']}],
        'triggers': [],
        'whisper': 'public',
    }
    result2 = add_creature_to_bundle(result, goblin_updated)
    assert len(result2['creatures']) == 2
    goblin = next(c for c in result2['creatures'] if c['creature']['name'] == 'Goblin')
    assert goblin['whisper'] == 'public'
    assert goblin['tables'][0]['ability'] == 'Bite'

    print("PASS: test_add_creature_to_bundle")


def test_round_trip():
    """split(upgrade(v1)) returns equivalent v1."""
    v1 = _make_v1('Goblin')
    v2 = upgrade_v1_to_v2(v1)
    v1_list = split_v2_to_v1(v2)

    assert len(v1_list) == 1
    v1_back = v1_list[0]

    # Compare all fields
    assert v1_back['formatVersion'] == v1['formatVersion']
    assert v1_back['creature'] == v1['creature']
    assert v1_back['tables'] == v1['tables']
    assert v1_back['triggers'] == v1['triggers']
    assert v1_back['whisper'] == v1['whisper']

    print("PASS: test_round_trip")


def test_merge_v2_bundles():
    """Merging two v2 bundles works correctly."""
    v2a = merge_creature_results(_make_v1('Goblin'), _make_v1('Skeleton'))
    v2b = merge_creature_results(_make_v1('Zombie'), _make_v1('Ghoul'))
    merged = merge_creature_results(v2a, v2b)

    assert merged['formatVersion'] == 2
    assert len(merged['creatures']) == 4
    names = {c['creature']['name'] for c in merged['creatures']}
    assert names == {'Goblin', 'Skeleton', 'Zombie', 'Ghoul'}

    print("PASS: test_merge_v2_bundles")


def test_add_to_v1_upgrades():
    """add_creature_to_bundle upgrades a v1 bundle to v2."""
    v1 = _make_v1('Goblin')
    entry = {
        'creature': {'name': 'Skeleton', 'tokenPattern': '*Skeleton*', 'cr': '1/4', 'type': 'undead', 'pronouns': 'it'},
        'tables': [],
        'triggers': [],
        'whisper': 'gm',
    }
    result = add_creature_to_bundle(v1, entry)
    assert result['formatVersion'] == 2
    assert len(result['creatures']) == 2

    print("PASS: test_add_to_v1_upgrades")


if __name__ == '__main__':
    test_detect_format_version()
    test_upgrade_v1_to_v2()
    test_split_v2_to_v1()
    test_merge_two_v1()
    test_merge_dedup()
    test_add_creature_to_bundle()
    test_round_trip()
    test_merge_v2_bundles()
    test_add_to_v1_upgrades()
    print("\nAll merger tests passed!")
