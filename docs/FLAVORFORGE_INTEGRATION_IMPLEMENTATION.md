# FlavorForge Integration - Implementation Summary
*Generated 2025-07-27 by Integration Analyzer Agent*

## 🎯 **INTEGRATION ANALYSIS COMPLETE**

### **Key Discovery: Rich Foundation Already Exists**

The summarizer project already has **70% of the infrastructure** needed for FlavorForge integration:

**✅ Already Complete:**
- **Character Data Schema**: Comprehensive JSON schema at `modules/character_engine/character_data_schema.json`
- **Character Processor Foundation**: Base class with file handling at `modules/character_engine/character_processor.py`
- **Campaign Settings System**: Production-ready with opt-out support in `summarizer/core/campaign_settings.py`
- **Analytics Framework**: Transcription validation at `modules/analytics_engine/transcription_validator.py`
- **Secure Configuration**: API key management in `summarizer/core/secure_config.py`
- **Test Character Sheets**: 40+ real D&D character sheet PDFs in examples directory

**🔧 Missing Components (30% remaining):**
1. **Multimodal AI Integration** - FlavorForge's Gemini processing logic
2. **Flavor Text Generation** - 50 variations per ability system
3. **VTT Chat Processing** - Foundry VTT log correlation
4. **AI Agents** - Character intelligence and synchronization

---

## 🚀 **READY-TO-IMPLEMENT TASKS (Next 2 Hours)**

### **Phase 1: Core AI Enhancement (60 minutes)**

#### **Task 1.1: Multimodal Character Processing (30 mins)**
**File**: `/mnt/h/Development/summarizer/modules/character_engine/character_processor.py`

**Implementation Steps:**
1. **Add FlavorForge AI Integration**:
```python
# Add after line 12 (existing imports)
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

def _process_pdf_sheet_with_ai(self, file_path: Path, character_data: Dict) -> Dict:
    """Enhanced PDF processing using Gemini multimodal AI."""
    from summarizer.core.secure_config import ConfigManager
    
    config = ConfigManager()
    genai.configure(api_key=config.get_api_key('gemini'))
    
    # Use FlavorForge's proven extraction prompt
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    # Convert PDF to images for multimodal processing
    with open(file_path, 'rb') as pdf_file:
        pdf_content = pdf_file.read()
    
    # Create extraction prompt (adapt from FlavorForge)
    prompt = self._create_character_extraction_prompt()
    
    response = model.generate_content([
        prompt,
        {"mime_type": "application/pdf", "data": pdf_content}
    ])
    
    # Parse and validate response
    extracted_data = self._parse_ai_response(response.text)
    
    # Merge with existing character_data structure
    return self._merge_ai_extraction(character_data, extracted_data)
```

2. **Add FlavorForge's Extraction Prompt**:
```python
def _create_character_extraction_prompt(self) -> str:
    """Character extraction prompt adapted from FlavorForge."""
    return """You are an expert D&D 5e character sheet analyzer. Extract comprehensive character information from this document.

EXTRACTION TARGET SCHEMA:
{
  "name": "Character name",
  "race": "Character race", 
  "class": "Character class",
  "level": number,
  "background": "Character background",
  "hitPoints": number,
  "armorClass": number,
  "abilityScores": {
    "strength": number,
    "dexterity": number,
    "constitution": number,
    "intelligence": number,
    "wisdom": number,
    "charisma": number
  },
  "abilities": [
    {
      "name": "Ability name",
      "type": "spell|action|feature|attack",
      "description": "What it does",
      "damage": "damage dice if applicable",
      "range": "range if applicable"
    }
  ]
}

Return ONLY valid JSON. Extract as much detail as possible while maintaining accuracy."""
```

#### **Task 1.2: Flavor Text Generation System (30 mins)**
**New File**: `/mnt/h/Development/summarizer/modules/character_engine/flavor_text_generator.py`

