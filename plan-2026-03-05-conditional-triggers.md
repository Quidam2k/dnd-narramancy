# Plan: Conditional Triggers & Roll-Aware Flavor

## Overview
Enhance the Flavor Forge module to produce context-sensitive flavor based on roll results,
defensive effects, and creature state. Research dnd5e hook payloads first, then implement
what's feasible.

---

## Phase 1: Research dnd5e Hook Payloads [PENDING]

**Goal:** Determine exactly what data is available in each hook we care about.

**Research targets:**
1. `dnd5e.rollAttack(rolls, data)` — Can we get:
   - The actual d20 roll result (for nat 1 / nat 20 detection)?
   - Target AC (to detect "barely hits" or "armor deflection vs dodge")?
   - Advantage/disadvantage status and source (item, spell, condition)?
2. `dnd5e.rollDamage(rolls, data)` — Is sneak attack identifiable as a separate component?
3. HP change detection — Is there a `dnd5e` hook for damage taken, or do we use
   core Foundry `updateActor` with HP diff? Can we detect crossing the bloodied threshold?
4. Defensive effects — Can we detect active effects like Cloak of Displacement, Mirror Image,
   Shield spell from the attack roll hook data or from the target actor's effects?
5. `dnd5e.preUseItem(activity, config, messageConfig)` — Does the activity carry enough
   info to distinguish spell casting from feature use?

**Method:** Read dnd5e system source code on GitHub (dnd5e/module/documents/), Foundry API
docs, and community wiki. Check actual hook call sites in the dnd5e codebase.

**Output:** Update this plan with findings per item. Mark each as FEASIBLE / PARTIAL / NOT FEASIBLE.

> NEXT: Upon completing this phase, immediately call EnterPlanMode for Phase 2. Do NOT stop or wait for the user to ask.

---

## Phase 2: Design Decisions [PENDING]

**Goal:** Based on research findings, define:
1. What new table categories to add (e.g., nat1, nat20, barely_hits, armor_deflect, bloodied, defensive_item)
2. New trigger types for the JS module
3. How the Python exporter maps these to the Flavor Forge JSON format
4. Whether advantage/disadvantage awareness is feasible and how to surface it
5. No-repeat tracking design (per-combat Set, reset on combat end)

**Dependencies:** Phase 1 findings

**Output:** Concrete specification added to this plan file — table types, trigger schema, hook logic.

> NEXT: Upon completing this phase, immediately call EnterPlanMode for Phase 3. Do NOT stop or wait for the user to ask.

---

## Phase 3: Python Generation — New Table Categories [PENDING]

**Goal:** Add generation support for new table types.

**Tasks:**
- Add new ability_type values or table categories based on Phase 2 design
- Update prompt in generator.py for each new category (nat1 flavor, crit flavor, bloodied flavor, etc.)
- Update models.py if new ParsedAbility types are needed
- Update exporters/flavor_forge_module.py to emit new trigger types in JSON
- Update __main__.py if new CLI flags needed (e.g., --with-crits, --with-bloodied)
- Test generation of each new category with LM Studio

**Files likely touched:**
- src/flavor_forge/generator.py
- src/flavor_forge/models.py
- src/flavor_forge/exporters/flavor_forge_module.py
- src/flavor_forge/__main__.py

> NEXT: Upon completing this phase, immediately call EnterPlanMode for Phase 4. Do NOT stop or wait for the user to ask.

---

## Phase 4: JS Module — Roll-Aware Trigger Engine [PENDING]

**Goal:** Update trigger-engine.js to use roll data for conditional dispatching.

**Tasks:**
- Extract d20 result from `rolls` parameter in rollAttack hook
- Detect nat 1 / nat 20 and dispatch to appropriate tables
- If feasible: compare roll to target AC for "barely hits" / "miss type" logic
- If feasible: detect advantage/disadvantage and source
- Add bloodied detection hook (updateActor or dnd5e-specific)
- Add defensive item/spell trigger support (fires alongside attack miss)
- Implement no-repeat tracking (Set per creature per combat, clear on combat end)
- Update importer.js if new table types need special handling during import

**Files likely touched:**
- foundry-module/flavor-forge/scripts/trigger-engine.js
- foundry-module/flavor-forge/scripts/settings.js (if new config needed)
- foundry-module/flavor-forge/scripts/importer.js (if new table structure)

> NEXT: Upon completing this phase, immediately call EnterPlanMode for Phase 5. Do NOT stop or wait for the user to ask.

---

## Phase 5: Integration Test [PENDING]

**Goal:** End-to-end verification.

**Tasks:**
- Generate full drow elite warrior tables with all new categories using LM Studio
- Verify JSON output has correct trigger types and table structure
- Review JS module for any remaining references to old patterns
- Manual review: do the generated fragments make sense for each category?
- Ensure existing tests still pass
- Document any new CLI flags or workflow changes

> NEXT: This is the final phase. Mark cascade complete.

---

## Key Design Principles (from brainstorm)
- Defensive items/spells get their OWN tables, not multipliers on attack tables
- DM sees both "attack missed" + "cloak worked" fragments, picks from either
- Bloodied is ONE trigger with ONE table, not mood escalation across everything
- No-repeat is a simple Set check, reset per combat
- Context/reskin flavor comes through context_blob — already works, just needs prominence
- Player-side flavor is future work (character sheet ingestion), not this cascade
- Triplet editing (regenerate one phrase, favorite individual phrases) is UI work, not this cascade
