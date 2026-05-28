"""Multi-creature format utilities.

v1 format: single creature per JSON file
v2 format: multiple creatures in a single JSON file

    {"formatVersion": 2, "creatures": [{creature, tables, triggers, whisper}, ...]}
"""


def detect_format_version(data: dict) -> int:
    """Return 1 or 2 based on the formatVersion key.

    Raises ValueError if the key is missing or unrecognized.
    """
    version = data.get('formatVersion')
    if version is None:
        raise ValueError("Missing formatVersion key in data")
    if version not in (1, 2):
        raise ValueError(f"Unrecognized formatVersion: {version}")
    return version


def upgrade_v1_to_v2(data: dict) -> dict:
    """Wrap a single v1 entry into a v2 bundle.

    Returns:
        {"formatVersion": 2, "creatures": [entry]}
        where entry has {creature, tables, triggers, whisper} (no formatVersion).
    """
    entry = {
        'creature': data['creature'],
        'tables': data.get('tables', []),
        'triggers': data.get('triggers', []),
        'whisper': data.get('whisper', 'gm'),
    }
    return {'formatVersion': 2, 'creatures': [entry]}


def split_v2_to_v1(data: dict) -> list:
    """Extract each creature entry from a v2 bundle into standalone v1 dicts.

    Returns:
        List of v1 dicts, each with formatVersion: 1.
    """
    results = []
    for entry in data.get('creatures', []):
        v1 = {'formatVersion': 1}
        v1['creature'] = entry['creature']
        v1['tables'] = entry.get('tables', [])
        v1['triggers'] = entry.get('triggers', [])
        v1['whisper'] = entry.get('whisper', 'gm')
        results.append(v1)
    return results


def merge_creature_results(*bundles: dict) -> dict:
    """Merge multiple v1 or v2 dicts into a single v2 bundle.

    Deduplicates by creature name — last wins.
    """
    merged = {'formatVersion': 2, 'creatures': []}
    seen = {}  # name -> index in creatures list

    for bundle in bundles:
        version = detect_format_version(bundle)
        if version == 1:
            bundle = upgrade_v1_to_v2(bundle)

        for entry in bundle['creatures']:
            name = entry['creature']['name']
            if name in seen:
                # Replace existing
                merged['creatures'][seen[name]] = entry
            else:
                seen[name] = len(merged['creatures'])
                merged['creatures'].append(entry)

    return merged


def add_creature_to_bundle(bundle: dict, creature_entry: dict) -> dict:
    """Add or replace a single creature entry in a v2 bundle.

    Matches by creature.name. If the bundle is v1, upgrades it first.

    Args:
        bundle: Existing v1 or v2 bundle.
        creature_entry: A creature entry dict with {creature, tables, triggers, whisper}.

    Returns:
        Updated v2 bundle.
    """
    version = detect_format_version(bundle)
    if version == 1:
        bundle = upgrade_v1_to_v2(bundle)
    else:
        # Shallow copy to avoid mutating the original
        bundle = {'formatVersion': 2, 'creatures': list(bundle['creatures'])}

    name = creature_entry['creature']['name']
    for i, existing in enumerate(bundle['creatures']):
        if existing['creature']['name'] == name:
            bundle['creatures'][i] = creature_entry
            return bundle

    bundle['creatures'].append(creature_entry)
    return bundle
