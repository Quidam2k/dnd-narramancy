# D&D Flavor Forge

Generate vivid, immersive narration text for D&D monster abilities. Creates rollable tables with multiple variations for attempt/success/failure scenarios.

**Input:**
```
Longsword Attack - Melee Weapon Attack, 1d8+4 slashing damage
```

**Output (rollable table):**
- **Attempt**: "Thorin raises his ancestral blade, firelight dancing along its edge..."
- **Success**: "Steel bites deep as the dwarf's strike finds its mark with a satisfying crunch..."
- **Failure**: "The longsword whistles through empty air as his foe sidesteps at the last moment..."

## Quick Start

```bash
pip install google-generativeai   # Gemini (default, free tier)
# or: pip install anthropic       # Claude (higher quality)

export GEMINI_API_KEY=your-key
# or: export ANTHROPIC_API_KEY=your-key

python -m flavor_forge generate --open5e goblin --style dramatic
```

## CLI Reference

Flavor Forge has three subcommands: `parse`, `generate`, and `export`.

### `parse` — Extract abilities from a stat block

```bash
# Fetch from Open5e and display parsed abilities
python -m flavor_forge parse --open5e goblin

# Output as JSON (for piping)
python -m flavor_forge parse --open5e goblin --json

# Parse a local text file
python -m flavor_forge parse goblin.txt

# Search by name (fuzzy match)
python -m flavor_forge parse --open5e "adult red dragon"

# Add context for flavor generation
python -m flavor_forge parse --open5e goblin --context "Swamp-dwelling goblins who worship a hag"
```

### `generate` — Generate flavor text

```bash
# Basic generation (Gemini default)
python -m flavor_forge generate --open5e goblin

# Choose provider and style
python -m flavor_forge generate --open5e goblin --provider claude --style gritty

# Output as JSON
python -m flavor_forge generate --open5e goblin --json

# Generate + export to Foundry VTT in one step
python -m flavor_forge generate --open5e goblin --export foundry --output-dir ./output/

# Export all formats at once
python -m flavor_forge generate --open5e goblin --export all --output-dir ./output/

# Batch process a folder of creature files
python -m flavor_forge generate --batch ./monsters/ --export all --output-dir ./output/

# Pipe from parse (useful for adding context mid-pipeline)
python -m flavor_forge parse --open5e goblin --json | python -m flavor_forge generate --stdin --export foundry

# Compare providers side by side
python -m flavor_forge generate --open5e goblin --providers gemini,claude --compare

# List configured providers
python -m flavor_forge generate --list-providers
```

### `export` — Convert saved results to VTT format

```bash
# Export to Foundry VTT rollable tables
python -m flavor_forge export goblin.json --format foundry

# Export to TokenSays format
python -m flavor_forge export goblin.json --format tokensays

# Export both formats
python -m flavor_forge export goblin.json --format all

# Custom output path
python -m flavor_forge export goblin.json --format foundry --output my-tables.json
```

## Providers

| Provider | Env Var | Default Model | Notes |
|----------|---------|---------------|-------|
| Gemini | `GEMINI_API_KEY` | `gemini-2.0-flash-exp` | Default. Free tier available. |
| Claude | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20250929` | Higher quality, paid. |
| Ollama | `OLLAMA_BASE_URL` | `llama3.2` @ `localhost:11434` | Local, free. Requires Ollama running. |

## Foundry VTT Integration

After generating with `--export foundry`:

1. **Rollable Tables**: Import the `-tables.json` file via Foundry's RollTable import. Each ability gets an Attempt/Success/Failure table.
2. **TokenSays**: Import the `-sayings.json` file into the TokenSays module for automatic narration on token actions.

## Project Structure

```
src/flavor_forge/
  __main__.py        # CLI entry point
  generator.py       # Core AI generation
  models.py          # Data structures
  config.py          # Configuration management
  providers.py       # AI provider abstraction (Gemini, Claude, Ollama)
  cost_tracker.py    # API cost logging
  profiler.py        # Character profiling
  parsers/           # Stat block parsing
    open5e.py        # Open5e API fetcher
    text_block.py    # Raw text stat block parser
    foundry.py       # Foundry JSON parser
  exporters/         # VTT export
    rollable_table.py  # Foundry rollable tables
    token_says.py      # TokenSays format
tests/               # Test suite
config.yaml.example  # Configuration template
```

## Configuration

Copy `config.yaml.example` to `config.yaml`, or use environment variables:

| Env Var | Purpose |
|---------|---------|
| `GEMINI_API_KEY` | Google Gemini API key |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `OLLAMA_BASE_URL` | Ollama server URL (default: `http://localhost:11434`) |
| `FLAVOR_FORGE_AI_GENERATION_MODEL` | Override default model for any provider |

## License

Private project - not for distribution.
