"""CLI entry point for Narramancy.

Usage:
    python -m narramancy parse goblin.txt
    python -m narramancy parse --open5e goblin
    python -m narramancy parse --open5e "adult-red-dragon" --json
    python -m narramancy parse goblin.txt --context "These goblins serve a hobgoblin warlord"

    python -m narramancy generate --open5e goblin --style dramatic --variations 3
    python -m narramancy generate --open5e goblin --provider ollama
    python -m narramancy generate --open5e goblin --providers gemini,ollama --compare
    python -m narramancy generate --list-providers
    python -m narramancy generate --open5e goblin --export foundry --output-dir ./output/
    python -m narramancy generate --batch ./monsters/ --export all --output-dir ./output/

    python -m narramancy export results.json --format foundry --output goblin-tables.json
    python -m narramancy export results.json --format tokensays --output goblin-sayings.json
"""

import argparse
import asyncio
import json
import os
import sys

from .models import ParsedCreature, FlavorTextResult, GENERIC_ACTIONS, get_save_abilities, get_skill_abilities


def cmd_parse(args):
    """Handle the 'parse' subcommand."""
    from .parsers import parse_stat_block, fetch_creature, search_creatures

    creature = None

    page = getattr(args, 'page', None)

    if args.open5e:
        slug = args.open5e
        try:
            creature = fetch_creature(slug)
        except ValueError:
            # Try search
            print(f"Exact slug '{slug}' not found, searching...", file=sys.stderr)
            results = search_creatures(slug)
            if not results:
                print(f"No creatures found matching '{slug}'", file=sys.stderr)
                return 1
            print(f"Found {len(results)} matches:", file=sys.stderr)
            for r in results:
                print(f"  {r['slug']:30s}  CR {r['cr']:5s}  {r['type']}", file=sys.stderr)
            # Auto-pick first result
            creature = fetch_creature(results[0]['slug'])
            print(f"Using: {creature.name}", file=sys.stderr)
    elif args.input:
        creature = parse_stat_block(args.input, page=page)
    else:
        # Read from stdin
        text = sys.stdin.read()
        if not text.strip():
            print("No input provided. Use --open5e <slug>, a file path, or pipe text to stdin.", file=sys.stderr)
            return 1
        creature = parse_stat_block(text)

    if args.context:
        creature.context_blob = args.context

    if args.json:
        print(json.dumps(_creature_to_dict(creature), indent=2))
    else:
        _print_creature(creature)

    return 0


def cmd_export(args):
    """Handle the 'export' subcommand — convert saved JSON to Foundry/TokenSays/Narramancy."""
    from .exporters import export_rollable_tables, export_token_says, export_narramancy

    # Read the input JSON
    try:
        with open(args.input, 'r') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error reading {args.input}: {e}", file=sys.stderr)
        return 1

    # Reconstruct results dict — infer creature name if _creature key is missing
    creature_name = data.get('_creature')
    if not creature_name:
        # Try to infer from first ability's metadata, or fall back to filename stem
        for key, val in data.items():
            if not key.startswith('_') and isinstance(val, dict) and 'metadata' in val:
                creature_name = val['metadata'].get('creature_name')
                if creature_name:
                    break
        if not creature_name:
            creature_name = os.path.splitext(os.path.basename(args.input))[0]
            print(f"No creature name in JSON, using filename: {creature_name}", file=sys.stderr)
    results = _load_results_from_json(data)
    if not results:
        print("No generation results found in input file.", file=sys.stderr)
        return 1

    fmt = args.format
    output_path = args.output
    slug = creature_name.lower().replace(' ', '-')

    if fmt in ('foundry', 'all'):
        tables_text = export_rollable_tables(creature_name, results)
        path = output_path or f"{slug}-tables.txt"
        if fmt == 'all':
            path = f"{slug}-tables.txt"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(tables_text)
        table_count = tables_text.count('\n\n') + 1
        print(f"Wrote {table_count} rollable tables to {path}")

    if fmt in ('tokensays', 'all'):
        sayings = export_token_says(creature_name, results)
        path = output_path if fmt != 'all' else f"{slug}-sayings.json"
        if not path:
            path = f"{slug}-sayings.json"
        with open(path, 'w') as f:
            json.dump(sayings, f, indent=2)
        print(f"Wrote {len(sayings['sayings'])} TokenSays sayings to {path}")

    if fmt in ('narramancy', 'all'):
        creature_obj = _reconstruct_creature_from_results(creature_name, results)
        ff_data = export_narramancy(creature_obj, results)
        path = output_path if fmt != 'all' else f"{slug}-narramancy.json"
        if not path:
            path = f"{slug}-narramancy.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(ff_data, f, indent=2)
        print(f"Wrote Narramancy JSON to {path} ({len(ff_data['tables'])} tables, {len(ff_data['triggers'])} triggers)")

    return 0


