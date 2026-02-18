#!/usr/bin/env python3
"""Test suite for provider abstraction and flavor text generation."""

import asyncio
import json
import subprocess
import sys
import os
from pathlib import Path

# Add src/ to path so flavor_forge package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from flavor_forge import (
    FlavorTextGenerator,
    FlavorTextRequest,
    ConfigManager,
    AIProvider,
    ProviderResult,
    GeminiProvider,
    ClaudeProvider,
    OllamaProvider,
)
from flavor_forge.providers import get_provider, get_available_providers


# ---------------------------------------------------------------------------
# Mock provider for testing without API keys
# ---------------------------------------------------------------------------

class MockProvider(AIProvider):
    """Returns canned JSON responses for testing."""

    name = "mock"

    def __init__(self, model="mock-v1", variations=5, should_fail=False):
        self.model = model
        self._variations = variations
        self._should_fail = should_fail
        self.call_count = 0

    async def generate(self, prompt: str) -> ProviderResult:
        self.call_count += 1
        if self._should_fail:
            raise ConnectionError("Mock provider failure")

        response = {
            "attempts": [f"Mock attempt {i+1}" for i in range(self._variations)],
            "successes": [f"Mock success {i+1}" for i in range(self._variations)],
            "failures": [f"Mock failure {i+1}" for i in range(self._variations)],
        }
        text = json.dumps(response)
        return ProviderResult(
            text=text,
            input_tokens=100,
            output_tokens=200,
            model=self.model,
            provider_name=self.name,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_provider_interface():
    """Verify each provider class implements the interface correctly."""
    print("\nTesting provider interface")
    print("-" * 40)

    try:
        # MockProvider
        mock = MockProvider()
        assert mock.name == "mock"
        assert mock.model == "mock-v1"
        assert hasattr(mock, 'generate')

        # GeminiProvider (instantiation only — no API call)
        gp = GeminiProvider(api_key="fake", model="gemini-test")
        assert gp.name == "gemini"
        assert gp.model == "gemini-test"

        # ClaudeProvider
        cp = ClaudeProvider(api_key="fake", model="claude-test")
        assert cp.name == "claude"
        assert cp.model == "claude-test"

        # OllamaProvider
        op = OllamaProvider(base_url="http://localhost:11434", model="llama3.2")
        assert op.name == "ollama"
        assert op.model == "llama3.2"

        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


def test_get_available_providers():
    """Test provider availability detection from env vars."""
    print("\nTesting get_available_providers")
    print("-" * 40)

    try:
        config = ConfigManager()

        # Save and clear keys
        saved = {}
        for key in ('GEMINI_API_KEY', 'ANTHROPIC_API_KEY', 'OLLAMA_BASE_URL'):
            saved[key] = os.environ.pop(key, None)

        # With nothing set, ollama should still show (defaults to localhost)
        available = get_available_providers(config)
        assert "ollama" in available, f"Expected ollama in {available}"
        assert "gemini" not in available
        assert "claude" not in available

        # Set gemini key
        os.environ['GEMINI_API_KEY'] = 'fake'
        available = get_available_providers(config)
        assert "gemini" in available

        # Restore
        del os.environ['GEMINI_API_KEY']
        for key, val in saved.items():
            if val is not None:
                os.environ[key] = val

        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


def test_get_provider():
    """Test get_provider factory function."""
    print("\nTesting get_provider factory")
    print("-" * 40)

    try:
        config = ConfigManager()

        # Save keys
        saved_gemini = os.environ.pop('GEMINI_API_KEY', None)

        # Should raise if no key
        try:
            get_provider("gemini", config)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "GEMINI_API_KEY" in str(e)

        # Set key and try again
        os.environ['GEMINI_API_KEY'] = 'test-key'
        p = get_provider("gemini", config)
        assert isinstance(p, GeminiProvider)
        assert p.api_key == 'test-key'

        # Unknown provider
        try:
            get_provider("openai", config)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown provider" in str(e)

        # Ollama always works (localhost default)
        p = get_provider("ollama", config)
        assert isinstance(p, OllamaProvider)

        # Restore
        del os.environ['GEMINI_API_KEY']
        if saved_gemini:
            os.environ['GEMINI_API_KEY'] = saved_gemini

        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


async def test_mock_generation():
    """Test full generation pipeline with mock provider (no API keys needed)."""
    print("\nTesting generation with MockProvider")
    print("-" * 40)

    try:
        config = ConfigManager()
        mock = MockProvider(variations=3)
        generator = FlavorTextGenerator(config, providers=[mock])

        request = FlavorTextRequest(
            character_name="Goblin",
            character_race="Goblinoid",
            character_class="Monster",
            character_level=1,
            ability_name="Scimitar",
            ability_type="attack",
            ability_description="Melee Weapon Attack: +4 to hit, 5 ft., one target.",
            style="dramatic",
            variations=3,
        )

        result = await generator.generate_flavor_text(request)

        assert len(result.attempts) == 3
        assert len(result.successes) == 3
        assert len(result.failures) == 3
        assert result.metadata['provider'] == 'mock'
        assert result.metadata['model'] == 'mock-v1'
        assert "Mock attempt 1" in result.attempts[0]
        assert mock.call_count == 1

        print(f"  Generated: {len(result.attempts)}a / {len(result.successes)}s / {len(result.failures)}f")
        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


async def test_comparison_mode():
    """Test multi-provider comparison with mock providers."""
    print("\nTesting comparison mode")
    print("-" * 40)

    try:
        config = ConfigManager()
        mock_a = MockProvider(model="model-a", variations=3)
        mock_a.name = "provider_a"
        mock_b = MockProvider(model="model-b", variations=3)
        mock_b.name = "provider_b"

        generator = FlavorTextGenerator(config, providers=[mock_a, mock_b])

        request = FlavorTextRequest(
            character_name="Goblin",
            character_race="Goblinoid",
            character_class="Monster",
            character_level=1,
            ability_name="Scimitar",
            ability_type="attack",
            variations=3,
        )

        results = await generator.generate_comparison(request, ["provider_a", "provider_b"])

        assert "provider_a" in results
        assert "provider_b" in results
        assert len(results["provider_a"].attempts) == 3
        assert len(results["provider_b"].attempts) == 3
        assert results["provider_a"].metadata['model'] == 'model-a'
        assert results["provider_b"].metadata['model'] == 'model-b'

        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


async def test_provider_error_handling():
    """Test that one failing provider doesn't kill comparison mode."""
    print("\nTesting provider error handling")
    print("-" * 40)

    try:
        config = ConfigManager()
        good = MockProvider(model="good-model", variations=3)
        good.name = "good"
        bad = MockProvider(model="bad-model", variations=3, should_fail=True)
        bad.name = "bad"

        generator = FlavorTextGenerator(config, providers=[good, bad])

        request = FlavorTextRequest(
            character_name="Goblin",
            character_race="Goblinoid",
            character_class="Monster",
            character_level=1,
            ability_name="Scimitar",
            ability_type="attack",
            variations=3,
        )

        results = await generator.generate_comparison(request, ["good", "bad"])

        # Good provider should succeed
        assert len(results["good"].attempts) == 3

        # Bad provider should have error metadata, not crash
        assert results["bad"].metadata.get('error') is not None
        assert len(results["bad"].attempts) == 0

        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


def test_prompt_generation():
    """Test that prompts include expected fields."""
    print("\nTesting prompt generation")
    print("-" * 40)

    try:
        config = ConfigManager()
        generator = FlavorTextGenerator(config, providers=[MockProvider()])

        request = FlavorTextRequest(
            character_name="Ancient Red Dragon",
            character_race="Dragon",
            character_class="Monster",
            character_level=20,
            ability_name="Fire Breath",
            ability_type="action",
            ability_description="The dragon exhales fire in a 90-foot cone.",
            style="heroic",
            variations=3,
            context_blob="This dragon guards a hoard of cursed gold.",
        )

        prompt = generator.generate_flavor_text_prompt(request)

        assert "Ancient Red Dragon" in prompt
        assert "Fire Breath" in prompt
        assert "heroic" in prompt
        assert "90-foot cone" in prompt
        assert "cursed gold" in prompt
        assert "3" in prompt  # variations count

        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


def test_cli_list_providers():
    """Test CLI --list-providers flag."""
    print("\nTesting CLI --list-providers")
    print("-" * 40)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "flavor_forge", "generate", "--list-providers"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).parent.parent / "src"),
        )
        assert result.returncode == 0, f"Exit code {result.returncode}: {result.stderr}"
        # Should at least mention ollama (always available)
        assert "ollama" in result.stdout.lower(), f"Output: {result.stdout}"

        print("  PASS")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


