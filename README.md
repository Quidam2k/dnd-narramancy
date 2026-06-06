# D&D Narramancy

Generate vivid narration text for D&D creatures and use it at the table — whether you run Foundry VTT, TaleSpire, or theater of the mind. Feed in a stat block, pick an AI provider (local or cloud), and get back rollable tables full of evocative one-liners for every ability, attack, and reaction.

**Input:** A creature stat block (pasted text, Open5e search, PDF, HTML, or Foundry JSON)

**Output:** Dozens of short, punchy narration lines per ability — organized into rollable tables with attempt/success/failure variations, plus optional critical hits, fumbles, killing blows, bloodied triggers, and more.

> *"A quick lunge, weight shifting forward — steel leads."*
> *"It drops low, jaws snapping shut like a sprung trap."*
> *"The blade finds only air — a half-step too slow."*

**[▶ Try the live demo](https://quidam2k.github.io/dnd-narramancy/web/roller.html?load=demo/gimbal-starwhisper.json)** — the Flavor Roller loaded with Gimbal Starwhisper, a level-5 Lotusden Halfling druid (107 abilities, 416 rollable tables).

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/Quidam2k/dnd-narramancy.git
cd dnd-narramancy

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Set up a provider (see Provider Setup below)
#    Easiest: install LM Studio and load a model — no API key needed

# 4. Generate flavor text
PYTHONPATH=src python -m narramancy generate --open5e goblin \
  --provider lmstudio --with-crits --generic --variations 20 \
  --export narramancy --output-dir output

# 5. Use the output
#    - Foundry VTT: import the JSON via the Narramancy module
#    - Other VTTs: open web/roller.html in a browser and load the JSON
```

## Provider Setup

You need at least one AI provider. Local providers are free and work offline; cloud providers need an API key.

### LM Studio (free, local — recommended for bulk generation)

1. Download [LM Studio](https://lmstudio.ai/) and install it
2. Download a model — `meta-llama-3.1-8b-instruct` works well
3. Load the model and start the local server (it runs on `localhost:1234`)
4. That's it — no environment variables needed

```bash
PYTHONPATH=src python -m narramancy generate --open5e goblin --provider lmstudio
```

### Ollama (free, local)

1. Install [Ollama](https://ollama.com/)
2. Pull a model: `ollama pull llama3.1`
3. Ollama runs on `localhost:11434` by default

```bash
# Optional: set a custom URL if Ollama isn't on the default port
export OLLAMA_BASE_URL=http://localhost:11434

PYTHONPATH=src python -m narramancy generate --open5e goblin --provider ollama
```

### Gemini (free tier available — recommended if you can't run local)

1. Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey)
2. Set the environment variable:

```bash
export GEMINI_API_KEY=your-key-here

PYTHONPATH=src python -m narramancy generate --open5e goblin --provider gemini
```

### Groq (free tier — fast cloud inference)

1. Get a free API key from [Groq Console](https://console.groq.com/)
2. Set the environment variable:

```bash
export GROQ_API_KEY=your-key-here

PYTHONPATH=src python -m narramancy generate --open5e goblin --provider groq
```

### OpenRouter (free models available — model marketplace)

1. Get an API key from [OpenRouter](https://openrouter.ai/keys)
2. Set the environment variable:

```bash
export OPENROUTER_API_KEY=your-key-here

PYTHONPATH=src python -m narramancy generate --open5e goblin --provider openrouter
```

### Together AI (free tier — open-source models)

1. Get a free API key from [Together](https://api.together.xyz/)
2. Set the environment variable:

```bash
export TOGETHER_API_KEY=your-key-here

PYTHONPATH=src python -m narramancy generate --open5e goblin --provider together
```

### Claude (paid, highest quality)

1. Get an API key from [Anthropic Console](https://console.anthropic.com/)
2. Set the environment variable:

```bash
export ANTHROPIC_API_KEY=your-key-here

PYTHONPATH=src python -m narramancy generate --open5e goblin --provider claude
```

## Foundry VTT Module

Narramancy includes a Foundry VTT module that automatically whispers narration to the GM when creatures use abilities in combat.

### Install

1. Download or build the module zip
2. Extract to your Foundry data folder: `Data/modules/narramancy/`
3. Enable the module in your world's module settings
4. Import a narramancy JSON file via the module's import dialog

### Features

- Whispers flavor text to GM when creatures attack, cast spells, use features, etc.
- Conditional triggers: different text for critical hits, fumbles, near-misses, and barely-hits
- Killing blow narration when an attack drops a target to 0 HP
- Bloodied trigger when a creature crosses the half-HP threshold
- Death narration when a creature dies
- No-repeat tracking — cycles through all entries before repeating

## Flavor Roller (non-Foundry users)

If you don't use Foundry VTT, you can use the **Flavor Roller** — a standalone HTML page that loads a narramancy JSON file and gives you clickable buttons for every ability.

**[Live demo with Gimbal Starwhisper](https://quidam2k.github.io/dnd-narramancy/web/roller.html?load=demo/gimbal-starwhisper.json)** — a level-5 Lotusden Halfling druid.

- Open `web/roller.html` in any browser (or use the [hosted version](https://quidam2k.github.io/dnd-narramancy/web/roller.html))
- Load a generated JSON file — or auto-load one via `?load=<url>`
- Click ability buttons to get random narration lines
- Works great on mobile — tap a button during a game session
- **Detail levels**: the Minimal / Standard / Full selector controls how many post-roll buttons appear. Minimal (the default) shows attempt rolls plus crits, fumbles, and killing blows; Standard adds Hit/Miss narration; Full adds fine-grained outcomes (barely hit, barely miss, dodge, armor deflection)

## Features

- **Multiple input formats**: Open5e API, pasted text, PDF, HTML (D&D Beyond), Foundry actor JSON
- **4 styles**: dramatic, comedic, gritty, heroic
- **Conditional triggers**: critical hits, fumbles, barely-hit, barely-miss, dodge, armor deflection
- **Killing blow**: special narration for the final strike that drops a target
- **Bloodied & death**: triggered when a creature crosses half HP or drops to 0
- **Generic actions**: saves (all 6), skill checks (proficient skills only), initiative, death saves
- **Batch generation**: process a folder of creature files at once
- **Context blobs**: add flavor guidance like "swamp-dwelling goblins who worship a hag" to steer the AI
- **Provider comparison**: generate the same creature with multiple providers side-by-side
- **Multiple export formats**: Foundry rollable tables, Narramancy module JSON, TokenSays

## CLI Reference

Narramancy has four subcommands: `parse`, `generate`, `export`, and `webui`.

All commands should be run from the project root with `PYTHONPATH=src`.

### `parse` — Extract abilities from a stat block

```bash
# Fetch from Open5e and display parsed abilities
PYTHONPATH=src python -m narramancy parse --open5e goblin

# Output as JSON (for piping to generate)
PYTHONPATH=src python -m narramancy parse --open5e goblin --json

# Parse a local text file
PYTHONPATH=src python -m narramancy parse goblin.txt

# Parse a PDF stat block (specify page number)
PYTHONPATH=src python -m narramancy parse monster-manual.pdf --page 5

# Add context for flavor generation
PYTHONPATH=src python -m narramancy parse --open5e goblin --context "Swamp-dwelling goblins who worship a hag"
```

### `generate` — Generate flavor text

```bash
# Basic generation (uses first available provider)
PYTHONPATH=src python -m narramancy generate --open5e goblin

# Choose provider and style
PYTHONPATH=src python -m narramancy generate --open5e goblin --provider lmstudio --style gritty

# Full generation with all the bells and whistles
PYTHONPATH=src python -m narramancy generate --open5e goblin \
  --provider lmstudio --style dramatic --variations 20 \
  --with-crits --crit-count 10 --generic \
  --export narramancy --output-dir ./output/

# Batch process a folder of creature files
PYTHONPATH=src python -m narramancy generate --batch ./monsters/ \
  --export narramancy --output-dir ./output/

# Compare providers side by side
PYTHONPATH=src python -m narramancy generate --open5e goblin \
  --providers gemini,lmstudio --compare

# List configured providers
PYTHONPATH=src python -m narramancy generate --list-providers
```

### `export` — Convert saved results to VTT format

```bash
# Export to Foundry VTT rollable tables
PYTHONPATH=src python -m narramancy export results.json --format foundry

# Export to Narramancy module format
PYTHONPATH=src python -m narramancy export results.json --format narramancy

# Export all formats
PYTHONPATH=src python -m narramancy export results.json --format all
```

### `webui` — Launch the web interface

```bash
PYTHONPATH=src python -m narramancy webui
# Opens at http://localhost:7870
```

## Providers

| Provider | CLI Name | Env Var | Default Model | Cost |
|----------|----------|---------|---------------|------|
| LM Studio | `lmstudio` | — | whatever you load | Free (local) |
| Ollama | `ollama` | `OLLAMA_BASE_URL` | `llama3.2` | Free (local) |
| Gemini | `gemini` | `GEMINI_API_KEY` | `gemini-2.0-flash-exp` | Free tier available |
| Groq | `groq` | `GROQ_API_KEY` | `llama-3.1-8b-instant` | Free tier |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | `meta-llama/llama-3.1-8b-instruct:free` | Free models available |
| Together | `together` | `TOGETHER_API_KEY` | `Meta-Llama-3.1-8B-Instruct-Turbo` | Free tier |
| Claude | `claude` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-5-20250929` | Paid |

## Configuration

You can set provider credentials via environment variables (recommended) or in a `config.yaml` file. Copy `config.yaml.example` to `config.yaml` to get started.

| Env Var | Purpose |
|---------|---------|
| `GEMINI_API_KEY` | Google Gemini API key |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `OLLAMA_BASE_URL` | Ollama server URL (default: `http://localhost:11434`) |
| `GROQ_API_KEY` | Groq API key |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `TOGETHER_API_KEY` | Together AI API key |

## Project Structure

```
dnd-narramancy/
├── src/narramancy/          # Main package
│   ├── __main__.py            # CLI entry point (parse/generate/export/webui)
│   ├── generator.py           # Core AI generation engine
│   ├── models.py              # Data structures (ParsedCreature, FlavorTextResult)
│   ├── config.py              # Configuration management
│   ├── providers.py           # AI provider abstraction
│   ├── cost_tracker.py        # API cost logging
│   ├── profiler.py            # Character profiling
│   ├── parsers/               # Stat block parsing
│   │   ├── open5e.py          # Open5e API fetcher
│   │   ├── text_block.py      # Raw text stat block parser
│   │   ├── foundry.py         # Foundry actor JSON parser
│   │   ├── html_block.py      # HTML page parser
│   │   └── pdf_block.py       # PDF parser
│   └── exporters/             # VTT export formats
│       ├── rollable_table.py  # Foundry rollable tables (Roll Table Importer)
│       ├── narramancy_module.py  # Narramancy module JSON
│       └── token_says.py      # TokenSays format
├── foundry-module/            # Foundry VTT module source
│   └── narramancy/
│       ├── module.json
│       ├── scripts/           # trigger-engine.js, import, settings
│       ├── templates/         # Handlebars templates
│       ├── styles/            # CSS
│       └── lang/              # Localization
├── web/
│   └── roller.html            # Flavor Roller (standalone, no dependencies)
├── tests/                     # Test suite
├── config.yaml.example        # Configuration template
└── requirements.txt           # Python dependencies
```

## License

MIT License — see [LICENSE](LICENSE) for details.
