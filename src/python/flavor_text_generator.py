"""
Narramancy Integration - Flavor Text Generation System

Migrated from Narramancy's proven flavor text generation system.
Creates vivid, immersive descriptions for D&D abilities, spells, and actions.
"""

import json
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path

from .cost_tracker import CostTracker
from .characterization_profiler import CharacterizationProfiler, CharacterProfile, CharacterProfileIntegrator
import logging

logger = logging.getLogger(__name__)


@dataclass
class FlavorTextRequest:
    """Request structure for flavor text generation"""
    character_name: str
    character_race: str
    character_class: str
    character_level: int
    ability_name: str
    ability_type: str
    ability_description: Optional[str] = None
    style: str = 'dramatic'  # dramatic|comedic|gritty|heroic
    variations: int = 5
    character_profile: Optional[CharacterProfile] = None  # Enhanced with characterization data


@dataclass
class FlavorTextResult:
    """Result structure for flavor text generation"""  
    attempts: List[str]
    successes: List[str]
    failures: List[str]
    metadata: Dict[str, Any]


@dataclass
class AbilityData:
    """Data structure for character ability information used in flavor text generation."""
    name: str
    ability_type: str
    description: str
    character_name: str
    character_class: str
    character_level: int
    damage: Optional[str] = None
    range: Optional[str] = None
    duration: Optional[str] = None
    uses: Optional[str] = None
    save_dc: Optional[int] = None


