#!/usr/bin/env python3
"""
Verify dependencies for Vertex AI Memory Bank integration.

This script checks that all required packages are installed and can be imported.

Usage:
    python backend/scripts/verify_dependencies.py
"""

import sys
from importlib import import_module
from typing import List, Tuple


def check_dependency(module_name: str, min_version: str = None) -> Tuple[bool, str]:
    """
    Check if a dependency is installed and optionally verify version.

    Args:
        module_name: Name of the module to import
        min_version: Minimum required version (optional)

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        module = import_module(module_name)

        # Get version if available
        version = getattr(module, '__version__', 'unknown')

        if min_version and version != 'unknown':
            # Simple version comparison (works for most cases)
            if version < min_version:
                return False, f"❌ {module_name}: version {version} < {min_version}"

        return True, f"✓ {module_name}: {version}"

    except ImportError as e:
        return False, f"❌ {module_name}: not installed ({e})"
    except Exception as e:
        return False, f"❌ {module_name}: error ({e})"


def main():
    """Verify all dependencies for Memory Bank integration."""

    print("=" * 80)
    print("Dependency Verification for Vertex AI Memory Bank")
    print("=" * 80)
    print()

    # Core dependencies
    print("1. Core Dependencies:")
    print("-" * 80)

    core_deps = [
        ("google.genai", "1.47.0"),
        ("google.adk", "1.17.0"),
        ("google.cloud.aiplatform", "1.125.0"),
    ]

    core_results = []
    for module, version in core_deps:
        success, message = check_dependency(module, version)
        core_results.append(success)
        print(f"   {message}")

    print()

    # Memory Bank specific imports
    print("2. Memory Bank Specific Imports:")
    print("-" * 80)

    memory_deps = [
        "google.adk.memory",
        "google.adk.tools.preload_memory_tool",
        "google.adk.tools",
    ]

    memory_results = []
    for module in memory_deps:
        success, message = check_dependency(module)
        memory_results.append(success)
        print(f"   {message}")

    print()

    # Supporting dependencies
    print("3. Supporting Dependencies:")
    print("-" * 80)

    support_deps = [
        "fastapi",
        "redis",
        "pydantic",
        "pydantic_settings",
    ]

    support_results = []
    for module in support_deps:
        success, message = check_dependency(module)
        support_results.append(success)
        print(f"   {message}")

    print()

    # Summary
    print("=" * 80)

    all_results = core_results + memory_results + support_results

    if all(all_results):
        print("✅ All dependencies verified successfully!")
        print()
        print("Next steps:")
        print("  1. Run: python backend/scripts/setup_memory_bank.py")
        print("  2. Add AGENT_ENGINE_ID to backend/.env")
        print("  3. Set ENABLE_MEMORY_BANK=true in backend/.env")
        print()
        print("=" * 80)
        return 0
    else:
        print("❌ Some dependencies are missing or outdated")
        print()
        print("To install missing dependencies:")
        print("  cd backend")
        print("  uv pip install -e .")
        print()
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
