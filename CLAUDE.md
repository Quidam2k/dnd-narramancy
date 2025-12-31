# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**D&D Flavor Forge** generates vivid narration text for D&D abilities. It creates multiple variations (attempt/success/failure) suitable for VTT rollable tables.

## Development Commands

```bash
# Run tests
python tests/test_flavor_generation.py

# Run the main generator directly
python src/python/flavor_text_generator.py
```

Note: This module depends on external modules (`cost_tracker`, `characterization_profiler`) that must be available in the Python path. The test file imports from `summarizer.core.flavor_text_generator` and `summarizer.config.settings`, suggesting this is part of a larger project structure.

## Key Files

### Python Implementation (Primary)
- `src/python/flavor_text_generator.py` - Main implementation with:
  - `FlavorTextGenerator` class - Core generation logic
  - `FlavorTextRequest` / `FlavorTextResult` - Data structures
  - `CharacterAbilityParser` - Extracts abilities from character data
  - `VTTExporter` - Export wrapper for VTT formats

### TypeScript Implementation (Reference)
- `src/typescript/flavorText.ts` - Original Firebase Functions version

### Tests
- `tests/test_flavor_generation.py` - Python test suite

## Architecture

```
FlavorTextRequest → FlavorTextGenerator → AI Service → FlavorTextResult
                         ↓
              (optional) CharacterProfile from dnd-character-profiler
```

## Key Concepts

### Request Structure
```python
FlavorTextRequest(
    character_name="Thorin",
    character_race="Dwarf",
    character_class="Fighter",
    character_level=5,
    ability_name="Action Surge",
    ability_type="feature",  # spell|cantrip|action|feature|attack|item
    style="dramatic",        # dramatic|comedic|gritty|heroic
    variations=5
)
```

### Result Structure
```python
FlavorTextResult(
    attempts=["...", "...", ...],    # Trying to use ability
    successes=["...", "...", ...],   # Ability succeeds
    failures=["...", "...", ...],    # Ability fails
    metadata={...}
)
```

## Dependencies

Python 3.8+ with:
- `google-generativeai` - For Gemini API calls
- `anthropic` - For Claude API calls (alternative)

External module imports (from parent project):
- `cost_tracker` - API cost tracking (can be stubbed)
- `characterization_profiler` - Character personality integration (can be mocked)
- `ConfigManager` - API key and settings management

For standalone use, mock these imports or comment them out.

## AI Service Integration

Supports both:
- **Gemini** (`gemini-2.0-flash-exp`) - Default, cost-effective
- **Claude** - Higher quality, more expensive

API keys managed via config manager.

## Output Guidelines

Generated text should be:
- Exactly 1 sentence, max 20 words
- Vivid but concise
- Include one key sensory detail
- Match character's race/class/level
- Appropriate for ability type

## Integration

This is a standalone module. Optional integrations:
- `dnd-character-profiler`: Personality-enhanced prompts
- `dnd-vtt-bridge`: Rollable table export
- `dnd-platform`: Unified management UI
