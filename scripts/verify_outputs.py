"""Verify generated narramancy JSONs: structure, pronouns, mechanics leakage.

Usage:
    python scripts/verify_outputs.py eldrin-adquinal young-modos ...
"""
import json
import re
import sys
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / 'output'
MECH = re.compile(r'\b(\d?d\d+|DC \d+|hit points|saving throw|attack roll)\b', re.I)

for name in sys.argv[1:]:
    path = OUTPUT / f'{name}-narramancy.json'
    if not path.exists():
        print(f'{name}: NOT FOUND')
        continue
    d = json.loads(path.read_text(encoding='utf-8'))
    entries = [e for t in d['tables'] for e in t['entries']]
    char = d['creature']['name']
    tokens = char.split()
    it_count = sum(1 for e in entries if re.search(r'\bits?\b', e, re.I)
                   and not any(tok in e for tok in tokens))
    name_used = sum(1 for e in entries if any(tok in e for tok in tokens))
    flagged = [e for e in entries if MECH.search(e)]
    empty = [f"{t['ability']}/{t['category']}" for t in d['tables'] if not t['entries']]
    words = [len(e.split()) for e in entries]
    print(f"{name}: pronouns={d['creature']['pronouns']}, type={d['creature']['type']}")
    print(f"  tables={len(d['tables'])}, entries={len(entries)}, "
          f"avg-words={sum(words)/len(words):.1f}, empty={empty or 0}")
    print(f"  entries-using-name={name_used} ({100*name_used//len(entries)}%), "
          f"it-without-name={it_count} ({100*it_count//len(entries)}%), mechanics={len(flagged)}")
    for e in flagged[:3]:
        print(f'  ! {e}')
