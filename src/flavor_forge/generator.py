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

        # Pronoun guidance based on creature type
        creature_type = (request.character_race or '').lower()
        if 'humanoid' in creature_type:
            prompt += "\nUse they/them pronouns for the creature.\n"
        else:
            prompt += "\nRefer to the creature as 'it'.\n"

        prompt += f"""
Guidelines:
- Each entry is exactly THREE short evocative phrases separated by " — "
- Each phrase is 2-4 words: a sensory snapshot, action beat, or emotional flash
- Total per entry: 8-12 words across the three phrases
- NOT full sentences. Fragments. No articles, no filler, no narration
- A DM will glance at this and grab one or two phrases to weave into their narration
- Vary imagery, senses, and word choices across entries
- Match the character's race, class, and level
- Keep descriptions appropriate for {request.ability_type} type abilities
- Example format: "blade hums eager — sidestep, fluid — cold eyes lock"
- Another example: "steel catches torchlight — sharp exhale — lunges low"

Format your response as JSON:
{{
  "attempts": ["phrase — phrase — phrase", ...],
  "successes": ["phrase — phrase — phrase", ...],
  "failures": ["phrase — phrase — phrase", ...]
}}

Generate exactly {request.variations} variations for each category (attempts, successes, failures)."""

        return prompt

    def generate_conditional_prompt(self, request: FlavorTextRequest, category: str, count: int = 5) -> str:
        """Create a prompt for conditional flavor categories (crit/fumble/barely)."""
        style_desc = self.STYLE_DESCRIPTIONS.get(request.style, self.STYLE_DESCRIPTIONS['dramatic'])
        description_part = f"\nDescription: {request.ability_description}" if request.ability_description else ""

        category_guidance = {
            'crits': (
                "Generate critical hit / natural 20 flavor text. "
                "These are devastating, emphatic, overwhelming — the hit that changes everything. "
                "The attack connects perfectly. Maximum impact. The crowd gasps."
            ),
            'fumbles': (
                "Generate natural 1 / fumble flavor text. "
                "These are whiffs, overextensions, stumbles — NOT necessarily dropping a weapon. "
                "The attack goes wrong. Embarrassing, awkward, or just plain unlucky. "
                "Keep it varied — sometimes comical, sometimes painful, sometimes just a miss."
            ),
            'barely_hits': (
                "Generate 'barely hits' flavor text — the attack JUST scrapes by. "
                "Glancing blows, last-second adjustments, the hit that almost wasn't. "
                "The margin was razor-thin. Lucky. Scraped armor. Caught a gap in the defense."
            ),
            'barely_misses': (
                "Generate 'barely misses' flavor text — SO close but not quite. "
                "Hair's breadth dodges, sparks off armor, the miss that stings. "
                "Almost had it. Frustrating. The target flinches even though it missed."
            ),
        }

        guidance = category_guidance.get(category, "Generate flavor text.")

        prompt = f"""You are a creative D&D flavor text generator. {guidance}

Character: {request.character_name}, Level {request.character_level} {request.character_race} {request.character_class}
Ability: {request.ability_name} ({request.ability_type}){description_part}

Style: Make all descriptions {style_desc}.
"""
        if request.context_blob:
            prompt += f"\nAdditional Context: {request.context_blob}\n"

        creature_type = (request.character_race or '').lower()
        if 'humanoid' in creature_type:
            prompt += "\nUse they/them pronouns for the creature.\n"
        else:
            prompt += "\nRefer to the creature as 'it'.\n"

        prompt += f"""
Guidelines:
- Each entry is exactly THREE short evocative phrases separated by " — "
- Each phrase is 2-4 words: a sensory snapshot, action beat, or emotional flash
- Total per entry: 8-12 words across the three phrases
- NOT full sentences. Fragments. No articles, no filler, no narration
- A DM will glance at this and grab one or two phrases to weave into their narration
- Vary imagery, senses, and word choices across entries
- Match the character's race, class, and level
- Example format: "blade hums eager — sidestep, fluid — cold eyes lock"

Format your response as JSON:
{{
  "entries": ["phrase — phrase — phrase", ...]
}}

Generate exactly {count} variations."""
        return prompt

    def generate_bloodied_prompt(self, request: FlavorTextRequest, count: int = 5) -> str:
        """Create a prompt for bloodied-threshold flavor text (creature-wide, not per-ability)."""
        style_desc = self.STYLE_DESCRIPTIONS.get(request.style, self.STYLE_DESCRIPTIONS['dramatic'])

        prompt = f"""You are a creative D&D flavor text generator. Generate "bloodied" flavor text — the moment a creature crosses half HP for the first time in combat.

This is NOT about a specific ability. This is about the creature's overall state changing: it's hurt, weakened, pushed to its limit. Blood, pain, desperation, or fury.

Character: {request.character_name}, Level {request.character_level} {request.character_race} {request.character_class}

Style: Make all descriptions {style_desc}.
"""
        if request.context_blob:
            prompt += f"\nAdditional Context: {request.context_blob}\n"

        creature_type = (request.character_race or '').lower()
        if 'humanoid' in creature_type:
            prompt += "\nUse they/them pronouns for the creature.\n"
        else:
            prompt += "\nRefer to the creature as 'it'.\n"

        prompt += f"""
Guidelines:
- Each entry is exactly THREE short evocative phrases separated by " — "
- Each phrase is 2-4 words: a sensory snapshot, action beat, or emotional flash
- Total per entry: 8-12 words across the three phrases
- NOT full sentences. Fragments. No articles, no filler, no narration
- Focus on: visible wounds, changed posture, sounds of pain, blood, desperation, fury, fear
- Vary imagery across entries — don't repeat the same wound or reaction
- Example: "staggers, knee buckling — blood trails dark — snarls through clenched teeth"

Format your response as JSON:
{{
  "entries": ["phrase — phrase — phrase", ...]
}}

Generate exactly {count} variations."""
        return prompt

    async def generate_flavor_text(
        self, request: FlavorTextRequest, provider_name: Optional[str] = None,
        with_crits: bool = False, crit_count: int = 5,
    ) -> FlavorTextResult:
        """Generate flavor text using a single AI provider.

        Args:
            request: FlavorTextRequest with character and ability details
            provider_name: Specific provider to use (default: first available)
            with_crits: Also generate crit/fumble/barely_hits/barely_misses tables
            crit_count: Number of variations for conditional categories

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

        # Generate conditional tables for attack abilities
        if with_crits and request.ability_type == 'attack':
            for category in ('crits', 'fumbles', 'barely_hits', 'barely_misses'):
                try:
                    cond_prompt = self.generate_conditional_prompt(request, category, crit_count)
                    cond_data = await self._call_provider_simple(provider, cond_prompt, crit_count)
                    setattr(result, category, cond_data)
                    logger.info(f"Generated {len(cond_data)} {category} entries for {request.ability_name}")
                except Exception as e:
                    logger.warning(f"Failed to generate {category} for {request.ability_name}: {e}")

        logger.info(
            f"Generated flavor text for {request.character_name}'s {request.ability_name} "
            f"via {provider.name} ({request.style} style, "
            f"{len(result.attempts) + len(result.successes) + len(result.failures)} variations)"
        )
        return result

    async def generate_bloodied(
        self, request: FlavorTextRequest, provider_name: Optional[str] = None,
        count: int = 5,
    ) -> FlavorTextResult:
        """Generate bloodied-threshold flavor text for a creature.

        Returns a FlavorTextResult with entries in 'attempts' (the only category that matters).
        """
        if provider_name:
            providers = self._get_providers()
            if provider_name not in providers:
                provider = get_provider(provider_name, self.config_manager)
            else:
                provider = providers[provider_name]
        else:
            provider = self._get_default_provider()

        prompt = self.generate_bloodied_prompt(request, count)
        entries = await self._call_provider_simple(provider, prompt, count)

        return FlavorTextResult(
            attempts=entries,
            successes=[],
            failures=[],
            metadata={
                'character_name': request.character_name,
                'character_class': request.character_class,
                'ability_name': 'Bloodied',
                'ability_type': 'bloodied',
                'style': request.style,
                'variations': count,
                'model': provider.model,
                'provider': provider.name,
            }
        )

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

    async def _call_provider_simple(
        self, provider: AIProvider, prompt: str, expected_count: int,
    ) -> List[str]:
        """Call a provider for a simple {"entries": [...]} response."""
        result = await provider.generate(prompt)

        self.cost_tracker.log_api_call(
            provider=provider.name, model=provider.model, operation='flavor_text_conditional',
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        )

        parsed = self._parse_ai_response(result.text)
        entries = parsed.get('entries', [])
        if not isinstance(entries, list):
            raise ValueError("Expected 'entries' list in response")
        if len(entries) != expected_count:
            logger.warning(f"Expected {expected_count} entries, got {len(entries)}")
        return entries[:expected_count] if len(entries) > expected_count else entries

    async def _call_provider(
        self, provider: AIProvider, prompt: str, expected_variations: int,
    ) -> Dict[str, List[str]]:
        """Call a provider and parse/validate the response, retrying if too few results."""
        result = await provider.generate(prompt)

        self.cost_tracker.log_api_call(
            provider=provider.name, model=provider.model, operation='flavor_text',
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        )

        parsed = self._parse_ai_response(result.text)
        self._validate_response_structure(parsed, expected_variations)

        # Retry/top-up: if any category has fewer entries than expected, ask for more
        for attempt in range(3):
            shortfalls = {}
            for key in ('attempts', 'successes', 'failures'):
                got = len(parsed.get(key, []))
                if got < expected_variations:
                    shortfalls[key] = expected_variations - got

            if not shortfalls:
                break

            needed_str = ', '.join(f'{n} more {k}' for k, n in shortfalls.items())
            logger.info(f"Top-up attempt {attempt + 1}: requesting {needed_str}")

            topup_prompt = (
                f"You previously generated flavor text but some categories were short. "
                f"Please generate ONLY the following additional entries in the same style:\n"
            )
            for key, count in shortfalls.items():
                topup_prompt += f"- {count} more {key}\n"
            topup_prompt += (
                f"\nOriginal prompt context:\n{prompt}\n\n"
                f"Return ONLY the new entries as JSON:\n"
                f'{{"attempts": [...], "successes": [...], "failures": [...]}}\n'
                f"Include empty arrays for categories that don't need more entries."
            )

            try:
                topup_result = await provider.generate(topup_prompt)
                self.cost_tracker.log_api_call(
                    provider=provider.name, model=provider.model, operation='flavor_text_topup',
                    input_tokens=topup_result.input_tokens, output_tokens=topup_result.output_tokens,
                )
                topup_parsed = self._parse_ai_response(topup_result.text)
                for key in ('attempts', 'successes', 'failures'):
                    if key in topup_parsed and isinstance(topup_parsed[key], list):
                        parsed[key].extend(topup_parsed[key])
                        # Trim to exact count if we got too many
                        parsed[key] = parsed[key][:expected_variations]
            except Exception as e:
                logger.warning(f"Top-up attempt {attempt + 1} failed: {e}")
                break

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
        # Strip trailing commas before ] or } (common with local models)
        clean_text = re.sub(r',\s*([\]}])', r'\1', clean_text)

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
