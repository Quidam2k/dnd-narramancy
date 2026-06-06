"""Print the exact prompt the generator would send for one ability of an actor.

Usage:
    python scripts/show_prompt.py input-pcs/fvtt-Actor-bael-*.json "Quarterstaff" [--context-file AoA_Bael]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from narramancy.batch_router import route_input
from narramancy.config import ConfigManager
from narramancy.generator import FlavorTextGenerator
from run_pc_stream import find_context_file, in_action_blurb, pronouns_from_blurb

actor_file, ability_name = sys.argv[1], sys.argv[2]
campaign = sys.argv[3] if len(sys.argv) > 3 else 'aoa'
creature = route_input(actor_file)
ctx_file = find_context_file(creature.name, campaign)
blurb = in_action_blurb(ctx_file) if ctx_file else None
if blurb:
    creature.context_blob = blurb
    creature.pronouns = pronouns_from_blurb(blurb) or creature.pronouns

ability = next(a for a in creature.abilities if ability_name.lower() in a.name.lower())
req = creature.to_flavor_request(ability)
gen = FlavorTextGenerator(ConfigManager())
prompt = (gen.generate_flavor_text_prompt(req) if req.has_outcomes
          else gen.generate_attempts_only_prompt(req))
print(f"--- ability: {ability.name} ({ability.ability_type}) has_outcomes={req.has_outcomes} ---")
print(f"--- description ({len(ability.description or '')} chars) ---")
print(prompt)
