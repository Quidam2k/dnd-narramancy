import * as functions from 'firebase-functions';
import * as admin from 'firebase-admin';
import { VertexAI } from '@google-cloud/vertexai';
import { v4 as uuidv4 } from 'uuid';

interface GenerateFlavorTextRequest {
  characterId: string;
  abilityId: string;
  abilityName: string;
  abilityType: string;
  characterName: string;
  characterRace: string;
  characterClass: string;
  characterLevel: number;
  abilityDescription?: string;
  style?: 'dramatic' | 'comedic' | 'gritty' | 'heroic';
  variations?: number;
}

interface FlavorTextResponse {
  success: boolean;
  flavorTextId?: string;
  descriptions?: {
    attempts: string[];
    successes: string[];
    failures: string[];
  };
  cost?: number;
  tokensUsed?: number;
  error?: string;
}

// Initialize Vertex AI
const vertexAI = new VertexAI({
  project: process.env.GOOGLE_CLOUD_PROJECT || 'flavorforge-project',
  location: 'us-central1',
});

const generateFlavorTextPrompt = (
  characterName: string,
  characterRace: string,
  characterClass: string,
  characterLevel: number,
  abilityName: string,
  abilityType: string,
  abilityDescription: string = '',
  style: string = 'dramatic',
  variations: number = 5
): string => {
  const styleDescriptions = {
    dramatic: 'dramatic, epic, and cinematic',
    comedic: 'humorous, lighthearted, and amusing',
    gritty: 'realistic, gritty, and visceral',
    heroic: 'noble, inspiring, and heroic'
  };

  return `You are a creative D&D flavor text generator. Create ${variations} unique variations each for attempting, succeeding, and failing at using an ability.

Character: ${characterName}, Level ${characterLevel} ${characterRace} ${characterClass}
Ability: ${abilityName} (${abilityType})
${abilityDescription ? `Description: ${abilityDescription}` : ''}

Style: Make all descriptions ${styleDescriptions[style as keyof typeof styleDescriptions] || styleDescriptions.dramatic}.

Guidelines:
- Each description should be 1-2 sentences
- Make them vivid and immersive
- Vary the approach and language used
- Include sensory details where appropriate
- Match the character's race, class, and level
- Keep descriptions appropriate for ${abilityType} type abilities

Format your response as JSON:
{
  "attempts": ["description1", "description2", ...],
  "successes": ["description1", "description2", ...],  
  "failures": ["description1", "description2", ...]
}

Generate exactly ${variations} variations for each category (attempts, successes, failures).`;
};