def cmd_generate(args):
    """Handle the 'generate' subcommand."""
    from .config import ConfigManager
    from .generator import FlavorTextGenerator
    from .providers import get_available_providers, get_provider

    config = ConfigManager()

    # Validate config and show warnings
    for warning in config.validate():
        print(f"Warning: {warning}", file=sys.stderr)

    # --list-providers: show what's available and exit
    if args.list_providers:
        available = get_available_providers(config)
        if not available:
            print("No providers configured.")
        else:
            print("Available providers:")
            for name in available:
                try:
                    p = get_provider(name, config)
                    print(f"  {name:10s}  model: {p.model}")
                except ValueError as e:
                    print(f"  {name:10s}  (error: {e})")
        return 0

    # Batch mode
    if hasattr(args, 'batch') and args.batch:
        return _run_batch(args, config)

    # Parse the creature
    creature = _resolve_creature(args)
    if creature is None:
        return 1

    if args.context:
        creature.context_blob = args.context

    if getattr(args, 'generic', False):
        existing_names = {a.name for a in creature.abilities}
        # Add per-save abilities (all 6 — any creature can be forced to save)
        for sa in get_save_abilities():
            if sa.name not in existing_names:
                creature.abilities.append(sa)
        # Add per-skill abilities (only proficient skills)
        for ska in get_skill_abilities(creature.skill_proficiencies):
            if ska.name not in existing_names:
                creature.abilities.append(ska)
        # Add death save and initiative
        for ga in GENERIC_ACTIONS:
            if ga.name not in existing_names:
                creature.abilities.append(ga)

    # Build generator
    generator = FlavorTextGenerator(config)
    style = args.style or 'dramatic'
    variations = args.variations or 5

    # Comparison mode
    if args.compare and args.providers:
        provider_names = [p.strip() for p in args.providers.split(",")]
        return asyncio.run(_run_comparison(
            generator, creature, provider_names, style, variations, args.json,
        ))

    # Single provider mode
    provider_name = args.provider  # may be None (auto-detect)
    return asyncio.run(_run_single(
        generator, creature, provider_name, style, variations,
        as_json=args.json,
        export_format=getattr(args, 'export', None),
        output_dir=getattr(args, 'output_dir', None),
        creature_obj=creature,
        with_crits=getattr(args, 'with_crits', False),
        crit_count=getattr(args, 'crit_count', 5),
    ))


async def _run_single(generator, creature, provider_name, style, variations,
                      as_json=False, export_format=None, output_dir=None,
                      creature_obj=None, with_crits=False, crit_count=5):
    """Generate flavor text for all abilities with a single provider."""
    creature_obj = creature_obj or creature
    creature_name = creature_obj.name

    # Enrich ability descriptions before generation
    from .enricher import enrich_creature
    enrich_creature(creature)

    results = {}
    for ability in creature.abilities:
        request = creature.to_flavor_request(ability, style=style, variations=variations)
        # Pass multi-phase flag to generator for cast entry generation
        request._is_multi_phase = getattr(ability, 'is_multi_phase', False)
        try:
            result = await generator.generate_flavor_text(
                request, provider_name=provider_name,
                with_crits=with_crits, crit_count=crit_count,
            )
            # Stash ability_type in metadata for exporters
            result.metadata['ability_type'] = ability.ability_type
            results[ability.name] = result
        except Exception as e:
            print(f"Error generating for {ability.name}: {e}", file=sys.stderr)
            continue

    # Generate bloodied and death tables if --with-crits is enabled
    if with_crits:
        base_request = creature.to_flavor_request(
            creature.abilities[0], style=style, variations=crit_count,
        )
        for gen_name, gen_method, gen_type in [
            ('Bloodied', generator.generate_bloodied, 'bloodied'),
            ('Death', generator.generate_death, 'death'),
        ]:
            try:
                result = await gen_method(base_request, provider_name=provider_name, count=crit_count)
                result.metadata['ability_type'] = gen_type
                results[gen_name] = result
                print(f"Generated {len(result.attempts)} {gen_name.lower()} entries", file=sys.stderr)
            except Exception as e:
                print(f"Error generating {gen_name.lower()}: {e}", file=sys.stderr)

    if not results:
        print("No flavor text generated.", file=sys.stderr)
        return 1

    if as_json:
        out = _results_to_json(creature_name, results)
        print(json.dumps(out, indent=2))
    else:
        _print_results(results)

    # Export if requested
    if export_format:
        _export_results(creature_name, results, export_format, output_dir, creature_obj=creature_obj)
        if not as_json:
            print("Tip: use --json to also save raw generation results", file=sys.stderr)

    return 0


