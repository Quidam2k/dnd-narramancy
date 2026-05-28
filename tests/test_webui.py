"""Tests for the Narramancy Web UI."""

import json
import pytest

from narramancy.models import (
    FlavorTextResult, ParsedAbility, ParsedCreature, GENERIC_ACTIONS,
)
from narramancy.webui import (
    _format_creature_summary,
    _format_results,
    _parse_input,
    _export,
    create_ui,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GOBLIN_TEXT = """\
Goblin
Small humanoid (goblinoid), neutral evil

Armor Class 15 (leather armor, shield)
Hit Points 7 (2d6)
Speed 30 ft.

STR 8 (-1) DEX 14 (+2) CON 10 (+0) INT 10 (+0) WIS 8 (-1) CHA 8 (-1)

Skills Stealth +6
Senses darkvision 60 ft., passive Perception 9
Languages Common, Goblin
Challenge 1/4 (50 XP)

Nimble Escape. The goblin can take the Disengage or Hide action as a bonus action on each of its turns.

Actions
Scimitar. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage.
Shortbow. Ranged Weapon Attack: +4 to hit, range 80/320 ft., one target. Hit: 5 (1d6 + 2) piercing damage.
"""


def _make_sample_results() -> dict[str, FlavorTextResult]:
    return {
        "Scimitar": FlavorTextResult(
            attempts=["The goblin slashes wildly!", "A rusty blade arcs through the air!"],
            successes=["Steel bites deep into flesh!"],
            failures=["The blade skitters off armor harmlessly."],
            metadata={"provider": "test", "ability_type": "attack"},
        ),
        "Shortbow": FlavorTextResult(
            attempts=["An arrow whistles through the air!"],
            successes=["The shaft finds its mark!"],
            failures=["The arrow clatters off stone."],
            metadata={"provider": "test", "ability_type": "attack"},
        ),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreateUI:
    """Test that the Gradio app constructs without error."""

    def test_create_ui_returns_blocks(self):
        app = create_ui()
        # Gradio Blocks instance
        assert app is not None
        assert hasattr(app, "launch")


class TestFormatCreatureSummary:
    def test_basic_creature(self):
        creature = ParsedCreature(
            name="Goblin",
            size="Small",
            creature_type="humanoid (goblinoid)",
            challenge_rating="1/4",
            abilities=[
                ParsedAbility(name="Scimitar", ability_type="attack",
                              description="Melee weapon attack", attack_bonus=4,
                              damage="1d6+2 slashing"),
            ],
        )
        summary = _format_creature_summary(creature)
        assert "**Goblin**" in summary
        assert "Small humanoid" in summary
        assert "CR 1/4" in summary
        assert "Scimitar" in summary
        assert "+4 to hit" in summary

    def test_creature_with_context(self):
        creature = ParsedCreature(
            name="Test", size="", creature_type="", challenge_rating="",
            abilities=[], context_blob="Guards the door",
        )
        summary = _format_creature_summary(creature)
        assert "Guards the door" in summary


class TestFormatResults:
    def test_empty_results(self):
        assert "No results" in _format_results({})

    def test_results_with_data(self):
        results = _make_sample_results()
        md = _format_results(results)
        assert "Scimitar" in md
        assert "Shortbow" in md
        assert "slashes wildly" in md
        assert "Attempts" in md
        assert "Successes" in md
        assert "Failures" in md


class TestParseInput:
    def test_paste_text(self):
        creature_json, summary = _parse_input(
            "Paste Text", GOBLIN_TEXT, "", None, "", False, 0,
        )
        assert creature_json is not None
        data = json.loads(creature_json)
        assert data["name"] == "Goblin"
        assert len(data["abilities"]) >= 2
        assert "**Goblin**" in summary

    def test_paste_empty(self):
        creature_json, summary = _parse_input(
            "Paste Text", "", "", None, "", False, 0,
        )
        assert creature_json is None
        assert "Paste" in summary

    def test_context_applied(self):
        creature_json, _ = _parse_input(
            "Paste Text", GOBLIN_TEXT, "", None, "Guards a cave", False, 0,
        )
        data = json.loads(creature_json)
        assert data["context"] == "Guards a cave"

    def test_generic_actions_added(self):
        creature_json, _ = _parse_input(
            "Paste Text", GOBLIN_TEXT, "", None, "", True, 0,
        )
        data = json.loads(creature_json)
        ability_names = [a["name"] for a in data["abilities"]]
        # Should have at least one generic action
        generic_names = {ga.name for ga in GENERIC_ACTIONS}
        assert any(name in generic_names for name in ability_names)

    def test_open5e_empty_query(self):
        creature_json, summary = _parse_input(
            "Open5e Search", "", "", None, "", False, 0,
        )
        assert creature_json is None
        assert "Enter" in summary

    def test_upload_file_no_file(self):
        creature_json, summary = _parse_input(
            "Upload File", "", "", None, "", False, 0,
        )
        assert creature_json is None
        assert "Upload" in summary


class TestExport:
    def test_export_all(self):
        results = _make_sample_results()
        results_json = json.dumps({
            "_creature": "Goblin",
            **{
                name: {
                    "attempts": r.attempts,
                    "successes": r.successes,
                    "failures": r.failures,
                    "metadata": r.metadata,
                }
                for name, r in results.items()
            },
        })
        files = _export(results_json, "all", True)
        assert files is not None
        assert len(files) == 2
        # Check filenames
        names = [f.split("\\")[-1].split("/")[-1] for f in files]
        assert any("tables" in n for n in names)
        assert any("sayings" in n for n in names)
        # Verify JSON is valid
        for path in files:
            with open(path) as f:
                data = json.load(f)
            assert data  # non-empty

    def test_export_empty(self):
        assert _export("", "all", True) is None
        assert _export(None, "all", True) is None

    def test_export_raw_json(self):
        results_json = json.dumps({
            "_creature": "Test",
            "Bite": {
                "attempts": ["Chomp!"],
                "successes": [],
                "failures": [],
                "metadata": {},
            },
        })
        files = _export(results_json, "raw_json", False)
        assert files is not None
        assert len(files) == 1
        assert "results.json" in files[0]
