# Flavor Text Generation Guide

Reference specification for generating rollable flavor text tables for the Foundry VTT narration mod.

---

## Entry Format

Each table entry is a single sentence, **8–12 words**, written with natural internal phrase boundaries so a DM can use the whole sentence or grab a fragment.

**Good example:**
> She drops low, blade singing upward — a flash of teeth.

A DM can use this whole, or grab "drops low," "blade singing upward," or "flash of teeth" independently.

**Bad example:**
> The fighter swings their sword at the enemy and hits them hard.

Generic, no grabable phrases, tells rather than evokes.

### Writing Principles

- **Evoke, don't narrate.** Sensory fragments over play-by-play.
- **Stay character-agnostic.** Use "she/he/they" or imperative mood. No names, no class references. The mod maps entries to specific actors at runtime.
- **Stay target-agnostic.** Don't reference what's being hit — the system handles pairing.
- **Vary sentence structure.** Mix fragments, dashes, commas, and full clauses.
- **Avoid fantasy clichés.** No "with a mighty blow," no "steel flashes in the torchlight" (unless you can make it feel fresh).
- **Keep mechanical language out.** No HP, AC, damage dice. Pure fiction.

---

## Generation Categories

These categories are **scaffolding for generation, not runtime structure.** The DM never sees or picks categories. They exist to ensure each table has varied sensory coverage.

When generating a table of N entries, distribute roughly evenly across categories. Not every category needs representation in every table — use what fits the event type.

### 1. Kinesthetic
Body mechanics, muscle, weight, momentum, physical effort.
> He pivots on his back foot, arm whipping forward in a single motion.

### 2. Auditory
Sounds of the action — impact, breath, environment, vocalization.
> The mace connects with a wet, resonant crack that echoes off stone.

### 3. Visual / Cinematic
Light, color, spatial framing, camera-angle descriptions.
> Firelight catches the arc of steel at the apex of the swing.

### 4. Emotional / Expression
Face, eyes, attitude, intent, psychological state.
> Cold focus settles behind her eyes as the blade finds its mark.

### 5. Tactile / Impact
What the action physically *feels* like — vibration, resistance, texture.
> The hit shudders up through the shaft and into her wrists.

### 6. Environmental
Interaction with surroundings — terrain, weather, surfaces, debris.
> His boot skids on wet stone as he lunges, catching himself mid-thrust.

### 7. Tempo / Rhythm
Speed, pacing, timing, the cadence of the action.
> Two quick feints, then one deliberate, crushing overhead blow.

### 8. Tactical / Spatial
Positioning, geometry, relative placement, exploitation of openings.
> She sidesteps inside his guard, too close now for him to parry.

---

## Event Types

These are the categories of game events that should have associated flavor tables.

### Activated Abilities & Actions (Primary)

These are the core use case — things an actor actively does where dice are rolled.

| Event Type | Variations | Notes |
|---|---|---|
| **Weapon attacks** | Attempt, Success, Failure, Critical, Killing Blow | Per weapon type (short sword, longbow, etc.) |
| **Spell casting** | Attempt, Success, Failure, Critical, Killing Blow | Per spell or spell school. Critical only if attack roll. Killing Blow only if damage-dealing. |
| **Skill checks** | Attempt, Success, Failure | Per skill (Persuasion, Athletics, Stealth, etc.) |
| **Ability checks** | Attempt, Success, Failure | Raw ability checks without skill proficiency |
| **Saving throws** | Attempt, Success, Failure | Per ability score |
| **Class features** | Activation, Killing Blow (if damage-dealing) | Rage, Wild Shape, Smite, Sneak Attack, Bardic Inspiration, Channel Divinity, Metamagic, Action Surge, Second Wind, etc. |
| **Racial/species features** | Activation, Killing Blow (if damage-dealing) | Breath weapon, Fey Step, Relentless Endurance, etc. |
| **Item use** | Activation | Potions, scrolls, magic item abilities |

**Variation definitions:**
- **Attempt:** The moment of trying, before outcome is known. Useful for narrating the action itself.
- **Success:** The action succeeds / hits / lands.
- **Failure:** The action fails / misses / fizzles.
- **Critical:** Exceptional success (attack rolls only). More dramatic, more visceral.
- **Killing Blow:** The finishing move — "How do you want to do this?" Applies to **any damage-dealing ability**, whether it has an attack roll or not. A Fireball can't crit, but it can absolutely be the thing that kills someone. These entries should be cinematic conclusions: decisive, final, satisfying. Distinct from crits in tone — crits are mid-fight exclamation marks, killing blows are endings.

### Passive / Trait Descriptions

Flavor text for features that aren't "activated" but might need description during play.

| Event Type | Notes |
|---|---|
| **Passive traits** | Darkvision, Pack Tactics, Fey Ancestry, Sunlight Sensitivity, etc. |
| **Resistances / Immunities** | "The fire washes over her scales and she barely flinches." |
| **Senses** | Blindsight, Tremorsense, etc. — what does it look like when they use it? |

These don't have success/failure variations. They're single-table: "describe this trait being relevant right now."

**Note:** A trait can have both a passive description table AND generate contextual riders (see below). The passive table is for when a DM wants to describe the trait on its own ("what does Darkvision look like?"). The rider fires automatically when the trait mechanically affects an event outcome. Different tables, different purpose, same trait.

### Contextual Rider Events

Flavor text that fires **alongside** another event when the system detects a relevant trait is in play. These aren't standalone events — they're appended to the primary event's whisper.

