#!/usr/bin/env python
"""
Test script for Lyria music generation.

This script tests the Lyria API integration by generating a short music sample.

Usage:
    export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"
    export GOOGLE_CLOUD_PROJECT="your-project-id"
    export GOOGLE_CLOUD_LOCATION="us-central1"

    python scripts/test_lyria_music.py

The generated WAV file will be saved to /tmp/lyria_test_output.wav
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.google_ai_client import lyria_client
from app.config import settings


async def test_lyria_music_generation():
    """Test Lyria music generation with a simple prompt."""

    print("=" * 80)
    print("Lyria Music Generation Test")
    print("=" * 80)

    # Check configuration
    print("\n📋 Configuration:")
    print(f"  Project ID: {settings.google_cloud_project}")
    print(f"  Location: {settings.google_cloud_location}")
    print(f"  Credentials: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'Not set')}")

    if not settings.google_cloud_project:
        print("\n❌ ERROR: GOOGLE_CLOUD_PROJECT not set!")
        print("   Set it in .env or export GOOGLE_CLOUD_PROJECT=your-project-id")
        return

    if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        print("\n⚠️  WARNING: GOOGLE_APPLICATION_CREDENTIALS not set!")
        print("   You may need to authenticate with: gcloud auth application-default login")

    # Test prompts
    prompts = [
        {
            "name": "Futuristic Electronic",
            "prompt": "An uplifting electronic track with synthesized beats and ambient textures. Modern and futuristic feel with driving rhythm.",
            "negative_prompt": "acoustic, vocals, piano"
        },
        {
            "name": "Luxury Orchestral",
            "prompt": "Sophisticated orchestral piece with elegant piano and subtle strings. Refined and luxurious atmosphere.",
            "negative_prompt": "rock, electric guitar, drums"
        }
    ]

    # Test each prompt
    for i, test in enumerate(prompts, 1):
        print(f"\n{'─' * 80}")
        print(f"Test {i}: {test['name']}")
        print(f"{'─' * 80}")
        print(f"Prompt: {test['prompt']}")
        if test.get('negative_prompt'):
            print(f"Negative: {test['negative_prompt']}")

        try:
            print("\n🎵 Generating music with Lyria...")

            # Generate music
            audio_bytes = await lyria_client.generate_music(
                prompt=test['prompt'],
                negative_prompt=test.get('negative_prompt'),
                duration_seconds=10  # Note: Lyria ignores this, generates 30s
            )

            if not audio_bytes or len(audio_bytes) == 0:
                print("❌ FAILED: Lyria returned empty bytes")
                print("   Possible causes:")
                print("   - Lyria not available in your region")
                print("   - API not enabled: gcloud services enable aiplatform.googleapis.com")
                print("   - Service account lacks permissions")
                print("   - Content safety filter triggered")
                continue

            # Success!
            print(f"✅ SUCCESS: Generated {len(audio_bytes):,} bytes of audio")
            print(f"   Format: WAV (48 kHz)")
            print(f"   Duration: ~30 seconds (Lyria fixed output)")

            # Save to file
            output_path = f"/tmp/lyria_test_{i}_{test['name'].replace(' ', '_').lower()}.wav"
            with open(output_path, 'wb') as f:
                f.write(audio_bytes)

            print(f"   Saved to: {output_path}")
            print(f"\n   Play with: ffplay {output_path}")
            print(f"   Or convert to MP3: ffmpeg -i {output_path} output.mp3")

        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)


async def test_lyria_simple():
    """Simple single-prompt test."""

    print("\n🎵 Testing Lyria music generation...")

    prompt = "A calm acoustic folk song with gentle guitar melody and soft strings."

    print(f"Prompt: {prompt}")
    print("Calling Lyria API...")

    audio_bytes = await lyria_client.generate_music(prompt=prompt)

    if audio_bytes and len(audio_bytes) > 0:
        print(f"✅ Success! Generated {len(audio_bytes):,} bytes")

        output_path = "/tmp/lyria_test_simple.wav"
        with open(output_path, 'wb') as f:
            f.write(audio_bytes)

        print(f"Saved to: {output_path}")
        print(f"Play with: ffplay {output_path}")

        return True
    else:
        print("❌ Failed: Lyria returned empty bytes")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Lyria music generation")
    parser.add_argument("--simple", action="store_true", help="Run simple single-prompt test")
    args = parser.parse_args()

    if args.simple:
        asyncio.run(test_lyria_simple())
    else:
        asyncio.run(test_lyria_music_generation())
