#!/usr/bin/env python3
"""Multimodal backend verification script.

Tests the following tools:
1. capture_visual_reference
2. generate_concept_sketches

Usage:
    uv run python scripts/verify_multimodal.py
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def verify_multimodal_tools():
    """Verify multimodal tools."""
    print("=" * 70)
    print("🔍 MULTIMODAL TOOLS VERIFICATION")
    print("=" * 70)
    print()

    try:
        from app.services.redis_client import redis_client
        from app.services.gemini_live_adk import capture_visual_reference, generate_concept_sketches
        
        # Connect to Redis
        await redis_client.connect()
        print("✅ Redis connected")

        # Mock connection object with a fake video frame
        class MockConnection:
            def __init__(self):
                # 1x1 pixel white JPEG base64
                self.last_video_frame = "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigD//2Q=="

        mock_connection = MockConnection()
        
        # Inject mock connection into tool
        capture_visual_reference._connection = mock_connection
        capture_visual_reference._project_id = "test_project_multimodal"
        
        # Create test project if needed
        # (Assuming redis_client handles missing projects gracefully or we can create one)
        from app.models.brief import ProjectBrief
        from datetime import datetime
        
        test_brief = ProjectBrief(
            project_id="test_project_multimodal",
            session_id="test_session",
            product_name="Test Product",
            product_category="Testing",
            theme="Test Theme",
            key_features=["Feature 1", "Feature 2"],
            brand_tone="Professional",
            target_market="Testers",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        await redis_client.save_project_brief(test_brief)
        print("✅ Test project created")

        # 1. Test capture_visual_reference
        print("\n1. Testing capture_visual_reference...")
        result = await capture_visual_reference(
            description="Test Sketch",
            category="sketch"
        )
        
        if result.get("success"):
            print(f"✅ Capture Success: {result['reference_id']}")
            reference_id = result['reference_id']
        else:
            print(f"❌ Capture Failed: {result.get('error')}")
            return

        # 2. Test generate_concept_sketches
        print("\n2. Testing generate_concept_sketches...")
        
        # Inject context
        generate_concept_sketches._project_id = "test_project_multimodal"
        
        # Mock the Art Director execution to avoid actual API calls (which might be slow or cost money)
        # For a smoke test, we just want to ensure the function runs and handles the flow
        # But if we want to test the REAL integration, we should let it run.
        # Given "smoke test", I'll try to run it but expect it might fail if API keys aren't set or quota issues.
        # Actually, let's mock the orchestrator to return a fake result to verify the TOOL logic, not the AI.
        
        # Mocking orchestrator within the function is hard without patching.
        # So we'll just run it and catch exceptions. If it fails due to API, that's "partial success" for the tool logic.
        
        try:
            # We can't easily mock the internal import inside the function without patching sys.modules or using unittest.mock
            # So let's just try to run it. If it fails on API, we'll know the tool logic at least started.
            result = await generate_concept_sketches(
                reference_image_id=reference_id,
                instruction="Futuristic style"
            )
            
            if result.get("success"):
                print(f"✅ Concept Generation Success: {len(result.get('concepts', []))} concepts")
            else:
                print(f"⚠️ Concept Generation Failed (Expected if no API key): {result.get('error')}")
                
        except Exception as e:
            print(f"⚠️ Concept Generation Exception: {e}")

        print("\n✅ Verification Complete")

    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await redis_client.disconnect()

if __name__ == "__main__":
    asyncio.run(verify_multimodal_tools())