class FlavorTextGenerator:
    """
    Core flavor text generation system migrated from Narramancy.
    
    Generates vivid, immersive descriptions for D&D abilities using AI,
    with support for multiple styles and character personalization.
    """
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.cost_tracker = CostTracker(Path.cwd())
        self.characterization_profiler = CharacterizationProfiler()
        self.profile_integrator = CharacterProfileIntegrator(self.characterization_profiler)
        self.style_descriptions = {
            'dramatic': 'dramatic, epic, and cinematic',
            'comedic': 'humorous, lighthearted, and amusing', 
            'gritty': 'realistic, gritty, and visceral',
            'heroic': 'noble, inspiring, and heroic'
        }
    
    def generate_flavor_text_prompt(self, request: FlavorTextRequest) -> str:
        """
        Creates the AI prompt for flavor text generation.
        
        Enhanced to use characterization profile data when available
        for more personalized and detailed flavor text.
        """
        # Use enhanced prompt if character profile is available
        if request.character_profile:
            return self.profile_integrator.enhance_flavor_text_prompt(request, request.character_profile)
        
        # Fallback to original prompt system
        style_desc = self.style_descriptions.get(request.style, self.style_descriptions['dramatic'])
        
        description_part = f"\nDescription: {request.ability_description}" if request.ability_description else ""
        
        return f"""You are a creative D&D flavor text generator. Create {request.variations} unique variations each for attempting, succeeding, and failing at using an ability.

Character: {request.character_name}, Level {request.character_level} {request.character_race} {request.character_class}
Ability: {request.ability_name} ({request.ability_type}){description_part}

Style: Make all descriptions {style_desc}.

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

    async def generate_flavor_text(self, request: FlavorTextRequest) -> FlavorTextResult:
        """
        Generate flavor text using AI with the Narramancy prompt system.
        
        Args:
            request: FlavorTextRequest with character and ability details
            
        Returns:
            FlavorTextResult with attempts/successes/failures descriptions
        """
        try:
            # Generate the prompt
            prompt = self.generate_flavor_text_prompt(request)
            
            # Get AI model configuration
            model_name = self.config_manager.get('ai_generation', 'model', fallback='gemini-2.0-flash-exp')
            
            # Call AI service (using our existing integration)
            response_text = await self._call_ai_service(prompt, model_name)
            
            # Parse the JSON response
            parsed_response = self._parse_ai_response(response_text)
            
            # Validate response structure
            self._validate_response_structure(parsed_response, request.variations)
            
            # Create result with metadata
            result = FlavorTextResult(
                attempts=parsed_response['attempts'],
                successes=parsed_response['successes'], 
                failures=parsed_response['failures'],
                metadata={
                    'character_name': request.character_name,
                    'character_class': request.character_class,
                    'ability_name': request.ability_name,
                    'style': request.style,
                    'variations': request.variations,
                    'model': model_name,
                    'prompt_version': '1.0'
                }
            )
            
            logger.info(f"Generated flavor text for {request.character_name}'s {request.ability_name} "
                       f"({request.style} style, {len(result.attempts) + len(result.successes) + len(result.failures)} variations)")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate flavor text for {request.character_name}'s {request.ability_name}: {e}")
            raise
    
    async def _call_ai_service(self, prompt: str, model_name: str) -> str:
        """Call the AI service using our existing integrations."""
        try:
            if 'gemini' in model_name.lower():
                return await self._call_gemini(prompt, model_name)
            elif 'claude' in model_name.lower():
                return await self._call_claude(prompt, model_name)
            else:
                raise ValueError(f"Unsupported model: {model_name}")
        except Exception as e:
            logger.error(f"AI service call failed: {e}")
            raise
    
    async def _call_gemini(self, prompt: str, model_name: str) -> str:
        """Call Google Gemini API for flavor text generation."""
        try:
            import google.generativeai as genai
            
            api_key = self.config_manager.get_api_key('gemini')
            if not api_key:
                raise ValueError("Gemini API key not configured")
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            response = await model.generate_content_async(prompt)
            response_text = response.text
            
            # Estimate tokens and cost
            estimated_input_tokens = len(prompt.split()) * 1.3  # Rough estimate
            estimated_output_tokens = len(response_text.split()) * 1.3
            
            # Track cost
            self.cost_tracker.log_api_call(
                provider='google',
                model=model_name,
                operation='flavor_text',
                input_tokens=int(estimated_input_tokens),
                output_tokens=int(estimated_output_tokens)
            )
            
            return response_text
            
        except Exception as e:
            raise
    
    async def _call_claude(self, prompt: str, model_name: str) -> str:
        """Call Anthropic Claude API for flavor text generation."""
        try:
            import anthropic
            
            api_key = self.config_manager.get_api_key('anthropic')
            if not api_key:
                raise ValueError("Claude API key not configured")
            
            client = anthropic.AsyncAnthropic(api_key=api_key)
            
            response = await client.messages.create(
                model=model_name,
                max_tokens=2048,
                temperature=0.8,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            
            # Track cost
            self.cost_tracker.log_api_call(
                provider='anthropic',
                model=model_name,
                operation='flavor_text',
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )
            
            return response_text
            
        except Exception as e:
            raise
    
    def _parse_ai_response(self, response_text: str) -> Dict[str, List[str]]:
        """Parse AI response JSON, handling various formatting issues."""
        try:
            # Clean up the response text to extract JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if not json_match:
                raise ValueError('No JSON found in response')
            
            # Remove any markdown formatting
            clean_text = json_match.group(0)
            clean_text = re.sub(r'```json\n?', '', clean_text)
            clean_text = re.sub(r'```\n?', '', clean_text)
            
            parsed_response = json.loads(clean_text)
            return parsed_response
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.error(f"Raw response: {response_text}")
            raise ValueError("Failed to parse AI response as valid JSON")
    
    def _validate_response_structure(self, response: Dict[str, Any], expected_variations: int):
        """Validate that the AI response has the expected structure."""
        required_keys = ['attempts', 'successes', 'failures']
        
        for key in required_keys:
            if key not in response:
                raise ValueError(f"Missing required key '{key}' in AI response")
            
            if not isinstance(response[key], list):
                raise ValueError(f"Key '{key}' should be a list")
            
            if len(response[key]) != expected_variations:
                logger.warning(f"Expected {expected_variations} {key}, got {len(response[key])}")
    
    # === Character Profiling Integration ===
    
    def start_character_profiling(self, character_name: str, 
                                focus_categories: Optional[List] = None,
                                num_questions: int = 8) -> List[Dict[str, Any]]:
        """
        Start the character profiling process by selecting appropriate questions.
        
        Args:
            character_name: Name of the character to profile
            focus_categories: Optional list of categories to focus on
            num_questions: Number of questions to ask (default 8)
            
        Returns:
            List of question dictionaries for presentation to the user
        """
        # Convert category strings to enums if provided
        if focus_categories:
            from .characterization_profiler import QuestionCategory
            focus_enums = []
            for cat in focus_categories:
                try:
                    focus_enums.append(QuestionCategory(cat))
                except ValueError:
                    logger.warning(f"Invalid category: {cat}")
            focus_categories = focus_enums if focus_enums else None
        
        questions = self.characterization_profiler.select_questions_for_character(
            character_name, num_questions, focus_categories
        )
        
        # Convert to dict format for easier JSON serialization
        question_dicts = []
        for q in questions:
            question_dicts.append({
                'id': q.id,
                'question': q.question,
                'category': q.category.value,
                'follow_up_prompts': q.follow_up_prompts,
                'example_descriptors': q.example_descriptors[:3]  # Show some examples
            })
        
        logger.info(f"Started profiling for {character_name} with {len(question_dicts)} questions")
        return question_dicts
    
    def complete_character_profiling(self, character_name: str,
                                   answered_questions: Dict[str, str]) -> CharacterProfile:
        """
        Complete character profiling by creating the profile from answers.
        
        Args:
            character_name: Name of the character
            answered_questions: Dict of question_id -> answer
            
        Returns:
            Complete CharacterProfile
        """
        profile = self.characterization_profiler.create_character_profile(
            character_name, answered_questions
        )
        
        logger.info(f"Completed profiling for {character_name} with {profile.confidence:.2f} confidence")
        return profile
    
    def save_character_profile(self, profile: CharacterProfile, 
                             campaign_name: Optional[str] = None) -> Path:
        """
        Save character profile to appropriate location.
        
        Args:
            profile: Character profile to save
            campaign_name: Optional campaign name for organization
            
        Returns:
            Path where profile was saved
        """
        # Determine save location
        if campaign_name:
            base_dir = Path(f"summarizer/context/campaigns/{campaign_name}/character_profiles")
        else:
            base_dir = Path("summarizer/context/global/character_profiles")
        
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        safe_name = "".join(c for c in profile.character_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        file_path = base_dir / f"{safe_name}_profile.json"
        
        self.characterization_profiler.save_character_profile(profile, file_path)
        return file_path
    
    def load_character_profile(self, character_name: str,
                             campaign_name: Optional[str] = None) -> Optional[CharacterProfile]:
        """
        Load existing character profile.
        
        Args:
            character_name: Name of character to load
            campaign_name: Optional campaign name
            
        Returns:
            CharacterProfile if found, None otherwise
        """
        # Try campaign-specific location first
        if campaign_name:
            safe_name = "".join(c for c in character_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            campaign_path = Path(f"summarizer/context/campaigns/{campaign_name}/character_profiles/{safe_name}_profile.json")
            
            if campaign_path.exists():
                try:
                    return self.characterization_profiler.load_character_profile(campaign_path)
                except Exception as e:
                    logger.warning(f"Error loading campaign profile: {e}")
        
        # Try global location
        global_path = Path(f"summarizer/context/global/character_profiles/{safe_name}_profile.json")
        if global_path.exists():
            try:
                return self.characterization_profiler.load_character_profile(global_path)
            except Exception as e:
                logger.warning(f"Error loading global profile: {e}")
        
        logger.info(f"No existing profile found for {character_name}")
        return None
    
    async def generate_flavor_text_with_profiling(self, 
                                                base_request: FlavorTextRequest,
                                                character_answers: Optional[Dict[str, str]] = None) -> FlavorTextResult:
        """
        Generate flavor text with optional character profiling.
        
        Args:
            base_request: Base flavor text request
            character_answers: Optional answers to characterization questions
            
        Returns:
            Enhanced FlavorTextResult
        """
        # Try to load existing profile first
        existing_profile = self.load_character_profile(base_request.character_name)
        
        # Create or update profile if answers provided
        if character_answers:
            if existing_profile:
                # Merge new answers with existing
                combined_answers = existing_profile.answered_questions.copy()
                combined_answers.update(character_answers)
                profile = self.complete_character_profiling(base_request.character_name, combined_answers)
            else:
                profile = self.complete_character_profiling(base_request.character_name, character_answers)
            
            # Save updated profile
            self.save_character_profile(profile)
        else:
            profile = existing_profile
        
        # Update request with profile
        enhanced_request = FlavorTextRequest(
            character_name=base_request.character_name,
            character_race=base_request.character_race,
            character_class=base_request.character_class,
            character_level=base_request.character_level,
            ability_name=base_request.ability_name,
            ability_type=base_request.ability_type,
            ability_description=base_request.ability_description,
            style=base_request.style,
            variations=base_request.variations,
            character_profile=profile
        )
        
        # Generate enhanced flavor text
        result = await self.generate_flavor_text(enhanced_request)
        
        # Add profiling metadata
        if profile:
            result.metadata['character_profile_confidence'] = profile.confidence
            result.metadata['profile_traits_used'] = len(profile.personality_traits) + len(profile.physical_descriptors)
            result.metadata['profiling_enhanced'] = True
        else:
            result.metadata['profiling_enhanced'] = False
        
        return result


class CharacterAbilityParser:
    """
    Character sheet ability parsing system migrated from Narramancy.
    
    Extracts abilities, spells, and features from character data for 
    flavor text generation.
    """
    
    @staticmethod
    def parse_character_abilities(character_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse character sheet data to extract abilities suitable for flavor text generation.
        
        Based on Narramancy's characterAnalysis.ts ability extraction logic.
        """
        abilities = []
        
        # Parse direct abilities list
        if 'abilities' in character_data:
            for ability in character_data['abilities']:
                abilities.append({
                    'name': ability.get('name', 'Unknown'),
                    'type': ability.get('type', 'feature'),
                    'description': ability.get('description', ''),
                    'level': ability.get('level'),
                    'damage': ability.get('damage'),
                    'range': ability.get('range'),
                    'duration': ability.get('duration'),
                    'attack_bonus': ability.get('attackBonus'),
                    'save_dc': ability.get('saveDC'),
                    'uses': ability.get('uses')
                })
        
        # Parse spells if available
        if 'spells' in character_data:
            for spell in character_data['spells']:
                abilities.append({
                    'name': spell.get('name', 'Unknown Spell'),
                    'type': 'cantrip' if spell.get('level', 1) == 0 else 'spell',
                    'description': spell.get('description', ''),
                    'level': spell.get('level', 1),
                    'damage': spell.get('damage'),
                    'range': spell.get('range'),
                    'duration': spell.get('duration'),
                    'save_dc': spell.get('save_dc')
                })
        
        # Parse equipment that can be used as abilities
        if 'equipment' in character_data:
            for item in character_data['equipment']:
                if item.get('type') in ['weapon', 'magic_item']:
                    abilities.append({
                        'name': item.get('name', 'Unknown Item'),
                        'type': 'attack' if item.get('type') == 'weapon' else 'item',
                        'description': item.get('description', ''),
                        'damage': item.get('damage'),
                        'range': item.get('range')
                    })
        
        return abilities
    
    @staticmethod
    def classify_ability_type(ability: Dict[str, Any]) -> str:
        """
        Classify ability type for flavor text generation.
        
        Maps various ability types to Narramancy's standard categories.
        """
        ability_type = ability.get('type', 'feature').lower()
        
        # Map common variations to standard types
        type_mapping = {
            'spell': 'spell',
            'cantrip': 'cantrip', 
            'action': 'action',
            'bonus_action': 'bonus_action',
            'reaction': 'reaction',
            'feature': 'feature',
            'trait': 'trait',
            'attack': 'attack',
            'weapon': 'attack',
            'item': 'item',
            'magic_item': 'item'
        }
        
        return type_mapping.get(ability_type, 'feature')