| Rider Type | Trigger Condition | Example |
|---|---|---|
| **Damage Resistance** | Damage of a matching type is halved | "The flames curl around her but find no purchase — her skin barely reddens." |
| **Damage Immunity** | Damage of a matching type is negated | "The lightning arcs across his chest and grounds out harmlessly, like water off stone." |
| **Condition Immunity** | A condition the target is immune to would have been applied (e.g., sleep on an elf) | "The magic tugs at her mind but slides away — her eyes never even flutter." |
| **Save Advantage** | A save succeeds where advantage from a trait contributed (e.g., Fey Ancestry turned a failed charm save into a success, Brave overcame a fear effect, Dwarven Resilience shrugged off poison) | "Something tries to take hold behind his eyes, but the old stubbornness pushes back." |
| **Damage Vulnerability** | Damage of a matching type is doubled | "The radiant light hits the shadow and it *screams* — the wound tears wider than it should." |

**Writing guidance for riders:**
- These should be **short** (6–10 words) since they accompany a primary event description.
- Focus on the *negation* or *amplification* — what it looks like when something expected doesn't happen, or hits harder than it should.
- Don't describe the attack itself — the primary event handles that. Describe the moment of resistance/immunity/vulnerability specifically.
- These are great candidates for the **Tactile/Impact** and **Visual/Cinematic** categories.

**Other traits that could generate riders** (non-exhaustive):
- Evasion (save-based damage avoidance)
- Uncanny Dodge (reaction-based damage reduction)
- Shield spell / Absorb Elements
- Rage damage reduction
- Heavy Armor Master
- Relentless Endurance / Undead Fortitude / similar "refuse to drop" effects
- Any feature that modifies incoming damage or save outcomes

### Status Events

Events triggered by game state changes rather than active choices.

| Event Type | Applies To | Notes |
|---|---|---|
| **Bloodied (half HP)** | PCs and Monsters | High-value narration moment. Describe visible deterioration. |
| **Death** | Monsters | Creature-specific death flavor — how *this creature* falls. Complements the attacker's Killing Blow text (which is weapon/spell-specific). A zombie crumbles differently than a dragon. |
| **Going unconscious** | PCs only | Dramatic PC moment — the fall, the collapse. |
| **Death saves** | PCs only | The tension of clinging to life. Success and failure variations. |
| **Stabilized** | PCs only | Pulled back from the edge. |
| **Revived** | PCs only | Coming back — gasping, confused, grateful, angry. |

### Future Considerations (Parked)

These are potentially valuable but not priority for initial implementation:

- **Short/long rest flavor** — camp scenes, wound-tending, meditation
- **Ongoing condition flavor** — what does round 3 of Frightened look like?
- **Travel/exploration moments** — dungeon atmosphere, overland journey beats
- **Receiving Bardic Inspiration** — what it feels like to be inspired

---

## Table Size Recommendations

| Event Type | Recommended Entries |
|---|---|
| Common weapon attacks | 20–30 per variation (including killing blow) |
| Common spells | 15–20 per variation; damage spells also get killing blow |
| Skill checks | 15–20 per skill per variation |
| Class features | 10–15 per feature; damage features also get killing blow |
| Passive traits | 8–12 per trait |
| Contextual riders | 8–12 per trait/feature |
| Bloodied | 15–20 |
| Death (monster) | 15–20 |
| PC unconscious | 10–15 |
| Death saves | 8–12 per variation |

These numbers balance variety (low repeat rate) against generation/curation effort.

---

## Generation Prompt Strategy

When using an LLM to populate tables, structure the prompt as follows:

1. **Specify the event type and variation** (e.g., "short sword attack — success")
2. **Specify the category distribution** (e.g., "Generate 20 entries: 3 kinesthetic, 3 auditory, 3 visual, 3 emotional, 2 tactile, 2 environmental, 2 tempo, 2 tactical")
3. **Provide 2–3 examples** that demonstrate the format and quality bar
4. **Include the writing principles** from this document
5. **Request the output in a structured format** (e.g., JSON array or one entry per line) for easy import

### Example Generation Prompt

```
Generate 20 flavor text entries for: SHORT SWORD ATTACK — SUCCESS

Each entry should be 8–12 words, written as a single evocative sentence with natural phrase boundaries a DM can fragment.

Distribute across these sensory categories:
- 3 Kinesthetic (body mechanics, movement)
- 3 Auditory (sounds)
- 3 Visual/Cinematic (light, framing)
- 3 Emotional/Expression (face, intent)
- 2 Tactile/Impact (physical feeling)
- 2 Environmental (interaction with surroundings)
- 2 Tempo/Rhythm (speed, pacing)
- 2 Tactical/Spatial (positioning, geometry)

Examples of the quality and format expected:
- "A quick thrust under the ribs — she's already stepping back."
- "Steel whispers through leather, and something warm follows."
- "He grins, almost gentle, as the point slides home."

Rules:
- No character names, class references, or target descriptions.
- No game mechanics (HP, AC, damage dice).
- Avoid cliché ("mighty blow", "flashing steel").
- Vary sentence structure across entries.
- Evoke, don't narrate.

Output as a JSON array of strings.
```

---

## Whisper Delivery Format

When the mod whispers flavor text to the DM or player, the display should be:

- **Minimal chrome.** No headers, no category labels, no instructions.
- **Just the text.** One sentence, ready to read or scan.
- **Subtle styling.** Italic or muted color — this is a suggestion, not an alert.

The goal is zero friction: glance, grab a phrase or ignore, keep going.
