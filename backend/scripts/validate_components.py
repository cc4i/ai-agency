#!/usr/bin/env python3
"""Component validation script.

Quick smoke test to verify all Level 1 components are working.
Run this after making changes to ensure nothing broke.

Usage:
    uv run python scripts/validate_components.py
"""

import sys
import os
from pathlib import Path
from typing import Dict, List

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))


def validate_agents() -> Dict[str, bool]:
    """Validate all specialist agents can be instantiated."""
    results = {}

    try:
        from app.agents.strategy import StrategyAgent
        strategy = StrategyAgent()
        results["Strategy Agent"] = True
        print(f"✅ Strategy Agent: {type(strategy).__name__}")
    except Exception as e:
        results["Strategy Agent"] = False
        print(f"❌ Strategy Agent: {e}")

    try:
        from app.agents.art_director import ArtDirectorAgent
        art = ArtDirectorAgent()
        results["Art Director"] = True
        print(f"✅ Art Director: {type(art).__name__}")
    except Exception as e:
        results["Art Director"] = False
        print(f"❌ Art Director: {e}")

    try:
        from app.agents.video_producer import VideoProducerAgent
        video = VideoProducerAgent()
        results["Video Producer"] = True
        print(f"✅ Video Producer: {type(video).__name__}")
    except Exception as e:
        results["Video Producer"] = False
        print(f"❌ Video Producer: {e}")

    try:
        from app.agents.audio_team import AudioTeamAgent
        audio = AudioTeamAgent()
        results["Audio Team"] = True
        print(f"✅ Audio Team: {type(audio).__name__}")
    except Exception as e:
        results["Audio Team"] = False
        print(f"❌ Audio Team: {e}")

    try:
        from app.agents.web_dev import WebDevAgent
        web = WebDevAgent()
        results["Web Dev"] = True
        print(f"✅ Web Dev: {type(web).__name__}")
    except Exception as e:
        results["Web Dev"] = False
        print(f"❌ Web Dev: {e}")

    return results


def validate_services() -> Dict[str, bool]:
    """Validate core services."""
    results = {}

    try:
        from app.services.agent_registry import agent_registry
        agents = agent_registry.list_agents()
        results["Agent Registry"] = len(agents) == 5
        print(f"✅ Agent Registry: {len(agents)} agents registered")
    except Exception as e:
        results["Agent Registry"] = False
        print(f"❌ Agent Registry: {e}")

    try:
        from app.services.orchestration import orchestrator
        results["Orchestrator"] = True
        print(f"✅ Orchestrator: {type(orchestrator).__name__}")
    except Exception as e:
        results["Orchestrator"] = False
        print(f"❌ Orchestrator: {e}")

    try:
        from app.services.event_bus import event_bus
        results["Event Bus"] = True
        print(f"✅ Event Bus: {type(event_bus).__name__}")
    except Exception as e:
        results["Event Bus"] = False
        print(f"❌ Event Bus: {e}")

    try:
        from app.services.brief_sync import brief_sync_manager
        results["Brief Sync"] = True
        print(f"✅ Brief Sync: {type(brief_sync_manager).__name__}")
    except Exception as e:
        results["Brief Sync"] = False
        print(f"❌ Brief Sync: {e}")

    try:
        from app.services.redis_client import redis_client
        results["Redis Client"] = True
        print(f"✅ Redis Client: {type(redis_client).__name__}")
    except Exception as e:
        results["Redis Client"] = False
        print(f"❌ Redis Client: {e}")

    return results


def validate_producer() -> Dict[str, bool]:
    """Validate Executive Producer components."""
    results = {}

    try:
        from app.producer.executive_producer import ExecutiveProducer
        results["Executive Producer"] = True
        print(f"✅ Executive Producer: {ExecutiveProducer.__name__}")
    except Exception as e:
        results["Executive Producer"] = False
        print(f"❌ Executive Producer: {e}")

    try:
        from app.producer.demo_flow import AuraDemoFlow
        results["Demo Flow"] = True
        print(f"✅ Demo Flow: {AuraDemoFlow.__name__}")
    except Exception as e:
        results["Demo Flow"] = False
        print(f"❌ Demo Flow: {e}")

    try:
        from app.producer.planner import CampaignPlanner
        results["Planner"] = True
        print(f"✅ Planner: {CampaignPlanner.__name__}")
    except Exception as e:
        results["Planner"] = False
        print(f"❌ Planner: {e}")

    try:
        from app.producer.critique import CritiqueSystem
        results["Critique System"] = True
        print(f"✅ Critique System: {CritiqueSystem.__name__}")
    except Exception as e:
        results["Critique System"] = False
        print(f"❌ Critique System: {e}")

    return results


def main():
    """Run all component validations."""
    print("=" * 70)
    print("🔍 COMPONENT VALIDATION")
    print("=" * 70)
    print()

    all_results = {}

    # Validate agents
    print("1. Specialist Agents")
    print("-" * 70)
    agent_results = validate_agents()
    all_results.update(agent_results)
    print()

    # Validate services
    print("2. Core Services")
    print("-" * 70)
    service_results = validate_services()
    all_results.update(service_results)
    print()

    # Validate producer
    print("3. Executive Producer Components")
    print("-" * 70)
    producer_results = validate_producer()
    all_results.update(producer_results)
    print()

    # Summary
    print("=" * 70)
    passed = sum(all_results.values())
    total = len(all_results)
    success_rate = (passed / total * 100) if total > 0 else 0

    if passed == total:
        print(f"✅ ALL COMPONENTS VALIDATED: {passed}/{total} ({success_rate:.0f}%)")
        print("=" * 70)
        print()
        print("System is healthy and ready! 🎉")
        return 0
    else:
        print(f"⚠️ VALIDATION INCOMPLETE: {passed}/{total} ({success_rate:.0f}%)")
        print("=" * 70)
        print()
        print("Failed components:")
        for component, status in all_results.items():
            if not status:
                print(f"  ❌ {component}")
        print()
        print("Please fix the failed components before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