async def _run_comparison(generator, creature, provider_names, style, variations, as_json):
    """Generate flavor text across multiple providers for comparison."""
    all_comparisons = {}

    for ability in creature.abilities:
        request = creature.to_flavor_request(ability, style=style, variations=variations)
        comparison = await generator.generate_comparison(request, provider_names)
        all_comparisons[ability.name] = comparison

    if as_json:
        out = {}
        for ability_name, comparison in all_comparisons.items():
            out[ability_name] = {
                pname: {
                    'attempts': r.attempts,
                    'successes': r.successes,
                    'failures': r.failures,
                    'metadata': r.metadata,
                }
                for pname, r in comparison.items()
            }
        print(json.dumps(out, indent=2))
    else:
        _print_comparison(all_comparisons)

    return 0


def _results_to_json(creature_name, results):
    """Convert results dict to JSON-serializable format with creature name."""
    out = {
        '_creature': creature_name,
    }
    for name, r in results.items():
        entry = {
            'attempts': r.attempts,
            'successes': r.successes,
            'failures': r.failures,
            'metadata': r.metadata,
        }
        # Include conditional fields only when populated
        for cond_field in ('crits', 'fumbles', 'barely_hits', 'barely_misses', 'miss_dodge', 'miss_armor', 'killing_blow', 'cast'):
            vals = getattr(r, cond_field, [])
            if vals:
                entry[cond_field] = vals
        out[name] = entry
    return out


def _load_results_from_json(data):
    """Reconstruct a Dict[str, FlavorTextResult] from saved JSON."""
    results = {}
    for key, val in data.items():
        if key.startswith('_'):
            continue
        if isinstance(val, dict) and 'attempts' in val:
            results[key] = FlavorTextResult(
                attempts=val.get('attempts', []),
                successes=val.get('successes', []),
                failures=val.get('failures', []),
                metadata=val.get('metadata', {}),
                crits=val.get('crits', []),
                fumbles=val.get('fumbles', []),
                barely_hits=val.get('barely_hits', []),
                barely_misses=val.get('barely_misses', []),
                miss_dodge=val.get('miss_dodge', []),
                miss_armor=val.get('miss_armor', []),
                killing_blow=val.get('killing_blow', []),
                cast=val.get('cast', []),
            )
    return results


def _reconstruct_creature_from_results(creature_name, results):
    """Build a ParsedCreature from generation result metadata when no creature object is available."""
    creature_type = ''
    cr = ''
    for result in results.values():
        meta = result.metadata
        if not creature_type and meta.get('character_race'):
            creature_type = meta['character_race']
        if not cr and meta.get('character_level'):
            cr = str(meta['character_level'])
        if creature_type and cr:
            break
    return ParsedCreature(name=creature_name, creature_type=creature_type, challenge_rating=cr)


