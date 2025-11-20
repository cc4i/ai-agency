"""Gemini Live ADK Connection - Simplified bidirectional audio streaming.

This is a production implementation using Google ADK (Agent Development Kit)
to replace the complex manual WebSocket handling in gemini_live.py.

Key simplifications:
- LiveRequestQueue handles bidirectional messaging automatically
- Tools are Python functions, no manual JSON schema definitions
- Automatic tool execution, no manual routing/handling
- Built-in session resumption and transcription
- ~250 lines vs 2219 lines in the manual implementation

Architecture:
┌──────────┐         ┌──────────┐         ┌──────────────┐         ┌─────────────┐
│ Frontend │◄───────►│ FastAPI  │◄───────►│  ADK Runner  │◄───────►│ Memory Bank │
│  (Next)  │ WebSocket│ Backend  │   ADK   │ (Gemini Live)│   Auto  │ (Vertex AI) │
└──────────┘         └──────────┘         └──────────────┘  Persist └─────────────┘

Session Management (Single Source of Truth):
- Active sessions: ADK InMemorySessionService (ephemeral)
- Persistence: Vertex AI Memory Bank (automatic on turn_complete)
- Retrieval: load_memory tool for semantic search
- No Redis conversation history (deprecated)
- No ConversationManager in ADK flow (only used in demo_flow.py)

Configuration:
- ENABLE_MEMORY_BANK=true: Enables automatic persistence to Memory Bank
- MEMORY_CALLBACK_ENABLED=true: Enables turn_complete persistence trigger
- See .env for full configuration
"""

import asyncio
import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import WebSocket
from google.adk import Agent, Runner
from google.adk.runners import RunConfig, LiveRequestQueue
from google.adk.agents.run_config import StreamingMode
from google.adk.sessions import InMemorySessionService
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.tools import load_memory

# Memory Bank integration
from app.services.memory_service import memory_service
# NOTE: after_agent_callback is not used - callbacks don't trigger in run_live() mode

from google import genai
from google.genai import types

from app.config import settings
from app.services.redis_client import redis_client

# Configure environment for Vertex AI
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
os.environ["GOOGLE_CLOUD_PROJECT"] = settings.google_cloud_project
os.environ["GOOGLE_CLOUD_LOCATION"] = settings.google_cloud_location
if settings.google_application_credentials:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials

logger = logging.getLogger(__name__)

# ============================================================================
# HELPER FUNCTIONS - WebSocket broadcasting utilities & data sanitization
# ============================================================================

def truncate_for_logging(data: Any, max_len: int = 100) -> Any:
    """
    Truncate long strings (like data URIs) in data for cleaner logging.

    Args:
        data: Data to process
        max_len: Maximum string length before truncation

    Returns:
        Data with long strings truncated
    """
    if isinstance(data, str) and len(data) > max_len:
        return f"{data[:30]}... (len={len(data)})"
    elif isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if isinstance(v, str) and len(v) > max_len:
                result[k] = f"{v[:30]}... (len={len(v)})"
            elif isinstance(v, dict) and 'url' in v:
                result[k] = {**v, 'url': truncate_for_logging(v['url'], max_len)}
            elif isinstance(v, list):
                result[k] = [truncate_for_logging(item, max_len) for item in v]
            elif isinstance(v, dict):
                result[k] = truncate_for_logging(v, max_len)
            else:
                result[k] = v
        return result
    elif isinstance(data, list):
        return [truncate_for_logging(item, max_len) for item in data]
    else:
        return data


def sanitize_for_json(obj: Any, max_depth: int = 10) -> Any:
    """
    Recursively sanitize objects to ensure JSON serializability and UTF-8 safety.

    Handles:
    - Non-serializable types (datetime, bytes, etc.)
    - Circular references
    - Deep nesting
    - Non-UTF-8 strings
    """
    if max_depth <= 0:
        return "[Max depth reached]"

    # Handle None
    if obj is None:
        return None

    # Handle primitives
    if isinstance(obj, (bool, int, float)):
        return obj

    # Handle strings - ensure UTF-8 safe
    if isinstance(obj, str):
        try:
            # Test UTF-8 encoding
            obj.encode('utf-8').decode('utf-8')
            return obj
        except UnicodeError:
            # Replace bad characters
            return obj.encode('utf-8', 'replace').decode('utf-8')

    # Handle bytes
    if isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            return base64.b64encode(obj).decode('ascii')

    # Handle datetime
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()

    # Handle lists/tuples
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item, max_depth - 1) for item in obj]

    # Handle dicts
    if isinstance(obj, dict):
        return {
            str(key): sanitize_for_json(value, max_depth - 1)
            for key, value in obj.items()
        }

    # Handle Pydantic models
    if hasattr(obj, 'model_dump'):
        try:
            return sanitize_for_json(obj.model_dump(), max_depth - 1)
        except Exception:
            return str(obj)

    # Handle other objects - convert to string
    try:
        return str(obj)
    except Exception:
        return "[Non-serializable object]"


def validate_tool_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and sanitize tool results before sending to Gemini Live API.

    This prevents WebSocket 1007 errors caused by:
    - Non-JSON-serializable data
    - Invalid UTF-8 characters
    - Circular references
    - Overly large payloads
    """
    try:
        # First pass - sanitize all values
        sanitized = sanitize_for_json(result)

        # Test JSON serialization
        json_str = json.dumps(sanitized, ensure_ascii=False)

        # Check payload size (ADK may have limits)
        if len(json_str) > 100000:  # 100KB limit
            logger.warning(f"Tool result is large ({len(json_str)} bytes), truncating...")
            # Keep only essential fields
            sanitized = {
                "success": sanitized.get("success", True),
                "message": sanitized.get("message", "")[:500],
                "note": "Result truncated due to size"
            }

        # Verify UTF-8 encoding
        json_str.encode('utf-8').decode('utf-8')

        logger.debug(f"[Tool Result] Validated: {len(json_str)} bytes")
        return sanitized

    except Exception as e:
        logger.error(f"[Tool Result] Sanitization failed: {e}", exc_info=True)
        # Return minimal safe result
        return {
            "success": False,
            "message": "Tool result could not be serialized safely",
            "error": str(e)
        }


async def broadcast_to_frontend(message_type: str, data: Dict[str, Any], frontend_ws=None) -> None:
    """
    Broadcast a message to the frontend WebSocket.

    Args:
        message_type: Type of message (e.g., "agent_status", "asset_added")
        data: Message payload
        frontend_ws: WebSocket connection (if None, uses default from context)
    """
    if not frontend_ws:
        # Try to get from any tool's context
        frontend_ws = getattr(update_project_brief, '_frontend_ws', None)
        logger.info(f"[WebSocket] Retrieved frontend_ws from tool context: {frontend_ws is not None}")

    if frontend_ws:
        try:
            message = {
                "type": message_type,
                "data": data
            }
            # Debug logging for asset_added
            if message_type == "asset_added" and "asset_data" in data:
                asset_data = data.get("asset_data", {})
                logger.info(f"[WebSocket] DEBUG asset_added: agent_id={data.get('agent_id')}, asset_type={data.get('asset_type')}")
                logger.info(f"[WebSocket] DEBUG asset_data keys: {list(asset_data.keys()) if isinstance(asset_data, dict) else 'not a dict'}")
                if isinstance(asset_data, dict) and "images" in asset_data:
                    images = asset_data.get("images", [])
                    logger.info(f"[WebSocket] DEBUG images count: {len(images) if isinstance(images, list) else 'not a list'}")
                    if isinstance(images, list) and len(images) > 0:
                        first_image = images[0]
                        url = first_image.get('url', '') if isinstance(first_image, dict) else ''
                        logger.info(f"[WebSocket] DEBUG first image url length: {len(url)}")

                        # Validate data URI format
                        if url.startswith('data:image'):
                            parts = url.split(',', 1)
                            if len(parts) == 2:
                                header, b64_data = parts
                                logger.info(f"[WebSocket] DEBUG first image - header: {header}, base64 length: {len(b64_data)}")
                            else:
                                logger.error(f"[WebSocket] ERROR first image has invalid data URI format (no comma separator)")
                        else:
                            logger.warning(f"[WebSocket] WARNING first image URL doesn't start with 'data:image': {url[:100]}")

            # Serialize message and check size
            message_json = json.dumps(message)
            message_size_kb = len(message_json) / 1024
            logger.info(f"[WebSocket] Sending {message_type}, size: {message_size_kb:.1f}KB")

            # Check for truncation - compare before and after serialization
            if message_type == "asset_added" and "asset_data" in data:
                asset_data = data.get("asset_data", {})
                if isinstance(asset_data, dict) and "images" in asset_data:
                    images = asset_data.get("images", [])
                    if isinstance(images, list) and len(images) > 0:
                        # Re-parse to check for truncation
                        reparsed = json.loads(message_json)
                        reparsed_url = reparsed.get("data", {}).get("asset_data", {}).get("images", [{}])[0].get("url", "")
                        original_url = images[0].get("url", "") if isinstance(images[0], dict) else ""

                        if len(reparsed_url) != len(original_url):
                            logger.error(f"[WebSocket] TRUNCATION DETECTED! Original: {len(original_url)}, After JSON: {len(reparsed_url)}")
                        else:
                            logger.info(f"[WebSocket] No truncation - URL size preserved: {len(original_url)} chars")

            await frontend_ws.send_text(message_json)
            logger.info(f"[WebSocket] ✓ Broadcasted {message_type}")
        except Exception as e:
            logger.error(f"[WebSocket] ✗ Failed to broadcast {message_type}: {e}", exc_info=True)
    else:
        logger.error(f"[WebSocket] ✗ No frontend connection available to broadcast {message_type}")


async def send_announcement(message: str, announcement_type: str = "info") -> None:
    """
    Send a producer announcement to the frontend.

    Args:
        message: Announcement text
        announcement_type: Type of announcement (info, success, error, warning)
    """
    logger.info(f"[Announcement] Sending to frontend: {message} (type: {announcement_type})")

    # Get frontend_ws from tool context
    frontend_ws = getattr(update_project_brief, '_frontend_ws', None)

    await broadcast_to_frontend("producer_announcement", {
        "message": message,
        "announcement_type": announcement_type
    }, frontend_ws=frontend_ws)


async def send_agent_status(agent_id: str, status: str, current_task: str = "") -> None:
    """
    Broadcast agent status update to frontend.

    Args:
        agent_id: Agent identifier
        status: Agent status (working, completed, failed)
        current_task: Description of current task
    """
    # Get frontend_ws from tool context
    frontend_ws = getattr(update_project_brief, '_frontend_ws', None)

    await broadcast_to_frontend("agent_status", {
        "agent_id": agent_id,
        "status": status,
        "current_task": current_task
    }, frontend_ws=frontend_ws)


async def send_websocket_event(event_data: Dict[str, Any]) -> None:
    """
    Send a custom WebSocket event to the frontend.

    Args:
        event_data: Event payload containing 'type' and other fields
    """
    # Get frontend_ws from tool context
    frontend_ws = getattr(update_project_brief, '_frontend_ws', None)

    event_type = event_data.get("type", "custom_event")

    await broadcast_to_frontend(event_type, event_data, frontend_ws=frontend_ws)


def _format_strategy_summary(result: Dict[str, Any], product_name: str) -> str:
    """
    Format strategy agent results as searchable text for Memory Bank.

    Args:
        result: Strategy agent output with slogans, personas, market_analysis
        product_name: Product name

    Returns:
        Formatted markdown summary
    """
    from datetime import datetime

    summary_parts = [
        f"[STRATEGY COMPLETE - {product_name}]",
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "CAMPAIGN SLOGANS GENERATED:"
    ]

    # Add slogans
    slogans = result.get("slogans", [])
    for i, slogan in enumerate(slogans, 1):
        summary_parts.append(f'{i}. "{slogan}"')

    summary_parts.append("")
    summary_parts.append("CUSTOMER PERSONAS CREATED:")

    # Add personas
    personas = result.get("personas", [])
    for persona in personas:
        summary_parts.append(f"\n• {persona.get('name', 'Unknown')} ({persona.get('age_range', 'N/A')})")
        summary_parts.append(f"  Description: {persona.get('description', 'N/A')}")

        pain_points = persona.get('pain_points', [])
        if pain_points:
            summary_parts.append(f"  Pain Points: {', '.join(pain_points[:3])}")

        motivations = persona.get('motivations', [])
        if motivations:
            summary_parts.append(f"  Motivations: {', '.join(motivations[:3])}")

    # Add market analysis excerpt
    market_analysis = result.get("market_analysis", "")
    if market_analysis:
        summary_parts.append("")
        summary_parts.append("MARKET ANALYSIS:")
        summary_parts.append(market_analysis[:300] + "..." if len(market_analysis) > 300 else market_analysis)

    return "\n".join(summary_parts)


def _format_image_summary(images: list, product_name: str, theme: str) -> str:
    """
    Format hero images as searchable text for Memory Bank.

    Args:
        images: List of generated images with metadata
        product_name: Product name
        theme: Visual theme

    Returns:
        Formatted markdown summary
    """
    from datetime import datetime

    summary_parts = [
        f"[HERO IMAGES GENERATED - {product_name}]",
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Art Director created {len(images)} image variations:",
        f"Visual Theme: {theme}",
        ""
    ]

    for i, img in enumerate(images, 1):
        if isinstance(img, dict):
            variation = img.get('variation', i)
            style_guide = img.get('style_guide', {})
            summary_parts.append(f"Variation {variation}:")
            summary_parts.append(f"  Style: {style_guide.get('description', 'N/A')}")
            summary_parts.append(f"  Mood: {style_guide.get('mood', 'N/A')}")
            summary_parts.append(f"  Setting: {style_guide.get('setting', 'N/A')}")
            summary_parts.append("")

    return "\n".join(summary_parts)


async def inject_creative_summary(
    session_service: Any,
    session: Any,
    tool_name: str,
    result: Dict[str, Any],
    product_info: Dict[str, Any]
) -> None:
    """
    Inject creative tool results as searchable text into ADK session for Memory Bank.

    Memory Bank filters out function_response parts, so we inject text summaries
    that can be semantically searched while keeping full structured data in Redis.

    Args:
        session_service: ADK SessionService
        session: Current ADK session
        tool_name: Name of the tool that executed
        result: Tool execution result
        product_info: Product name and other context
    """
    try:
        from google.genai.types import Content, Part

        product_name = product_info.get('product_name', 'Product')
        summary = ""

        if tool_name == "create_campaign_strategy":
            summary = _format_strategy_summary(result, product_name)

        elif tool_name == "generate_hero_images":
            images = result.get("images", [])
            theme = product_info.get('theme', 'modern')
            summary = _format_image_summary(images, product_name, theme)

        elif tool_name == "generate_social_video":
            summary = f"""
