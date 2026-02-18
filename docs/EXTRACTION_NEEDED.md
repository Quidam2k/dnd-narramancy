# Flavor Forge: Extraction Requirements

**Purpose**: This document details what needs to be extracted from the parent "summarizer" project to make Flavor Forge a standalone tool.

**Target Workflow**:
```
Upload Stat Block → Parse Abilities → Generate Flavor Text → Export to:
  ├── Foundry VTT Rollable Tables
  └── TokenSays Configuration (auto-wire tables to triggers)
```

---

## Missing Dependencies

The Python implementation (`src/python/flavor_text_generator.py`) has these relative imports that need to be resolved:

### 1. `cost_tracker.py`

**What it does**: Tracks API costs across providers (Anthropic, Google, etc.)

**Required interface**:
```python
class CostTracker:
    def __init__(self, base_path: Path): ...

    def log_api_call(
        self,
        provider: str,        # 'google' | 'anthropic'
        model: str,           # 'gemini-2.0-flash-exp' | 'claude-3-5-sonnet'
        operation: str,       # 'flavor_text'
        input_tokens: int,
        output_tokens: int
    ) -> None: ...
```

**Can we stub it?**: Yes - logging to file or no-op is fine for standalone use.

---

### 2. `characterization_profiler.py`

**What it does**: Character personality profiling system. Asks questions about a character to build a profile that enhances flavor text generation.

**Required exports**:
```python
class CharacterizationProfiler:
    def select_questions_for_character(
        self,
        character_name: str,
        num_questions: int,
        focus_categories: Optional[List[QuestionCategory]] = None
    ) -> List[Question]: ...

    def create_character_profile(
        self,
        character_name: str,
        answered_questions: Dict[str, str]
    ) -> CharacterProfile: ...

    def save_character_profile(self, profile: CharacterProfile, path: Path) -> None: ...
    def load_character_profile(self, path: Path) -> CharacterProfile: ...

@dataclass
class CharacterProfile:
    character_name: str
    personality_traits: List[str]
    physical_descriptors: List[str]
    answered_questions: Dict[str, str]
    confidence: float  # 0.0-1.0

class CharacterProfileIntegrator:
    def __init__(self, profiler: CharacterizationProfiler): ...

    def enhance_flavor_text_prompt(
        self,
        request: FlavorTextRequest,
        profile: CharacterProfile
    ) -> str: ...

class QuestionCategory(Enum):
    # What categories exist? Need full enum.
    PERSONALITY = "personality"
    COMBAT_STYLE = "combat_style"
    # ... others?

@dataclass
class Question:
    id: str
    question: str
    category: QuestionCategory
    follow_up_prompts: List[str]
    example_descriptors: List[str]
```

**Can we stub it?**: Partially. The core generator works without profiling (see `generate_flavor_text_prompt` fallback path). But profiling is valuable - extract if possible.

**Questions for extraction**:
- What questions does it ask?
- What categories exist?
- How does `enhance_flavor_text_prompt` modify the prompt?

---

### 3. `ConfigManager` (from `summarizer.config.settings`)

**What it does**: Manages API keys and configuration settings.

**Required interface**:
```python
class ConfigManager:
    def get(self, section: str, key: str, fallback: Any = None) -> Any: ...
    def get_api_key(self, provider: str) -> Optional[str]: ...
    # provider: 'gemini' | 'anthropic'
```

**Can we stub it?**: Yes - simple env var or config file reader.

---

## Test File Import Path

The test file (`tests/test_flavor_generation.py`) imports:
```python
from summarizer.core.flavor_text_generator import (...)
from summarizer.config.settings import ConfigManager
```

This reveals the parent project structure:
```
summarizer/
├── core/
│   ├── flavor_text_generator.py  # ← This file
│   ├── cost_tracker.py           # ← Need this
│   └── characterization_profiler.py  # ← Need this
├── config/
│   └── settings.py               # ← ConfigManager lives here
└── context/
    └── campaigns/                # ← Profile storage location
```

---

## VTT Export Additions Needed

The current `VTTExporter` class is a stub. For the target workflow, we need:

### Foundry VTT Rollable Table Format

```json
{
  "name": "Thorin - Longsword Attack - Attempts",
  "img": "icons/svg/d20-black.svg",
  "description": "Flavor text for attempting a longsword attack",
  "results": [
    {
      "type": 0,
      "text": "Steel whispers through the air as Thorin brings his blade to bear.",
      "weight": 1,
      "range": [1, 1],
      "drawn": false
    },
    {
      "type": 0,
      "text": "With a grunt, the dwarf's ancestral blade arcs toward his foe.",
      "weight": 1,
      "range": [2, 2],
      "drawn": false
    }
    // ... more entries
  ],
  "formula": "1d{count}",
  "replacement": true,
  "displayRoll": true,
  "folder": null,
  "flags": {}
}
```

