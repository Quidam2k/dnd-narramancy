"""Dry-test run_pc_stream's context-file mapping for the new campaign exports."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_pc_stream import find_context_file, in_action_blurb, pronouns_from_blurb

TESTS = [
    ('Bueller von Ferris 2024', 'undermountain'),
    ('Henry Swiftfoot 2024', 'undermountain'),
    ('Grumph', 'undermountain'),
    ('Iryi 2024', 'undermountain'),
    ('Ioko', 'undermountain'),
    ('Iryi of Devotion', 'witchlight'),
    ('Kathreen Shacklehammer', 'witchlight'),
    ('Thelonius', 'witchlight'),
    ('Vickarius Env', 'witchlight'),
]

for name, camp in TESTS:
    f = find_context_file(name, camp)
    blurb = in_action_blurb(f) if f else None
    pron = pronouns_from_blurb(blurb) if blurb else None
    detail = f' ({len(blurb)} chars, {pron or "sheet"})' if blurb else ''
    print(f'{name} [{camp}]: {f.name if f else "no context"}{detail}')