async def test_live_generation():
    """Test with real API (skipped if no keys configured)."""
    print("\nTesting live AI generation")
    print("-" * 40)

    config = ConfigManager()
    available = get_available_providers(config)
    # Only try providers with actual API keys (not ollama localhost)
    real_providers = [p for p in available if p != "ollama"]

    if not real_providers:
        print("  SKIP: No API keys configured")
        return None

    provider_name = real_providers[0]
    provider = get_provider(provider_name, config)
    generator = FlavorTextGenerator(config, providers=[provider])

    request = FlavorTextRequest(
        character_name="Goblin",
        character_race="Goblinoid",
        character_class="Monster",
        character_level=1,
        ability_name="Scimitar",
        ability_type="attack",
        ability_description="Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6+2) slashing damage.",
        style="dramatic",
        variations=3,
    )

    try:
        result = await generator.generate_flavor_text(request, provider_name=provider_name)
        print(f"  Provider: {provider_name}, Model: {result.metadata['model']}")
        print(f"  Generated {len(result.attempts)}a / {len(result.successes)}s / {len(result.failures)}f")
        if result.attempts:
            print(f"  Sample: {result.attempts[0]}")
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL ({provider_name}): {e}")
        return False


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def main():
    """Run all tests."""
    print("Flavor Forge — Generation & Provider Tests")
    print("=" * 60)

    results = {}

    # Sync tests
    results['provider_interface'] = test_provider_interface()
    results['available_providers'] = test_get_available_providers()
    results['get_provider'] = test_get_provider()
    results['prompt_generation'] = test_prompt_generation()
    results['cli_list_providers'] = test_cli_list_providers()

    # Async tests
    results['mock_generation'] = await test_mock_generation()
    results['comparison_mode'] = await test_comparison_mode()
    results['error_handling'] = await test_provider_error_handling()
    results['live_generation'] = await test_live_generation()

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