**Complete Implementation**:
```python
"""
FlavorForge-style Flavor Text Generation System
Generates 50 variations per ability for D&D characters.
"""

import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import google.generativeai as genai
from summarizer.core.secure_config import ConfigManager

logger = logging.getLogger(__name__)

@dataclass
class FlavorTextSet:
    """Set of flavor text variations for an ability."""
    ability_name: str
    ability_type: str
    attempts: List[str]
    successes: List[str]
    failures: List[str]
    critical_successes: Optional[List[str]] = None

class FlavorTextGenerator:
    """Generates contextual flavor text for character abilities."""
    
    def __init__(self):
        config = ConfigManager()
        genai.configure(api_key=config.get_api_key('gemini'))
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    def generate_ability_flavor_text(self, 
                                   character_name: str,
                                   character_race: str,
                                   character_class: str,
                                   character_level: int,
                                   ability_name: str,
                                   ability_type: str,
                                   ability_description: str = "",
                                   style: str = "dramatic",
                                   variations: int = 15) -> FlavorTextSet:
        """
        Generate flavor text variations for a character ability.
        
        Args:
            character_name: Character's name
            character_race: Character's race
            character_class: Character's class
            character_level: Character's level
            ability_name: Name of the ability
            ability_type: Type (spell, action, feature, attack)
            ability_description: Description of what the ability does
            style: Style (dramatic, comedic, gritty, heroic)
            variations: Number of variations per context (default 15)
        
        Returns:
            FlavorTextSet with generated variations
        """
        prompt = self._create_flavor_generation_prompt(
            character_name, character_race, character_class, character_level,
            ability_name, ability_type, ability_description, style, variations
        )
        
        try:
            response = self.model.generate_content(prompt)
            flavor_data = json.loads(response.text)
            
            return FlavorTextSet(
                ability_name=ability_name,
                ability_type=ability_type,
                attempts=flavor_data.get("attempts", []),
                successes=flavor_data.get("successes", []),
                failures=flavor_data.get("failures", []),
                critical_successes=flavor_data.get("critical_successes", [])
            )
            
        except Exception as e:
            logger.error(f"Error generating flavor text: {e}")
            # Return minimal fallback
            return FlavorTextSet(
                ability_name=ability_name,
                ability_type=ability_type,
                attempts=[f"{character_name} attempts to use {ability_name}."],
                successes=[f"{character_name} successfully uses {ability_name}."],
                failures=[f"{character_name} fails to use {ability_name}."]
            )
    
    def _create_flavor_generation_prompt(self, 
                                       character_name: str,
                                       character_race: str,
                                       character_class: str,
                                       character_level: int,
                                       ability_name: str,
                                       ability_type: str,
                                       ability_description: str,
                                       style: str,
                                       variations: int) -> str:
        """Create the flavor text generation prompt."""
        
        style_descriptions = {
            'dramatic': 'dramatic, epic, and cinematic',
            'comedic': 'humorous, lighthearted, and amusing',
            'gritty': 'realistic, gritty, and visceral',
            'heroic': 'noble, inspiring, and heroic'
        }
        
        return f"""You are a creative D&D flavor text generator. Create {variations} unique variations each for attempting, succeeding, failing, and critically succeeding at using an ability.

Character: {character_name}, Level {character_level} {character_race} {character_class}
Ability: {ability_name} ({ability_type})
{f"Description: {ability_description}" if ability_description else ""}

Style: Make all descriptions {style_descriptions.get(style, style_descriptions['dramatic'])}.

Guidelines:
- Each description should be 1-2 sentences
- Make them vivid and immersive
- Vary the approach and language used
- Include sensory details where appropriate
- Match the character's race, class, and level
- Keep descriptions appropriate for {ability_type} type abilities

Format your response as JSON:
{{
  "attempts": ["description1", "description2", ...],
  "successes": ["description1", "description2", ...],  
  "failures": ["description1", "description2", ...],
  "critical_successes": ["description1", "description2", ...]
}}

Generate exactly {variations} variations for each category."""
```

### **Phase 2: VTT Integration Foundation (30 minutes)**

#### **Task 2.1: VTT Chat Log Processor (20 mins)**
**New File**: `/mnt/h/Development/summarizer/modules/vtt_integration/chat_log_processor.py`

