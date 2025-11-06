"""Gemini Live model and voice configuration.

This module defines all available Gemini Live models and voices
for the model/voice selection feature.

Voice organization:
- 30 voices total
- Grouped by personality (Professional, Energetic, Warm, Smooth, Casual)
- All voices work with native audio models
"""

from typing import Dict, List, Any

# Available Gemini Live Models
AVAILABLE_MODELS: Dict[str, Dict[str, Any]] = {
    "gemini-live-2.5-flash": {
        "name": "Gemini Live 2.5 Flash",
        "description": "Current stable release for production. Supports native audio, tool calling, and session resumption.",
        "features": [],
        "recommended": False
    },
    "gemini-live-2.5-flash-preview-native-audio": {
        "name": "Gemini Live 2.5 Flash Preview",
        "description": "Preview version with enhanced native audio. Supports enhanced audio quality, tool calling, and session resumption.",
        "features": [],
        "recommended": False
    },
    "gemini-live-2.5-flash-preview-native-audio-09-2025": {
        "name": "Gemini Live 2.5 Flash Preview (Sept 2025)",
        "description": "September 2025 preview with latest audio improvements. Supports latest audio features, tool calling, and session resumption.",
        "features": [],
        "recommended": True
    }
}

# Voice Groups - Organized by Personality
VOICE_GROUPS: Dict[str, Dict[str, Any]] = {
    "professional": {
        "label": "Clear & Professional",
        "voices": {
            "Kore": {"personality": "Firm", "description": "Firm, professional (default)"},
            "Charon": {"personality": "Informative", "description": "Informative, clear"},
            "Rasalgethi": {"personality": "Informative", "description": "Informative, knowledgeable"},
            "Orus": {"personality": "Firm", "description": "Firm, authoritative"},
            "Alnilam": {"personality": "Firm", "description": "Firm, steady"},
            "Iapetus": {"personality": "Clear", "description": "Clear, articulate"},
            "Erinome": {"personality": "Clear", "description": "Clear, precise"},
        }
    },
    "energetic": {
        "label": "Bright & Energetic",
        "voices": {
            "Puck": {"personality": "Upbeat", "description": "Upbeat, energetic"},
            "Fenrir": {"personality": "Excitable", "description": "Excitable, dynamic"},
            "Zephyr": {"personality": "Bright", "description": "Bright, cheerful"},
            "Autonoe": {"personality": "Bright", "description": "Bright, expressive"},
            "Laomedeia": {"personality": "Upbeat", "description": "Upbeat, lively"},
            "Sadachbia": {"personality": "Lively", "description": "Lively, animated"},
        }
    },
    "warm": {
        "label": "Warm & Friendly",
        "voices": {
            "Aoede": {"personality": "Breezy", "description": "Breezy, natural"},
            "Leda": {"personality": "Youthful", "description": "Youthful, friendly"},
            "Achird": {"personality": "Friendly", "description": "Friendly, warm"},
            "Sulafat": {"personality": "Warm", "description": "Warm, comforting"},
            "Callirrhoe": {"personality": "Easy-going", "description": "Easy-going, relaxed"},
            "Umbriel": {"personality": "Easy-going", "description": "Easy-going, calm"},
        }
    },
    "smooth": {
        "label": "Smooth & Sophisticated",
        "voices": {
            "Algieba": {"personality": "Smooth", "description": "Smooth, polished"},
            "Despina": {"personality": "Smooth", "description": "Smooth, refined"},
            "Achernar": {"personality": "Soft", "description": "Soft, gentle"},
            "Schedar": {"personality": "Even", "description": "Even, balanced"},
            "Gacrux": {"personality": "Mature", "description": "Mature, experienced"},
            "Sadaltager": {"personality": "Knowledgeable", "description": "Knowledgeable, wise"},
        }
    },
    "casual": {
        "label": "Casual & Approachable",
        "voices": {
            "Zubenelgenubi": {"personality": "Casual", "description": "Casual, relaxed"},
            "Vindemiatrix": {"personality": "Gentle", "description": "Gentle, soothing"},
            "Enceladus": {"personality": "Breathy", "description": "Breathy, soft"},
            "Algenib": {"personality": "Gravelly", "description": "Gravelly, textured"},
            "Pulcherrima": {"personality": "Forward", "description": "Forward, direct"},
        }
    }
}

# Default Configuration
DEFAULT_MODEL = "gemini-live-2.5-flash-preview-native-audio-09-2025"
DEFAULT_VOICE = "Kore"

# Flatten voice list for validation (all voice names across all groups)
ALL_VOICES: set[str] = set()
for group in VOICE_GROUPS.values():
    ALL_VOICES.update(group["voices"].keys())


def get_all_models() -> List[str]:
    """Get list of all available model IDs."""
    return list(AVAILABLE_MODELS.keys())


def get_all_voices() -> List[str]:
    """Get list of all available voice names."""
    return sorted(ALL_VOICES)


def is_valid_model(model: str) -> bool:
    """Check if model ID is valid."""
    return model in AVAILABLE_MODELS


def is_valid_voice(voice: str) -> bool:
    """Check if voice name is valid."""
    return voice in ALL_VOICES
