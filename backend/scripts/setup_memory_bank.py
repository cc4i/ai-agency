#!/usr/bin/env python3
"""
Setup script for Vertex AI Memory Bank - Create Agent Engine Instance

This script creates a new Agent Engine instance for Memory Bank integration.
The Agent Engine ID must be saved to the .env file for the application to use.

Usage:
    python backend/scripts/setup_memory_bank.py

Requirements:
    - GOOGLE_CLOUD_PROJECT environment variable set
    - GOOGLE_CLOUD_LOCATION environment variable set (default: us-central1)
    - GOOGLE_APPLICATION_CREDENTIALS environment variable set
    - google-cloud-aiplatform package installed
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


def create_agent_engine():
    """Create a new Agent Engine instance for Memory Bank."""

    print("=" * 80)
    print("Vertex AI Memory Bank - Agent Engine Setup")
    print("=" * 80)
    print()

    # Verify environment configuration
    print("1. Verifying environment configuration...")

    if not settings.google_cloud_project:
        print("❌ ERROR: GOOGLE_CLOUD_PROJECT not set")
        print("   Set it in backend/.env or as environment variable")
        sys.exit(1)

    if not settings.google_cloud_location:
        print("❌ ERROR: GOOGLE_CLOUD_LOCATION not set")
        print("   Set it in backend/.env or as environment variable")
        sys.exit(1)

    print(f"   ✓ Project: {settings.google_cloud_project}")
    print(f"   ✓ Location: {settings.google_cloud_location}")
    print()

    # Configure Vertex AI
    print("2. Initializing Vertex AI client...")

    try:
        import vertexai
        from google.adk.memory import VertexAiMemoryBankService

        # Set environment variables for Vertex AI
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
        os.environ["GOOGLE_CLOUD_PROJECT"] = settings.google_cloud_project
        os.environ["GOOGLE_CLOUD_LOCATION"] = settings.google_cloud_location

        if settings.google_application_credentials:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials

        # Initialize Vertex AI client
        client = vertexai.Client(
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )

        print(f"   ✓ Vertex AI client initialized")
        print()

    except ImportError as e:
        print(f"❌ ERROR: Missing required package: {e}")
        print("   Install with: pip install google-cloud-aiplatform google-adk")
        sys.exit(1)
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize Vertex AI client: {e}")
        sys.exit(1)

    # Create Agent Engine
    print("3. Creating Agent Engine instance...")
    print("   This may take a few minutes...")
    print()

    try:
        agent_engine = client.agent_engines.create()
        agent_engine_id = agent_engine.api_resource.name.split("/")[-1]

        print(f"   ✓ Agent Engine created successfully!")
        print()

    except Exception as e:
        print(f"❌ ERROR: Failed to create Agent Engine: {e}")
        print()
        print("Common issues:")
        print("  - Insufficient permissions (need aiplatform.agentEngines.create)")
        print("  - Vertex AI API not enabled in GCP project")
        print("  - Invalid credentials")
        sys.exit(1)

    # Display results
    print("=" * 80)
    print("✅ Setup Complete!")
    print("=" * 80)
    print()
    print(f"Agent Engine ID: {agent_engine_id}")
    print()
    print("Next steps:")
    print()
    print("1. Add the following to your backend/.env file:")
    print()
    print(f"   AGENT_ENGINE_ID={agent_engine_id}")
    print(f"   ENABLE_MEMORY_BANK=true")
    print(f"   MEMORY_CALLBACK_ENABLED=true")
    print()
    print("2. Restart your backend server for changes to take effect")
    print()
    print("=" * 80)

    return agent_engine_id


if __name__ == "__main__":
    try:
        create_agent_engine()
    except KeyboardInterrupt:
        print()
        print("❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print()
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
