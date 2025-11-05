#!/usr/bin/env python3
"""
Test script for Lyria music generation.

This script tests if the Lyria API is properly configured and working.

Usage:
    python backend/scripts/test_lyria.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.google_ai_client import lyria_client
from app.config import settings


async def test_lyria():
    """Test Lyria music generation."""

    print("=" * 80)
    print("Lyria Music Generation Test")
    print("=" * 80)
    print()

    # Verify configuration
    print("1. Verifying configuration...")
    print(f"   Project: {settings.google_cloud_project}")
    print(f"   Location: {settings.google_cloud_location}")
    print(f"   Credentials: {settings.google_application_credentials[:50]}..." if settings.google_application_credentials else "   Credentials: Not set")
    print()

    # Test music generation
    print("2. Testing music generation...")
    print("   Generating 10-second test jingle...")
    print()

    test_prompt = """
    Compose a 10-second upbeat jingle.

    STYLE: Uplifting, electronic, energetic
    MOOD: Happy and exciting
    FORMAT: Instrumental background music
    """

    try:
        audio_data = await lyria_client.generate_music(
            prompt=test_prompt,
            duration_seconds=10
        )

        if audio_data and len(audio_data) > 0:
            print(f"   ✅ SUCCESS: Generated {len(audio_data)} bytes of audio")
            print(f"   Audio format: WAV, 48kHz, ~30 seconds (Lyria fixed duration)")
            print()

            # Optionally save to file for testing
            output_file = "/tmp/test_jingle.wav"
            with open(output_file, "wb") as f:
                f.write(audio_data)
            print(f"   Saved test jingle to: {output_file}")
            print(f"   You can play it with: afplay {output_file} (macOS) or aplay {output_file} (Linux)")
            print()

            return True
        else:
            print("   ❌ FAILED: Lyria returned empty data")
            print("   Check the logs above for error details")
            print()
            return False

    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        print()
        print("   Full traceback:")
        print("   " + "\n   ".join(traceback.format_exc().split("\n")))
        print()
        return False


async def test_tts():
    """Test Text-to-Speech."""

    print("3. Testing Text-to-Speech...")
    print("   Generating test speech...")
    print()

    test_text = "This is a test of the Text-to-Speech system."

    try:
        audio_data = await lyria_client.synthesize_speech(
            text=test_text,
            voice="en-US-Studio-O"
        )

        if audio_data and len(audio_data) > 0:
            print(f"   ✅ SUCCESS: Generated {len(audio_data)} bytes of speech")
            print()

            # Save to file
            output_file = "/tmp/test_speech.mp3"
            with open(output_file, "wb") as f:
                f.write(audio_data)
            print(f"   Saved test speech to: {output_file}")
            print(f"   You can play it with: afplay {output_file} (macOS) or mpg123 {output_file} (Linux)")
            print()

            return True
        else:
            print("   ❌ FAILED: TTS returned empty data")
            print()
            return False

    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        print()
        print("   Full traceback:")
        print("   " + "\n   ".join(traceback.format_exc().split("\n")))
        print()
        return False


async def main():
    """Run all tests."""

    # Test Lyria music generation
    lyria_ok = await test_lyria()

    # Test TTS
    tts_ok = await test_tts()

    # Summary
    print("=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Lyria Music Generation: {'✅ PASS' if lyria_ok else '❌ FAIL'}")
    print(f"Text-to-Speech:         {'✅ PASS' if tts_ok else '❌ FAIL'}")
    print()

    if not lyria_ok:
        print("Common issues with Lyria:")
        print("  1. API not enabled: gcloud services enable aiplatform.googleapis.com")
        print("  2. Model not available in region: Try 'us-central1' location")
        print("  3. Permissions issue: Check if service account has 'aiplatform.endpoints.predict' permission")
        print("  4. Quota exceeded: Check Vertex AI quota in GCP console")
        print()

    if not tts_ok:
        print("Common issues with TTS:")
        print("  1. API not enabled: gcloud services enable texttospeech.googleapis.com")
        print("  2. Permissions issue: Check if service account has 'cloudtexttospeech.voices.list' permission")
        print()

    sys.exit(0 if (lyria_ok and tts_ok) else 1)


if __name__ == "__main__":
    asyncio.run(main())
