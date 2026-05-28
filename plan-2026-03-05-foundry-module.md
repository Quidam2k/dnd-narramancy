# Plan: Narramancy Foundry VTT Module + Generator Improvements

**Created:** 2026-03-05
**Status:** Complete (pending Forge VTT deployment test)

## Phase 1: Foundry Module Scaffold
**Status:** complete
- [x] Create `foundry-module/narramancy/` directory structure
- [x] `module.json` manifest (dnd5e dependency, Foundry v11+)
- [x] `scripts/main.js` — entry point, hook registration, init
- [x] `scripts/settings.js` — module settings registration
- [x] `scripts/utils.js` — wildcard matching, slug helpers
- [x] `lang/en.json` — i18n strings
- [x] `styles/narramancy.css` — basic styling

## Phase 2: Import System
**Status:** complete
- [x] `scripts/importer.js` — JSON import, folder + RollTable creation, settings storage
- [x] `templates/import-dialog.hbs` — file upload dialog
- [x] Wire import button into settings/header buttons

## Phase 3: Trigger Engine
**Status:** complete
- [x] `scripts/trigger-engine.js` — hook listeners, token matching, table rolling, whisper
- [x] `templates/creature-list.hbs` — manage imported creatures UI
- [x] Wire creature management into module settings

## Phase 4: Python Exporter + Generator Improvements
**Status:** complete
- [x] `src/narramancy/exporters/narramancy_module.py` — new combined JSON exporter
- [x] Update `models.py` — per-save abilities (6 saves), per-skill generation from proficient skills
- [x] Update `generator.py` — retry/top-up logic, pronoun guidance in prompts
- [x] Update `exporters/__init__.py` — register new exporter
- [x] Update `__main__.py` — add `--export narramancy` option
- [x] Update `__init__.py` — export new function
- [x] Test end-to-end: generate creature → export narramancy JSON → validate format

## Phase 5: Integration Testing
**Status:** complete (code-side)
- [x] Verify JSON format via mock export (validated - format correct)
- [x] Verify all dnd5e 3.x hooks are correct (rollSavingThrow, rollSkill, rollAttack, etc.)
- [ ] Deploy to Forge VTT and test live (requires Todd)

---

## Key Decisions
- Pre-generated tables only (no live API gen) — instant response beats infinite variety
- Live gen via Haiku parked as future idea if latency improves
- Combined JSON format: creature metadata + tables + triggers in one file
- Foundry table names: `{CreatureName} - {Ability} - {Category}`
- Wildcard token matching: `*Drow Elite Warrior*` catches adjective-prefixed tokens
- Whisper options: gm, owner, gm+owner, public

## Combined JSON Format
```json
{
  "formatVersion": 1,
  "creature": {
    "name": "Drow Elite Warrior",
    "tokenPattern": "*Drow Elite Warrior*",
    "cr": "5",
    "type": "humanoid",
    "pronouns": "they"
  },
  "whisper": "gm",
  "tables": [
    {
      "ability": "Shortsword",
      "category": "attempts",
      "description": "Flavor text for attempting a Shortsword attack",
      "entries": ["The drow's blade flashes...", "..."]
    }
  ],
  "triggers": [
    {
      "hookType": "attackRoll",
      "itemName": "Shortsword",
      "table": "Shortsword|attempts"
    }
  ]
}
```

## Hook → Trigger Mapping
| Game Event | dnd5e Hook | hookType | Match Field |
|---|---|---|---|
| Attack roll | dnd5e.rollAttack | attackRoll | item.name |
| Damage roll | dnd5e.rollDamage | damageRoll | item.name |
| Saving throw | dnd5e.rollAbilitySave | savingThrow | abilityId |
| Skill check | dnd5e.rollSkill | skill | skillId |
| Death save | dnd5e.rollDeathSave | deathSave | (any) |
| Item/feature use | dnd5e.useItem | itemUse | item.name |
| Initiative | combatant added to combat | initiative | (any) |