### TokenSays Configuration Format

Based on the module, we need to generate sayings that reference rollable tables:

```json
{
  "sayings": [
    {
      "title": "Thorin - Longsword Attack",
      "tokenName": "Thorin",
      "actorName": "Thorin Ironforge",
      "actionType": "Attack Roll",
      "actionName": "Longsword",
      "tableName": "Thorin - Longsword Attack - Attempts",
      "likelihood": 100,
      "suppressChatBubble": false,
      "suppressChatMessage": false
    }
  ]
}
```

**Action Types we need to support**:
- `Attack Roll` → attempts/successes/failures based on roll result
- `Damage Roll` → success variations
- `Saving Throw` → attempts/successes/failures
- `Skill` → attempts/successes/failures
- `Ability Check` → attempts/successes/failures
- `Takes Damage` → could use failure/hit reactions

---

## Stat Block Parsing (New Requirement)

Need to parse various stat block formats:

### Input Formats to Support
1. **D&D Beyond JSON** (if API accessible)
2. **Foundry VTT Actor JSON** (exported from Foundry)
3. **Plain text stat block** (copied from PDF/book)
4. **Open5e API** (open source monster/spell data)

### Output: Ability List
```python
@dataclass
class ParsedAbility:
    name: str
    ability_type: str  # attack|spell|cantrip|feature|action|reaction|legendary
    description: str
    damage: Optional[str]
    attack_bonus: Optional[int]
    save_dc: Optional[int]
    save_type: Optional[str]  # DEX, CON, etc.
    range: Optional[str]
    uses: Optional[str]
    recharge: Optional[str]  # "5-6", "short rest", etc.
```

---

## Recommended Standalone Structure

```
dnd-flavor-forge/
├── src/
│   └── flavor_forge/
│       ├── __init__.py
│       ├── generator.py          # Core FlavorTextGenerator
│       ├── config.py             # Simple ConfigManager
│       ├── cost_tracker.py       # Stub or real tracker
│       ├── profiler.py           # CharacterizationProfiler (if extracted)
│       ├── parsers/
│       │   ├── __init__.py
│       │   ├── foundry.py        # Parse Foundry actor JSON
│       │   ├── text_block.py     # Parse plain text stat blocks
│       │   └── ddb.py            # Parse D&D Beyond (if possible)
│       └── exporters/
│           ├── __init__.py
│           ├── rollable_table.py # Foundry rollable table JSON
│           └── token_says.py     # TokenSays config JSON
├── cli.py                        # Command-line interface
├── config.yaml                   # API keys, defaults
└── README.md
```

---

## Priority Order

1. **P0 - Core Generation**: Stub dependencies, get `generate_flavor_text` working standalone
2. **P1 - Rollable Table Export**: Generate Foundry VTT rollable table JSON
3. **P2 - TokenSays Integration**: Generate sayings config that auto-wires to tables
4. **P3 - Stat Block Parsing**: Parse various input formats
5. **P4 - Character Profiling**: Extract full profiler for personality-enhanced generation

---

## Questions for Parent Project

1. **Full `characterization_profiler.py`** - Can you export this file?
2. **Question bank** - What questions does it ask? What categories exist?
3. **`enhance_flavor_text_prompt` implementation** - How does profiling modify prompts?
4. **Any other files in `summarizer/core/`** that flavor_text_generator.py depends on?
5. **Config file format** - What does the config look like? INI? YAML? JSON?

---

## TokenSays Integration Notes

From the TokenSays documentation:

- **Rollable Tables**: TokenSays can reference a rollable table by name. When triggered, it rolls on that table and displays the result.
- **Action Types**: Attack Roll, Damage Roll, Saving Throw, Skill, Ability Check, Takes Damage, etc.
- **Per-outcome tables**: We can create separate tables for attempts/successes/failures and wire them to different trigger conditions.

**Smart Integration Idea**:
- Create 3 tables per ability: `{Name} - Attempts`, `{Name} - Successes`, `{Name} - Failures`
- TokenSays config:
  - On Attack Roll → roll Attempts table
  - On Damage Roll (hit confirmed) → roll Successes table
  - On "miss" detection → roll Failures table (requires hook or macro)

This may require a companion Foundry module or macro to detect success/failure and trigger the appropriate saying.
