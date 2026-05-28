# Narramancy Quick Test Guide

## 1. Launch the Web UI

```bash
cd /path/to/dnd-narramancy
PYTHONPATH=src python -m narramancy webui
```

Opens at **http://localhost:7870**

## 2. Parse a Creature

- **Paste Text**: Copy a stat block from anywhere, paste it in
- **Open5e Search**: Type a creature name (e.g. `goblin`, `adult-red-dragon`)
- **Upload File**: Upload a `.json` (Foundry actor), `.html` (saved D&D Beyond page), or `.pdf`
  - For PDFs, set the page number if the stat block isn't on page 1

Click **Parse** — you'll see the creature summary on the right.

## 3. Generate Flavor Text

- Pick a **Style** (dramatic, comedic, gritty, heroic)
- Set **Variations** (how many lines per category — 5 is default)
- Pick a **Provider** (auto picks first available; needs at least one configured in `config.yaml`)
- Check **Include generic actions** if you want saves/skills/initiative/death saves too

Click **Generate** — wait for it to process each ability. Results appear on the right.

## 4. Export to TokenSays

- Under **Export**, set Format to **tokensays** (or **all** for both rollable tables + TokenSays)
- Check **Whisper to GM** if you want sayings whispered (recommended)
- Click **Export & Download**
- Download the `<creature>-sayings.json` file

## 5. Import into Foundry VTT / TokenSays

1. Open Foundry VTT
2. Go to **TokenSays** module settings
3. Use TokenSays' import feature to load the `.json` file
4. The sayings are keyed by actor name + ability name — they'll auto-match when that creature uses those abilities

## CLI Alternative

```bash
# Parse + generate + export in one shot
PYTHONPATH=src python -m narramancy generate --open5e goblin --style dramatic --variations 5 --export tokensays --output-dir ./output/

# Or from a saved HTML page
PYTHONPATH=src python -m narramancy generate goblin-page.html --export all --output-dir ./output/
```

## Config Required

You need a `config.yaml` with at least one provider. Example:

```yaml
providers:
  gemini:
    api_key: "your-key-here"
    model: "gemini-2.0-flash"
```

Copy `config.yaml.example` and fill in your keys.