def _export_results(creature_name, results, export_format, output_dir, creature_obj=None):
    """Write export files for the given results."""
    from .exporters import export_rollable_tables, export_token_says, export_narramancy

    output_dir = output_dir or '.'
    os.makedirs(output_dir, exist_ok=True)
    slug = creature_name.lower().replace(' ', '-')

    if export_format in ('foundry', 'all'):
        tables_text = export_rollable_tables(creature_name, results)
        path = os.path.join(output_dir, f"{slug}-tables.txt")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(tables_text)
        table_count = tables_text.count('\n\n') + 1
        print(f"Wrote {table_count} rollable tables to {path}")

    if export_format in ('tokensays', 'all'):
        sayings = export_token_says(creature_name, results)
        path = os.path.join(output_dir, f"{slug}-sayings.json")
        with open(path, 'w') as f:
            json.dump(sayings, f, indent=2)
        print(f"Wrote {len(sayings['sayings'])} TokenSays sayings to {path}")

    if export_format in ('narramancy', 'all'):
        if creature_obj is None:
            # Build a minimal ParsedCreature for backward compat
            creature_obj = ParsedCreature(name=creature_name)
        ff_data = export_narramancy(creature_obj, results)
        path = os.path.join(output_dir, f"{slug}-narramancy.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(ff_data, f, indent=2)
        print(f"Wrote Narramancy JSON to {path} ({len(ff_data['tables'])} tables, {len(ff_data['triggers'])} triggers)")


def _run_batch(args, config):
    """Process all creature files in a directory."""
    from .generator import FlavorTextGenerator
    from .batch_router import scan_batch_folder, route_input, SkipFileError

    batch_dir = args.batch
    if not os.path.isdir(batch_dir):
        print(f"Batch directory not found: {batch_dir}", file=sys.stderr)
        return 1

    # Read folder-level context if present
    flavor_ctx = None
    flavor_path = os.path.join(batch_dir, 'flavor.txt')
    if os.path.isfile(flavor_path):
        with open(flavor_path, 'r') as f:
            flavor_ctx = f.read().strip()
        print(f"Using folder context from flavor.txt ({len(flavor_ctx)} chars)", file=sys.stderr)

    # Scan and classify all files
    entries = scan_batch_folder(batch_dir)
    if not entries:
        print(f"No processable files found in {batch_dir}", file=sys.stderr)
        return 1

    processable = [e for e in entries if not e.skip_reason]
    skipped = [e for e in entries if e.skip_reason]

    # Print scan summary
    print(f"Scanned {len(entries)} files: {len(processable)} to process, {len(skipped)} skipped", file=sys.stderr)
    for e in skipped:
        print(f"  skip: {e.filename} ({e.skip_reason})", file=sys.stderr)

    if not processable:
        print("Nothing to process.", file=sys.stderr)
        return 1

    generator = FlavorTextGenerator(config)
    style = args.style or 'dramatic'
    variations = args.variations or 5
    provider_name = args.provider
    export_format = getattr(args, 'export', None)
    output_dir = getattr(args, 'output_dir', None)
    merge_output = getattr(args, 'merge_output', False)
    errors = 0

    # Collect per-creature narramancy exports for merge
    narramancy_v1_list = []

    for entry in processable:
        print(f"\nProcessing {entry.filename} [{entry.input_type.value}]...", file=sys.stderr)

        try:
            creature = route_input(entry.path)

            # Apply folder context if creature doesn't have its own
            if not creature.context_blob and flavor_ctx:
                creature.context_blob = flavor_ctx

            if hasattr(args, 'context') and args.context:
                creature.context_blob = args.context

            rc = asyncio.run(_run_single(
                generator, creature, provider_name, style, variations,
                as_json=args.json,
                export_format=export_format,
                output_dir=output_dir,
                creature_obj=creature,
            ))
            if rc != 0:
                errors += 1
            elif merge_output and export_format in ('narramancy', 'all'):
                # Read back the per-creature narramancy JSON for merging
                slug = creature.name.lower().replace(' ', '-')
                per_creature_path = os.path.join(output_dir or '.', f"{slug}-narramancy.json")
                if os.path.isfile(per_creature_path):
                    with open(per_creature_path, 'r') as f:
                        narramancy_v1_list.append(json.load(f))
        except SkipFileError as e:
            print(f"  Skipped: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error processing {entry.filename}: {e}", file=sys.stderr)
            errors += 1

    # Produce merged v2 JSON if requested
    if merge_output and narramancy_v1_list:
        from .merger import merge_creature_results
        merged = merge_creature_results(*narramancy_v1_list)
        merged_path = os.path.join(output_dir or '.', 'merged-narramancy.json')
        with open(merged_path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=2)
        total_tables = sum(len(c.get('tables', [])) for c in merged['creatures'])
        total_triggers = sum(len(c.get('triggers', [])) for c in merged['creatures'])
        print(f"\nWrote merged v2 JSON to {merged_path} "
              f"({len(merged['creatures'])} creatures, {total_tables} tables, {total_triggers} triggers)")

    if errors:
        print(f"\n{errors} file(s) had errors.", file=sys.stderr)
    return 1 if errors == len(processable) else 0


def _resolve_creature(args):
    """Resolve creature from CLI args (shared by parse and generate)."""
    from .parsers import parse_stat_block, fetch_creature, search_creatures

    if args.open5e:
        slug = args.open5e
        try:
            return fetch_creature(slug)
        except ValueError:
            print(f"Exact slug '{slug}' not found, searching...", file=sys.stderr)
            results = search_creatures(slug)
            if not results:
                print(f"No creatures found matching '{slug}'", file=sys.stderr)
                return None
            print(f"Found {len(results)} matches, using first: {results[0]['slug']}", file=sys.stderr)
            return fetch_creature(results[0]['slug'])

    elif hasattr(args, 'stdin') and args.stdin:
        text = sys.stdin.read()
        if not text.strip():
            print("No input on stdin.", file=sys.stderr)
            return None
        # Try parsing as JSON (piped from `parse --json`)
        try:
            data = json.loads(text)
            return _dict_to_creature(data)
        except (json.JSONDecodeError, KeyError):
            return parse_stat_block(text)

    elif args.input:
        page = getattr(args, 'page', None)
        return parse_stat_block(args.input, page=page)

    else:
        print("No input provided. Use --open5e <slug>, a file path, or --stdin.", file=sys.stderr)
        return None


def _dict_to_creature(data: dict) -> ParsedCreature:
    """Reconstruct ParsedCreature from a dict (e.g. piped JSON from `parse --json`)."""
    return ParsedCreature.from_dict(data)


def _creature_to_dict(creature: ParsedCreature) -> dict:
    """Convert a ParsedCreature to a JSON-serializable dict."""
    return {
        'name': creature.name,
        'size': creature.size,
        'type': creature.creature_type,
        'cr': creature.challenge_rating,
        'context': creature.context_blob,
        'skill_proficiencies': creature.skill_proficiencies,
        'save_proficiencies': creature.save_proficiencies,
        'abilities': [
            {
                'name': a.name,
                'ability_type': a.ability_type,
                'description': a.description,
                'damage': a.damage,
                'attack_bonus': a.attack_bonus,
                'save_dc': a.save_dc,
                'save_type': a.save_type,
                'range': a.range,
                'uses': a.uses,
                'recharge': a.recharge,
            }
            for a in creature.abilities
        ],
    }


def _print_creature(creature: ParsedCreature):
    """Pretty-print a parsed creature."""
    print(f"{creature.name}")
    print(f"  {creature.size} {creature.creature_type}, CR {creature.challenge_rating}")
    if creature.context_blob:
        print(f"  Context: {creature.context_blob}")
    print(f"  {len(creature.abilities)} abilities:")
    for a in creature.abilities:
        extras = []
        if a.attack_bonus is not None:
            extras.append(f"+{a.attack_bonus} to hit")
        if a.damage:
            extras.append(a.damage)
        if a.save_dc:
            extras.append(f"DC {a.save_dc} {a.save_type}")
        if a.recharge:
            extras.append(f"recharge {a.recharge}")
        if a.uses:
            extras.append(a.uses)
        extra_str = f" ({', '.join(extras)})" if extras else ""
        print(f"    [{a.ability_type:12s}] {a.name}{extra_str}")


def _print_results(results):
    """Pretty-print single-provider generation results."""
    for ability_name, result in results.items():
        print(f"\n{'='*60}")
        print(f"  {ability_name}  [{result.metadata.get('provider', '?')}]")
        print(f"{'='*60}")
        all_categories = ['attempts', 'successes', 'failures', 'cast', 'crits', 'fumbles', 'barely_hits', 'barely_misses', 'miss_dodge', 'miss_armor', 'killing_blow']
        for category in all_categories:
            texts = getattr(result, category, [])
            if texts:
                print(f"\n  {category.upper()}:")
                for i, text in enumerate(texts, 1):
                    print(f"    {i}. {text}")


def _print_comparison(all_comparisons):
    """Pretty-print comparison results across providers."""
    for ability_name, comparison in all_comparisons.items():
        print(f"\n{'='*60}")
        print(f"  {ability_name}")
        print(f"{'='*60}")

        for pname, result in comparison.items():
            if result.metadata.get('error'):
                print(f"\n  [{pname}] ERROR: {result.metadata['error']}")
                continue

            print(f"\n  [{pname}] (model: {result.metadata.get('model', '?')})")
            all_categories = ['attempts', 'successes', 'failures', 'cast', 'crits', 'fumbles', 'barely_hits', 'barely_misses', 'miss_dodge', 'miss_armor', 'killing_blow']
            for category in all_categories:
                texts = getattr(result, category, [])
                if texts:
                    print(f"    {category.upper()}:")
                    for i, text in enumerate(texts, 1):
                        print(f"      {i}. {text}")


def main():
    # Ensure UTF-8 output on Windows (avoids cp1252 encoding errors)
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(
        prog='narramancy',
        description='D&D Narramancy — vivid narration for abilities and actions',
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # parse subcommand
    parse_cmd = subparsers.add_parser('parse', help='Parse a monster stat block')
    parse_cmd.add_argument('input', nargs='?', help='File path or text to parse')
    parse_cmd.add_argument('--open5e', metavar='SLUG', help='Fetch creature from Open5e API by slug')
    parse_cmd.add_argument('--page', type=int, metavar='N', help='PDF page number to extract (1-based)')
    parse_cmd.add_argument('--context', help='Additional context for flavor generation')
    parse_cmd.add_argument('--json', action='store_true', help='Output as JSON')

    # generate subcommand
    gen_cmd = subparsers.add_parser('generate', help='Generate flavor text for a creature')
    gen_cmd.add_argument('input', nargs='?', help='File path or text to parse')
    gen_cmd.add_argument('--open5e', metavar='SLUG', help='Fetch creature from Open5e API by slug')
    gen_cmd.add_argument('--page', type=int, metavar='N', help='PDF page number to extract (1-based)')
    gen_cmd.add_argument('--context', help='Additional context for flavor generation')
    gen_cmd.add_argument('--style', choices=['dramatic', 'comedic', 'gritty', 'heroic'],
                         default='dramatic', help='Flavor text style (default: dramatic)')
    gen_cmd.add_argument('--variations', type=int, default=5,
                         help='Number of variations per category (default: 5)')
    gen_cmd.add_argument('--provider', help='AI provider to use (gemini, claude, ollama)')
    gen_cmd.add_argument('--providers', help='Comma-separated providers for comparison mode')
    gen_cmd.add_argument('--compare', action='store_true', help='Compare output across providers')
    gen_cmd.add_argument('--list-providers', action='store_true', help='List available providers and exit')
    gen_cmd.add_argument('--json', action='store_true', help='Output as JSON')
    gen_cmd.add_argument('--stdin', action='store_true', help='Read parsed creature JSON from stdin')
    gen_cmd.add_argument('--export', choices=['foundry', 'tokensays', 'narramancy', 'all'],
                         help='Export format (triggers export after generation)')
    gen_cmd.add_argument('--output-dir', metavar='PATH',
                         help='Directory for export output files (default: current dir)')
    gen_cmd.add_argument('--batch', metavar='PATH',
                         help='Directory of creature files for batch processing')
    gen_cmd.add_argument('--generic', action='store_true',
                         help='Include generic actions (saves, skills, initiative, death saves)')
    gen_cmd.add_argument('--with-crits', action='store_true',
                         help='Generate crit/fumble/barely tables for attack abilities')
    gen_cmd.add_argument('--crit-count', type=int, default=5,
                         help='Number of variations for conditional categories (default: 5)')
    gen_cmd.add_argument('--merge-output', action='store_true',
                         help='Produce a merged v2 JSON with all creatures (batch mode + narramancy export)')

    # export subcommand
    export_cmd = subparsers.add_parser('export', help='Export saved generation results')
    export_cmd.add_argument('input', help='Path to saved generation JSON')
    export_cmd.add_argument('--format', choices=['foundry', 'tokensays', 'narramancy', 'all'],
                            default='foundry', help='Export format (default: foundry)')
    export_cmd.add_argument('--output', metavar='PATH',
                            help='Output file path (auto-named if omitted)')

    # serve subcommand
    serve_cmd = subparsers.add_parser('serve', help='Launch the Narramancy web server')
    serve_cmd.add_argument('--port', type=int, default=5000, help='Port to serve on (default: 5000)')
    serve_cmd.add_argument('--work-dir', default='./output', help='Working directory for JSON files (default: ./output)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == 'parse':
        return cmd_parse(args)
    elif args.command == 'generate':
        return cmd_generate(args)
    elif args.command == 'export':
        return cmd_export(args)
    elif args.command == 'serve':
        from .server import launch
        launch(port=args.port, work_dir=args.work_dir)
        return 0

    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