[VIDEO GENERATED - {product_name}]
Timestamp: {result.get('created_at', 'N/A')}

Video Producer created social media video:
Duration: {result.get('duration_seconds', 'N/A')} seconds
Platform: {result.get('platform', 'social media')}
Style: {result.get('style', 'N/A')}
"""

        elif tool_name == "generate_audio_assets":
            summary = f"""
[AUDIO ASSETS GENERATED - {product_name}]

Audio Team created:
• Jingle: {result.get('jingle', {}).get('duration_seconds', 'N/A')}s musical theme
• Podcast Ad: {result.get('podcast_ad', {}).get('duration_seconds', 'N/A')}s spoken ad
• Script: {result.get('podcast_ad', {}).get('transcription', 'N/A')[:200]}...
"""

        elif tool_name == "generate_landing_page":
            summary = f"""
[LANDING PAGE GENERATED - {product_name}]

Web Dev Agent created responsive landing page:
• HTML: {len(result.get('code', {}).get('html', ''))} characters
• CSS: {len(result.get('code', {}).get('css', ''))} characters
• JavaScript: {len(result.get('code', {}).get('js', ''))} characters
• Features: Countdown timer, email signup, feature highlights
"""

        if summary:
            # Add to session
            await session_service.append_event(
                session,
                Content(
                    role='model',
                    parts=[Part(text=summary)]
                )
            )
            logger.info(f"[Memory Bank] ✓ Injected {tool_name} summary ({len(summary)} chars)")

    except Exception as e:
        logger.warning(f"[Memory Bank] Failed to inject {tool_name} summary: {e}")


async def send_asset_added(agent_id: str, asset_type: str, asset_data: Dict[str, Any]) -> None:
    """
    Broadcast asset addition to frontend.

    Args:
        agent_id: Agent that created the asset
        asset_type: Type of asset (image, video, audio, etc.)
        asset_data: Asset details (url, metadata, etc.)
    """
    logger.info(f"[ASSET] Sending asset_added: agent={agent_id}, type={asset_type}")
    logger.info(f"[ASSET] Asset data keys: {list(asset_data.keys()) if isinstance(asset_data, dict) else 'not a dict'}")

    # Debug: Check image URLs
    if isinstance(asset_data, dict) and "images" in asset_data:
        images = asset_data.get("images", [])
        if isinstance(images, list) and len(images) > 0:
            first_img = images[0]
            if isinstance(first_img, dict):
                url = first_img.get("url", "")
                logger.info(f"[ASSET] First image URL type: {type(url)}, length: {len(url) if isinstance(url, str) else 'N/A'}")
                if isinstance(url, str):
                    if url.startswith("data:image"):
                        # Check if it's a valid data URI
                        parts = url.split(',', 1)
                        logger.info(f"[ASSET] Data URI parts count: {len(parts)}")
                        if len(parts) == 2:
                            header, b64_data = parts
                            logger.info(f"[ASSET] Data URI header: {header}, base64 length: {len(b64_data)}")
                            # Check if base64 contains any commas (it shouldn't!)
                            comma_count = b64_data.count(',')
                            if comma_count > 0:
                                logger.error(f"[ASSET] ERROR: Base64 data contains {comma_count} commas! Data is corrupted!")
                        else:
                            logger.error(f"[ASSET] ERROR: Invalid data URI format - found {len(parts)} parts when splitting by comma")
                    else:
                        logger.warning(f"[ASSET] WARNING: URL doesn't start with 'data:image': {url[:100]}")
            else:
                logger.error(f"[ASSET] ERROR: First image is not a dict: {type(first_img)}")

    # Get frontend_ws from tool context
    frontend_ws = getattr(update_project_brief, '_frontend_ws', None)

    await broadcast_to_frontend("asset_added", {
        "agent_id": agent_id,
        "asset_type": asset_type,
        "asset_data": asset_data
    }, frontend_ws=frontend_ws)


# ============================================================================
# TOOL DEFINITIONS - Python functions instead of JSON schemas
# ============================================================================

async def update_project_brief(
    product_name: str = "",
    product_category: str = "",
    theme: str = "",
    brand_tone: str = "",
    target_market: str = "",
    key_features: Optional[List[str]] = None,
    selected_slogan: str = "",
    selected_image_url: str = "",
    selected_image_variation: int = 0,
) -> Dict[str, Any]:
    """
    Update the project brief with user-provided information.

    Call this IMMEDIATELY when the user provides ANY information about their product or campaign.
    Extract ALL relevant fields from the user's message and pass them in ONE call.

    Fields to extract from conversation:
    - product_name: Product or brand name
    - product_category: Type of product (e.g., "smart e-bike", "luxury watch")
    - theme: Visual or conceptual theme (e.g., "futuristic", "timeless elegance")
    - brand_tone: Brand voice/personality (e.g., "cutting-edge but approachable")
    - target_market: Target audience description (e.g., "urban athletes aged 18-35")
    - key_features: List of product features/benefits
    - selected_slogan: The exact slogan text the user chose (when selecting from options)
    - selected_image_url: DEPRECATED - Use selected_image_variation instead
    - selected_image_variation: Which image variation user selected (1-4). Use this when user says "first one", "second", "third", "fourth".

    CRITICAL: If user mentions multiple fields, batch them into ONE function call.
    Example: If user says "luxury watch for executives, timeless vibe", call with:
    update_project_brief(product_category="luxury watch", target_market="executives", theme="timeless")

    For image selection: User says "I choose the fourth one" → call update_project_brief(selected_image_variation=4)
    """
    # Get current project from context (set during connection)
    project_id = getattr(update_project_brief, '_project_id', 'default')
    frontend_ws = getattr(update_project_brief, '_frontend_ws', None)

    logger.info(f"[TOOL] update_project_brief called for {project_id}")
    logger.info(f"[TOOL] Parameters received: product_name={product_name!r}, category={product_category!r}, theme={theme!r}, brand_tone={brand_tone!r}, target_market={target_market!r}, key_features={key_features!r}, selected_image_variation={selected_image_variation}")

    # Build updates dict (only non-empty values)
    updates = {}
    if product_name:
        updates["product_name"] = product_name
    if product_category:
        updates["product_category"] = product_category
    if theme:
        updates["theme"] = theme
    if brand_tone:
        updates["brand_tone"] = brand_tone
    if target_market:
        updates["target_market"] = target_market
    if key_features:
        updates["key_features"] = key_features
    if selected_slogan:
        updates["selected_slogan"] = selected_slogan
        logger.info(f"[TOOL] User selected slogan: {selected_slogan}")

    # Handle image selection by variation number (preferred method)
    if selected_image_variation > 0:
        logger.info(f"[TOOL] User selected image variation: {selected_image_variation}")
        # Fetch project brief to get hero_images list
        brief = await redis_client.get_project_brief(project_id)
        if brief and brief.hero_images:
            # Find image with matching variation number
            selected_image = None
            for img in brief.hero_images:
                if img.generation_params.get("variation") == selected_image_variation:
                    selected_image = img
                    break

            if selected_image:
                updates["selected_image"] = selected_image
                logger.info(f"[TOOL] Found image variation {selected_image_variation}: {selected_image.description}")
            else:
                logger.error(f"[TOOL] Image variation {selected_image_variation} not found in hero_images")
                return validate_tool_result({
                    "success": False,
                    "error": f"Image variation {selected_image_variation} not found",
                    "message": f"Could not find image variation {selected_image_variation}. Available variations: {[img.generation_params.get('variation') for img in brief.hero_images]}"
                })
        else:
            logger.error(f"[TOOL] No hero images found in project brief")
            return validate_tool_result({
                "success": False,
                "error": "No hero images available",
                "message": "No hero images have been generated yet. Please generate images first."
            })

    # Fallback: Handle image selection by URL (for UI clicks)
    elif selected_image_url:
        from app.models.assets import ImageAsset
        import hashlib
        url_hash = hashlib.md5(selected_image_url.encode()).hexdigest()[:12]
        selected_image = ImageAsset(
            asset_id=f"img_{url_hash}",
            url=selected_image_url,
            generation_params={},
            description="User selected hero image"
        )
        updates["selected_image"] = selected_image
        logger.info(f"[TOOL] User selected image by URL: {selected_image_url[:50]}...")

    # Update brief in Redis
    brief = await redis_client.update_project_brief(project_id, updates)

    logger.info(f"[TOOL] Updated brief fields: {list(updates.keys())}")

    # Broadcast update to frontend via WebSocket
    if frontend_ws:
        try:
            await frontend_ws.send_text(json.dumps({
                "type": "brief_update",
                "data": {
                    "brief": brief.model_dump(mode="json"),
                    "changed_fields": list(updates.keys())
                }
            }))
            logger.info(f"[TOOL] Broadcasted brief update to frontend")
        except Exception as e:
            logger.error(f"[TOOL] Failed to broadcast brief update: {e}")

    tool_result = {
        "success": True,
        "message": f"Updated project brief for {product_name or 'product'}",
        "updated_fields": list(updates.keys()),
        "brief": brief.model_dump(mode="json")
    }

    # Validate before returning to prevent WebSocket 1007 errors
    return validate_tool_result(tool_result)


async def create_campaign_strategy(
    product_name: str = "",
    product_category: str = "",
    theme: str = "",
    brand_tone: str = "",
    target_market: str = "",
    key_features: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Task the Strategy Agent to create campaign personas, slogans, and market positioning.

    Call this when user requests strategy/personas/slogans.
    Missing fields will be pulled from the project brief.
    """
    try:
        from app.services.orchestration import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        project_id = getattr(create_campaign_strategy, '_project_id', 'default')

        logger.info(f"[TOOL] create_campaign_strategy called for {project_id}")

        # Fetch project brief and fill in missing parameters
        brief = await redis_client.get_project_brief(project_id)
        if brief:
            if not product_name:
                product_name = brief.product_name
            if not product_category:
                product_category = brief.product_category
            if not theme:
                theme = brief.theme
            if not brand_tone:
                brand_tone = brief.brand_tone
            if not target_market:
                target_market = brief.target_market
            if not key_features:
                key_features = brief.key_features
            logger.info(f"[TOOL] Filled missing params from brief: product={product_name}, category={product_category}, theme={theme}")

        task = {
            "task_id": "strategy",
            "product_name": product_name,
            "product_category": product_category,
            "theme": theme,
            "brand_tone": brand_tone,
            "target_market": target_market,
            "key_features": key_features or [],
        }

        # Send agent status update: thinking (frontend expects 'thinking', not 'working')
        await send_agent_status("strategy", "thinking", "Generating campaign strategy and slogans")

        # Announce to user that agent is starting
        await send_announcement("Strategy Agent is creating campaign slogans and customer personas...", "info")

        # Execute agent with announcement callback for real-time updates
        result = await orchestrator.execute_agent(
            "strategy",
            task=task,
            project_id=project_id,
            with_critique=True,
            announcement_callback=send_announcement  # ← Pass callback for frontend updates
        )

        # Send agent status update: complete (frontend expects 'complete', not 'completed')
        await send_agent_status("strategy", "complete", "")

        # Extract slogans from result to present to Gemini
        slogans = result.get("slogans", [])
        personas = result.get("personas", [])

        # CRITICAL: Save slogans and personas to Redis for persistence
        # This ensures they survive page refreshes and reconnections
        if slogans or personas:
            await redis_client.update_project_brief(project_id, {
                "slogans": slogans,
                "personas": personas
            })
            logger.info(f"[TOOL] Saved {len(slogans)} slogans and {len(personas)} personas to project brief")

        # Broadcast asset if slogans were generated
        if "slogans" in result:
            await send_asset_added("strategy", "slogans", result)

        # Queue creative summary for Memory Bank injection at turn_complete
        if hasattr(create_campaign_strategy, '_connection'):
            connection = create_campaign_strategy._connection
            summary = _format_strategy_summary(result, product_name)
            connection.pending_creative_summaries.append(summary)
            logger.info(f"[Memory Bank] Queued strategy summary for injection ({len(summary)} chars)")

        tool_result = {
            "success": True,
            "message": f"Strategy Agent generated {len(slogans)} slogans and {len(personas)} personas. Present each slogan to the user.",
            "slogans": slogans,
            "personas": personas
        }

        # Validate before returning to prevent WebSocket 1007 errors
        return validate_tool_result(tool_result)

    except Exception as e:
        logger.error(f"[TOOL] create_campaign_strategy failed: {e}", exc_info=True)
        await send_agent_status("strategy", "error", "")
        return validate_tool_result({
            "success": False,
            "error": str(e),
            "message": f"Strategy Agent encountered an error: {str(e)}"
        })