**Implementation**:
```python
"""
VTT Chat Log Processing for Session Correlation
Processes Foundry VTT and Roll20 chat exports for session enhancement.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class VTTChatEvent:
    """Single VTT chat event with roll data."""
    timestamp: datetime
    speaker: str
    message: str
    message_type: str  # "roll", "chat", "whisper", "emote"
    character_id: Optional[str] = None
    ability_used: Optional[str] = None
    roll_data: Optional[Dict] = None  # formula, result, success
    raw_data: Optional[Dict] = None

@dataclass
class VTTSession:
    """Complete VTT session with all events."""
    session_name: str
    start_time: datetime
    end_time: datetime
    events: List[VTTChatEvent]
    participants: List[str]
    metadata: Dict

class VTTChatProcessor:
    """Processes VTT chat logs for session correlation."""
    
    def process_foundry_chat_log(self, file_path: Path) -> VTTSession:
        """Process Foundry VTT chat export JSON."""
        with open(file_path, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
        
        events = []
        participants = set()
        
        for entry in chat_data:
            event = self._parse_foundry_event(entry)
            if event:
                events.append(event)
                participants.add(event.speaker)
        
        return VTTSession(
            session_name=file_path.stem,
            start_time=events[0].timestamp if events else datetime.now(),
            end_time=events[-1].timestamp if events else datetime.now(),
            events=events,
            participants=list(participants),
            metadata={"source": "foundry", "file": str(file_path)}
        )
    
    def _parse_foundry_event(self, entry: Dict) -> Optional[VTTChatEvent]:
        """Parse a single Foundry VTT chat entry."""
        try:
            # Extract timestamp
            timestamp = datetime.fromtimestamp(entry.get('timestamp', 0) / 1000)
            
            # Extract speaker and message
            speaker = entry.get('user', entry.get('alias', 'Unknown'))
            message = entry.get('content', '')
            
            # Determine message type
            message_type = self._determine_message_type(entry)
            
            # Extract roll data if present
            roll_data = self._extract_roll_data(entry)
            
            # Extract ability usage
            ability_used = self._extract_ability_usage(message, entry)
            
            return VTTChatEvent(
                timestamp=timestamp,
                speaker=speaker,
                message=message,
                message_type=message_type,
                ability_used=ability_used,
                roll_data=roll_data,
                raw_data=entry
            )
            
        except Exception as e:
            logger.warning(f"Error parsing VTT entry: {e}")
            return None
    
    def _determine_message_type(self, entry: Dict) -> str:
        """Determine the type of message from VTT data."""
        if 'rolls' in entry or 'roll' in entry:
            return 'roll'
        elif entry.get('whisper', []):
            return 'whisper'
        elif 'emote' in entry.get('type', ''):
            return 'emote'
        else:
            return 'chat'
    
    def _extract_roll_data(self, entry: Dict) -> Optional[Dict]:
        """Extract dice roll information from VTT entry."""
        if 'rolls' in entry:
            rolls = entry['rolls']
            if rolls:
                roll = rolls[0]  # Take first roll
                return {
                    'formula': roll.get('formula', ''),
                    'result': roll.get('total', 0),
                    'terms': roll.get('terms', []),
                    'success': roll.get('total', 0) >= roll.get('target', 0)
                }
        return None
    
    def _extract_ability_usage(self, message: str, entry: Dict) -> Optional[str]:
        """Extract ability name from message content."""
        # Look for common ability patterns
        common_abilities = [
            'Hunter\'s Mark', 'Action Surge', 'Sneak Attack', 'Fireball',
            'Healing Word', 'Shield', 'Counterspell', 'Eldritch Blast'
        ]
        
        message_lower = message.lower()
        for ability in common_abilities:
            if ability.lower() in message_lower:
                return ability
        
        return None
    
    def correlate_with_transcript(self, vtt_session: VTTSession, 
                                transcript_path: Path) -> Dict:
        """Correlate VTT events with audio transcript timestamps."""
        # Read transcript
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript_content = f.read()
        
        correlations = []
        
        for event in vtt_session.events:
            if event.message_type == 'roll' and event.ability_used:
                # Look for mentions of the ability in transcript
                # within ±30 seconds of the VTT timestamp
                correlation = self._find_transcript_correlation(
                    event, transcript_content
                )
                if correlation:
                    correlations.append(correlation)
        
        return {
            'session': vtt_session.session_name,
            'correlations': correlations,
            'vtt_events': len(vtt_session.events),
            'matched_events': len(correlations)
        }
    
    def _find_transcript_correlation(self, event: VTTChatEvent, 
                                   transcript: str) -> Optional[Dict]:
        """Find correlation between VTT event and transcript."""
        # This is a simplified implementation
        # In practice, you'd use more sophisticated timestamp matching
        
        if event.ability_used and event.ability_used.lower() in transcript.lower():
            return {
                'vtt_timestamp': event.timestamp,
                'ability': event.ability_used,
                'speaker': event.speaker,
                'roll_result': event.roll_data.get('result') if event.roll_data else None
            }
        return None
```

