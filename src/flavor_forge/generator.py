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


# Shared writing rules appended to all prompts
_WRITING_RULES = """\
Rules:
- Each entry is a single evocative sentence, 8-12 words
- Write with natural internal phrase boundaries so a DM can use the whole sentence or grab a fragment
- Stay character-agnostic: use "it" (or "they" for humanoids). No creature names, no class references
- Stay target-agnostic: don't reference what's being hit or who's affected
- No game mechanics (HP, AC, damage dice). Pure fiction
- Avoid fantasy cliches ("mighty blow", "flashing steel") — find fresh imagery
- Vary sentence structure: mix fragments, dashes, commas, and full clauses
- Evoke, don't narrate. Sensory fragments over play-by-play"""

# Category distribution guidance for generating varied entries
def _sensory_distribution(count: int) -> str:
    """Build sensory category distribution guidance for a given entry count."""
    if count <= 8:
        return (
            "Distribute entries across these sensory categories (1 each):\n"
            "- Kinesthetic (body mechanics, movement)\n"
            "- Auditory (sounds of the action)\n"
            "- Visual/Cinematic (light, color, spatial framing)\n"
            "- Emotional/Expression (face, eyes, attitude, intent)\n"
            "- Tactile/Impact (vibration, resistance, texture)\n"
            "- Environmental (terrain, weather, debris)\n"
            "- Tempo/Rhythm (speed, pacing, timing)\n"
            "- Tactical/Spatial (positioning, geometry, openings)"
        )
    # For larger counts, scale proportionally
    base = count // 8
    remainder = count % 8
    cats = [
        ("Kinesthetic (body mechanics, movement)", base + (1 if remainder > 0 else 0)),
        ("Auditory (sounds of the action)", base + (1 if remainder > 1 else 0)),
        ("Visual/Cinematic (light, color, spatial framing)", base + (1 if remainder > 2 else 0)),
        ("Emotional/Expression (face, eyes, attitude, intent)", base + (1 if remainder > 3 else 0)),
        ("Tactile/Impact (vibration, resistance, texture)", base + (1 if remainder > 4 else 0)),
        ("Environmental (terrain, weather, debris)", base + (1 if remainder > 5 else 0)),
        ("Tempo/Rhythm (speed, pacing, timing)", base + (1 if remainder > 6 else 0)),
        ("Tactical/Spatial (positioning, geometry, openings)", base),
    ]
    lines = ["Distribute entries across these sensory categories:"]
    for desc, n in cats:
        lines.append(f"- {n} {desc}")
    return "\n".join(lines)


def _pronoun_guidance(creature_type: str) -> str:
    """Return pronoun instruction based on creature type."""
    if 'humanoid' in (creature_type or '').lower():
        return 'Use they/them pronouns.'
    return 'Use "it" as the pronoun.'


def _examples_for_event(event_type: str) -> str:
    """Return style examples appropriate for the event type."""
    examples = {
        'attack_attempt': (
            '- "A quick lunge, weight shifting forward — steel leads."\n'
            '- "It coils low, then unwinds in a single vicious arc."\n'
            '- "The blade traces a tight circle before committing to the thrust."'
        ),
        'attack_success': (
            '- "Steel whispers through leather, and something warm follows."\n'
            '- "The point finds the gap it was looking for — a wet crunch."\n'
            '- "Impact shudders up through the shaft and into its wrists."'
        ),
        'attack_failure': (
            '- "The swing carves empty air, momentum pulling it off-balance."\n'
            '- "A scrape of steel on stone where flesh should have been."\n'
            '- "It overcommits, and the opening closes before the blade arrives."'
        ),
        'crit': (
            '- "Everything aligns — angle, force, timing — and something breaks."\n'
            '- "The hit lands with the sound of certainty, deep and final."\n'
            '- "A perfect arc that ends exactly where it was always going to."'
        ),
        'fumble': (
            '- "The swing goes wide, dragging its whole body with it."\n'
            '- "A misstep turns the attack into an awkward stumble."\n'
            '- "The weapon catches on nothing, and balance deserts it completely."'
        ),
        'barely_hits': (
            '- "The tip catches a gap it didn\'t know was there — lucky."\n'
            '- "A scraping blow that almost wasn\'t, but was."\n'
            '- "It grazes through, more accident than aim."'
        ),
        'barely_misses': (
            '- "So close the air hisses between blade and skin."\n'
            '- "A hair\'s breadth — the target feels the wind of it."\n'
            '- "The strike passes close enough to lift fabric, nothing more."'
        ),
        'miss_dodge': (
            '- "The target flows aside like water around a stone."\n'
            '- "Quick feet carry it clear — the attack finds only air."\n'
            '- "A sidestep so smooth it looks rehearsed."'
        ),
        'miss_armor': (
            '- "Steel rings on steel — the armor does its job."\n'
            '- "The blow connects and skids, throwing sparks but drawing nothing."\n'
            '- "A solid hit that the plate turns aside with a dull clang."'
        ),
        'killing_blow': (
            '- "One last, unhurried strike — it was always going to end like this."\n'
            '- "The final blow lands with the weight of inevitability behind it."\n'
            '- "Something decisive in the swing, the kind that ends things."'
        ),
        'spell_attempt': (
            '- "Words tumble out, sharp and precise — the air bends."\n'
            '- "Fingers trace a pattern that leaves afterimages in the dark."\n'
            '- "Power builds behind the eyes, looking for a way out."'
        ),
        'bloodied': (
            '- "It staggers, one leg buckling — dark blood threads down."\n'
            '- "A wet, ragged breath escapes — something inside has shifted."\n'
            '- "The wound opens its posture, revealing how much it\'s hiding."'
        ),
        'death': (
            '- "It folds forward in slow motion, already gone before it lands."\n'
            '- "A last exhale, quiet and final — then just weight and stillness."\n'
            '- "The light behind its eyes gutters out like a spent candle."'
        ),
    }
    return examples.get(event_type, examples['attack_attempt'])