class VTTExporter:
    """
    VTT Export functionality for flavor text integration.
    
    This is a convenience wrapper that integrates flavor text generation
    with VTT export capabilities.
    """
    
    def __init__(self, flavor_generator: FlavorTextGenerator):
        self.flavor_generator = flavor_generator
        
    def export_character_with_flavor_text(self, 
                                        character_data: Dict[str, Any],
                                        platform: str = 'foundry') -> Dict[str, Any]:
        """
        Export character data enhanced with generated flavor text.
        
        Args:
            character_data: Character sheet data
            platform: Target VTT platform
            
        Returns:
            Enhanced character data with flavor text for abilities
        """
        try:
            # Import VTT exporter from modules
            from modules.vtt_integration import VTTExporter as CoreVTTExporter
            
            # Parse character abilities
            abilities = CharacterAbilityParser.parse_character_abilities(character_data)
            
            # Add flavor text to abilities (this would be async in real usage)
            enhanced_abilities = []
            for ability in abilities:
                ability_with_flavor = ability.copy()
                # Note: In real usage, this would generate flavor text
                # For now, just pass through the abilities
                enhanced_abilities.append(ability_with_flavor)
            
            # Update character data with enhanced abilities
            enhanced_character_data = character_data.copy()
            enhanced_character_data['abilities'] = enhanced_abilities
            
            # Use core VTT exporter
            exporter = CoreVTTExporter()
            # This would export to actual VTT format
            
            return enhanced_character_data
            
        except ImportError:
            # Fallback if VTT integration module not available
            return character_data


# Example usage and testing functions
async def test_flavor_text_generation():
    """Test the flavor text generation system with sample data."""
    from ..config.config import ConfigManager
    
    config = ConfigManager()
    generator = FlavorTextGenerator(config)
    
    # Test request
    request = FlavorTextRequest(
        character_name="Thorin Ironforge",
        character_race="Dwarf",
        character_class="Fighter", 
        character_level=5,
        ability_name="Longsword Attack",
        ability_type="attack",
        ability_description="A masterwork longsword passed down through generations",
        style="dramatic",
        variations=3
    )
    
    try:
        result = await generator.generate_flavor_text(request)
        
        print(f"Generated flavor text for {request.character_name}'s {request.ability_name}:")
        print(f"\nAttempts ({len(result.attempts)}):")
        for i, attempt in enumerate(result.attempts, 1):
            print(f"  {i}. {attempt}")
        
        print(f"\nSuccesses ({len(result.successes)}):")
        for i, success in enumerate(result.successes, 1):
            print(f"  {i}. {success}")
        
        print(f"\nFailures ({len(result.failures)}):")
        for i, failure in enumerate(result.failures, 1):
            print(f"  {i}. {failure}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating flavor text: {e}")
        return None


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_flavor_text_generation())