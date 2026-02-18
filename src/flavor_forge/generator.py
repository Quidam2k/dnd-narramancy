"""Core flavor text generation engine.

Generates vivid, immersive descriptions for D&D abilities using AI,
with support for multiple styles, character personalization, and
multi-provider comparison.
"""

import asyncio
import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from .models import FlavorTextRequest, FlavorTextResult
from .config import ConfigManager
from .cost_tracker import CostTracker
from .providers import AIProvider, ProviderResult, get_provider, get_available_providers

logger = logging.getLogger(__name__)


class FlavorTextGenerator:
    """Core flavor text generation system.

    Generates vivid, immersive descriptions for D&D abilities using AI,
    with support for multiple providers and comparison mode.
    """

    STYLE_DESCRIPTIONS = {
        'dramatic': 'dramatic, epic, and cinematic',
        'comedic': 'humorous, lighthearted, and amusing',
        'gritty': 'realistic, gritty, and visceral',
        'heroic': 'noble, inspiring, and heroic',
    }

    def __init__(self, config_manager: ConfigManager, providers: Optional[List[AIProvider]] = None):
        self.config_manager = config_manager
        self.cost_tracker = CostTracker(Path.cwd())

        if providers is not None:
            self._providers = {p.name: p for p in providers}
        else:
            self._providers = None  # lazy init from config on first use

    def _get_providers(self) -> Dict[str, AIProvider]:
        """Get provider dict, initializing from config if needed."""
        if self._providers is not None:
            return self._providers

        self._providers = {}
        for name in get_available_providers(self.config_manager):
            try:
                self._providers[name] = get_provider(name, self.config_manager)
            except ValueError:
                pass  # Skip unconfigured
        return self._providers

    def _get_default_provider(self) -> AIProvider:
        """Get the first available provider."""
        providers = self._get_providers()
        if not providers:
            raise ValueError(
                "No AI providers configured. Set GEMINI_API_KEY, ANTHROPIC_API_KEY, "
                "or OLLAMA_BASE_URL."
            )
        return next(iter(providers.values()))

    def generate_flavor_text_prompt(self, request: FlavorTextRequest) -> str:
        """Create the AI prompt for flavor text generation."""
        style_desc = self.STYLE_DESCRIPTIONS.get(request.style, self.STYLE_DESCRIPTIONS['dramatic'])
        description_part = f"\nDescription: {request.ability_description}" if request.ability_description else ""

        prompt = f"""You are a creative D&D flavor text generator. Create {request.variations} unique variations each for attempting, succeeding, and failing at using an ability.

Character: {request.character_name}, Level {request.character_level} {request.character_race} {request.character_class}
Ability: {request.ability_name} ({request.ability_type}){description_part}

Style: Make all descriptions {style_desc}.
"""

        if request.context_blob:
            prompt += f"\nAdditional Context: {request.context_blob}\n"

        prompt += f"""
Guidelines:
- Each description should be exactly 1 sentence, maximum 20 words
- Make them vivid but concise
- Vary the approach and language used
- Include one key sensory detail
- Match the character's race, class, and level
- Keep descriptions appropriate for {request.ability_type} type abilities

Format your response as JSON:
{{
  "attempts": ["description1", "description2", ...],
  "successes": ["description1", "description2", ...],
  "failures": ["description1", "description2", ...]
}}

Generate exactly {request.variations} variations for each category (attempts, successes, failures)."""

        return prompt

    async def generate_flavor_text(
        self, request: FlavorTextRequest, provider_name: Optional[str] = None,
    ) -> FlavorTextResult:
        """Generate flavor text using a single AI provider.

        Args:
            request: FlavorTextRequest with character and ability details
            provider_name: Specific provider to use (default: first available)

        Returns:
            FlavorTextResult with attempts/successes/failures descriptions
        """
        if provider_name:
            providers = self._get_providers()
            if provider_name not in providers:
                provider = get_provider(provider_name, self.config_manager)
            else:
                provider = providers[provider_name]
        else:
            provider = self._get_default_provider()

        prompt = self.generate_flavor_text_prompt(request)
        result_data = await self._call_provider(provider, prompt, request.variations)

        result = FlavorTextResult(
            attempts=result_data['attempts'],
            successes=result_data['successes'],
            failures=result_data['failures'],
            metadata={
                'character_name': request.character_name,
                'character_class': request.character_class,
                'ability_name': request.ability_name,
                'style': request.style,
                'variations': request.variations,
                'model': provider.model,
                'provider': provider.name,
                'prompt_version': '1.0',
            }
        )

        logger.info(
            f"Generated flavor text for {request.character_name}'s {request.ability_name} "
            f"via {provider.name} ({request.style} style, "
            f"{len(result.attempts) + len(result.successes) + len(result.failures)} variations)"
        )
        return result

    async def generate_comparison(
        self, request: FlavorTextRequest, provider_names: List[str],
    ) -> Dict[str, FlavorTextResult]:
        """Generate flavor text from multiple providers for comparison.

        Runs all providers concurrently. Individual provider failures don't
        kill the whole batch — failed providers get error metadata instead.

        Returns:
            Dict mapping provider name to FlavorTextResult (or error result).
        """
        prompt = self.generate_flavor_text_prompt(request)

        async def _run_one(name: str) -> tuple[str, FlavorTextResult]:
            try:
                providers = self._get_providers()
                if name in providers:
                    provider = providers[name]
                else:
                    provider = get_provider(name, self.config_manager)

                parsed = await self._call_provider(provider, prompt, request.variations)
                return name, FlavorTextResult(
                    attempts=parsed['attempts'],
                    successes=parsed['successes'],
                    failures=parsed['failures'],
                    metadata={
                        'character_name': request.character_name,
                        'ability_name': request.ability_name,
                        'style': request.style,
                        'model': provider.model,
                        'provider': name,
                    }
                )
            except Exception as e:
                logger.error(f"Provider {name} failed: {e}")
                return name, FlavorTextResult(
                    attempts=[], successes=[], failures=[],
                    metadata={'provider': name, 'error': str(e)},
                )

        tasks = [_run_one(name) for name in provider_names]
        pairs = await asyncio.gather(*tasks)
        return dict(pairs)

    async def _call_provider(
        self, provider: AIProvider, prompt: str, expected_variations: int,
    ) -> Dict[str, List[str]]:
        """Call a provider and parse/validate the response."""
        result = await provider.generate(prompt)

        self.cost_tracker.log_api_call(
            provider=provider.name, model=provider.model, operation='flavor_text',
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        )

        parsed = self._parse_ai_response(result.text)
        self._validate_response_structure(parsed, expected_variations)
        self._check_output_quality(parsed)
        return parsed

    def _parse_ai_response(self, response_text: str) -> Dict[str, List[str]]:
        """Parse AI response JSON, handling various formatting issues."""
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            raise ValueError('No JSON found in response')

        clean_text = json_match.group(0)
        clean_text = re.sub(r'```json\n?', '', clean_text)
        clean_text = re.sub(r'```\n?', '', clean_text)

        try:
            return json.loads(clean_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Raw response: {response_text}")
            raise ValueError("Failed to parse AI response as valid JSON")

    def _validate_response_structure(self, response: Dict[str, Any], expected_variations: int):
        """Validate that the AI response has the expected structure."""
        for key in ('attempts', 'successes', 'failures'):
            if key not in response:
                raise ValueError(f"Missing required key '{key}' in AI response")
            if not isinstance(response[key], list):
                raise ValueError(f"Key '{key}' should be a list")
            if len(response[key]) != expected_variations:
                logger.warning(f"Expected {expected_variations} {key}, got {len(response[key])}")

    def _check_output_quality(self, response: Dict[str, List[str]]):
        """Light quality checks on generated text (warnings only)."""
        for category, texts in response.items():
            if category not in ('attempts', 'successes', 'failures'):
                continue
            for i, text in enumerate(texts):
                words = text.split()
                if len(words) > 25:
                    logger.warning(
                        f"{category}[{i}] is {len(words)} words (target: <=20): {text[:60]}..."
                    )
                sentences = [s.strip() for s in text.split('.') if s.strip()]
                if len(sentences) > 2:
                    logger.warning(
                        f"{category}[{i}] has {len(sentences)} sentences (target: 1)"
                    )
