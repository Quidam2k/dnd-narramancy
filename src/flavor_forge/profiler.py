"""Character profiling stubs for Flavor Forge.

The context_blob field is the key interface: it accepts free-text context
about a creature or character that gets appended to the generation prompt.
This serves both manual seasoning ("this skeleton was once a knight...") and
future automated context from the summarizer project.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CharacterProfile:
    character_name: str
    personality_traits: List[str] = field(default_factory=list)
    physical_descriptors: List[str] = field(default_factory=list)
    context_blob: Optional[str] = None
    answered_questions: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0


class CharacterizationProfiler:
    """Stub — all methods return empty/None."""

    def select_questions_for_character(self, character_name, num_questions=8,
                                       focus_categories=None):
        return []

    def create_character_profile(self, character_name, answered_questions):
        return CharacterProfile(character_name=character_name,
                                answered_questions=answered_questions)

    def save_character_profile(self, profile, file_path):
        pass

    def load_character_profile(self, file_path):
        return None


class CharacterProfileIntegrator:
    """Integrates character profile data into flavor text prompts."""

    def __init__(self, profiler: CharacterizationProfiler = None):
        self.profiler = profiler or CharacterizationProfiler()

    def enhance_flavor_text_prompt(self, request, profile: CharacterProfile) -> str:
        """Build prompt with profile context appended if available."""
        from .models import FlavorTextRequest

        # Build the base prompt (same as generator's default)
        style_descriptions = {
            'dramatic': 'dramatic, epic, and cinematic',
            'comedic': 'humorous, lighthearted, and amusing',
            'gritty': 'realistic, gritty, and visceral',
            'heroic': 'noble, inspiring, and heroic'
        }
        style_desc = style_descriptions.get(request.style, style_descriptions['dramatic'])
        description_part = f"\nDescription: {request.ability_description}" if request.ability_description else ""

        prompt = f"""You are a creative D&D flavor text generator. Create {request.variations} unique variations each for attempting, succeeding, and failing at using an ability.

Character: {request.character_name}, Level {request.character_level} {request.character_race} {request.character_class}
Ability: {request.ability_name} ({request.ability_type}){description_part}

Style: Make all descriptions {style_desc}.
"""

        # Append profile context if available
        if profile:
            context_parts = []
            if profile.personality_traits:
                context_parts.append(f"Personality: {', '.join(profile.personality_traits)}")
            if profile.physical_descriptors:
                context_parts.append(f"Appearance: {', '.join(profile.physical_descriptors)}")
            if profile.context_blob:
                context_parts.append(f"Context: {profile.context_blob}")
            if context_parts:
                prompt += "\nCharacter Details:\n" + "\n".join(f"- {p}" for p in context_parts) + "\n"

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
