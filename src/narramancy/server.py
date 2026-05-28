"""FastAPI web server for Narramancy."""

import asyncio
import json
import os
import webbrowser
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Resolve web/app/ directory relative to this file
_PKG_DIR = Path(__file__).resolve().parent
_WEB_APP_DIR = _PKG_DIR.parent.parent / "web" / "app"

app = FastAPI(title="Narramancy")

# Will be set by launch()
_work_dir: Path = Path("./output")

# Lazy-init config
_config = None

# Generation concurrency guard
_generating = False


def _get_config():
    global _config
    if _config is None:
        from .config import ConfigManager
        _config = ConfigManager()
    return _config


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/app")


@app.get("/app", include_in_schema=False)
async def serve_app():
    index = _WEB_APP_DIR / "index.html"
    if not index.exists():
        raise HTTPException(404, "Web UI not found")
    return HTMLResponse(index.read_text(encoding="utf-8"))


@app.get("/api/files")
async def list_files():
    """List JSON files in the working directory."""
    if not _work_dir.exists():
        return []
    files = []
    for f in sorted(_work_dir.iterdir()):
        if f.suffix == ".json" and f.is_file():
            stat = f.stat()
            files.append({
                "name": f.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
    return files


@app.get("/api/files/{filename}")
async def get_file(filename: str):
    """Load and return a JSON file's contents."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    filepath = _work_dir / filename
    if not filepath.exists() or not filepath.suffix == ".json":
        raise HTTPException(404, "File not found")
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Invalid JSON: {e}")
    return data


@app.post("/api/files/{filename}")
async def save_file(filename: str, request: Request):
    """Save JSON data to a file."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    if not filename.endswith(".json"):
        raise HTTPException(400, "Filename must end with .json")
    _work_dir.mkdir(parents=True, exist_ok=True)
    body = await request.json()
    filepath = _work_dir / filename
    filepath.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return {"status": "saved", "name": filename}


# ── Phase 3: Generation & Curation Endpoints ────────────────────


@app.get("/api/providers")
async def list_providers():
    """List available AI providers with their model names."""
    from .providers import get_available_providers, get_provider

    config = _get_config()
    available = get_available_providers(config)
    # LM Studio is always available (localhost, no key needed) like Ollama
    if "lmstudio" not in available:
        available.append("lmstudio")
    result = []
    for name in available:
        try:
            p = get_provider(name, config)
            result.append({"name": name, "model": p.model})
        except ValueError:
            pass
    return result


@app.post("/api/parse")
async def parse_character(request: Request):
    """Parse a Foundry actor JSON and return creature + abilities."""
    from .parsers import parse_stat_block

    body = await request.json()
    try:
        creature = parse_stat_block(json.dumps(body))
    except Exception as e:
        raise HTTPException(400, f"Failed to parse: {e}")

    return _creature_response(creature)


@app.post("/api/parse-pdf")
async def parse_pdf(request: Request):
    """Parse a D&D Beyond PDF upload and return creature + abilities."""
    import tempfile
    from .parsers.pdf_block import parse_pdf_block

    content_type = request.headers.get("content-type", "")
    if "multipart" not in content_type:
        raise HTTPException(400, "Expected multipart/form-data with a PDF file")

    form = await request.form()
    file = form.get("file")
    if file is None:
        raise HTTPException(400, "No file uploaded")

    # Save to temp file and parse
    try:
        body = await file.read()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(body)
            tmp_path = tmp.name

        creature = parse_pdf_block(tmp_path)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse PDF: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return _creature_response(creature)


def _creature_response(creature):
    """Build the standard creature + abilities JSON response."""
    return {
        "creature": {
            "name": creature.name,
            "type": creature.creature_type,
            "cr": creature.challenge_rating,
            "context_blob": creature.context_blob or "",
        },
        "abilities": [
            {
                "name": a.name,
                "ability_type": a.ability_type,
                "description": a.description,
                "damage": a.damage,
                "attack_bonus": a.attack_bonus,
                "save_dc": a.save_dc,
                "save_type": a.save_type,
                "range": a.range,
                "uses": a.uses,
                "recharge": a.recharge,
            }
            for a in creature.abilities
        ],
        "skill_proficiencies": creature.skill_proficiencies,
        "save_proficiencies": creature.save_proficiencies,
    }


@app.post("/api/generate")
async def generate(request: Request):
    """Generate flavor text for abilities via SSE stream."""
    global _generating
    if _generating:
        raise HTTPException(409, "Generation already in progress")

    from .models import GENERIC_ACTIONS, get_save_abilities, get_skill_abilities
    from .generator import FlavorTextGenerator
    from .exporters.narramancy_module import export_narramancy

    body = await request.json()

    async def event_stream():
        global _generating
        _generating = True
        try:
            creature = _rebuild_creature(body)
            config = _get_config()

            provider_name = body.get('provider')
            style = body.get('style', 'dramatic')
            variations = body.get('variations', 20)
            with_crits = body.get('with_crits', True)
            crit_count = body.get('crit_count', 5)
            include_generic = body.get('include_generic', False)

            # Optionally append generic abilities
            if include_generic:
                existing_names = {a.name for a in creature.abilities}
                for sa in get_save_abilities():
                    if sa.name not in existing_names:
                        creature.abilities.append(sa)
                for ska in get_skill_abilities(creature.skill_proficiencies):
                    if ska.name not in existing_names:
                        creature.abilities.append(ska)
                for ga in GENERIC_ACTIONS:
                    if ga.name not in existing_names:
                        creature.abilities.append(ga)

            # Enrich ability descriptions before generation
            from .enricher import enrich_creature
            enrich_creature(creature)

            generator = FlavorTextGenerator(config)
            results = {}
            total = len(creature.abilities)

            for i, ability in enumerate(creature.abilities):
                if await request.is_disconnected():
                    break

                yield _sse("progress", {
                    "ability": ability.name,
                    "index": i + 1,
                    "total": total,
                    "status": "generating",
                })

                try:
                    req = creature.to_flavor_request(
                        ability, style=style, variations=variations,
                    )
                    result = await generator.generate_flavor_text(
                        req, provider_name=provider_name,
                        with_crits=with_crits, crit_count=crit_count,
                    )
                    result.metadata['ability_type'] = ability.ability_type
                    results[ability.name] = result

                    yield _sse("progress", {
                        "ability": ability.name,
                        "index": i + 1,
                        "total": total,
                        "status": "done",
                    })
                except Exception as e:
                    yield _sse("error", {
                        "ability": ability.name,
                        "error": str(e),
                    })

            # Generate bloodied and death if crits enabled
            if with_crits and results and not await request.is_disconnected():
                base_ability = creature.abilities[0]
                base_request = creature.to_flavor_request(
                    base_ability, style=style, variations=crit_count,
                )
                for gen_name, gen_method, gen_type in [
                    ('Bloodied', generator.generate_bloodied, 'bloodied'),
                    ('Death', generator.generate_death, 'death'),
                ]:
                    try:
                        result = await gen_method(
                            base_request, provider_name=provider_name,
                            count=crit_count,
                        )
                        result.metadata['ability_type'] = gen_type
                        results[gen_name] = result
                    except Exception as e:
                        yield _sse("error", {
                            "ability": gen_name,
                            "error": str(e),
                        })

            if results and not await request.is_disconnected():
                ff_data = export_narramancy(creature, results)
                yield _sse("complete", ff_data)

        finally:
            _generating = False

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/reroll")
async def reroll(request: Request):
    """Reroll a single flavor text entry."""
    from .models import ParsedCreature, ParsedAbility
    from .generator import FlavorTextGenerator

    body = await request.json()
    creature_data = body.get('creature', {})
    creature = ParsedCreature(
        name=creature_data.get('name', 'Unknown'),
        creature_type=creature_data.get('type', ''),
        challenge_rating=creature_data.get('cr', ''),
        context_blob=creature_data.get('context_blob', ''),
    )

    ability_data = body['ability']
    ability = ParsedAbility(
        name=ability_data['name'],
        ability_type=ability_data['ability_type'],
        description=ability_data.get('description', ''),
        damage=ability_data.get('damage'),
        attack_bonus=ability_data.get('attack_bonus'),
        save_dc=ability_data.get('save_dc'),
        save_type=ability_data.get('save_type'),
        range=ability_data.get('range'),
        uses=ability_data.get('uses'),
        recharge=ability_data.get('recharge'),
    )

    category = body.get('category', 'attempts')
    provider_name = body.get('provider')
    style = body.get('style', 'dramatic')

    config = _get_config()
    generator = FlavorTextGenerator(config)
    req = creature.to_flavor_request(ability, style=style, variations=1)

    conditional_cats = (
        'crits', 'fumbles', 'barely_hits', 'barely_misses',
        'miss_dodge', 'miss_armor', 'killing_blow',
    )

    if category in conditional_cats:
        provider = generator._resolve_provider(provider_name)
        prompt = generator.generate_conditional_prompt(req, category, count=1)
        entries = await generator._call_provider_simple(provider, prompt, 1)
        return {"entry": entries[0] if entries else ""}
    else:
        result = await generator.generate_flavor_text(req, provider_name=provider_name)
        entries = getattr(result, category, [])
        return {"entry": entries[0] if entries else ""}


# ── Helpers ──────────────────────────────────────────────────────


def _rebuild_creature(data: dict):
    """Rebuild a ParsedCreature from API request data."""
    from .models import ParsedCreature, ParsedAbility

    creature_data = data.get('creature', {})
    abilities_data = data.get('abilities', [])

    abilities = []
    for a in abilities_data:
        abilities.append(ParsedAbility(
            name=a['name'],
            ability_type=a['ability_type'],
            description=a.get('description', ''),
            damage=a.get('damage'),
            attack_bonus=a.get('attack_bonus'),
            save_dc=a.get('save_dc'),
            save_type=a.get('save_type'),
            range=a.get('range'),
            uses=a.get('uses'),
            recharge=a.get('recharge'),
        ))

    return ParsedCreature(
        name=creature_data.get('name', 'Unknown'),
        creature_type=creature_data.get('type', ''),
        challenge_rating=creature_data.get('cr', ''),
        context_blob=data.get('context_blob') or creature_data.get('context_blob', ''),
        abilities=abilities,
        skill_proficiencies=data.get('skill_proficiencies', {}),
        save_proficiencies=data.get('save_proficiencies', {}),
    )


def _sse(event: str, data) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def launch(port: int = 5000, work_dir: str = "./output"):
    """Start the Narramancy web server."""
    import uvicorn

    global _work_dir
    _work_dir = Path(work_dir).resolve()
    print(f"Narramancy server starting on http://localhost:{port}")
    print(f"Working directory: {_work_dir}")

    if not _work_dir.exists():
        print(f"Warning: Working directory does not exist: {_work_dir}")
        print("  Create it or use --work-dir to point at your JSON files.")

    # Open browser after a short delay
    import threading
    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
