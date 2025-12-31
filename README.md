# D&D Flavor Forge

Generate vivid, immersive narration text for D&D abilities, spells, and actions. Creates rollable tables with multiple variations for attempt/success/failure scenarios.

## Overview

FlavorForge transforms dry ability descriptions into dramatic narration:

**Input:**
```
Longsword Attack - Melee Weapon Attack, 1d8+4 slashing damage
```

**Output (rollable table):**
- **Attempt**: "Thorin raises his ancestral blade, firelight dancing along its edge..."
- **Success**: "Steel bites deep as the dwarf's strike finds its mark with a satisfying crunch..."
- **Failure**: "The longsword whistles through empty air as his foe sidesteps at the last moment..."

## Features

- **Multiple variations**: Generate 5-50 unique descriptions per ability
- **Three outcome types**: Attempt, Success, Failure (plus Critical variants)
- **Style options**: Dramatic, Comedic, Gritty, Heroic
- **VTT Export**: Output as Foundry VTT rollable tables
- **Character integration**: Optional personality-aware generation via `dnd-character-profiler`

## Project Structure

```
dnd-flavor-forge/
├── src/
│   ├── python/
│   │   └── flavor_text_generator.py    # Main implementation (newer)
│   └── typescript/
│       └── flavorText.ts               # Original TypeScript version
├── docs/
│   └── [Integration plans and naming docs]
├── tests/
│   └── test_flavor_generation.py
└── README.md
```

## Quick Start (Python)

```python
from flavor_text_generator import FlavorTextGenerator, FlavorTextRequest

generator = FlavorTextGenerator(config)

request = FlavorTextRequest(
    character_name="Thorin Ironforge",
    character_race="Dwarf",
    character_class="Fighter",
    character_level=5,
    ability_name="Longsword Attack",
    ability_type="attack",
    style="dramatic",
    variations=5
)

result = await generator.generate_flavor_text(request)
# result.attempts, result.successes, result.failures
```

## Dependencies

### Python Version
- Python 3.8+
- `google-generativeai` (for Gemini) or `anthropic` (for Claude)
- Optional: `dnd-character-profiler` for personality-enhanced generation

### TypeScript Version
- Node.js 18+
- Firebase Functions (original deployment target)

## Integration Points

- **dnd-character-profiler**: Enhanced generation using character personality profiles
- **dnd-vtt-bridge**: Export as Foundry VTT rollable tables
- **dnd-platform**: Unified UI for flavor text management

## API Keys Required

- Google Gemini API key (preferred), OR
- Anthropic Claude API key

## Status

- Python version: More recent, includes character profiling integration
- TypeScript version: Original implementation, Firebase-focused

## License

Private project - not for distribution.
