# Plan: Conditional Triggers & Roll-Aware Flavor

## Overview
Enhance the Narramancy module to produce context-sensitive flavor based on roll results,
defensive effects, and creature state.

---

## Phase 1: Research dnd5e Hook Payloads [COMPLETE]
Researched hook signatures, payloads, and feasibility. All implemented in trigger-engine.js.

## Phase 2: Design Decisions [COMPLETE]
Defined table categories: attempts, successes, failures, crits, fumbles, barely_hits, barely_misses, miss_dodge, miss_armor, bloodied, death, killing_blow.

## Phase 3: Python Generation — New Table Categories [COMPLETE]
All categories implemented in generator.py with ability-type-aware prompts, examples, and sensory categories.

## Phase 4: JS Module — Roll-Aware Trigger Engine [COMPLETE]
- Roll-aware attack classification (nat 1/20, margin-based barely hits/misses, dodge vs armor)
- Bloodied/death/killing blow detection via updateActor hook
- No-repeat tracking per combat
- Whisper context headers (actor + ability + category) added 2026-03-13

## Phase 5: Integration Test [PARTIALLY COMPLETE]
- Generated full Gimbal output (143/143 abilities complete) with Qwen 2.5 14B
- Web UI tested and fixed (scroll, Success/Fail labels)
- Foundry module whisper headers added but not yet tested in Foundry
- Foundry PC parser tested with Gimbal's actor export (42 abilities, proper race/class/level)

---

## Remaining work
- Test updated Foundry module in Foundry VTT (whisper headers, import flow)
- Todd considering simplifying to single pool instead of attempt/success/failure split
- Todd mentioned potentially testing with Foundry token export