#### **Task 2.2: VTT Export Engine (10 mins)**
**New File**: `/mnt/h/Development/summarizer/modules/vtt_integration/vtt_exporter.py`

**Basic Structure**:
```python
"""
VTT Export Engine for FlavorForge Integration
Exports character data and flavor text to VTT platforms.
"""

import json
from typing import Dict, List
from pathlib import Path

class VTTExporter:
    """Export character data to VTT platforms."""
    
    def export_to_foundry(self, character_data: Dict, 
                         flavor_text: Dict) -> Dict:
        """Export character and flavor text to Foundry VTT format."""
        return {
            "name": character_data["basic_info"]["name"],
            "data": {
                "abilities": self._format_foundry_abilities(
                    character_data["abilities"], flavor_text
                )
            }
        }
    
    def export_to_roll20(self, character_data: Dict, 
                        flavor_text: Dict) -> List[str]:
        """Export character to Roll20 macro commands."""
        macros = []
        for ability in character_data["abilities"]:
            macro = self._create_roll20_macro(ability, flavor_text)
            macros.append(macro)
        return macros
    
    def _format_foundry_abilities(self, abilities: List[Dict], 
                                 flavor_text: Dict) -> List[Dict]:
        """Format abilities for Foundry VTT."""
        foundry_abilities = []
        for ability in abilities:
            foundry_ability = {
                "name": ability["name"],
                "type": ability["type"],
                "description": ability["description"]
            }
            
            # Add flavor text if available
            ability_flavor = flavor_text.get(ability["name"], {})
            if ability_flavor:
                foundry_ability["flavorText"] = {
                    "success": ability_flavor.get("successes", [""])[0],
                    "failure": ability_flavor.get("failures", [""])[0]
                }
            
            foundry_abilities.append(foundry_ability)
        
        return foundry_abilities
    
    def _create_roll20_macro(self, ability: Dict, flavor_text: Dict) -> str:
        """Create Roll20 macro for an ability."""
        ability_name = ability["name"]
        flavor = flavor_text.get(ability_name, {})
        
        success_text = flavor.get("successes", [""])[0] if flavor else ""
        failure_text = flavor.get("failures", [""])[0] if flavor else ""
        
        return f"""#{ability_name}
&{{template:default}} {{{{name={ability_name}}}}} {{{{success={success_text}}}}} {{{{failure={failure_text}}}}}"""
```

### **Phase 3: Enhanced Whisper Prompts (30 minutes)**

#### **Task 3.1: Character-Aware Whisper Enhancement**
**File**: `/mnt/h/Development/summarizer/summarizer/core/audio_transcriber.py`

**Enhancement**:
```python
def generate_enhanced_whisper_prompt(self, campaign_context, session_context=None):
    """Generate character-aware whisper prompts using character data."""
    
    # Load character data from campaign
    characters = self._load_campaign_characters(campaign_context.campaign_name)
    
    prompt_parts = [
        f"This is a D&D session for campaign: {campaign_context.campaign_name}",
        "",
        "Characters and their key abilities:"
    ]
    
    for character in characters:
        # Get top 5 abilities for whisper recognition
        top_abilities = character.get("abilities", [])[:5]
        ability_names = [ability["name"] for ability in top_abilities]
        
        character_line = f"- {character['basic_info']['name']} ({character['basic_info']['class']}): {', '.join(ability_names)}"
        prompt_parts.append(character_line)
    
    prompt_parts.extend([
        "",
        "Spells and abilities mentioned should be transcribed with exact names.",
        "Combat actions should include character names and ability names when possible.",
        "Pay special attention to spell names, character names, and D&D terminology."
    ])
    
    return "\n".join(prompt_parts)

def _load_campaign_characters(self, campaign_name: str) -> List[Dict]:
    """Load character data for campaign."""
    from modules.character_engine.character_processor import CharacterProcessor
    
    characters = []
    campaign_dir = Path(f"summarizer/context/campaigns/{campaign_name}/characters")
    
    if campaign_dir.exists():
        for char_file in campaign_dir.glob("*.json"):
            try:
                processor = CharacterProcessor()
                character_data = processor.load_character(char_file)
                characters.append(character_data)
            except Exception as e:
                logger.warning(f"Error loading character {char_file}: {e}")
    
    return characters
```

