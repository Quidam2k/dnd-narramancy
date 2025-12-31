#!/usr/bin/env python3
"""
Test script for the FlavorForge flavor text generation system.

This script tests the existing implementation to understand current capabilities.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from summarizer.core.flavor_text_generator import (
    FlavorTextGenerator, 
    FlavorTextRequest, 
    CharacterAbilityParser
)
from summarizer.config.settings import ConfigManager

async def test_flavor_text_system():
    """Test the current flavor text generation system."""
    print("🎲 Testing FlavorForge Flavor Text Generation System")
    print("=" * 60)
    
    try:
        # Initialize configuration
        config = ConfigManager()
        
        # Test if we have API keys configured
        gemini_key = config.get_api_key('gemini')
        claude_key = config.get_api_key('anthropic')
        
        print(f"📋 Configuration Status:")
        print(f"   Gemini API Key: {'✅ Configured' if gemini_key else '❌ Missing'}")
        print(f"   Claude API Key: {'✅ Configured' if claude_key else '❌ Missing'}")
        
        if not gemini_key and not claude_key:
            print("\n⚠️  No API keys configured. Cannot test AI generation.")
            print("   Configure an API key first: python3 main.py --help")
            return False
        
        # Initialize the generator
        generator = FlavorTextGenerator(config)
        print(f"\n🤖 FlavorTextGenerator initialized successfully")
        
        # Create test requests for different ability types
        test_requests = [
            FlavorTextRequest(
                character_name="Thorin Ironforge",
                character_race="Dwarf",
                character_class="Fighter",
                character_level=5,
                ability_name="Action Surge",
                ability_type="feature",
                ability_description="Push yourself beyond normal limits for a moment",
                style="dramatic",
                variations=3
            ),
            FlavorTextRequest(
                character_name="Lyralei Windwhisper",
                character_race="Elf",
                character_class="Ranger",
                character_level=3,
                ability_name="Hunter's Mark",
                ability_type="spell",
                ability_description="Choose a creature you can see within range. Until the spell ends, you deal an extra 1d6 damage to the target whenever you hit it with a weapon attack",
                style="heroic",
                variations=2
            )
        ]
        
        print(f"\n🧪 Testing flavor text generation with {len(test_requests)} abilities:")
        
        for i, request in enumerate(test_requests, 1):
            print(f"\n--- Test {i}: {request.character_name}'s {request.ability_name} ---")
            
            try:
                result = await generator.generate_flavor_text(request)
                
                print(f"✅ Generated {len(result.attempts)} attempts, {len(result.successes)} successes, {len(result.failures)} failures")
                print(f"   Style: {request.style}")
                print(f"   Model: {result.metadata.get('model', 'unknown')}")
                
                # Show one example from each category
                if result.attempts:
                    print(f"   📝 Attempt: {result.attempts[0]}")
                if result.successes:
                    print(f"   🎯 Success: {result.successes[0]}")
                if result.failures:
                    print(f"   ❌ Failure: {result.failures[0]}")
                    
            except Exception as e:
                print(f"❌ Failed to generate flavor text for {request.ability_name}: {e}")
                return False
        
        print(f"\n🎉 All flavor text generation tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_character_ability_parser():
    """Test the character ability parsing system."""
    print(f"\n🔍 Testing CharacterAbilityParser")
    print("-" * 40)
    
    # Sample character data
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
        parser = CharacterAbilityParser()
        abilities = parser.parse_character_abilities(sample_character)
        
        print(f"✅ Parsed {len(abilities)} abilities from character data:")
        for ability in abilities:
            ability_type = parser.classify_ability_type(ability)
            print(f"   • {ability['name']} ({ability_type})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error parsing character abilities: {e}")
        return False

async def main():
    """Main test function."""
    print("🚀 FlavorForge Integration Test Suite")
    print("=" * 60)
    
    # Test ability parser first (no API required)
    parser_success = test_character_ability_parser()
    
    # Test flavor text generation (requires API key)
    generator_success = await test_flavor_text_system()
    
    print(f"\n📊 Test Results:")
    print(f"   Character Parser: {'✅ Pass' if parser_success else '❌ Fail'}")
    print(f"   Flavor Generator: {'✅ Pass' if generator_success else '❌ Fail'}")
    
    if parser_success and generator_success:
        print(f"\n🎉 All tests passed! FlavorForge integration is working.")
        return True
    else:
        print(f"\n⚠️  Some tests failed. Check configuration and dependencies.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)