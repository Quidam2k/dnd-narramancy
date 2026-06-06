"""Smoke test an LM Studio endpoint before a full generation run.

Runs two small generations against one endpoint:
  1. A rolled ability (attack/save) - verifies the 3-section
     ATTEMPTS/SUCCESSES/FAILURES format parses.
  2. A no-roll ability - verifies the attempts-only path live.

Usage:
    python scripts/smoke_lmstudio.py http://localhost:1234 [actor.json]
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

DEFAULT_ACTOR = 'fvtt-Actor-gimbal-starwhisper-fCEZTwnXtpQXOcuH.json'


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    os.environ['LMSTUDIO_BASE_URL'] = sys.argv[1].rstrip('/')
    actor_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_ACTOR

    from narramancy.batch_router import route_input
    from narramancy.config import ConfigManager
    from narramancy.generator import FlavorTextGenerator
    from narramancy.models import has_roll_outcomes

    creature = route_input(actor_path)
    rolled = next((a for a in creature.abilities if has_roll_outcomes(a)), None)
    noroll = next((a for a in creature.abilities if not has_roll_outcomes(a)), None)
    if not rolled or not noroll:
        print(f"Could not find both a rolled and a no-roll ability in {actor_path}")
        return 1

    generator = FlavorTextGenerator(ConfigManager())
    failures = 0

    for label, ability in (('rolled', rolled), ('no-roll', noroll)):
        req = creature.to_flavor_request(ability, variations=3)
        print(f"\n=== {label}: {ability.name} ({ability.ability_type}, "
              f"has_outcomes={req.has_outcomes}) ===")
        try:
            result = asyncio.run(generator.generate_flavor_text(req, provider_name='lmstudio'))
        except Exception as e:
            print(f"FAILED: {type(e).__name__}: {e}")
            failures += 1
            continue
        for section in ('attempts', 'successes', 'failures'):
            entries = getattr(result, section)
            print(f"  {section} ({len(entries)}):")
            for entry in entries:
                print(f"    - {entry}")
        if label == 'rolled' and not (result.attempts and result.successes and result.failures):
            print("FAILED: rolled ability missing one or more sections")
            failures += 1
        if label == 'no-roll' and (result.successes or result.failures):
            print("FAILED: no-roll ability produced success/failure entries")
            failures += 1
        if label == 'no-roll' and not result.attempts:
            print("FAILED: no-roll ability produced no attempts")
            failures += 1

    print(f"\n{'SMOKE TEST PASSED' if failures == 0 else f'SMOKE TEST FAILED ({failures})'} "
          f"against {os.environ['LMSTUDIO_BASE_URL']} "
          f"(model: {result.metadata.get('model', '?') if failures == 0 else '?'})")
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
