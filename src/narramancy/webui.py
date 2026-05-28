"""Narramancy Web UI — Gradio-based standalone app.

Launch:
    python -m narramancy webui [--port 7870] [--share]
    python src/narramancy/webui.py
"""

import asyncio
import json
import os
import tempfile
from typing import Optional

import gradio as gr

from .config import ConfigManager
from .generator import FlavorTextGenerator
from .models import GENERIC_ACTIONS, FlavorTextResult, ParsedCreature
from .providers import get_available_providers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_creature_summary(creature: ParsedCreature) -> str:
    """Render a parsed creature as a readable summary string."""
    lines = [
        f"**{creature.name}**",
        f"{creature.size} {creature.creature_type}, CR {creature.challenge_rating}",
    ]
    if creature.context_blob:
        lines.append(f"*Context:* {creature.context_blob}")
    lines.append(f"\n**{len(creature.abilities)} abilities:**")
    for a in creature.abilities:
        extras = []
        if a.attack_bonus is not None:
            extras.append(f"+{a.attack_bonus} to hit")
        if a.damage:
            extras.append(a.damage)
        if a.save_dc:
            extras.append(f"DC {a.save_dc} {a.save_type}")
        if a.recharge:
            extras.append(f"recharge {a.recharge}")
        if a.uses:
            extras.append(a.uses)
        extra_str = f" ({', '.join(extras)})" if extras else ""
        lines.append(f"- **[{a.ability_type}]** {a.name}{extra_str}")
    return "\n".join(lines)


def _format_results(results: dict[str, FlavorTextResult]) -> str:
    """Render generation results as Markdown."""
    if not results:
        return "*No results.*"
    sections = []
    for ability_name, result in results.items():
        provider = result.metadata.get("provider", "?")
        parts = [f"### {ability_name}  *(via {provider})*"]
        for category in ("attempts", "successes", "failures"):
            texts = getattr(result, category)
            if texts:
                parts.append(f"\n**{category.title()}:**")
                for i, text in enumerate(texts, 1):
                    parts.append(f"{i}. {text}")
        sections.append("\n".join(parts))
    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def _parse_input(source: str, text_input: str, open5e_query: str,
                 file_upload, context: str, include_generic: bool,
                 pdf_page: int):
    """Parse creature from the selected source. Returns (creature_json, summary_md)."""
    from .parsers import parse_stat_block, fetch_creature, search_creatures

    creature: Optional[ParsedCreature] = None

    if source == "Paste Text":
        if not text_input or not text_input.strip():
            return None, "*Paste a stat block in the text box.*"
        creature = parse_stat_block(text_input)

    elif source == "Open5e Search":
        if not open5e_query or not open5e_query.strip():
            return None, "*Enter a creature name or slug to search.*"
        slug = open5e_query.strip()
        try:
            creature = fetch_creature(slug)
        except ValueError:
            results = search_creatures(slug)
            if not results:
                return None, f"*No creatures found matching '{slug}'.*"
            creature = fetch_creature(results[0]["slug"])

    elif source == "Upload File":
        if file_upload is None:
            return None, "*Upload a .json, .html, or .pdf file.*"
        page = int(pdf_page) if pdf_page and int(pdf_page) > 0 else None
        creature = parse_stat_block(file_upload, page=page)

    if creature is None:
        return None, "*Could not parse creature.*"

    if context and context.strip():
        creature.context_blob = context.strip()

    if include_generic:
        existing = {a.name for a in creature.abilities}
        for ga in GENERIC_ACTIONS:
            if ga.name not in existing:
                creature.abilities.append(ga)

    # Serialize creature for the generate step
    creature_dict = {
        "name": creature.name,
        "size": creature.size,
        "type": creature.creature_type,
        "cr": creature.challenge_rating,
        "context": creature.context_blob,
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
    }
    return json.dumps(creature_dict), _format_creature_summary(creature)


def _reconstruct_creature(creature_json: str) -> ParsedCreature:
    """Rebuild ParsedCreature from the stashed JSON."""
    from .models import ParsedAbility

    data = json.loads(creature_json)
    abilities = []
    for a in data.get("abilities", []):
        abilities.append(ParsedAbility(
            name=a["name"],
            ability_type=a["ability_type"],
            description=a.get("description", ""),
            damage=a.get("damage"),
            attack_bonus=a.get("attack_bonus"),
            save_dc=a.get("save_dc"),
            save_type=a.get("save_type"),
            range=a.get("range"),
            uses=a.get("uses"),
            recharge=a.get("recharge"),
        ))
    return ParsedCreature(
        name=data["name"],
        size=data.get("size", ""),
        creature_type=data.get("type", ""),
        challenge_rating=data.get("cr", ""),
        abilities=abilities,
        context_blob=data.get("context"),
    )


