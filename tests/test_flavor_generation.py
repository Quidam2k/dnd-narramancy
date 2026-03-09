#!/usr/bin/env python3
"""Test suite for the Flavor Forge flavor text generation system."""

import asyncio
import sys
import os
from pathlib import Path

# Add src/ to path so flavor_forge package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flavor_forge import (
    FlavorTextGenerator,
    FlavorTextRequest,
    CharacterAbilityParser,
    ConfigManager,
    AIProvider,
    LMStudioProvider,
    OpenAICompatibleProvider,
)
from flavor_forge.providers import (
    get_provider,
    get_available_providers,
    GroqProvider,
    OpenRouterProvider,
    TogetherProvider,
)


def test_character_ability_parser():
    """Test the character ability parsing system (no API required)."""
    print("\nTesting CharacterAbilityParser")
    print("-" * 40)

    sample_character = {
        "name": "Test Character",
        "class": "Fighter",
        "level": 5,
        "abilities": [
            {
                "name": "Action Surge",
                "type": "feature",
                "description": "Starting at 2nd level, you can push yourself beyond your normal limits for a moment.",
                "uses": "1 per short rest"
            },
            {
                "name": "Second Wind",
                "type": "feature",
                "description": "You have a limited well of stamina that you can draw on to protect yourself from harm.",
                "uses": "1 per short rest"
            }
        ],
        "spells": [
            {
                "name": "Hunter's Mark",
                "level": 1,
                "description": "You choose a creature you can see within range and mystically mark it as your quarry.",
                "damage": "1d6",
                "range": "90 feet"
            }
        ],
        "equipment": [
            {
                "name": "Longsword",
                "type": "weapon",
                "damage": "1d8",
                "description": "A versatile martial weapon"
            }
        ]
    }

    try:
        abilities = CharacterAbilityParser.parse_character_abilities(sample_character)

        print(f"  Parsed {len(abilities)} abilities from character data:")
        for ability in abilities:
            ability_type = CharacterAbilityParser.classify_ability_type(ability)
            print(f"    - {ability['name']} ({ability_type})")

        assert len(abilities) == 4, f"Expected 4 abilities, got {len(abilities)}"
        assert abilities[0]['name'] == 'Action Surge'
        assert abilities[2]['name'] == "Hunter's Mark"
        assert abilities[2]['type'] == 'spell'
        assert abilities[3]['name'] == 'Longsword'
        assert CharacterAbilityParser.classify_ability_type(abilities[3]) == 'attack'

        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_manager():
    """Test ConfigManager env var and fallback logic."""
    print("\nTesting ConfigManager")
    print("-" * 40)

    try:
        config = ConfigManager()

        # Test fallback
        val = config.get('ai_generation', 'model', fallback='gemini-2.0-flash-exp')
        assert val == 'gemini-2.0-flash-exp', f"Expected fallback, got {val}"

        # Test env var override
        os.environ['FLAVOR_FORGE_AI_GENERATION_MODEL'] = 'test-model'
        val = config.get('ai_generation', 'model', fallback='default')
        assert val == 'test-model', f"Expected 'test-model', got {val}"
        del os.environ['FLAVOR_FORGE_AI_GENERATION_MODEL']

        # Test API key lookup
        os.environ['GEMINI_API_KEY'] = 'fake-key'
        key = config.get_api_key('gemini')
        assert key == 'fake-key'
        del os.environ['GEMINI_API_KEY']

        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_generator_init():
    """Test that FlavorTextGenerator instantiates without errors."""
    print("\nTesting FlavorTextGenerator instantiation")
    print("-" * 40)

    try:
        config = ConfigManager()
        generator = FlavorTextGenerator(config)

        # Test prompt generation (no API call)
        request = FlavorTextRequest(
            character_name="Thorin Ironforge",
            character_race="Dwarf",
            character_class="Fighter",
            character_level=5,
            ability_name="Action Surge",
            ability_type="feature",
            ability_description="Push beyond normal limits",
            style="dramatic",
            variations=3
        )
        prompt = generator.generate_flavor_text_prompt(request)
        assert "Thorin Ironforge" in prompt
        assert "Action Surge" in prompt
        assert "dramatic" in prompt

        # Test with context_blob
        request_with_context = FlavorTextRequest(
            character_name="Skeleton",
            character_race="Undead",
            character_class="Fighter",
            character_level=1,
            ability_name="Shortsword",
            ability_type="attack",
            context_blob="This skeleton was once a noble knight who fell defending the castle.",
            variations=3
        )
        prompt2 = generator.generate_flavor_text_prompt(request_with_context)
        assert "noble knight" in prompt2

        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_provider_interface():
    """Test that provider classes implement the AIProvider interface correctly."""
    print("\nTesting provider interface")
    print("-" * 40)

    try:
        # LMStudioProvider is a subclass of OpenAICompatibleProvider
        lm = LMStudioProvider()
        assert isinstance(lm, OpenAICompatibleProvider)
        assert isinstance(lm, AIProvider)
        assert lm.name == "lmstudio"
        assert lm.base_url == "http://localhost:1234"
        assert lm.api_key is None

        # OpenAICompatibleProvider with API key
        oai = OpenAICompatibleProvider(
            base_url="https://example.com/v1",
            model="test-model",
            api_key="test-key",
            name="test-provider",
        )
        assert oai.api_key == "test-key"
        assert oai.name == "test-provider"

        # Preset subclasses
        groq = GroqProvider(api_key="gk")
        assert groq.name == "groq"
        assert groq.api_key == "gk"
        assert "groq.com" in groq.base_url

        ortr = OpenRouterProvider(api_key="ok")
        assert ortr.name == "openrouter"
        assert "openrouter.ai" in ortr.base_url

        tog = TogetherProvider(api_key="tk")
        assert tog.name == "together"
        assert "together.xyz" in tog.base_url

        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_provider_new_providers():
    """Test get_provider() for groq, openrouter, together."""
    print("\nTesting get_provider for new providers")
    print("-" * 40)

    try:
        config = ConfigManager()

        # Should raise ValueError when no key is set
        for name in ("groq", "openrouter", "together"):
            # Make sure key is not set
            env_var = {'groq': 'GROQ_API_KEY', 'openrouter': 'OPENROUTER_API_KEY', 'together': 'TOGETHER_API_KEY'}[name]
            old_val = os.environ.pop(env_var, None)
            try:
                get_provider(name, config)
                print(f"  FAIL: {name} should raise ValueError without key")
                return False
            except ValueError:
                pass  # Expected
            finally:
                if old_val is not None:
                    os.environ[env_var] = old_val

        # Should succeed when key is set
        os.environ['GROQ_API_KEY'] = 'test-groq-key'
        p = get_provider("groq", config)
        assert isinstance(p, GroqProvider)
        assert p.api_key == 'test-groq-key'
        del os.environ['GROQ_API_KEY']

        os.environ['OPENROUTER_API_KEY'] = 'test-or-key'
        p = get_provider("openrouter", config)
        assert isinstance(p, OpenRouterProvider)
        del os.environ['OPENROUTER_API_KEY']

        os.environ['TOGETHER_API_KEY'] = 'test-tog-key'
        p = get_provider("together", config)
        assert isinstance(p, TogetherProvider)
        del os.environ['TOGETHER_API_KEY']

        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_available_providers_new():
    """Test that new providers appear in get_available_providers when keys are set."""
    print("\nTesting get_available_providers with new providers")
    print("-" * 40)

    try:
        config = ConfigManager()

        # Baseline — no new provider keys set
        for var in ('GROQ_API_KEY', 'OPENROUTER_API_KEY', 'TOGETHER_API_KEY'):
            os.environ.pop(var, None)
        available = get_available_providers(config)
        assert "groq" not in available
        assert "openrouter" not in available
        assert "together" not in available

        # Set keys and verify they appear
        os.environ['GROQ_API_KEY'] = 'k'
        os.environ['OPENROUTER_API_KEY'] = 'k'
        os.environ['TOGETHER_API_KEY'] = 'k'
        available = get_available_providers(config)
        assert "groq" in available
        assert "openrouter" in available
        assert "together" in available

        # Cleanup
        del os.environ['GROQ_API_KEY']
        del os.environ['OPENROUTER_API_KEY']
        del os.environ['TOGETHER_API_KEY']

        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_ai_generation():
    """Test actual AI generation (requires API key). Skipped if no key available."""
    print("\nTesting AI Generation (requires API key)")
    print("-" * 40)

    config = ConfigManager()
    gemini_key = config.get_api_key('gemini')
    claude_key = config.get_api_key('anthropic')

    if not gemini_key and not claude_key:
        print("  SKIP: No API keys configured")
        return None  # None = skipped, not failed

    generator = FlavorTextGenerator(config)

    request = FlavorTextRequest(
        character_name="Thorin Ironforge",
        character_race="Dwarf",
        character_class="Fighter",
        character_level=5,
        ability_name="Action Surge",
        ability_type="feature",
        ability_description="Push yourself beyond normal limits for a moment",
        style="dramatic",
        variations=3
    )

    try:
        result = await generator.generate_flavor_text(request)
        print(f"  Generated {len(result.attempts)} attempts, {len(result.successes)} successes, {len(result.failures)} failures")
        if result.attempts:
            print(f"  Sample: {result.attempts[0]}")
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


async def main():
    """Run all tests."""
    print("Flavor Forge Test Suite")
    print("=" * 60)

    results = {}
    results['parser'] = test_character_ability_parser()
    results['config'] = test_config_manager()
    results['provider_interface'] = test_provider_interface()
    results['get_provider_new'] = test_get_provider_new_providers()
    results['available_providers_new'] = test_get_available_providers_new()
    results['generator_init'] = test_generator_init()
    results['ai_generation'] = await test_ai_generation()

    print(f"\n{'=' * 60}")
    print("Results:")
    for name, result in results.items():
        if result is None:
            status = "SKIP"
        elif result:
            status = "PASS"
        else:
            status = "FAIL"
        print(f"  {name}: {status}")

    failures = [k for k, v in results.items() if v is False]
    if failures:
        print(f"\nFailed: {', '.join(failures)}")
        return False
    else:
        print("\nAll tests passed (or skipped).")
        return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
