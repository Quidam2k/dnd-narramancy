# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

**D&D Flavor Forge** generates vivid narration text for D&D abilities. It creates multiple variations (attempt/success/failure) suitable for VTT rollable tables.

## Development Commands

```bash
# Run tests (from project root)
python tests/test_flavor_generation.py

# Quick import check
python -c "from flavor_forge import FlavorTextGenerator; print('OK')"

# Generate flavor text (once CLI is built in Phase 2+)
# python -m flavor_forge generate ...
```

Note: Run from project root. Tests add `src/` to sys.path automatically.

## Project Structure

```
dnd-flavor-forge/
├── src/flavor_forge/          # Main package
│   ├── __init__.py            # Public exports
│   ├── generator.py           # FlavorTextGenerator (core AI generation)
│   ├── models.py              # FlavorTextRequest, FlavorTextResult, AbilityData
│   ├── parser.py              # CharacterAbilityParser
│   ├── config.py              # ConfigManager (env vars + optional YAML)
│   ├── cost_tracker.py        # API cost logging (stub)
│   ├── profiler.py            # Character profiling stubs + context_blob interface
│   └── exporters/             # VTT export (Phase 4)
├── archive/typescript/        # Original Firebase Functions version (reference only)
├── tests/
│   └── test_flavor_generation.py
├── docs/                      # Design docs and extraction notes
├── config.yaml.example        # Config template
└── requirements.txt
```

## Architecture

```
FlavorTextRequest → FlavorTextGenerator → AI Provider → FlavorTextResult
                         ↓                    ↑
                    context_blob         Gemini / Claude / Ollama (Phase 3)
```

## Key Concepts

### context_blob
The `FlavorTextRequest.context_blob` field accepts free-text context that gets appended
to the AI prompt. This serves both:
- **Per-creature seasoning**: "This skeleton was once a noble knight..."
- **Future PC context**: Automated summaries from the summarizer project

### Request/Result
```python
FlavorTextRequest(
    character_name="Thorin", character_race="Dwarf", character_class="Fighter",
    character_level=5, ability_name="Action Surge", ability_type="feature",
    style="dramatic", variations=5, context_blob="optional seasoning..."
)

FlavorTextResult(
    attempts=["...", ...], successes=["...", ...], failures=["...", ...],
    metadata={...}
)
```

## AI Providers

- **Gemini** (`gemini-2.0-flash-exp`) — Default, cost-effective
- **Claude** — Higher quality, more expensive
- **Ollama** — Local models, free (Phase 3)

API keys via env vars: `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`

## Output Guidelines

Generated text should be:
- Exactly 1 sentence, max 20 words
- Vivid but concise, with one key sensory detail
- Matched to character's race/class/level
- Appropriate for ability type
