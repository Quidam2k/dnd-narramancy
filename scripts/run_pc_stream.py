"""Run narramancy generation for PC actor exports against one LM Studio endpoint.

Generalizes run_aoa_stream.py across campaigns: each campaign maps to the
directory + filename pattern of its character context files. PCs without a
context file (new campaigns, familiars) generate without a character-voice
blurb instead of being skipped.

One stream = one endpoint, PCs processed sequentially. Launch one stream per
machine as concurrent background processes.

Usage:
    python scripts/run_pc_stream.py <endpoint> --campaign undermountain actor1.json [actor2.json ...]
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL = 'google/gemma-4-12b'

# campaign -> (context dir, filename pattern)
CAMPAIGNS = {
    'aoa': (Path(r'Q:\DnD\Absence of Alternatives'), 'AoA_{name}.md'),
    'undermountain': (Path(r'Q:\DnD\Undermountain\Active_Campaign\Campaign_Notes'), 'Undermountain_{name}.md'),
    # CFK files double as context for the same group's new Witchlight campaign (e.g. Iryi)
    'witchlight': (Path(r'Q:\DnD\Order of the Hourglass- Cloudfang Keep'), 'CFK_{name}.md'),
    'cfk': (Path(r'Q:\DnD\Order of the Hourglass- Cloudfang Keep'), 'CFK_{name}.md'),
}

# Actor-name token -> context-file name when spellings differ
ALIASES = {
    'grumph': 'Grumpf',
}


def find_context_file(actor_name: str, campaign: str) -> Path | None:
    """Match actor name tokens (and aliases) against the campaign's context files."""
    ctx_dir, pattern = CAMPAIGNS[campaign]
    for token in actor_name.split():
        token = ALIASES.get(token.lower(), token)
        path = ctx_dir / pattern.format(name=token)
        if path.exists():
            return path
    return None


def in_action_blurb(path: Path) -> str | None:
    """Extract the '## In Action' section from a character context file."""
    lines = path.read_text(encoding='utf-8').splitlines()
    blurb, capturing = [], False
    for line in lines:
        if line.startswith('## '):
            if capturing:
                break
            capturing = line.strip().lower() == '## in action'
            continue
        if capturing:
            blurb.append(line)
    return '\n'.join(blurb).strip() or None


def pronouns_from_blurb(blurb: str) -> str | None:
    """Infer pronouns from the In Action prose (sheet gender fields are often blank)."""
    he = len(re.findall(r'\b(he|him|his)\b', blurb, re.I))
    she = len(re.findall(r'\b(she|her|hers)\b', blurb, re.I))
    if he > she and he >= 3:
        return 'he/him'
    if she > he and she >= 3:
        return 'she/her'
    return None  # ambiguous — let the sheet/parser fallback decide


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('endpoint')
    parser.add_argument('--campaign', required=True, choices=sorted(CAMPAIGNS))
    parser.add_argument('actors', nargs='+')
    args = parser.parse_args()

    env = os.environ.copy()
    env['LMSTUDIO_BASE_URL'] = args.endpoint.rstrip('/')
    env['NARRAMANCY_AI_GENERATION_LMSTUDIO_MODEL'] = MODEL
    env['PYTHONPATH'] = str(PROJECT_ROOT / 'src')
    env['PYTHONIOENCODING'] = 'utf-8'

    failures = []
    for actor_path in args.actors:
        actor_file = Path(actor_path)
        actor_name = json.loads(actor_file.read_text(encoding='utf-8'))['name']

        ctx_file = find_context_file(actor_name, args.campaign)
        blurb = in_action_blurb(ctx_file) if ctx_file else None
        pronouns = pronouns_from_blurb(blurb) if blurb else None

        print(f'[stream] {actor_name} -> {args.endpoint} '
              f'(context: {ctx_file.name if ctx_file else "NONE"}, '
              f'pronouns: {pronouns or "from sheet"})', flush=True)

        cmd = [sys.executable, '-m', 'narramancy', 'generate', str(actor_file),
               '--provider', 'lmstudio', '--generic', '--with-crits',
               '--json', '--export', 'narramancy', '--output-dir', 'output/']
        if blurb:
            cmd += ['--context', blurb]
        if pronouns:
            cmd += ['--pronouns', pronouns]

        result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env)
        if result.returncode != 0:
            print(f'[stream] FAILED {actor_name} (exit {result.returncode})', flush=True)
            failures.append(actor_name)
        else:
            print(f'[stream] DONE {actor_name}', flush=True)

    print(f'[stream] Finished {args.endpoint}: '
          f'{len(args.actors) - len(failures)}/{len(args.actors)} OK'
          + (f' — failures: {", ".join(failures)}' if failures else ''), flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
