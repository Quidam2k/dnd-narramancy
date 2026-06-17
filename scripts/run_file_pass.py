"""Run one file-provider pass for a PC: record pending prompts / ingest responses.

Used for agent-backed generation (e.g. Claude Code Haiku subagents as the model).
Run repeatedly: each pass serves recorded responses and records any new prompts
(conditionals, top-ups) to pending/. Done when a pass reports 0 pending.

Usage:
    python scripts/run_file_pass.py <actor.json> --campaign aoa \
        [--file-dir output/agent-run] [--model-label claude-haiku-4-5] \
        [--output-dir output/haiku/]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))

from run_pc_stream import CAMPAIGNS, find_context_file, in_action_blurb, pronouns_from_blurb


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('actor')
    parser.add_argument('--campaign', required=True, choices=sorted(CAMPAIGNS))
    parser.add_argument('--file-dir', default='output/agent-run')
    parser.add_argument('--model-label', default='file')
    parser.add_argument('--output-dir', default='output/agent-run/')
    args = parser.parse_args()

    import json
    actor_file = Path(args.actor)
    actor_name = json.loads(actor_file.read_text(encoding='utf-8'))['name']
    ctx_file = find_context_file(actor_name, args.campaign)
    blurb = in_action_blurb(ctx_file) if ctx_file else None
    pronouns = pronouns_from_blurb(blurb) if blurb else None

    env = os.environ.copy()
    env['NARRAMANCY_AI_GENERATION_FILE_DIR'] = args.file_dir
    env['NARRAMANCY_AI_GENERATION_FILE_MODEL'] = args.model_label
    env['PYTHONPATH'] = str(PROJECT_ROOT / 'src')
    env['PYTHONIOENCODING'] = 'utf-8'

    cmd = [sys.executable, '-m', 'narramancy', 'generate', str(actor_file),
           '--provider', 'file', '--generic', '--with-crits',
           '--export', 'narramancy', '--output-dir', args.output_dir]
    if blurb:
        cmd += ['--context', blurb]
    if pronouns:
        cmd += ['--pronouns', pronouns]

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env,
                            capture_output=True, text=True, encoding='utf-8')

    pending = sorted((PROJECT_ROOT / args.file_dir / 'pending').glob('*.txt'))
    responses = list((PROJECT_ROOT / args.file_dir / 'responses').glob('*.txt'))
    # Pending prompts that already have a response are stale leftovers — clear them
    answered = {p.stem for p in responses}
    fresh = [p for p in pending if p.stem not in answered]
    for p in pending:
        if p.stem in answered:
            p.unlink()

    print(f'pass complete (cli exit {result.returncode})')
    print(f'responses on disk: {len(responses)}')
    print(f'pending prompts: {len(fresh)}')
    for p in fresh:
        print(f'  {p}')
    # Surface real (non-missing-response) errors from the CLI
    for line in (result.stderr or '').splitlines():
        if 'Error' in line and 'No response for prompt' not in line:
            print(f'  ! {line}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
