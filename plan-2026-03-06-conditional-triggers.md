# Plan: Conditional Triggers & Roll-Aware Flavor

## Phase Status

- [x] **Phase 1**: Python — New Table Categories (models, generator, exporter, CLI)
- [x] **Phase 2**: Python — Generation & Prompt Work (craft prompts, verified structure)
- [x] **Phase 3**: JS Module — Roll-Aware Dispatch (trigger-engine, importer, bloodied, no-repeat)
- [x] **Phase 4**: Integration Test (tests pass, export verified, JS reviewed)

## Key Design Decisions

- FlavorTextResult gets new optional fields: crits, fumbles, barely_hits, barely_misses (default [])
- Bloodied is generated as a separate "ability" with ability_type='bloodied'
- `--with-crits` flag on generate enables the new categories
- New trigger hookTypes: attackRoll_crit, attackRoll_fumble, attackRoll_barely_hits, attackRoll_barely_misses, bloodied
- JS trigger-engine inspects rolls[0] for nat d20, compares to target AC for margin
- No-repeat tracking via Map keyed by creature+table, resets on deleteCombat

## Files Modified

### Phase 1 + 2 (Python)
- src/flavor_forge/models.py — new FlavorTextResult fields
- src/flavor_forge/generator.py — new prompts for crit/fumble/barely/bloodied
- src/flavor_forge/exporters/flavor_forge_module.py — emit new tables + triggers
- src/flavor_forge/__main__.py — --with-crits flag, bloodied generation

### Phase 3 (JS)
- foundry-module/flavor-forge/scripts/trigger-engine.js — roll inspection, bloodied, no-repeat
- foundry-module/flavor-forge/scripts/importer.js — handle new table types