async def _generate_async(creature: ParsedCreature, style: str,
                           variations: int, provider_name: Optional[str]):
    """Run generation for all abilities, yielding progress updates."""
    config = ConfigManager()
    generator = FlavorTextGenerator(config)
    results: dict[str, FlavorTextResult] = {}

    for i, ability in enumerate(creature.abilities):
        request = creature.to_flavor_request(ability, style=style, variations=variations)
        try:
            result = await generator.generate_flavor_text(request, provider_name=provider_name)
            result.metadata["ability_type"] = ability.ability_type
            results[ability.name] = result
        except Exception as e:
            results[ability.name] = FlavorTextResult(
                attempts=[], successes=[], failures=[],
                metadata={"error": str(e), "ability_type": ability.ability_type},
            )

    return results


def _generate(creature_json: str, style: str, variations: int,
              provider: str, progress=gr.Progress()):
    """Synchronous wrapper for the async generation pipeline."""
    if not creature_json:
        return "", None

    creature = _reconstruct_creature(creature_json)
    provider_name = provider if provider != "auto" else None

    progress(0, desc=f"Generating flavor for {creature.name}...")

    config = ConfigManager()
    generator = FlavorTextGenerator(config)
    results: dict[str, FlavorTextResult] = {}
    total = len(creature.abilities)

    for i, ability in enumerate(creature.abilities):
        progress((i) / total, desc=f"[{i+1}/{total}] {ability.name}...")
        request = creature.to_flavor_request(ability, style=style, variations=variations)
        try:
            result = asyncio.run(
                generator.generate_flavor_text(request, provider_name=provider_name)
            )
            result.metadata["ability_type"] = ability.ability_type
            results[ability.name] = result
        except Exception as e:
            results[ability.name] = FlavorTextResult(
                attempts=[], successes=[], failures=[],
                metadata={"error": str(e), "ability_type": ability.ability_type},
            )

    progress(1.0, desc="Done!")

    # Stash results JSON for export
    results_json = {
        "_creature": creature.name,
    }
    for name, r in results.items():
        results_json[name] = {
            "attempts": r.attempts,
            "successes": r.successes,
            "failures": r.failures,
            "metadata": r.metadata,
        }

    return _format_results(results), json.dumps(results_json)