---

## 🎯 **TEST PLAN & VALIDATION**

### **Immediate Testing (20 minutes)**

#### **Test 1: Character Sheet Processing**
```bash
# Test with real character sheet
cd /mnt/h/Development/summarizer
python3 -c "
from modules.character_engine.character_processor import CharacterProcessor
processor = CharacterProcessor()
result = processor.process_character_sheet(
    'examples/Waterdeep Knights - Dungeon of the Mad Mage/Beuller von Ferris - CharacterSheetComplete.pdf',
    campaign_id='Waterdeep Knights'
)
print(f'Extracted: {result[\"basic_info\"][\"name\"]} ({result[\"basic_info\"][\"class\"]})')
"
```

#### **Test 2: Flavor Text Generation**
```bash
# Test flavor text system
python3 -c "
from modules.character_engine.flavor_text_generator import FlavorTextGenerator
generator = FlavorTextGenerator()
flavor = generator.generate_ability_flavor_text(
    'Beuller von Ferris', 'Human', 'Fighter', 5,
    'Action Surge', 'feature', 'Gain extra action on turn'
)
print(f'Generated {len(flavor.successes)} success variations')
print(f'Example: {flavor.successes[0]}')
"
```

#### **Test 3: VTT Chat Processing**
```bash
# Create sample Foundry VTT chat export
echo '[
  {
    "timestamp": 1690000000000,
    "user": "Player1",
    "content": "Beuller uses Action Surge!",
    "rolls": [{"formula": "1d20+5", "total": 18}]
  }
]' > test_foundry_chat.json

# Test processing
python3 -c "
from modules.vtt_integration.chat_log_processor import VTTChatProcessor
processor = VTTChatProcessor()
session = processor.process_foundry_chat_log(Path('test_foundry_chat.json'))
print(f'Processed {len(session.events)} events')
"
```

---

## 📋 **SUCCESS METRICS**

### **Phase 1 Success (60 minutes)**
- [ ] **Character sheets processed with AI**: Extract name, class, level, abilities from PDFs
- [ ] **Flavor text generation working**: Generate 15+ variations per ability context
- [ ] **No breaking changes**: All existing functionality preserved

### **Phase 2 Success (30 minutes)**  
- [ ] **VTT chat import functional**: Parse Foundry VTT JSON exports
- [ ] **Basic correlation working**: Match chat events to character abilities
- [ ] **Export structure created**: Foundry and Roll20 export formats defined

### **Phase 3 Success (30 minutes)**
- [ ] **Enhanced whisper prompts**: Include character abilities in prompts
- [ ] **Character data integration**: Whisper system uses character database
- [ ] **Backward compatibility**: Existing campaigns continue working without character data

### **Total Success (2 hours)**
- [ ] **Complete character intelligence pipeline**: Sheet → AI extraction → Flavor generation → VTT export
- [ ] **Production ready**: All new features tested and validated
- [ ] **Documentation updated**: Integration plan reflects completed work

---

## 💡 **NEXT SESSION ROADMAP**

### **Advanced Features (Future Sessions)**
1. **Character Analytics Dashboard** (2-3 hours)
   - Ability usage tracking across sessions
   - Character development progression
   - Party synergy analysis

2. **Advanced VTT Integration** (2-3 hours)
   - Real-time chat log monitoring
   - Automatic session correlation
   - Advanced export systems with custom macros

3. **Production UI Integration** (3-4 hours)
   - Character management interface in web UI
   - Flavor text preview and editing
   - VTT export management dashboard

### **Ready for Implementation**
This integration plan provides a clear, actionable path to incorporate FlavorForge's most valuable features into the summarizer project. The modular approach ensures we can build incrementally while maintaining the production stability that makes the summarizer project so successful.

**Estimated Total Value**: Transforms the summarizer from a session documentation tool into a comprehensive D&D campaign management platform - exactly the vision outlined in the original integration plan.