export const generateFlavorText = async (
  data: GenerateFlavorTextRequest,
  context: functions.https.CallableContext
): Promise<FlavorTextResponse> => {
  // Verify authentication
  if (!context.auth) {
    throw new functions.https.HttpsError(
      'unauthenticated',
      'User must be authenticated to generate flavor text'
    );
  }

  const userId = context.auth.uid;

  try {
    // Validate input
    if (!data.characterId || !data.abilityId || !data.abilityName) {
      throw new functions.https.HttpsError(
        'invalid-argument',
        'Missing required fields: characterId, abilityId, or abilityName'
      );
    }

    // Verify user owns the character
    const characterRef = admin.firestore().collection('characters').doc(data.characterId);
    const characterDoc = await characterRef.get();
    
    if (!characterDoc.exists) {
      throw new functions.https.HttpsError(
        'not-found',
        'Character not found'
      );
    }

    const characterData = characterDoc.data();
    if (characterData?.userId !== userId) {
      throw new functions.https.HttpsError(
        'permission-denied',
        'User does not own this character'
      );
    }

    // Get user data for usage limits
    const userRef = admin.firestore().collection('users').doc(userId);
    const userDoc = await userRef.get();
    const userData = userDoc.data();

    // Check subscription limits (simplified for MVP)
    const subscriptionTier = userData?.subscriptionTier || 'free';
    const maxVariations = subscriptionTier === 'free' ? 5 : 
                          subscriptionTier === 'basic' ? 50 : 50;
    
    const requestedVariations = Math.min(data.variations || 5, maxVariations);

    // Generate the prompt
    const prompt = generateFlavorTextPrompt(
      data.characterName,
      data.characterRace, 
      data.characterClass,
      data.characterLevel,
      data.abilityName,
      data.abilityType,
      data.abilityDescription,
      data.style || 'dramatic',
      requestedVariations
    );

    // Call Vertex AI Gemini
    const model = vertexAI.preview.getGenerativeModel({
      model: 'gemini-2.0-flash-exp',
      generationConfig: {
        temperature: 0.8,
        topP: 0.9,
        topK: 40,
        maxOutputTokens: 2048,
      },
    });

    const result = await model.generateContent(prompt);
    const response = result.response;
    const text = response.text();

    // Parse JSON response
    let parsedResponse;
    try {
      // Clean up the response text to extract JSON
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        throw new Error('No JSON found in response');
      }
      parsedResponse = JSON.parse(jsonMatch[0]);
    } catch (parseError) {
      functions.logger.error('Failed to parse AI response:', text);
      throw new functions.https.HttpsError(
        'internal',
        'Failed to parse AI response'
      );
    }

    // Validate response structure
    if (!parsedResponse.attempts || !parsedResponse.successes || !parsedResponse.failures) {
      throw new functions.https.HttpsError(
        'internal',
        'Invalid response structure from AI'
      );
    }

    // Calculate costs (simplified)
    const tokensUsed = response.usageMetadata?.totalTokenCount || 1500;
    const costPerToken = 0.000002; // Approximate cost for Gemini Flash
    const cost = tokensUsed * costPerToken;

    // Create flavor text document
    const flavorTextId = uuidv4();
    const flavorTextData = {
      id: flavorTextId,
      userId,
      characterId: data.characterId,
      abilityId: data.abilityId,
      abilityName: data.abilityName,
      abilityType: data.abilityType,
      descriptions: {
        attempts: parsedResponse.attempts || [],
        successes: parsedResponse.successes || [],
        failures: parsedResponse.failures || []
      },
      generationMetadata: {
        model: 'gemini-2.0-flash-exp',
        promptVersion: '1.0',
        tokensUsed,
        cost,
        generatedAt: admin.firestore.FieldValue.serverTimestamp()
      },
      exportFormats: {
        foundryVTT: {
          name: `${data.characterName} - ${data.abilityName}`
        }
      },
      userEdits: [],
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
      updatedAt: admin.firestore.FieldValue.serverTimestamp()
    };

    // Save to Firestore
    await admin.firestore()
      .collection('flavorTexts')
      .doc(flavorTextId)
      .set(flavorTextData);

    // Update user usage
    await userRef.update({
      'usage.descriptionsGenerated': admin.firestore.FieldValue.increment(1),
      updatedAt: admin.firestore.FieldValue.serverTimestamp()
    });

    // Log usage for billing
    await admin.firestore().collection('usage_logs').add({
      userId,
      operation: 'description_generation',
      resourcesUsed: {
        aiModel: 'gemini-2.0-flash-exp',
        tokens: tokensUsed
      },
      costs: {
        aiCost: cost,
        totalCost: cost
      },
      characterId: data.characterId,
      success: true,
      processingTimeMs: Date.now() - Date.now(), // Would need actual timing
      timestamp: admin.firestore.FieldValue.serverTimestamp()
    });

    return {
      success: true,
      flavorTextId,
      descriptions: parsedResponse,
      cost,
      tokensUsed
    };

  } catch (error) {
    functions.logger.error('Error generating flavor text:', error);
    
    if (error instanceof functions.https.HttpsError) {
      throw error;
    }

    // Log failed usage
    await admin.firestore().collection('usage_logs').add({
      userId,
      operation: 'description_generation',
      characterId: data.characterId,
      success: false,
      errorMessage: error instanceof Error ? error.message : 'Unknown error',
      timestamp: admin.firestore.FieldValue.serverTimestamp()
    });

    throw new functions.https.HttpsError(
      'internal',
      'Failed to generate flavor text'
    );
  }
};