class FlavorTextGenerator:
    """Core flavor text generation system."""

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

    def _resolve_provider(self, provider_name: Optional[str] = None) -> AIProvider:
        """Resolve a provider by name, or return the default."""
        if provider_name:
            providers = self._get_providers()
            if provider_name in providers:
                return providers[provider_name]
            return get_provider(provider_name, self.config_manager)
        return self._get_default_provider()

    # ── Prompt Builders ──────────────────────────────────────────────

    def generate_flavor_text_prompt(self, request: FlavorTextRequest) -> str:
        """Create the AI prompt for flavor text generation (attempts/successes/failures)."""
        style_desc = self.STYLE_DESCRIPTIONS.get(request.style, self.STYLE_DESCRIPTIONS['dramatic'])
        description_part = f"\nAbility description: {request.ability_description}" if request.ability_description else ""
        n = request.variations
        distribution = _sensory_distribution(n)
        pronouns = _pronoun_guidance(request.character_race)

        # Pick examples based on ability type
        if request.ability_type == 'attack':
            ex_attempt = _examples_for_event('attack_attempt')
            ex_success = _examples_for_event('attack_success')
            ex_failure = _examples_for_event('attack_failure')
        elif request.ability_type in ('spell', 'cantrip'):
            ex_attempt = _examples_for_event('spell_attempt')
            ex_success = _examples_for_event('attack_success')
            ex_failure = _examples_for_event('attack_failure')
        else:
            ex_attempt = _examples_for_event('attack_attempt')
            ex_success = _examples_for_event('attack_success')
            ex_failure = _examples_for_event('attack_failure')

        prompt = f"""You are a creative D&D flavor text generator. Generate {n} unique entries each for ATTEMPTING, SUCCEEDING, and FAILING at using an ability.

Creature: {request.character_name} ({request.character_race}, CR {request.character_level})
Ability: {request.ability_name} ({request.ability_type}){description_part}
Style: {style_desc}
{pronouns}
"""
        if request.context_blob:
            prompt += f"Flavor guidance: {request.context_blob}\n"

        prompt += f"""
{distribution}

{_WRITING_RULES}

Examples of ATTEMPT entries:
{ex_attempt}

Examples of SUCCESS entries:
{ex_success}

Examples of FAILURE entries:
{ex_failure}

Format your response as JSON:
{{
  "attempts": ["...", ...],
  "successes": ["...", ...],
  "failures": ["...", ...]
}}

Generate exactly {n} entries per category ({n} attempts, {n} successes, {n} failures)."""
        return prompt

    def generate_conditional_prompt(self, request: FlavorTextRequest, category: str, count: int = 5) -> str:
        """Create a prompt for conditional flavor categories (crit/fumble/barely/killing_blow)."""
        style_desc = self.STYLE_DESCRIPTIONS.get(request.style, self.STYLE_DESCRIPTIONS['dramatic'])
        description_part = f"\nAbility description: {request.ability_description}" if request.ability_description else ""
        pronouns = _pronoun_guidance(request.character_race)

        category_guidance = {
            'crits': (
                "Generate CRITICAL HIT flavor text — natural 20, the perfect strike. "
                "Devastating, emphatic, overwhelming. Maximum impact. More dramatic than a regular hit, "
                "but still mid-fight — these are exclamation marks, not endings."
            ),
            'fumbles': (
                "Generate FUMBLE flavor text — natural 1, something goes wrong. "
                "Whiffs, overextensions, stumbles, misfires. NOT always dropping a weapon. "
                "Varied: sometimes comical, sometimes painful, sometimes just unlucky."
            ),
            'barely_hits': (
                "Generate BARELY HITS flavor text — the attack JUST scrapes by, razor-thin margin. "
                "Glancing blows, last-second adjustments, lucky angles. The hit that almost wasn't."
            ),
            'barely_misses': (
                "Generate BARELY MISSES flavor text — SO close but not quite. "
                "Hair's breadth from connecting. The target flinches. Frustrating. Almost."
            ),
            'miss_dodge': (
                "Generate DODGE flavor text — the target was too quick, too agile. "
                "Focus on the TARGET's evasion: sidesteps, ducks, flows aside. "
                "The attack never touched them. Not the attacker's fault — the target was just better."
            ),
            'miss_armor': (
                "Generate ARMOR DEFLECTION flavor text — the attack connected but armor held. "
                "Steel on steel, sparks, ringing metal, blade skidding off plate. "
                "Focus on the ARMOR doing its job. The hit landed but couldn't penetrate."
            ),
            'killing_blow': (
                "Generate KILLING BLOW flavor text — the finishing strike, the one that ends it. "
                "'How do you want to do this?' Cinematic conclusions: decisive, final, satisfying. "
                "These are ENDINGS, not mid-fight moments. The fight is over after this. "
                "Distinct from crits — crits are exclamation marks, killing blows are periods."
            ),
        }

        guidance = category_guidance.get(category, "Generate flavor text.")
        examples = _examples_for_event(category)
        distribution = _sensory_distribution(count)

        prompt = f"""You are a creative D&D flavor text generator. {guidance}

Creature: {request.character_name} ({request.character_race}, CR {request.character_level})
Ability: {request.ability_name} ({request.ability_type}){description_part}
Style: {style_desc}
{pronouns}
"""
        if request.context_blob:
            prompt += f"Flavor guidance: {request.context_blob}\n"

        prompt += f"""
{distribution}

{_WRITING_RULES}

Examples:
{examples}

Format your response as JSON:
{{
  "entries": ["...", ...]
}}

Generate exactly {count} entries."""
        return prompt

    def generate_bloodied_prompt(self, request: FlavorTextRequest, count: int = 5) -> str:
        """Create a prompt for bloodied-threshold flavor text."""
        style_desc = self.STYLE_DESCRIPTIONS.get(request.style, self.STYLE_DESCRIPTIONS['dramatic'])
        pronouns = _pronoun_guidance(request.character_race)
        distribution = _sensory_distribution(count)
        examples = _examples_for_event('bloodied')

        prompt = f"""You are a creative D&D flavor text generator. Generate BLOODIED flavor text — the moment a creature crosses half HP for the first time in combat.

This is NOT about a specific ability. This is about the creature's overall state changing: hurt, weakened, pushed to its limit. Blood, pain, desperation, or fury.

Creature: {request.character_name} ({request.character_race}, CR {request.character_level})
Style: {style_desc}
{pronouns}
"""
        if request.context_blob:
            prompt += f"Flavor guidance: {request.context_blob}\n"

        prompt += f"""
{distribution}

{_WRITING_RULES}
- Focus on: visible wounds, changed posture, sounds of pain, blood, desperation, fury, fear

Examples:
{examples}

Format your response as JSON:
{{
  "entries": ["...", ...]
}}

Generate exactly {count} entries."""
        return prompt

    def generate_death_prompt(self, request: FlavorTextRequest, count: int = 5) -> str:
        """Create a prompt for death flavor text — creature reaches 0 HP."""
        style_desc = self.STYLE_DESCRIPTIONS.get(request.style, self.STYLE_DESCRIPTIONS['dramatic'])
        pronouns = _pronoun_guidance(request.character_race)
        distribution = _sensory_distribution(count)
        examples = _examples_for_event('death')

        prompt = f"""You are a creative D&D flavor text generator. Generate DEATH flavor text — the moment a creature drops to 0 HP and falls.

This is creature-specific: how THIS creature dies. Complements the attacker's Killing Blow text (which is weapon-specific). A zombie crumbles differently than a dragon.

Creature: {request.character_name} ({request.character_race}, CR {request.character_level})
Style: {style_desc}
{pronouns}
"""
        if request.context_blob:
            prompt += f"Flavor guidance: {request.context_blob}\n"

        prompt += f"""
{distribution}

{_WRITING_RULES}
- Focus on: collapse, final sounds, stillness, light fading, the specific way THIS creature falls

Examples:
{examples}

Format your response as JSON:
{{
  "entries": ["...", ...]
}}

Generate exactly {count} entries."""
        return prompt

    # ── Generation Methods ───────────────────────────────────────────

    async def generate_flavor_text(
        self, request: FlavorTextRequest, provider_name: Optional[str] = None,
        with_crits: bool = False, crit_count: int = 5,
    ) -> FlavorTextResult:
        """Generate flavor text using a single AI provider."""
        provider = self._resolve_provider(provider_name)

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
                'prompt_version': '2.0',
            }
        )

        # Generate conditional tables for attack abilities
        if with_crits and request.ability_type == 'attack':
            for category in ('crits', 'fumbles', 'barely_hits', 'barely_misses', 'miss_dodge', 'miss_armor', 'killing_blow'):
                try:
                    cond_prompt = self.generate_conditional_prompt(request, category, crit_count)
                    cond_data = await self._call_provider_simple(provider, cond_prompt, crit_count)
                    setattr(result, category, cond_data)
                    logger.info(f"Generated {len(cond_data)} {category} entries for {request.ability_name}")
                except Exception as e:
                    logger.warning(f"Failed to generate {category} for {request.ability_name}: {e}")

        # Generate killing blow for non-attack damage-dealing abilities
        if with_crits and request.ability_type != 'attack' and _is_damage_dealing(request):
            try:
                kb_prompt = self.generate_conditional_prompt(request, 'killing_blow', crit_count)
                kb_data = await self._call_provider_simple(provider, kb_prompt, crit_count)
                result.killing_blow = kb_data
                logger.info(f"Generated {len(kb_data)} killing_blow entries for {request.ability_name}")
            except Exception as e:
                logger.warning(f"Failed to generate killing_blow for {request.ability_name}: {e}")

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
        """Generate bloodied-threshold flavor text for a creature."""
        provider = self._resolve_provider(provider_name)

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

    async def generate_death(
        self, request: FlavorTextRequest, provider_name: Optional[str] = None,
        count: int = 5,
    ) -> FlavorTextResult:
        """Generate death flavor text for a creature (0 HP moment)."""
        provider = self._resolve_provider(provider_name)

        prompt = self.generate_death_prompt(request, count)
        entries = await self._call_provider_simple(provider, prompt, count)

        return FlavorTextResult(
            attempts=entries,
            successes=[],
            failures=[],
            metadata={
                'character_name': request.character_name,
                'character_class': request.character_class,
                'ability_name': 'Death',
                'ability_type': 'death',
                'style': request.style,
                'variations': count,
                'model': provider.model,
                'provider': provider.name,
            }
        )

    async def generate_comparison(
        self, request: FlavorTextRequest, provider_names: List[str],
    ) -> Dict[str, FlavorTextResult]:
        """Generate flavor text from multiple providers for comparison."""
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

    # ── Provider Communication ───────────────────────────────────────

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
                        parsed[key] = parsed[key][:expected_variations]
            except Exception as e:
                logger.warning(f"Top-up attempt {attempt + 1} failed: {e}")
                break

        self._check_output_quality(parsed)
        return parsed

    # ── Parsing & Validation ─────────────────────────────────────────

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
            parsed = json.loads(clean_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Raw response: {response_text}")
            raise ValueError("Failed to parse AI response as valid JSON")

        # Sanitize: strip control characters (newlines, tabs) from string entries
        for key, val in parsed.items():
            if isinstance(val, list):
                parsed[key] = [
                    re.sub(r'[\x00-\x1f\x7f]', ' ', entry).strip()
                    if isinstance(entry, str) else entry
                    for entry in val
                ]

        return parsed

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
                if len(words) > 18:
                    logger.warning(
                        f"{category}[{i}] is {len(words)} words (target: 8-12): {text[:60]}..."
                    )


def _is_damage_dealing(request: FlavorTextRequest) -> bool:
    """Check if an ability deals damage based on its description."""
    if not request.ability_description:
        return False
    desc = request.ability_description.lower()
    return any(kw in desc for kw in ('damage', 'hit:', 'attack:', 'saving throw, taking'))