async def generate_hero_images(
    slogan: str,
    product_name: str,
    product_category: str = "",
    theme: str = "",
    brand_tone: str = "",
    key_features: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Task the Art Director Agent to create hero images.

    Call ONLY when:
    1. Strategy Agent has completed and generated slogans
    2. User has explicitly SELECTED one slogan
    3. User requests images/visuals
    """
    try:
        from app.services.orchestration import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        project_id = getattr(generate_hero_images, '_project_id', 'default')

        logger.info(f"[TOOL] generate_hero_images called for {project_id}, slogan={slogan[:50] if slogan else 'none'}...")

        # Fetch project brief and fill in missing parameters
        brief = await redis_client.get_project_brief(project_id)
        reference_images = []

        if brief:
            # ALWAYS use selected_slogan from brief if it exists (user's explicit choice)
            # This prevents Memory Bank from polluting the slogan with old campaigns
            if brief.selected_slogan:
                slogan = brief.selected_slogan
                logger.info(f"[TOOL] Using selected_slogan from brief (overriding parameter): {slogan}")
            elif not slogan:
                slogan = ""

            if not product_name:
                product_name = brief.product_name
            if not product_category:
                product_category = brief.product_category
            if not theme:
                theme = brief.theme
            if not brand_tone:
                brand_tone = brief.brand_tone
            if not key_features:
                key_features = brief.key_features

            # Get reference images from brief
            reference_images = brief.reference_images or []

            logger.info(
                f"[TOOL] Filled params from brief: slogan={slogan[:30] if slogan else 'none'}, "
                f"product={product_name}, reference_images={len(reference_images)}"
            )

        task = {
            "task_id": "art_director",
            "slogan": slogan,
            "product_name": product_name,
            "product_category": product_category,
            "theme": theme,
            "brand_tone": brand_tone,
            "key_features": key_features or [],
            "reference_images": [img.model_dump() for img in reference_images] if reference_images else [],
        }

        # Send agent status update: thinking
        await send_agent_status("art_director", "thinking", "Generating hero images")

        # Announce to user that agent is starting
        await send_announcement("Art Director is creating hero images for your campaign...", "info")

        # Execute agent with announcement callback for real-time updates
        result = await orchestrator.execute_agent(
            "art_director",
            task=task,
            project_id=project_id,
            with_critique=True,
            announcement_callback=send_announcement  # ← Pass callback for frontend updates
        )

        # Extract images from result
        images = result.get("images", [])

        # VALIDATION: Ensure we got all 4 images when generating from scratch
        # If this is the first generation (no existing hero_images), require all 4
        if brief and (not brief.hero_images or len(brief.hero_images) == 0):
            if len(images) < 4:
                error_msg = f"Art Director only generated {len(images)}/4 images. All 4 variations are required for initial generation. Please try again."
                logger.error(f"[TOOL] {error_msg}")
                await send_agent_status("art_director", "error", "")
                return validate_tool_result({
                    "success": False,
                    "error": "incomplete_generation",
                    "message": error_msg,
                    "images_generated": len(images)
                })

        # Send agent status update: complete
        await send_agent_status("art_director", "complete", "")

        # Save images to project brief in Redis so refinement tools can access them
        if images:
            from app.models.assets import ImageAsset, GenerationSnapshot
            from datetime import datetime

            # Determine if this is a regeneration or initial generation
            is_regeneration = brief and brief.hero_images and len(brief.hero_images) > 0
            new_generation_number = brief.current_generation if brief else 1

            if is_regeneration:
                # PRODUCTION-LEVEL GENERATION TRACKING
                # Save current generation to history before replacing
                logger.info(f"[TOOL] Regeneration detected. Saving Generation {brief.current_generation} to history")

                snapshot = GenerationSnapshot(
                    generation_number=brief.current_generation,
                    created_at=datetime.now(),
                    images=brief.hero_images,
                    theme=brief.theme,
                    reason="regenerated" if brief.current_generation > 1 else "initial generation",
                    slogan=brief.selected_slogan
                )
                brief.generation_history.append(snapshot)

                # Increment generation number for new images
                new_generation_number = brief.current_generation + 1
                logger.info(f"[TOOL] Starting Generation {new_generation_number}")

            # Create image assets with generation tracking metadata
            image_assets = []
            for i, img_dict in enumerate(images, 1):
                # Add generation metadata to each image
                img_dict['generation_number'] = new_generation_number
                img_dict['variation_number'] = i
                image_assets.append(ImageAsset(**img_dict))

            # Build update dict
            update_dict = {
                "hero_images": image_assets,
                "current_generation": new_generation_number,
            }

            # If regeneration, also update generation_history and clear refinement_history
            if is_regeneration:
                update_dict["generation_history"] = brief.generation_history
                update_dict["image_refinement_history"] = {}  # Clear for new generation
                logger.info(f"[TOOL] Cleared refinement history for Generation {new_generation_number}")
            else:
                # First generation, keep existing (empty) refinement_history
                update_dict["image_refinement_history"] = brief.image_refinement_history if brief else {}

            # Now save new images
            updated_brief = await redis_client.update_project_brief(project_id, update_dict)
            logger.info(f"[TOOL] Saved {len(images)} new hero images to project brief")

            # Broadcast brief update to frontend
            frontend_ws = getattr(generate_hero_images, '_frontend_ws', None)
            if frontend_ws:
                try:
                    # Build changed fields list
                    changed_fields = ["hero_images", "current_generation"]
                    if is_regeneration:
                        changed_fields.extend(["generation_history", "image_refinement_history"])

                    await frontend_ws.send_text(json.dumps({
                        "type": "brief_update",
                        "data": {
                            "brief": updated_brief.model_dump(mode="json"),
                            "changed_fields": changed_fields
                        }
                    }))
                    logger.info(f"[TOOL] Broadcasted brief_update (Generation {new_generation_number}) to frontend")
                except Exception as e:
                    logger.error(f"[TOOL] Failed to broadcast brief_update: {e}")

        # Broadcast asset if images were generated (with generation metadata and refinement history)
        if "images" in result:
            await send_asset_added("art_director", "images", {
                **result,
                "current_generation": new_generation_number,
                "is_regeneration": is_regeneration,
                "generation_history": [snapshot.model_dump(mode="json") for snapshot in updated_brief.generation_history],
                "refinement_history": {
                    asset_id: history.model_dump()
                    for asset_id, history in updated_brief.image_refinement_history.items()
                }
            })

        # Create lightweight summary for Gemini (no base64 data to avoid 100KB limit)
        # The full images with base64 are already sent to frontend via send_asset_added
        image_summaries = [
            {
                "description": img.get("description", ""),
                "variation": img.get("generation_params", {}).get("variation", i+1),
                "score": img.get("generation_params", {}).get("score", 0.0),
                "approved": img.get("generation_params", {}).get("approved", False),
            }
            for i, img in enumerate(images)
        ]

        # Queue creative summary for Memory Bank injection at turn_complete
        if hasattr(generate_hero_images, '_connection') and images:
            connection = generate_hero_images._connection
            summary = _format_image_summary(images, product_name, theme)
            connection.pending_creative_summaries.append(summary)
            logger.info(f"[Memory Bank] Queued hero images summary for injection ({len(summary)} chars)")

        tool_result = {
            "success": True,
            "message": f"Art Director generated {len(images)} hero images. They have been displayed to the user. Describe each variation briefly.",
            "image_summaries": image_summaries
        }

        # Validate before returning to prevent WebSocket 1007 errors
        return validate_tool_result(tool_result)

    except Exception as e:
        logger.error(f"[TOOL] generate_hero_images failed: {e}", exc_info=True)
        await send_agent_status("art_director", "error", "")
        return validate_tool_result({
            "success": False,
            "error": str(e),
            "message": f"Art Director encountered an error: {str(e)}"
        })


async def generate_social_video(
    product_name: str = "",
    theme: str = "",
    slogan: str = "",
    key_features: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Task the Video Producer Agent to create a 8-second social media video.

    IMPORTANT: Do NOT pass selected_image_url parameter. The tool will automatically
    fetch the selected image from the project brief. Just call this function with
    product_name, theme, slogan, and key_features.

    Args:
        product_name: Product name (auto-filled from brief if not provided)
        theme: Visual theme (auto-filled from brief if not provided)
        slogan: Campaign slogan (auto-filled from brief if not provided)
        key_features: List of key product features (auto-filled from brief if not provided)

    Call ONLY when:
    1. Hero images have been generated
    2. User has selected one image
    3. User requests video
    """
    try:
        from app.services.orchestration import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        project_id = getattr(generate_social_video, '_project_id', 'default')

        logger.info(f"[TOOL] generate_social_video called for {project_id}")

        # Fetch project brief to get selected image
        brief = await redis_client.get_project_brief(project_id)
        image_url = ""

        if brief:
            # ALWAYS get selected image URL from brief
            if brief.selected_image:
                logger.info(f"[TOOL] Found selected_image in brief: type={type(brief.selected_image)}, has_url={hasattr(brief.selected_image, 'url')}")
                # Handle both ImageAsset object and dict (for backwards compatibility)
                if hasattr(brief.selected_image, 'url'):
                    image_url = brief.selected_image.url
                elif isinstance(brief.selected_image, dict) and 'url' in brief.selected_image:
                    image_url = brief.selected_image['url']
                    logger.warning(f"[TOOL] selected_image was dict instead of ImageAsset, using dict access")
                logger.info(f"[TOOL] Extracted image_url: {image_url[:30] if image_url else 'None'}...")
            else:
                logger.warning(f"[TOOL] No selected_image found in brief!")
            if not product_name:
                product_name = brief.product_name
            if not theme:
                theme = brief.theme
            if not slogan:
                slogan = brief.selected_slogan or ""
            if not key_features:
                key_features = brief.key_features
            logger.info(f"[TOOL] Filled missing params from brief: image={image_url[:30] if image_url else 'none'}, product={product_name}")

        # Validate prerequisites
        if not image_url or image_url == "":
            error_msg = "PREREQUISITE MISSING: User has not selected a hero image yet. You MUST ask the user which of the 4 hero images they would like to use before you can generate a video. Do NOT tell the user you've triggered the video producer - instead ask them to select an image first."
            logger.warning(f"[TOOL] {error_msg}")
            await send_agent_status("video_producer", "error", "")
            return validate_tool_result({
                "success": False,
                "error": "missing_prerequisite",
                "message": error_msg
            })

        # Log image URL (truncated for readability)
        if isinstance(image_url, str):
            logger.info(f"[TOOL] video: image_url={image_url[:30]}... (len={len(image_url)})")

        task = {
            "task_id": "video_producer",
            "image_url": image_url,
            "product_name": product_name,
            "theme": theme,
            "slogan": slogan,
            "key_features": key_features or [],
        }

        # Send agent status update: thinking
        await send_agent_status("video_producer", "thinking", "Generating social media video")

        # Announce to user that agent is starting
        await send_announcement("Video Producer is creating your social media video...", "info")

        # Execute agent with announcement callback for real-time updates
        result = await orchestrator.execute_agent(
            "video_producer",
            task=task,
            project_id=project_id,
            with_critique=True,
            announcement_callback=send_announcement  # ← Pass callback for frontend updates
        )

        # Send agent status update: complete
        await send_agent_status("video_producer", "complete", "")

        # Broadcast asset if video was generated
        if "video_url" in result or "video" in result:
            await send_asset_added("video_producer", "video", result)

        tool_result = {
            "success": True,
            "message": "Video Producer has created a social media video",
            "result": result
        }

        # Validate before returning to prevent WebSocket 1007 errors
        return validate_tool_result(tool_result)

    except Exception as e:
        logger.error(f"[TOOL] generate_social_video failed: {e}", exc_info=True)
        await send_agent_status("video_producer", "error", "")
        return validate_tool_result({
            "success": False,
            "error": str(e),
            "message": f"Video Producer encountered an error: {str(e)}. Please ensure an image has been selected."
        })


async def generate_audio_assets(
    product_name: str,
    theme: str,
    slogan: str = "",
    brand_tone: str = "",
    product_category: str = "",
) -> Dict[str, Any]:
    """
    Task the Audio Team Agent to create audio assets (jingle, podcast ad, voiceover).

    Call when user requests audio content or music for the campaign.
    Can be called after strategy is complete.
    """
    try:
        from app.services.orchestration import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        project_id = getattr(generate_audio_assets, '_project_id', 'default')

        logger.info(f"[TOOL] generate_audio_assets called for {project_id}")

        # Fetch project brief and fill in missing parameters
        brief = await redis_client.get_project_brief(project_id)
        if brief:
            if not product_name:
                product_name = brief.product_name
            if not theme:
                theme = brief.theme
            if not slogan:
                slogan = brief.selected_slogan or ""
            if not brand_tone:
                brand_tone = brief.brand_tone
            if not product_category:
                product_category = brief.product_category
            logger.info(f"[TOOL] Filled missing params from brief: product={product_name}, theme={theme}, slogan={slogan[:30] if slogan else 'none'}")

        task = {
            "task_id": "audio_team",
            "product_name": product_name,
            "theme": theme,
            "slogan": slogan,
            "brand_tone": brand_tone,
            "product_category": product_category,
        }

        # Send agent status update: thinking
        await send_agent_status("audio_team", "thinking", "Generating audio assets")

        # Announce to user that agent is starting
        await send_announcement("Audio Team is composing jingles and creating audio assets...", "info")

        # Execute agent with announcement callback for real-time updates
        result = await orchestrator.execute_agent(
            "audio_team",
            task=task,
            project_id=project_id,
            with_critique=True,
            announcement_callback=send_announcement  # ← Pass callback for frontend updates
        )

        # Send agent status update: complete
        await send_agent_status("audio_team", "complete", "")

        # Broadcast asset if audio was generated
        # AudioTeamOutput contains: jingle, podcast_ad, transcription, proactive_suggestion
        if "jingle" in result or "podcast_ad" in result:
            await send_asset_added("audio_team", "audio", result)

        tool_result = {
            "success": True,
            "message": "Audio Team has created audio assets",
            "result": result
        }

        # Validate before returning to prevent WebSocket 1007 errors
        return validate_tool_result(tool_result)

    except Exception as e:
        logger.error(f"[TOOL] generate_audio_assets failed: {e}", exc_info=True)
        await send_agent_status("audio_team", "error", "")
        return validate_tool_result({
            "success": False,
            "error": str(e),
            "message": f"Audio Team encountered an error: {str(e)}"
        })


async def generate_landing_page(
    product_name: str = "",
    slogan: str = "",
    brand_tone: str = "",
    key_features: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Task the Web Dev Agent to create a landing page.

    IMPORTANT: Do NOT pass selected_image_url parameter. The tool will automatically
    fetch the selected image from the project brief. Just call this function with
    product_name, slogan, brand_tone, and key_features.

    Args:
        product_name: Product name (auto-filled from brief if not provided)
        slogan: Campaign slogan (auto-filled from brief if not provided)
        brand_tone: Brand tone/voice (auto-filled from brief if not provided)
        key_features: List of key product features (auto-filled from brief if not provided)

    Call ONLY when:
    1. Hero images exist
    2. User has selected an image
    3. User requests landing page/website
    """
    try:
        from app.services.orchestration import AgentOrchestrator

        orchestrator = AgentOrchestrator()
        project_id = getattr(generate_landing_page, '_project_id', 'default')

        logger.info(f"[TOOL] generate_landing_page called for {project_id}")

        # Fetch project brief to get selected image
        brief = await redis_client.get_project_brief(project_id)
        image_url = ""

        if brief:
            # ALWAYS get selected image URL from brief
            if brief.selected_image:
                logger.info(f"[TOOL] Found selected_image in brief: type={type(brief.selected_image)}, has_url={hasattr(brief.selected_image, 'url')}")
                # Handle both ImageAsset object and dict (for backwards compatibility)
                if hasattr(brief.selected_image, 'url'):
                    image_url = brief.selected_image.url
                elif isinstance(brief.selected_image, dict) and 'url' in brief.selected_image:
                    image_url = brief.selected_image['url']
                    logger.warning(f"[TOOL] selected_image was dict instead of ImageAsset, using dict access")
                logger.info(f"[TOOL] Extracted image_url: {image_url[:30] if image_url else 'None'}...")
            else:
                logger.warning(f"[TOOL] No selected_image found in brief!")
            if not product_name:
                product_name = brief.product_name
            if not slogan:
                slogan = brief.selected_slogan or ""
            if not brand_tone:
                brand_tone = brief.brand_tone
            if not key_features:
                key_features = brief.key_features
            logger.info(f"[TOOL] Filled missing params from brief: image={image_url[:30] if image_url else 'none'}, product={product_name}")

        # Validate prerequisites
        if not image_url or image_url == "":
            error_msg = "PREREQUISITE MISSING: User has not selected a hero image yet. You MUST ask the user which of the 4 hero images they would like to use before you can generate a landing page. Do NOT tell the user you've triggered the web dev agent - instead ask them to select an image first."
            logger.warning(f"[TOOL] {error_msg}")
            await send_agent_status("web_dev", "error", "")
            return validate_tool_result({
                "success": False,
                "error": "missing_prerequisite",
                "message": error_msg
            })

        task = {
            "task_id": "web_dev",
            "image_url": image_url,
            "product_name": product_name,
            "slogan": slogan,
            "brand_tone": brand_tone,
            "key_features": key_features or [],
        }

        # Send agent status update: thinking
        await send_agent_status("web_dev", "thinking", "Generating landing page")

        # Announce to user that agent is starting
        await send_announcement("Web Dev Agent is building your landing page...", "info")

        # Execute agent with announcement callback for real-time updates
        result = await orchestrator.execute_agent(
            "web_dev",
            task=task,
            project_id=project_id,
            with_critique=False,
            announcement_callback=send_announcement  # ← Pass callback for frontend updates
        )

        # Send agent status update: complete
        await send_agent_status("web_dev", "complete", "")

        # Broadcast asset if landing page was generated
        # WebDevOutput contains: code (CodeAsset), framework, deployment_status
        logger.info(f"[WEB_DEV] Result keys: {list(result.keys())}")
        logger.info(f"[WEB_DEV] Has 'code' key: {'code' in result}")

        if "code" in result:
            logger.info(f"[WEB_DEV] Broadcasting landing_page asset to frontend")
            logger.info(f"[WEB_DEV] Code asset: {result['code']}")
            await send_asset_added("web_dev", "landing_page", result)
        else:
            logger.error(f"[WEB_DEV] No 'code' key in result, cannot broadcast asset")

        tool_result = {
            "success": True,
            "message": "Web Dev Agent has created the landing page",
            "result": result
        }

        # Validate before returning to prevent WebSocket 1007 errors
        return validate_tool_result(tool_result)

    except Exception as e:
        logger.error(f"[TOOL] generate_landing_page failed: {e}", exc_info=True)
        await send_agent_status("web_dev", "error", "")
        return validate_tool_result({
            "success": False,
            "error": str(e),
            "message": f"Web Dev Agent encountered an error: {str(e)}. Please ensure an image has been selected."
        })


# ============================================================================
# IMAGE REFINEMENT TOOLS (NEW)
# ============================================================================

async def refine_hero_image(
    variation_number: int,
    feedback: str,
) -> Dict[str, Any]:
    """
    Refine a specific hero image based on user feedback, creating a new version.

    Use this when the user wants to improve or modify ONE specific image variation.
    Creates a new version (v2, v3, etc.) while preserving the original.

    The refinement process:
    1. Analyzes user feedback to determine what to keep vs. change
    2. Uses the original image as reference for consistency
    3. Generates refined image maintaining brand alignment
    4. Validates that feedback was addressed (quality score >= 0.7)
    5. Returns new version with version history

    Args:
        variation_number: Which image variation to refine (1-4)
        feedback: User's refinement request describing desired changes.
                 Be specific about what they want modified.
                 Examples: "add modern UI elements", "make it brighter",
                          "dial back the holographic overlays"

    Returns:
        Success status and refined image details

    Usage patterns:
        - "Option 1 is nice, but add modern elements"
          → refine_hero_image(variation_number=1, feedback="add modern elements")
        - "Make option 2 brighter with more vibrant colors"
          → refine_hero_image(variation_number=2, feedback="make brighter with vibrant colors")
        - "Option 3 needs the background blurred"
          → refine_hero_image(variation_number=3, feedback="blur the background")

    Note: Max 5 refinement iterations per image. Returns error if limit exceeded.
    """
    try:
        from app.workflows.art_director_workflow import ArtDirectorWorkflow

        project_id = getattr(refine_hero_image, '_project_id', 'default')
        logger.info(f"[TOOL] refine_hero_image called: variation={variation_number}, feedback='{feedback}'")

        # Validate variation number
        if variation_number < 1 or variation_number > 4:
            return validate_tool_result({
                "success": False,
                "error": f"Invalid variation number: {variation_number}. Must be 1-4."
            })

        # Load project brief
        brief = await redis_client.get_project_brief(project_id)
        if not brief:
            return validate_tool_result({
                "success": False,
                "error": "Project brief not found. Generate images first."
            })

        # Check if images exist
        if not brief.hero_images or len(brief.hero_images) < variation_number:
            return validate_tool_result({
                "success": False,
                "error": f"Image variation {variation_number} not found. Generate images first."
            })

        # Get current image
        current_image = brief.hero_images[variation_number - 1]

        # Check max iterations
        if current_image.refinement_iteration >= 5:
            return validate_tool_result({
                "success": False,
                "error": "Maximum refinement iterations (5) reached. Consider selecting existing version or generating new image."
            })

        # Send status update
        await send_agent_status("art_director", "thinking", f"Refining image {variation_number}")
        await send_announcement(
            f"Art Director is refining Option {variation_number} with your feedback...",
            "info"
        )

        # Call Art Director workflow
        workflow = ArtDirectorWorkflow()

        refined_image_dict = await workflow.refine_image(
            original_image=current_image.model_dump(),
            user_feedback=feedback,
            product_context={
                "product_name": brief.product_name,
                "product_category": brief.product_category,
                "theme": brief.theme,
                "brand_tone": brief.brand_tone,
                "key_features": brief.key_features,
            }
        )

        # Convert dict back to ImageAsset
        from app.models.assets import ImageAsset
        refined_image = ImageAsset(**refined_image_dict)

        # Update refinement history BEFORE replacing the image
        # Get the original asset_id (use parent_asset_id if current is already refined, otherwise use asset_id)
        original_id = current_image.parent_asset_id or current_image.asset_id

        if original_id not in brief.image_refinement_history:
            from app.models.assets import ImageRefinementHistory
            brief.image_refinement_history[original_id] = ImageRefinementHistory(
                original_asset_id=original_id,
                refinements=[],
                feedback_history=[],
                iteration_count=0
            )

        # CRITICAL: Save the current/previous version to history BEFORE replacing it
        # This ensures we can navigate back to v0, v1, etc.
        brief.image_refinement_history[original_id].refinements.append(current_image)
        brief.image_refinement_history[original_id].feedback_history.append(feedback)
        brief.image_refinement_history[original_id].iteration_count += 1

        # Now replace the image in hero_images with the refined version
        brief.hero_images[variation_number - 1] = refined_image

        # Save updated brief to Redis and get the saved version back
        updated_brief = await redis_client.update_project_brief(
            project_id,
            {
                "hero_images": brief.hero_images,
                "image_refinement_history": brief.image_refinement_history
            }
        )

        # Send status update
        await send_agent_status("art_director", "complete", "")

        # Broadcast updated brief to frontend (for Project Brief panel)
        frontend_ws = getattr(refine_hero_image, '_frontend_ws', None)
        if frontend_ws:
            try:
                await frontend_ws.send_text(json.dumps({
                    "type": "brief_update",
                    "data": {
                        "brief": updated_brief.model_dump(mode="json"),
                        "changed_fields": ["hero_images", "image_refinement_history"]
                    }
                }))
                logger.info(f"[TOOL] Broadcasted brief_update with refined hero_images to frontend")
            except Exception as e:
                logger.error(f"[TOOL] Failed to broadcast brief_update: {e}")

        # Broadcast asset_added to update Hero Images panel (with generation and refinement metadata)
        await send_asset_added("art_director", "images", {
            "images": [img.model_dump() for img in updated_brief.hero_images],
            "current_generation": updated_brief.current_generation,
            "generation_history": [snapshot.model_dump(mode="json") for snapshot in updated_brief.generation_history],
            "refinement_history": {
                asset_id: history.model_dump()
                for asset_id, history in updated_brief.image_refinement_history.items()
            }
        })

        # Broadcast refinement event
        await send_websocket_event({
            "type": "image_refined",
            "variation_number": variation_number,
            "refined_image": refined_image.model_dump(),
            "version_number": refined_image.refinement_iteration,
            "feedback": feedback,
        })

        return validate_tool_result({
            "success": True,
            "message": f"Image {variation_number} refined successfully (version {refined_image.refinement_iteration})",
            "version_number": refined_image.refinement_iteration,
            "feedback_applied": feedback,
            "quality_score": refined_image.generation_params.get("score", 0.0),
        })

    except Exception as e:
        logger.error(f"[TOOL] refine_hero_image failed: {e}", exc_info=True)
        await send_agent_status("art_director", "error", "")
        return validate_tool_result({
            "success": False,
            "error": str(e),
            "message": f"Art Director encountered an error while refining: {str(e)}"
        })


async def refine_all_hero_images(
    feedback: str,
) -> Dict[str, Any]:
    """
    Refine ALL 4 hero images with the same feedback, processing in parallel.

    Use this when the user wants to apply the same change to all image variations.
    All 4 images are refined simultaneously for speed (~20 seconds total).

    Args:
        feedback: Global change to apply to all images.
                 Examples: "make brighter", "increase color vibrancy",
                          "add more energy", "reduce saturation"

    Returns:
        Success status and refined images summary

    Usage patterns:
        - "All images feel too dark"
          → refine_all_hero_images(feedback="increase brightness")
        - "Make them all more vibrant"
          → refine_all_hero_images(feedback="increase color vibrancy")
        - "All images need more energy"
          → refine_all_hero_images(feedback="add more dynamic energy")
    """
    try:
        from app.workflows.art_director_workflow import ArtDirectorWorkflow

        project_id = getattr(refine_all_hero_images, '_project_id', 'default')
        logger.info(f"[TOOL] refine_all_hero_images called: feedback='{feedback}'")

        # Load project brief
        brief = await redis_client.get_project_brief(project_id)
        if not brief:
            return validate_tool_result({
                "success": False,
                "error": "Project brief not found. Generate images first."
            })

        if not brief.hero_images or len(brief.hero_images) == 0:
            return validate_tool_result({
                "success": False,
                "error": "No hero images found. Generate images first."
            })

        # Send status update
        await send_agent_status("art_director", "thinking", "Refining all images")
        await send_announcement(
            "Art Director is refining all 4 variations with your feedback...",
            "info"
        )

        # Call Art Director workflow
        workflow = ArtDirectorWorkflow()

        refined_images_dicts = await workflow.refine_all_images(
            all_images=[img.model_dump() for img in brief.hero_images],
            global_feedback=feedback,
            product_context={
                "product_name": brief.product_name,
                "product_category": brief.product_category,
                "theme": brief.theme,
                "brand_tone": brief.brand_tone,
                "key_features": brief.key_features,
            }
        )

        # Convert dicts back to ImageAssets
        from app.models.assets import ImageAsset, ImageRefinementHistory
        refined_images = [ImageAsset(**img_dict) for img_dict in refined_images_dicts]

        # Update refinement history for ALL images BEFORE replacing them
        for i, (current_image, refined_image) in enumerate(zip(brief.hero_images, refined_images)):
            # Get the original asset_id
            original_id = current_image.parent_asset_id or current_image.asset_id

            if original_id not in brief.image_refinement_history:
                brief.image_refinement_history[original_id] = ImageRefinementHistory(
                    original_asset_id=original_id,
                    refinements=[],
                    feedback_history=[],
                    iteration_count=0
                )

            # Save the current/previous version to history BEFORE replacing it
            brief.image_refinement_history[original_id].refinements.append(current_image)
            brief.image_refinement_history[original_id].feedback_history.append(feedback)
            brief.image_refinement_history[original_id].iteration_count += 1

        # Update project brief in Redis (replace all images and update history)
        updated_brief = await redis_client.update_project_brief(
            project_id,
            {
                "hero_images": refined_images,
                "image_refinement_history": brief.image_refinement_history
            }
        )

        # Send status update
        await send_agent_status("art_director", "complete", "")

        # Broadcast updated brief to frontend (for Project Brief panel)
        frontend_ws = getattr(refine_all_hero_images, '_frontend_ws', None)
        if frontend_ws:
            try:
                await frontend_ws.send_text(json.dumps({
                    "type": "brief_update",
                    "data": {
                        "brief": updated_brief.model_dump(mode="json"),
                        "changed_fields": ["hero_images", "image_refinement_history"]
                    }
                }))
                logger.info(f"[TOOL] Broadcasted brief_update with all refined hero_images to frontend")
            except Exception as e:
                logger.error(f"[TOOL] Failed to broadcast brief_update: {e}")

        # Broadcast asset_added to update Hero Images panel (with generation and refinement metadata)
        await send_asset_added("art_director", "images", {
            "images": [img.model_dump() for img in refined_images],
            "current_generation": updated_brief.current_generation,
            "generation_history": [snapshot.model_dump(mode="json") for snapshot in updated_brief.generation_history],
            "refinement_history": {
                asset_id: history.model_dump()
                for asset_id, history in updated_brief.image_refinement_history.items()
            }
        })

        # Broadcast batch refinement event
        await send_websocket_event({
            "type": "all_images_refined",
            "refined_images": [img.model_dump() for img in refined_images],
            "feedback": feedback,
        })

        # Calculate average score
        scores = [img.generation_params.get("score", 0.0) for img in refined_images]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        return validate_tool_result({
            "success": True,
            "message": f"All {len(refined_images)} images refined successfully",
            "feedback_applied": feedback,
            "average_quality_score": avg_score,
        })

    except Exception as e:
        logger.error(f"[TOOL] refine_all_hero_images failed: {e}", exc_info=True)
        await send_agent_status("art_director", "error", "")
        return validate_tool_result({
            "success": False,
            "error": str(e),
            "message": f"Art Director encountered an error while refining: {str(e)}"
        })


async def select_image_version(
    variation_number: int,
    version_number: int,
) -> Dict[str, Any]:
    """
    Select a specific version of an image from refinement history (rollback).

    Use when the user wants to go back to a previous version of a refined image.
    This restores an earlier version as the current version without regeneration.

    Args:
        variation_number: Which image variation (1-4)
        version_number: Which version to restore (1=original, 2=v2, 3=v3, etc.)

    Returns:
        Success status and selected version details

    Usage patterns:
        - "Go back to version 2 of option 1"
          → select_image_version(variation_number=1, version_number=2)
        - "I prefer version 1 of option 3"
          → select_image_version(variation_number=3, version_number=1)
        - "Restore the original version of option 2"
          → select_image_version(variation_number=2, version_number=1)
    """
    try:
        project_id = getattr(select_image_version, '_project_id', 'default')
        logger.info(f"[TOOL] select_image_version called: variation={variation_number}, version={version_number}")

        # Load project brief
        brief = await redis_client.get_project_brief(project_id)
        if not brief:
            return validate_tool_result({
                "success": False,
                "error": "Project brief not found."
            })

        # Validate variation number
        if variation_number < 1 or variation_number > 4 or len(brief.hero_images) < variation_number:
            return validate_tool_result({
                "success": False,
                "error": f"Invalid variation number: {variation_number}"
            })

        # Get current image
        current_image = brief.hero_images[variation_number - 1]
        original_id = current_image.asset_id if current_image.refinement_iteration == 0 else current_image.parent_asset_id

        # Find the requested version
        target_version = None

        if version_number == 1:
            # Find original in history
            if original_id in brief.image_refinement_history:
                # Original should be the one with refinement_iteration = 0
                for img in [current_image] + brief.image_refinement_history[original_id].refinements:
                    if img.refinement_iteration == 0:
                        target_version = img
                        break
            else:
                # No refinement history, current is original
                if current_image.refinement_iteration == 0:
                    target_version = current_image

        else:
            # Get from refinement history
            if original_id in brief.image_refinement_history:
                history = brief.image_refinement_history[original_id]
                # version_number - 1 because version 1 is original (index 0), version 2 is refinements[0]
                if version_number - 2 < len(history.refinements):
                    target_version = history.refinements[version_number - 2]

        if not target_version:
            return validate_tool_result({
                "success": False,
                "error": f"Version {version_number} not found for variation {variation_number}"
            })

        # Update current image in Redis
        brief.hero_images[variation_number - 1] = target_version
        updated_brief = await redis_client.update_project_brief(
            project_id,
            {"hero_images": brief.hero_images}
        )

        # Broadcast updated brief to frontend (for Project Brief panel)
        frontend_ws = getattr(select_image_version, '_frontend_ws', None)
        if frontend_ws:
            try:
                await frontend_ws.send_text(json.dumps({
                    "type": "brief_update",
                    "data": {
                        "brief": updated_brief.model_dump(mode="json"),
                        "changed_fields": ["hero_images"]
                    }
                }))
                logger.info(f"[TOOL] Broadcasted brief_update with version rollback to frontend")
            except Exception as e:
                logger.error(f"[TOOL] Failed to broadcast brief_update: {e}")

        # Broadcast asset_added to update Hero Images panel (with generation and refinement metadata)
        await send_asset_added("art_director", "images", {
            "images": [img.model_dump() for img in updated_brief.hero_images],
            "current_generation": updated_brief.current_generation,
            "generation_history": [snapshot.model_dump(mode="json") for snapshot in updated_brief.generation_history],
            "refinement_history": {
                asset_id: history.model_dump()
                for asset_id, history in updated_brief.image_refinement_history.items()
            }
        })

        # Broadcast version selection event
        await send_websocket_event({
            "type": "image_version_selected",
            "variation_number": variation_number,
            "version_number": version_number,
            "selected_image": target_version.model_dump(),
        })

        return validate_tool_result({
            "success": True,
            "message": f"Restored version {version_number} of image {variation_number}",
            "version_number": version_number,
            "description": target_version.description,
        })

    except Exception as e:
        logger.error(f"[TOOL] select_image_version failed: {e}", exc_info=True)
        return validate_tool_result({
            "success": False,
            "error": str(e),
            "message": f"Failed to select version: {str(e)}"
        })


# ============================================================================
# ADK AGENT & RUNNER SETUP
# ============================================================================

def create_system_prompt(project_id: str) -> str:
    """Create the Executive Producer system prompt (optimized for voice streaming)."""
    return f"""
# IDENTITY
You're the Executive Producer of AI Agency Hub. Guide clients via conversational voice from product vision to campaign assets. Audio-first interface—brief, warm, descriptive.

# 🚨 CRITICAL RULES

**DO**: ✅ Call `update_project_brief` BEFORE responding when user shares product info | ✅ Batch all info into ONE function call per message | ✅ Use exact tool returns—never hallucinate | ✅ Wait for tool results before presenting options | ✅ Announce which team is working BEFORE calling agent tools

**DON'T**: ❌ Call `generate_social_video`/`generate_landing_page` without selected image | ❌ Present options before tool returns | ❌ Use technical function names in speech | ❌ Skip prerequisites

# WORKFLOW
**Stage 1: Discovery** → Ask about product → Call `update_project_brief` for each detail (name, category, target_market, theme, brand_tone, key_features) → When complete, offer strategy

**Stage 2: Strategy** → Call `create_campaign_strategy` → Present 3 slogans (exact text from tool) → User selects → Call `update_project_brief(selected_slogan="...")`

**Stage 3: Images** → Call `generate_hero_images` (needs slogan) → Art Director generates 4 complete variations (will auto-retry failed ones) → Present 4 images (exact descriptions) → User selects (e.g., "fourth one") → Call `update_project_brief(selected_image_variation=4)`

**Stage 3b: Image Refinement (Optional)** → After presenting images, user may refine:
- Single: "Option 1 needs more color" → `refine_hero_image(1, "add more vibrant colors")`
- Batch: "All too dark" → `refine_all_hero_images("increase brightness")`
- Creates new version (v2, v3, etc.) → Present refined images
- User can compare versions → Continue refining or select final
- Max 5 iterations per image → Suggest starting fresh if limit reached

**Stage 4: Assets** → video (`generate_social_video`, needs image) | audio (`generate_audio_assets`, needs slogan) | page (`generate_landing_page`, needs image)

**Rejections**: Ask "What's not clicking—tone, concept, wording?" → Regenerate → Don't proceed until selection.

# FUNCTION MAP
- User mentions product → `update_project_brief(product_name, product_category, theme, brand_tone, target_market, key_features)`
- User selects slogan → `update_project_brief(selected_slogan="exact text")`
- User selects image → `update_project_brief(selected_image_variation=1-4)`
- User requests strategy → `create_campaign_strategy`
- User requests images → `generate_hero_images` (needs slogan ✓)
- User requests video → `generate_social_video` (needs image ✓)
- User requests audio → `generate_audio_assets` (needs slogan ✓)
- User requests page → `generate_landing_page` (needs image ✓)
- User references past → `load_memory(query="...")`

# 🎨 IMAGE REFINEMENT
- User refines single image → `refine_hero_image(variation_number, feedback)`
  Patterns: "option N is nice, but [feedback]" | "make option N [changes]" | "option N needs [changes]"
  Examples: "Option 1 is great, but add modern elements" → `refine_hero_image(1, "add modern elements")`
- User refines all images → `refine_all_hero_images(feedback)`
  Patterns: "all images [change]" | "make them all [change]"
  Examples: "All images feel too dark" → `refine_all_hero_images("increase brightness")`
- User selects version → `select_image_version(variation_number, version_number)`
  Patterns: "go back to version N" | "use version N of option X"
  Examples: "Go back to version 2 of option 1" → `select_image_version(1, 2)`

# VOICE & TONE
**Style**: Warm partner, not robot. Concise (audio = brevity). Visually descriptive. Balanced critique (strength + consideration per option).

**Audio**: Say "option one" not "#1". Confirm selections ("Going with two—great!"). Natural pauses. Stay in character—decline off-topic.

**Critique Example**: "Option 1 is bold, tech-forward. Option 2 is catchy, playful, might skew younger. Option 3 emphasizes precision."

**Refinements**: Acknowledge what user likes ("Great, you like the composition..."), confirm change ("...let me add those modern elements"). After refinement: describe what changed while preserving what they liked ("I've added holographic UI overlays while keeping that dramatic lighting you loved"). Offer comparison: "Want to see before and after?"

# TEAM ANNOUNCEMENTS (CRITICAL!)
Always verbally announce which team is working BEFORE calling agent tools. Use natural language, not technical names:

**Agent Tool → Natural Announcement**
- `create_campaign_strategy` → "Let me get our Strategy team working on this..." OR "I'll bring in our strategists..."
- `generate_hero_images` → "Let me bring in our Art Director for hero images..." OR "I'll have our Art Director create those visuals..."
- `refine_hero_image` → "I'll have them refine that..." OR "Let me ask the Art Director to adjust that..."
- `refine_all_hero_images` → "I'll have them update all four variations..." OR "Let me ask the Art Director to refine these..."
- `generate_social_video` → "I'll bring in our Video Producer..." OR "Let me get the video team on this..."
- `generate_audio_assets` → "I'll bring in our Audio team..." OR "Let me get our composers working on this..."
- `generate_landing_page` → "I'll have our Web Dev team build that..." OR "Let me bring in our developers..."

**Purpose**: This sets expectations that work is happening and provides transparency into the creative process.

# MEMORY
**PreloadMemoryTool** (auto): Memories load at start. Use: "Last time for AuraAI, you preferred minimalist..."

**load_memory** (manual): Call when user asks about past ("What slogan before?" → `load_memory(query="previous slogans")`) or references project ("Like sneaker campaign" → `load_memory(query="sneaker campaign")`).

Don't hallucinate. If no results: "No notes from that—want to tell me more?"

# ERROR HANDLING
**Tool fails**: Brief apology + non-tech explain + retry offer. Example: Tool error → "Art Director needs a moment—renders take time. Try again?"

**Rejections**: Ask specifics → Offer regen → Block progression until selection.

# EXAMPLE
User: "Aura smart sneaker for urban athletes. Futuristic."
You: *[Call `update_project_brief(product_name="Aura", product_category="smart sneaker", target_market="urban athletes", theme="futuristic")`]* "Great! What's special?"

User: "Glowing sole, tracks runs."
You: *[Call `update_project_brief(key_features=["glowing sole", "run tracking"])`]* "Perfect. Ready for slogans?"

User: "Yes."
You: "Let me get our Strategy team working on this..." *[Call `create_campaign_strategy`]* *[Returns: ["Step Into Your Aura", "Glow with the Flow", "The Future at Your Feet"]]* "They've created three options: One, 'Step Into Your Aura'—empowering. Two, 'Glow with the Flow'—catchy, playful. Three, 'The Future at Your Feet'—bold, tech. Thoughts?"

User: "One."
You: *[Call `update_project_brief(selected_slogan="Step Into Your Aura")`]* "Excellent choice! Let me bring in our Art Director for hero images..." *[Call `generate_hero_images`]* *[Returns: 4 images]* "Here are four variations they've created..."

User: "I like the first one but add modern elements."
You: "Great, I'll have them refine that with modern elements..." *[Call `refine_hero_image(1, "add modern elements")`]* *[Returns: refined image]* "There we go—added holographic UI overlays while keeping that dramatic lighting you loved. Better?"

# CURRENT PROJECT
Project: `{project_id}` | First message: Warmly greet, ask product vision.
"""


# ============================================================================
# DEPRECATED: Global agent and runner (kept for backwards compatibility)
# ============================================================================
# NOTE: These globals are no longer used. Each GeminiLiveADKConnection now
# creates its own agent and runner with user-selected model and voice.
# The per-connection architecture allows multiple users with different
# settings to connect simultaneously without conflicts.

# Create the Executive Producer agent with all tools
# DEPRECATED & COMMENTED OUT TO FIX STARTUP CRASH
# The following global initialization causes Pydantic validation errors because
# required fields (like 'instruction') are missing. Since this code is unused
# (replaced by per-connection initialization), it is safe to disable.

# agent_kwargs = {
#     "name": "executive_producer",
#     "model": "gemini-live-2.5-flash", #"gemini-live-2.5-flash-preview-native-audio-09-2025",  # Vertex AI native audio model
#     "description": "Executive Producer for AI Agency Hub - coordinates creative campaign development",
#     "instruction": "",  # Will be set dynamically per session
#     "tools": [
#         # Campaign management tools
#         update_project_brief,
#         create_campaign_strategy,
#         generate_hero_images,
#         # Image refinement tools (NEW)
#         refine_hero_image,
#         refine_all_hero_images,
#         select_image_version,
#         # Video/audio/web tools
#         generate_social_video,
#         generate_audio_assets,
#         generate_landing_page,
#         # Memory Bank tools (enabled via feature flag)
#         PreloadMemoryTool() if settings.enable_memory_bank else None,
#         load_memory if settings.enable_memory_bank else None,
#     ],
# }

# NOTE: after_agent_callback is NOT registered because it doesn't trigger in run_live() mode
# Memory Bank persistence is handled manually on turn_complete events instead
# See _agent_to_client_messaging() method for manual persistence logic

# executive_producer_agent = Agent(**agent_kwargs)

# Remove None values from tools list (when Memory Bank is disabled)
# executive_producer_agent.tools = [t for t in executive_producer_agent.tools if t is not None]

# Fix ADK app name mismatch warning by explicitly setting the agent file path
# This overrides the automatic detection that infers app name from package path
# executive_producer_agent._file = "app/services/gemini_live_adk.py"

# Create session service and runner (reuse across connections)
# session_service = InMemorySessionService()

# Configure runner with Memory Bank support
# runner_kwargs = {
#     "app_name": "ai_agency_hub",
#     "agent": executive_producer_agent,
#     "session_service": session_service,
# }

# Add Memory Bank service if enabled
# if settings.enable_memory_bank:
#     # Initialize memory service before passing to runner
#     memory_service.initialize()
#     if memory_service._service:
#         # Pass the underlying VertexAiMemoryBankService to runner
#         runner_kwargs["memory_service"] = memory_service._service
#         logger.info("✓ Memory Bank service registered with runner")
#     else:
#         logger.warning("⚠ Memory Bank service failed to initialize, running without memory")

# runner = Runner(**runner_kwargs)

# Count tools for logging
# tool_count = len(executive_producer_agent.tools)
# memory_status = "with Memory Bank (turn_complete persistence)" if settings.enable_memory_bank else "without Memory Bank"
# logger.info(f"✓ ADK Executive Producer agent created with {tool_count} tools ({memory_status})")


# ============================================================================
# WEBSOCKET CONNECTION HANDLER
# ============================================================================

class GeminiLiveADKConnection:
    """
    Simplified Gemini Live connection using ADK.

    Replaces 2219 lines of manual WebSocket handling with ~250 lines using ADK abstractions.

    Session Management:
    - Conversation history is automatically persisted to Vertex AI Memory Bank
    - ADK InMemorySessionService handles active session state
    - Memory Bank provides semantic search across all conversations
    - See ENABLE_MEMORY_BANK setting in .env to configure
    """

    def __init__(
        self,
        session_id: str,
        project_id: str = "aura_smart_sneaker",
        model_name: str = "gemini-live-2.5-flash",
        voice_name: str = "Kore",
    ):
        self.session_id = session_id
        self.project_id = project_id
        self.model_name = model_name
        self.voice_name = voice_name
        self.frontend_ws: Optional[WebSocket] = None
        self.live_request_queue = None
        self.live_events = None

        # Storage for pending creative summaries (injected at turn_complete)
        self.pending_creative_summaries: List[str] = []

        # Set context for tools (so they know which project to use)
        for tool in [update_project_brief, create_campaign_strategy, generate_hero_images,
                     refine_hero_image, refine_all_hero_images, select_image_version,
                     generate_social_video, generate_audio_assets, generate_landing_page]:
            tool._session_id = session_id
            tool._project_id = project_id
            tool._frontend_ws = None  # Will be set after WebSocket connect
            tool._connection = self  # Reference to connection for pending summaries

        # Create agent with user-selected model (per-connection instance)
        agent_kwargs = {
            "name": "executive_producer",
            "model": self.model_name,  # Use instance model (user-selected)
            "description": "Executive Producer for AI Agency Hub - coordinates creative campaign development",
            "instruction": "",  # Will be set dynamically per session
            "tools": [
                # Campaign management tools
                update_project_brief,
                create_campaign_strategy,
                generate_hero_images,
                # Image refinement tools (NEW)
                refine_hero_image,
                refine_all_hero_images,
                select_image_version,
                # Video/audio/web tools
                generate_social_video,
                generate_audio_assets,
                generate_landing_page,
                # Memory Bank tools (enabled via feature flag)
                PreloadMemoryTool() if settings.enable_memory_bank else None,
                load_memory if settings.enable_memory_bank else None,
            ],
        }

        self.agent = Agent(**agent_kwargs)

        # Remove None values from tools list (when Memory Bank is disabled)
        self.agent.tools = [t for t in self.agent.tools if t is not None]

        # Fix ADK app name mismatch warning
        self.agent._file = "app/services/gemini_live_adk.py"

        # Create per-connection session service and runner
        self.session_service = InMemorySessionService()

        # Configure runner with Memory Bank support
        runner_kwargs = {
            "app_name": "ai_agency_hub",
            "agent": self.agent,
            "session_service": self.session_service,
        }

        # Add Memory Bank service if enabled
        if settings.enable_memory_bank:
            # Initialize memory service before passing to runner
            memory_service._initialize()
            if memory_service._service:
                # Pass the underlying VertexAiMemoryBankService to runner
                runner_kwargs["memory_service"] = memory_service._service
                logger.info("✓ Memory Bank service registered with runner")
            else:
                logger.warning("⚠ Memory Bank service failed to initialize, running without memory")

        self.runner = Runner(**runner_kwargs)

        logger.info(f"✓ ADK connection initialized: session={session_id}, project={project_id}, model={model_name}, voice={voice_name}")

    async def connect(self, frontend_ws: WebSocket):
        """
        Establish connection: Frontend → Backend → ADK → Gemini Live

        Note: WebSocket is already accepted in main.py before this method is called.
        """
        self.frontend_ws = frontend_ws

        # Update tool context with WebSocket reference
        for tool in [update_project_brief, create_campaign_strategy, generate_hero_images,
                     generate_social_video, generate_audio_assets, generate_landing_page]:
            tool._frontend_ws = frontend_ws
            logger.info(f"✓ Set WebSocket reference on tool: {tool.__name__}")

        # Send initial connection confirmation to frontend
        try:
            await frontend_ws.send_text(json.dumps({
                "type": "connection_established",
                "data": {
                    "session_id": self.session_id,
                    "project_id": self.project_id
                }
            }))
            logger.info(f"✓ Sent connection confirmation to frontend")
        except Exception as e:
            logger.error(f"✗ Failed to send connection confirmation: {e}")

        # Send initial project brief to frontend
        try:
            brief = await redis_client.get_project_brief(self.project_id)
            if brief:
                await frontend_ws.send_text(json.dumps({
                    "type": "brief_init",
                    "data": {
                        "brief": brief.model_dump(mode="json")
                    }
                }))
                logger.info(f"✓ Sent initial project brief to frontend")
            else:
                logger.warning(f"⚠ No project brief found for {self.project_id}")
        except Exception as e:
            logger.error(f"✗ Failed to send initial project brief: {e}")

        try:
            # Initialize ADK session
            await self._initialize_adk_session()

            # Create bidirectional messaging tasks
            agent_to_client_task = asyncio.create_task(
                self._agent_to_client_messaging()
            )
            client_to_agent_task = asyncio.create_task(
                self._client_to_agent_messaging()
            )

            # Wait for either task to complete
            tasks = [agent_to_client_task, client_to_agent_task]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

            # Check for exceptions
            for task in done:
                if task.exception():
                    logger.error(f"Task error: {task.exception()}")
                    raise task.exception()

        except Exception as e:
            logger.error(f"Connection error: {e}")
            raise
        finally:
            await self.disconnect()

    async def _initialize_adk_session(self):
        """Initialize ADK session with Gemini Live."""
        # Get or create session
        session = await self.runner.session_service.get_session(
            app_name="ai_agency_hub",
            user_id=self.session_id,
            session_id=self.session_id,
        )

        if not session:
            session = await self.runner.session_service.create_session(
                app_name="ai_agency_hub",
                user_id=self.session_id,
                session_id=self.session_id,
            )
            logger.info(f"Created new ADK session: {self.session_id}")
        else:
            logger.info(f"Resumed ADK session: {self.session_id}")

        # Store session for Memory Bank persistence
        self.session = session

        # Update agent instruction with project-specific system prompt
        self.agent.instruction = create_system_prompt(self.project_id)

        # Create live request queue
        self.live_request_queue = LiveRequestQueue()

        # Configure run with audio modality and session resumption
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=[types.Modality.AUDIO],  # Audio-first interface
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self.voice_name
                    )
                )
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,  # Re-enable VAD, as disabling it caused Gemini to not respond.
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                    silence_duration_ms=1000, # Increased from 100ms, which may have been an invalid argument.
                    prefix_padding_ms=20,
                )
            ),
            session_resumption=types.SessionResumptionConfig(transparent=True),  # Enable resumption
            output_audio_transcription={},  # Get transcripts from AI
            input_audio_transcription={},
        )

        # Start live streaming session
        self.live_events = self.runner.run_live(
            user_id=self.session_id,
            session_id=self.session_id,
            live_request_queue=self.live_request_queue,
            run_config=run_config,
        )

        logger.info("✓ ADK live session started")

    async def _client_to_agent_messaging(self):
        """Handle Frontend → ADK messaging."""
        message_count = 0
        while True:
            try:
                try:
                    message_json = await self.frontend_ws.receive_text()
                except WebSocketDisconnect:
                    logger.info(f"[ADK] WebSocket disconnected by client")
                    break
                except RuntimeError as e:
                    if "WebSocket is not connected" in str(e):
                        logger.warning(f"[ADK] WebSocket not connected in receive loop: {e}")
                        break
                    raise e
                    
                message = json.loads(message_json)
                message_count += 1

                logger.debug(f"[ADK] Received message #{message_count}: type={message.get('type')}")

                # Handle audio input (frontend sends "audio_input" type with "data" field)
                if message.get("type") == "audio_input" and message.get("data"):
                    audio_base64 = message["data"]

                    # Validate and clean base64 string to prevent 1007 errors
                    if not isinstance(audio_base64, str):
                        logger.error(f"[ADK] Audio data is not a string: {type(audio_base64)}")
                        continue

                    # Remove whitespace/newlines that might cause invalid frame payload
                    audio_base64 = audio_base64.strip().replace('\n', '').replace('\r', '').replace(' ', '')

                    try:
                        # Validate base64 encoding
                        decoded_audio = base64.b64decode(audio_base64, validate=True)

                        # Sanity check - audio should be reasonable size
                        if len(decoded_audio) == 0:
                            logger.warning(f"[ADK] Empty audio chunk received")
                            continue

                        if len(decoded_audio) > 1000000:  # 1MB max
                            logger.warning(f"[ADK] Audio chunk too large: {len(decoded_audio)} bytes")
                            continue

                        logger.debug(f"[ADK] Sending audio chunk: {len(decoded_audio)} bytes (base64: {len(audio_base64)} chars)")

                        # Send realtime audio to ADK
                        # IMPORTANT: Must specify sample rate - frontend sends 16kHz PCM
                        # Using audio/l16 as it's the standard for raw 16-bit PCM audio.
                        self.live_request_queue.send_realtime(
                            types.Blob(data=decoded_audio, mime_type="audio/l16;rate=16000")
                        )

                    except base64.binascii.Error as e:
                        logger.error(f"[ADK] Invalid base64 audio data: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"[ADK] Error processing audio chunk: {e}", exc_info=True)
                        continue

                # Handle text input
                elif message.get("type") == "text" and message.get("text"):
                    text = message["text"]
                    logger.info(f"[ADK] 💬 Received text message: {text[:100]}{'...' if len(text) > 100 else ''}")

                    content = types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=text)]
                    )
                    self.live_request_queue.send_content(content=content)
                    logger.info(f"[ADK] ✓ Text message sent to Gemini")

                # Handle image upload
                elif message.get("type") == "image" and message.get("data"):
                    image_data = message["data"]
                    logger.info(f"[ADK] 🖼️ Received image upload (size: {len(image_data)} chars)")

                    try:
                        # Extract base64 data (handle data URIs like "data:image/png;base64,...")
                        if image_data.startswith("data:"):
                            # Split data URI format
                            header, base64_data = image_data.split(",", 1)
                            mime_type = header.split(";")[0].replace("data:", "")
                        else:
                            # Assume raw base64
                            base64_data = image_data
                            mime_type = "image/png"  # default

                        # Decode base64 to bytes
                        image_bytes = base64.b64decode(base64_data)

                        logger.info(f"[ADK] Image decoded: {len(image_bytes)} bytes, mime={mime_type}")

                        # Create content with image
                        content = types.Content(
                            role="user",
                            parts=[
                                types.Part.from_bytes(
                                    data=image_bytes,
                                    mime_type=mime_type
                                )
                            ]
                        )
                        self.live_request_queue.send_content(content=content)
                        logger.info(f"[ADK] ✓ Image sent to Gemini")

                    except Exception as e:
                        logger.error(f"[ADK] ✗ Error processing image: {e}", exc_info=True)
                        continue

                # Handle image selection from UI
                elif message.get("type") == "update_brief" and message.get("data"):
                    data = message["data"]
                    if "selected_image_url" in data:
                        image_url = data["selected_image_url"]
                        logger.info(f"[ADK] User selected image via UI: {image_url[:50]}...")

                        # Update project brief in Redis
                        try:
                            brief = await redis_client.get_project_brief(self.project_id)
                            if brief:
                                # Create ImageAsset from URL
                                from app.models.assets import ImageAsset
                                import hashlib
                                # Generate asset_id from hash of URL (works for both data URIs and regular URLs)
                                url_hash = hashlib.md5(image_url.encode()).hexdigest()[:12]
                                selected_image = ImageAsset(
                                    asset_id=f"img_{url_hash}",
                                    url=image_url,
                                    generation_params={},
                                    description="User selected hero image"
                                )

                                # Update brief - pass ImageAsset object, not dict
                                updated_brief = await redis_client.update_project_brief(
                                    self.project_id,
                                    {"selected_image": selected_image}
                                )

                                # ADD HERO IMAGE SELECTION EVENT TO MEMORY BANK
                                # This captures the user's asset selection for conversation memory
                                if hasattr(self, 'session') and self.session:
                                    from google.adk.events import Event

                                    # Create descriptive text for the selection
                                    description = selected_image.description or "Hero image"
                                    selection_text = f"Selected hero image: {selected_image.asset_id} - {description}"

                                    selection_event = Event(
                                        author="user",
                                        content=types.Content(
                                            role="user",
                                            parts=[types.Part.from_text(text=selection_text)]
                                        )
                                    )
                                    await self.session_service.append_event(self.session, selection_event)
                                    logger.info(f"[Memory Bank] ✓ Added hero image selection event: {selected_image.asset_id}")
                                else:
                                    logger.warning(f"[Memory Bank] ⚠ Session not available, skipping hero image selection event")

                                # Broadcast update to frontend
                                await self.frontend_ws.send_text(json.dumps({
                                    "type": "brief_update",
                                    "data": {
                                        "brief": updated_brief.model_dump(mode="json"),
                                        "changed_fields": ["selected_image"]
                                    }
                                }))

                                logger.info(f"[ADK] ✓ Updated project brief with selected image")
                                logger.info(f"[ADK] ✓ Broadcasted brief_update to frontend")
                            else:
                                logger.error(f"[ADK] Project brief not found for {self.project_id}")
                        except Exception as e:
                            logger.error(f"[ADK] ✗ Failed to update brief with selected image: {e}", exc_info=True)
                            logger.error(f"[ADK] image_url was: {image_url[:100] if image_url else 'None'}")
                            # Send error to frontend
                            try:
                                await self.frontend_ws.send_text(json.dumps({
                                    "type": "error",
                                    "data": {
                                        "message": "Failed to update selected image",
                                        "error": str(e)
                                    }
                                }))
                            except:
                                pass

                    # Handle slogan selection from UI
                    elif "selected_slogan" in data:
                        slogan = data["selected_slogan"]
                        logger.info(f"[ADK] User selected slogan via UI: {slogan[:50]}...")

                        # Update project brief in Redis
                        try:
                            brief = await redis_client.get_project_brief(self.project_id)
                            if brief:
                                updated_brief = await redis_client.update_project_brief(
                                    self.project_id,
                                    {"selected_slogan": slogan}
                                )

                                # ADD SLOGAN SELECTION EVENT TO MEMORY BANK
                                if hasattr(self, 'session') and self.session:
                                    from google.adk.events import Event

                                    selection_text = f"Selected campaign slogan: \"{slogan}\""

                                    selection_event = Event(
                                        author="user",
                                        content=types.Content(
                                            role="user",
                                            parts=[types.Part.from_text(text=selection_text)]
                                        )
                                    )
                                    await self.session_service.append_event(self.session, selection_event)
                                    logger.info(f"[Memory Bank] ✓ Added slogan selection event")
                                else:
                                    logger.warning(f"[Memory Bank] ⚠ Session not available, skipping slogan selection event")

                                # Broadcast update to frontend
                                await self.frontend_ws.send_text(json.dumps({
                                    "type": "brief_update",
                                    "data": {
                                        "brief": updated_brief.model_dump(mode="json"),
                                        "changed_fields": ["selected_slogan"]
                                    }
                                }))

                                logger.info(f"[ADK] ✓ Updated project brief with selected slogan")
                                logger.info(f"[ADK] ✓ Broadcasted brief_update to frontend")
                            else:
                                logger.error(f"[ADK] Project brief not found for {self.project_id}")
                        except Exception as e:
                            logger.error(f"[ADK] ✗ Failed to update brief with selected slogan: {e}", exc_info=True)
                            # Send error to frontend
                            try:
                                await self.frontend_ws.send_text(json.dumps({
                                    "type": "error",
                                    "data": {
                                        "message": "Failed to update selected slogan",
                                        "error": str(e)
                                    }
                                }))
                            except:
                                pass

            except Exception as e:
                # Check if this is a normal disconnect (code 1005 = NO_STATUS_RCVD means client closed connection normally)
                from starlette.websockets import WebSocketDisconnect
                if isinstance(e, WebSocketDisconnect) and e.code in (1000, 1005):
                    # Normal closure - user clicked Settings or navigated away
                    logger.info(f"[ADK] Client disconnected normally after {message_count} messages (code: {e.code})")
                else:
                    # Unexpected error
                    logger.error(f"Client→Agent error after {message_count} messages: {e}", exc_info=True)
                    logger.error(f"Last message type: {message.get('type') if 'message' in locals() else 'N/A'}")
                break

    async def _agent_to_client_messaging(self):
        """Handle ADK → Frontend messaging."""
        event_count = 0
        async for event in self.live_events:
            event_count += 1
            try:
                logger.debug(f"[ADK] Processing event #{event_count}: {type(event).__name__}")
                # Handle input transcription (user speech → text)
                # Only process FINAL transcriptions to avoid sending partial/incomplete text
                if event.input_transcription and event.input_transcription.text:
                    # Check if transcription is finished
                    # finished=True means final, finished=False means partial, finished=None means unknown (treat as final)
                    is_finished = getattr(event.input_transcription, 'finished', None)

                    # Only skip if explicitly marked as partial (finished=False)
                    if is_finished is not False:
                        user_text = event.input_transcription.text
                        logger.debug(f"[User Transcript] Final transcription (finished={is_finished}): {user_text[:50]}...")

                        # ADD USER TEXT EVENT TO SESSION FOR MEMORY BANK
                        # This captures what the user said as text for conversation memory
                        # Must use session_service.append_event() to properly persist
                        if hasattr(self, 'session') and self.session:
                            from google.adk.events import Event
                            user_event = Event(
                                author="user",
                                content=types.Content(
                                    role="user",
                                    parts=[types.Part.from_text(text=user_text)]
                                )
                            )
                            await self.session_service.append_event(self.session, user_event)
                            logger.debug(f"[Memory Bank] Added user text event: {user_text[:50]}...")

                        # SEND USER TRANSCRIPT TO FRONTEND FOR DISPLAY
                        # Frontend TranscriptDisplay expects "text_output" type with "text" and "role"
                        await self.frontend_ws.send_text(json.dumps({
                            "type": "text_output",
                            "role": "user",
                            "text": user_text,
                        }))
                    else:
                        # Partial transcription (finished=False) - log but don't send to frontend
                        logger.debug(f"[User Transcript] Partial (finished=False, skipped): {event.input_transcription.text[:30]}...")

                # Handle output transcription (assistant speech → text)
                # Only process FINAL transcriptions to avoid sending partial/incomplete text
                if event.output_transcription and event.output_transcription.text:
                    # Check if transcription is finished
                    # finished=True means final, finished=False means partial, finished=None means unknown (treat as final)
                    is_finished = getattr(event.output_transcription, 'finished', None)

                    # Only skip if explicitly marked as partial (finished=False)
                    if is_finished is not False:
                        transcript_text = event.output_transcription.text
                        logger.debug(f"[Assistant Transcript] Final transcription (finished={is_finished}): {transcript_text[:50]}...")

                        # Log for debugging
                        await self._save_transcript("assistant", transcript_text)

                        # ADD ASSISTANT TEXT EVENT TO SESSION FOR MEMORY BANK
                        # The ADK session events only contain function calls by default
                        # We need to manually add text content for conversation memory
                        # Must use session_service.append_event() to properly persist
                        if hasattr(self, 'session') and self.session:
                            from google.adk.events import Event
                            assistant_event = Event(
                                author="model",
                                content=types.Content(
                                    role="model",
                                    parts=[types.Part.from_text(text=transcript_text)]
                                )
                            )
                            await self.session_service.append_event(self.session, assistant_event)
                            logger.debug(f"[Memory Bank] Added assistant text event: {transcript_text[:50]}...")

                        # Send to frontend (matching expected format)
                        await self.frontend_ws.send_text(json.dumps({
                            "type": "text_output",
                            "role": "assistant",
                            "text": transcript_text,
                        }))
                    else:
                        # Partial transcription (finished=False) - log but don't send to frontend
                        logger.debug(f"[Assistant Transcript] Partial (finished=False, skipped): {event.output_transcription.text[:30]}...")

                # Handle audio output
                # Frontend expects "audio_output" type with "data" field and "mime_type"
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.inline_data and part.inline_data.mime_type.startswith("audio/pcm"):
                            audio_data = part.inline_data.data
                            audio_base64 = base64.b64encode(audio_data).decode("ascii")

                            await self.frontend_ws.send_text(json.dumps({
                                "type": "audio_output",
                                "data": audio_base64,
                                "mime_type": "audio/pcm",
                            }))

                # Handle turn completion
                # Frontend expects "turn_complete" to know when to stop "producer speaking" indicator
                if hasattr(event, 'turn_complete') and event.turn_complete:
                    await self.frontend_ws.send_text(json.dumps({
                        "type": "turn_complete",
                    }))

                    # ================================================================
                    # MEMORY BANK PERSISTENCE (Single Source of Truth)
                    # ================================================================
                    # Persist conversation to Vertex AI Memory Bank after turn completes
                    # This is the ONLY persistence mechanism - Redis conversation history is deprecated
                    # NOTE: after_agent_callback doesn't trigger in run_live() mode,
                    # so we manually persist here when turn_complete is detected
                    if settings.enable_memory_bank and settings.memory_callback_enabled:
                        try:
                            from app.services.memory_service import memory_service

                            logger.info(
                                f"[Memory Bank] 🔄 Turn complete detected, persisting session: "
                                f"session_id={self.session_id}"
                            )

                            # Get the actual session from ADK's session_service
                            # This contains all events from the ADK conversation flow
                            latest_session = await self.session_service.get_session(
                                app_name="ai_agency_hub",
                                user_id=self.session_id,
                                session_id=self.session_id,
                            )

                            if latest_session:
                                # Log session state for debugging
                                event_count = len(latest_session.events) if hasattr(latest_session, 'events') else 0
                                logger.info(f"[Memory Bank] Retrieved session from ADK has {event_count} events")

                                # Log session details
                                logger.info(f"[Memory Bank] Session ID: {latest_session.id if hasattr(latest_session, 'id') else 'N/A'}")
                                logger.info(f"[Memory Bank] Session app_name: {latest_session.app_name}")
                                logger.info(f"[Memory Bank] Session user_id: {latest_session.user_id}")

                                # Only persist if we have events
                                if event_count == 0:
                                    logger.warning(
                                        f"[Memory Bank] ⚠ Session has no events yet, skipping persistence. "
                                        f"This may be the first turn before events are committed."
                                    )
                                else:
                                    # Check if events have content
                                    events_with_content = sum(
                                        1 for e in latest_session.events
                                        if hasattr(e, 'content') and e.content is not None
                                    )
                                    logger.info(f"[Memory Bank] Events with content: {events_with_content}/{event_count}")

                                    # ============================================================
                                    # INJECT PENDING CREATIVE SUMMARIES FOR MEMORY BANK
                                    # ============================================================
                                    # Inject any pending creative tool summaries queued during this turn
                                    if self.pending_creative_summaries:
                                        try:
                                            from google.genai.types import Content, Part

                                            for summary in self.pending_creative_summaries:
                                                latest_session.add_event(
                                                    Content(
                                                        role='model',
                                                        parts=[Part(text=summary)]
                                                    )
                                                )
                                                logger.info(f"[Memory Bank] ✓ Injected creative summary ({len(summary)} chars)")

                                            # Clear pending summaries
                                            count = len(self.pending_creative_summaries)
                                            self.pending_creative_summaries.clear()
                                            logger.info(f"[Memory Bank] Injected {count} creative summaries, queue cleared")
                                        except Exception as e:
                                            logger.warning(f"[Memory Bank] Failed to inject creative summaries: {e}")

                                    # ============================================================
                                    # INJECT PROJECT STATE SUMMARY FOR MEMORY BANK
                                    # ============================================================
                                    # Memory Bank filters out function calls/responses, so inject
                                    # project data as text content for semantic retrieval
                                    try:
                                        brief = await redis_client.get_project_brief(self.project_id)
                                        if brief:
                                            summary_parts = [
                                                f"[PROJECT STATE SNAPSHOT]",
                                                f"Product: {brief.product_name or 'Not set'}",
                                                f"Category: {brief.product_category or 'Not set'}",
                                                f"Theme: {brief.theme or 'Not set'}",
                                                f"Brand Tone: {brief.brand_tone or 'Not set'}",
                                                f"Target Market: {brief.target_market or 'Not set'}",
                                            ]

                                            if brief.key_features:
                                                summary_parts.append(f"Key Features: {', '.join(brief.key_features)}")

                                            if brief.selected_slogan:
                                                summary_parts.append(f"Selected Slogan: \"{brief.selected_slogan}\"")

                                            if brief.selected_image:
                                                summary_parts.append(f"Hero Image: Selected (variation {brief.selected_image.generation_params.get('variation', 'unknown')})")

                                            summary = "\n".join(summary_parts)

                                            # Add summary as model content to session
                                            from google.genai.types import Content, Part
                                            latest_session.add_event(
                                                Content(
                                                    role='model',
                                                    parts=[Part(text=summary)]
                                                )
                                            )
                                            logger.info(f"[Memory Bank] ✓ Injected project state summary into session")
                                    except Exception as e:
                                        logger.warning(f"[Memory Bank] Failed to inject project summary: {e}")

                                    # Persist to Memory Bank
                                    success = await memory_service.add_session_to_memory(
                                        session=latest_session,
                                    )

                                    if success:
                                        logger.info(
                                            f"[Memory Bank] ✅ SUCCESS: Session persisted to Vertex AI "
                                            f"(session={self.session_id}, events={event_count}, "
                                            f"with_content={events_with_content})"
                                        )
                                    else:
                                        logger.warning(
                                            f"[Memory Bank] ⚠️ SKIPPED: Persistence skipped "
                                            f"(session={self.session_id}, events={event_count}) - "
                                            f"Check memory_service logs for details"
                                        )
                            else:
                                logger.error(
                                    f"[Memory Bank] ❌ ERROR: Could not retrieve session from ADK "
                                    f"(session={self.session_id}) - Session may not exist in InMemorySessionService"
                                )

                        except Exception as e:
                            logger.error(
                                f"[Memory Bank] ❌ EXCEPTION: Failed to persist session "
                                f"(session={self.session_id}): {e}",
                                exc_info=True
                            )

                # Handle interruption
                if hasattr(event, 'interrupted') and event.interrupted:
                    await self.frontend_ws.send_text(json.dumps({
                        "type": "interrupted",
                    }))

            except Exception as e:
                # Check if this is a normal disconnect (sending to closed WebSocket)
                from starlette.websockets import WebSocketDisconnect
                if isinstance(e, (WebSocketDisconnect, ConnectionError, BrokenPipeError)):
                    logger.info(f"[ADK] Client connection closed while sending event #{event_count}")
                else:
                    logger.error(f"Agent→Client error at event #{event_count}: {e}", exc_info=True)
                    logger.error(f"Event type: {type(event).__name__ if 'event' in locals() else 'N/A'}")
                break

    async def _save_transcript(self, role: str, text: str):
        """
        Log conversation transcript for debugging.

        NOTE: Conversation history is automatically persisted to Vertex AI Memory Bank
        via turn_complete events. This method is kept only for debug logging.

        Args:
            role: Speaker role (user or assistant)
            text: Transcript text
        """
        # Log transcript for debugging (not persisted to storage)
        logger.debug(f"[Transcript] {role}: {text[:100]}{'...' if len(text) > 100 else ''}")

        # Conversation persistence is handled by Memory Bank on turn_complete
        # See _agent_to_client_messaging() method around line 1455 for Memory Bank integration

    async def disconnect(self):
        """Clean up ADK resources."""
        if self.live_request_queue:
            self.live_request_queue.close()
            logger.info("✓ ADK live queue closed")

        if self.frontend_ws:
            try:
                await self.frontend_ws.close()
            except:
                pass