def _export(results_json: str, fmt: str, whisper_gm: bool):
    """Export generation results to downloadable files. Returns list of file paths."""
    if not results_json:
        return None

    from .exporters import export_rollable_tables, export_token_says

    data = json.loads(results_json)
    creature_name = data.get("_creature", "creature")
    slug = creature_name.lower().replace(" ", "-")

    # Reconstruct results dict
    results = {}
    for key, val in data.items():
        if key.startswith("_"):
            continue
        if isinstance(val, dict) and "attempts" in val:
            results[key] = FlavorTextResult(
                attempts=val.get("attempts", []),
                successes=val.get("successes", []),
                failures=val.get("failures", []),
                metadata=val.get("metadata", {}),
            )

    if not results:
        return None

    files = []
    tmpdir = tempfile.mkdtemp(prefix="narramancy_")

    if fmt in ("rollable_tables", "all"):
        tables_text = export_rollable_tables(creature_name, results)
        path = os.path.join(tmpdir, f"{slug}-tables.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(tables_text)
        files.append(path)

    if fmt in ("tokensays", "all"):
        whisper = "GM" if whisper_gm else None
        sayings = export_token_says(creature_name, results, whisper=whisper)
        path = os.path.join(tmpdir, f"{slug}-sayings.json")
        with open(path, "w") as f:
            json.dump(sayings, f, indent=2)
        files.append(path)

    if fmt == "raw_json":
        path = os.path.join(tmpdir, f"{slug}-results.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        files.append(path)

    return files if files else None


# ---------------------------------------------------------------------------
# UI Construction
# ---------------------------------------------------------------------------

def create_ui() -> gr.Blocks:
    """Build and return the Gradio Blocks app."""
    config = ConfigManager()
    providers = ["auto"] + get_available_providers(config)

    with gr.Blocks(
        title="Narramancy",
        theme=gr.themes.Soft(),
    ) as app:
        gr.Markdown("# Narramancy\n*Vivid narration for D&D abilities and actions*")

        # Hidden state for passing data between callbacks
        creature_state = gr.State(value=None)   # JSON string of parsed creature
        results_state = gr.State(value=None)     # JSON string of generation results

        with gr.Row():
            # ---- Left column: Input ----
            with gr.Column(scale=1):
                source = gr.Radio(
                    choices=["Paste Text", "Open5e Search", "Upload File"],
                    value="Paste Text",
                    label="Source",
                )

                text_input = gr.Textbox(
                    label="Stat Block Text",
                    placeholder="Paste a monster stat block here...",
                    lines=12,
                    visible=True,
                )
                open5e_input = gr.Textbox(
                    label="Creature Name / Slug",
                    placeholder="e.g. goblin, adult-red-dragon",
                    visible=False,
                )
                file_upload = gr.File(
                    label="Upload File (.json, .html, .pdf)",
                    file_types=[".json", ".html", ".htm", ".pdf"],
                    visible=False,
                )
                pdf_page_input = gr.Number(
                    label="PDF Page (optional, 1-based)",
                    value=0,
                    precision=0,
                    visible=False,
                )

                context_input = gr.Textbox(
                    label="Context / Seasoning (optional)",
                    placeholder="e.g. These goblins serve a hobgoblin warlord in a frozen mountain pass",
                    lines=2,
                )

                with gr.Row():
                    style_input = gr.Dropdown(
                        choices=["dramatic", "comedic", "gritty", "heroic"],
                        value="dramatic",
                        label="Style",
                    )
                    variations_input = gr.Slider(
                        minimum=1, maximum=10, value=5, step=1,
                        label="Variations",
                    )

                with gr.Row():
                    provider_input = gr.Dropdown(
                        choices=providers,
                        value="auto",
                        label="Provider",
                    )
                    generic_check = gr.Checkbox(
                        label="Include generic actions",
                        value=False,
                    )

                with gr.Row():
                    parse_btn = gr.Button("Parse", variant="secondary")
                    generate_btn = gr.Button("Generate", variant="primary")

            # ---- Right column: Output ----
            with gr.Column(scale=1):
                creature_summary = gr.Markdown(
                    value="*Parse a creature to see its summary here.*",
                    label="Creature",
                )
                results_output = gr.Markdown(
                    value="",
                    label="Results",
                )

                gr.Markdown("### Export")
                with gr.Row():
                    export_fmt = gr.Dropdown(
                        choices=["all", "rollable_tables", "tokensays", "raw_json"],
                        value="all",
                        label="Format",
                    )
                    whisper_check = gr.Checkbox(
                        label="Whisper to GM",
                        value=True,
                    )
                export_btn = gr.Button("Export & Download", variant="secondary")
                export_files = gr.File(label="Downloads", interactive=False)

        # ---- Visibility toggles ----
        def _toggle_source(choice):
            return (
                gr.update(visible=choice == "Paste Text"),
                gr.update(visible=choice == "Open5e Search"),
                gr.update(visible=choice == "Upload File"),
                gr.update(visible=choice == "Upload File"),
            )

        source.change(
            fn=_toggle_source,
            inputs=[source],
            outputs=[text_input, open5e_input, file_upload, pdf_page_input],
        )

        # ---- Parse button ----
        parse_btn.click(
            fn=_parse_input,
            inputs=[source, text_input, open5e_input, file_upload,
                    context_input, generic_check, pdf_page_input],
            outputs=[creature_state, creature_summary],
        )

        # ---- Generate button ----
        generate_btn.click(
            fn=_generate,
            inputs=[creature_state, style_input, variations_input, provider_input],
            outputs=[results_output, results_state],
        )

        # ---- Export button ----
        export_btn.click(
            fn=_export,
            inputs=[results_state, export_fmt, whisper_check],
            outputs=[export_files],
        )

    return app


def launch(port: int = 7870, share: bool = False):
    """Create and launch the Gradio app."""
    app = create_ui()
    app.launch(server_port=port, share=share)


if __name__ == "__main__":
    launch()
