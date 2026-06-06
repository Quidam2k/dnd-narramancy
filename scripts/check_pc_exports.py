"""Dry-run check: parse each PC export and report ability counts."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from narramancy.batch_router import route_input
from narramancy.models import has_roll_outcomes

for f in sorted((Path(__file__).resolve().parent.parent / 'input-pcs').glob('*.json')):
    if 'gimbal' in f.name:
        continue
    actor_name = json.loads(f.read_text(encoding='utf-8'))['name']
    c = route_input(str(f))
    rolled = sum(1 for a in c.abilities if has_roll_outcomes(a))
    print(f"{f.name}\n  actor={actor_name!r} parsed={c.name!r} "
          f"class={getattr(c, '_pc_class', '?')} lvl={getattr(c, '_pc_level', '?')} "
          f"abilities={len(c.abilities)} (rolled={rolled}, no-roll={len(c.abilities) - rolled})")
