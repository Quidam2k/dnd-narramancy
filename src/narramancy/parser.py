"""Character ability parsing for Narramancy.

Extracts abilities, spells, and features from character data
for flavor text generation.
"""

from typing import Dict, List, Any


class CharacterAbilityParser:
    """Character sheet ability parsing system.

    Extracts abilities, spells, and features from character data for
    flavor text generation.
    """

    @staticmethod
    def parse_character_abilities(character_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse character sheet data to extract abilities suitable for flavor text generation."""
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

        # Parse spells
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
        """Classify ability type for flavor text generation."""
        ability_type = ability.get('type', 'feature').lower()

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
