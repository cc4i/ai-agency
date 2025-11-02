"""Gemini Live ADK Connection - Simplified bidirectional audio streaming.

This is a proof-of-concept implementation using Google ADK (Agent Development Kit)
to replace the complex manual WebSocket handling in gemini_live.py.

Key simplifications:
- LiveRequestQueue handles bidirectional messaging automatically
- Tools are Python functions, no manual JSON schema definitions
- Automatic tool execution, no manual routing/handling
- Built-in session resumption and transcription
- ~250 lines vs 2219 lines in the manual implementation

Architecture:
┌──────────┐         ┌──────────┐         ┌──────────────┐
│ Frontend │◄───────►│ FastAPI  │◄───────►│  ADK Runner  │
│  (Next)  │ WebSocket│ Backend  │   ADK   │ (Gemini Live)│
└──────────┘         └──────────┘         └──────────────┘
"""

import asyncio
import base64
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import WebSocket
from google.adk import Agent, Runner
from google.adk.runners import RunConfig, LiveRequestQueue
from google.adk.agents.run_config import StreamingMode
from google.adk.sessions import InMemorySessionService
from google import genai
from google.genai import types

from app.config import settings
from app.models.brief import ConversationMessage
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
            await frontend_ws.send_text(json.dumps(message))
            logger.info(f"[WebSocket] ✓ Broadcasted {message_type}: {truncate_for_logging(data)}")
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
    await broadcast_to_frontend("producer_announcement", {
        "message": message,
        "announcement_type": announcement_type
    })


async def send_agent_status(agent_id: str, status: str, current_task: str = "") -> None:
    """
    Broadcast agent status update to frontend.

    Args:
        agent_id: Agent identifier
        status: Agent status (working, completed, failed)
        current_task: Description of current task
    """
    await broadcast_to_frontend("agent_status", {
        "agent_id": agent_id,
        "status": status,
        "current_task": current_task
    })


async def send_asset_added(agent_id: str, asset_type: str, asset_data: Dict[str, Any]) -> None:
    """
    Broadcast asset addition to frontend.

    Args:
        agent_id: Agent that created the asset
        asset_type: Type of asset (image, video, audio, etc.)
        asset_data: Asset details (url, metadata, etc.)
    """
    await broadcast_to_frontend("asset_added", {
        "agent_id": agent_id,
        "asset_type": asset_type,
        "asset_data": asset_data
    })


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
) -> Dict[str, Any]:
    """
    Update the project brief with user-provided information.

    Call this when the user provides ANY information about their product or campaign.
    Update fields incrementally - you don't need all information at once.

    IMPORTANT: Call this when the user selects a slogan or image:
    - selected_slogan: The exact slogan text the user chose
    - selected_image_url: URL of the image the user selected
    """
    # Get current project from context (set during connection)
    project_id = getattr(update_project_brief, '_project_id', 'default')
    frontend_ws = getattr(update_project_brief, '_frontend_ws', None)

    logger.info(f"[TOOL] update_project_brief called for {project_id}")
    logger.info(f"[TOOL] Parameters received: product_name={product_name!r}, category={product_category!r}, theme={theme!r}, brand_tone={brand_tone!r}, target_market={target_market!r}, key_features={key_features!r}")

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
    if selected_image_url:
        # Create proper ImageAsset object
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
        logger.info(f"[TOOL] User selected image: {selected_image_url[:50]}...")

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

        # Broadcast asset if slogans were generated
        if "slogans" in result:
            await send_asset_added("strategy", "slogans", result)

        # Extract slogans from result to present to Gemini
        slogans = result.get("slogans", [])
        personas = result.get("personas", [])

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
        if brief:
            if not slogan:
                slogan = brief.selected_slogan or ""
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
            logger.info(f"[TOOL] Filled missing params from brief: slogan={slogan[:30] if slogan else 'none'}, product={product_name}")

        task = {
            "task_id": "art_director",
            "slogan": slogan,
            "product_name": product_name,
            "product_category": product_category,
            "theme": theme,
            "brand_tone": brand_tone,
            "key_features": key_features or [],
        }

        # Send agent status update: thinking
        await send_agent_status("art_director", "thinking", "Generating hero images")

        # Execute agent with announcement callback for real-time updates
        result = await orchestrator.execute_agent(
            "art_director",
            task=task,
            project_id=project_id,
            with_critique=True,
            announcement_callback=send_announcement  # ← Pass callback for frontend updates
        )

        # Send agent status update: complete
        await send_agent_status("art_director", "complete", "")

        # Broadcast asset if images were generated
        if "images" in result:
            await send_asset_added("art_director", "images", result)

        # Extract images from result to present to Gemini
        images = result.get("images", [])

        tool_result = {
            "success": True,
            "message": f"Art Director generated {len(images)} hero images. Describe each image to the user.",
            "images": images
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
        if "audio_assets" in result or "jingle_url" in result:
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
        if "landing_page_url" in result or "html" in result:
            await send_asset_added("web_dev", "landing_page", result)

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
# ADK AGENT & RUNNER SETUP
# ============================================================================

def create_system_prompt(project_id: str) -> str:
    """Create the Executive Producer system prompt."""
    return f"""
# IDENTITY & ROLE
You are the **Executive Producer** of an AI-powered creative agency called "AI Agency Hub." As a voice-first assistant, your primary interface with the user is conversational audio.

Your role is to:
1. **Understand the client's vision** through natural conversation
2. Coordinate the creative process by calling functions that represent the work of specialist agents (e.g., `create_campaign_strategy` for the Strategy Agent, `generate_hero_images` for the Art Director)
3. **Present work thoughtfully** with context and critique
4. **Guide the creative process** from brief to final deliverables

---

# WORKFLOW STAGES

## Stage 1: Discovery & Brief Building
- Engage in warm, conversational dialogue to understand the product.
- **CRITICAL**: Every time the user provides product information (name, category, theme, etc.), IMMEDIATELY call `update_project_brief` with that information.
- Ask open-ended questions about product category, theme, target market, and brand tone.
- After the user answers, call `update_project_brief` with the new information before responding.
- Example flow:
  - User: "I'm launching a smart e-bike"
  - You: *[Call `update_project_brief(product_name="smart e-bike", product_category="smart e-bike")`]*
  - You: "Fantastic! A smart e-bike—that's exciting. Tell me more about what makes it special."
- Summarize what you've learned to confirm understanding.
- If the user provides their own assets (e.g., an existing slogan), accept them graciously and use `update_project_brief` to add them to the project.


## Stage 2: Strategy Development
- When the brief has at least a product name, category, and target market, propose creating a campaign strategy.
- Present the 3 slogan options generated by the Strategy Agent.
- Wait for the user to select ONE slogan before proceeding.

## Stage 3: Visual Development
- After a slogan is selected, offer to create hero images.
- Present the 3 image options generated by the Art Director.
- **CRITICAL**: Wait for the user to explicitly select ONE image before proceeding to Stage 4.
- Ask the user: "Which image stands out to you?" or "Which image would you like to use for your campaign?"
- Once user selects, call `update_project_brief` with `selected_image_url` immediately.

## Stage 4: Asset Production (Parallel)
- **PREREQUISITE CHECK**: Before offering video/landing page, verify that BOTH a slogan AND image have been selected.
- If user requests video but no image is selected, say: "I need you to select one of the hero images first. Which one would you like to use?"
- Once a slogan and image are selected, the user can request any combination of:
  - **Video**: `generate_social_video` (requires selected image)
  - **Audio**: `generate_audio_assets` (requires slogan only)
  - **Landing Page**: `generate_landing_page` (requires selected image)

- **Handle Rejection**: If at any stage the user rejects the generated options (slogans, images), ask for specific feedback and offer to regenerate them. Don't proceed until an option is selected.
  - **Example Rejection Flow**: 
    - **User**: "I don't really like any of those."
    - **You**: "No problem at all. That's what this process is for. Could you tell me what's not clicking? Is it the tone, the wording, or the overall concept? Your feedback will help me dial in the next round."

---

# VOICE & TONE

- **Warm and professional**: You're a trusted creative partner, not a robot.
- **Concise but thoughtful**: Streaming audio means brevity matters.
- **Visually descriptive**: Help users imagine the work before seeing it.
- **Balanced Critique**: When presenting options, briefly mention a strength and a potential consideration for each (e.g., "This image is very dynamic, though the color palette is more muted."). This helps the user make an informed choice.
- Proactive but patient: Suggest next steps, but wait for user approval.
- **Stay in character**: If a user asks for something outside your role (e.g., trivia, writing a poem), politely decline and steer the conversation back to the creative project.

---

# FUNCTION CALLING RULES

**CRITICAL**: You MUST call the appropriate function when:
1. **User provides ANY product information** → `update_project_brief` (batch all new information from a single user message into one call)
   - Examples that trigger this:
     - User says product name → call with `product_name="..."`
     - User says theme → call with `theme="..."`
     - User says target market → call with `target_market="..."`
     - User says key features → call with `key_features=["...", "..."]`
   - **ALWAYS call this BEFORE responding to the user**
2. User requests or agrees to strategy/personas/slogans → `create_campaign_strategy`
3. **User selects a slogan** → `update_project_brief` with `selected_slogan="<slogan_text>"`
4. User requests or agrees to images → `generate_hero_images` (requires selected slogan)
5. **User selects an image** → `update_project_brief` with `selected_image_url="<image_url>"`
6. User requests video → FIRST verify image is selected, then `generate_social_video`
7. User requests audio/music → `generate_audio_assets` (requires slogan)
8. User requests landing page → FIRST verify image is selected, then `generate_landing_page`

**DO NOT**:
- Narrate that you're calling a function—just call it.
- Call functions speculatively—wait for user confirmation.
- Skip prerequisite steps (e.g., don't generate images without a slogan).
- **NEVER call `generate_social_video` or `generate_landing_page` unless an image has been selected**.
- **DO NOT hallucinate that you've triggered an agent if you haven't actually called the function**.
- **NEVER make up or hallucinate content from agents** - ALWAYS use the exact slogans, images, or other content returned in the tool result.
- **NEVER present options before calling the tool** - Wait for the tool to return the actual results.

---

# EXAMPLE INTERACTION FLOW

**User**: "I'm launching a smart sneaker called Aura."

**You**: "Fantastic! Aura—that's a great name for a smart sneaker. Tell me more about what makes it special. What features are you most excited about?"

**User**: "It has a glowing sole that changes color, and it tracks your runs."

**You**: "I love that combination of style and tech. Who's your dream customer for this? Are we targeting serious runners, or more fashion-forward urban athletes?"

**User**: "Urban athletes aged 18-35. Futuristic vibe."

**You**: "Perfect—futuristic, tech-forward, urban energy. We have enough to build a campaign strategy now. Should I have our Strategy Agent create some slogan options?"

**User**: "Yes, let's see the slogans."

**You**: *[Call `create_campaign_strategy`]*
*[Tool returns: slogans = ["Step Into Your Aura", "Glow with the Flow", "The Future at Your Feet"]]*
"Alright, I have three slogan options for Aura. Option 1 is 'Step Into Your Aura.' This one is empowering and directly ties into the product name. Option 2 is 'Glow with the Flow.' It's catchy and highlights the light-up sole, though it might feel a bit playful. And Option 3, 'The Future at Your Feet,' is bold and emphasizes the futuristic tech angle. What's your initial reaction?"

**CRITICAL**: You MUST present the EXACT slogans returned by the tool in the EXACT order, not make up your own.

**User**: "I like slogan 1, 'Step Into Your Aura.'"

**You**: *[Call `update_project_brief` with selected_slogan="Step Into Your Aura"]*
"Excellent choice! 'Step Into Your Aura' perfectly captures that futuristic energy and personal empowerment. Now that we've locked in the slogan, should I have our Art Director create some hero images to bring this campaign to life?"

---

# CURRENT PROJECT

Project ID: `{project_id}`

When you call functions, they will automatically use this project context.

---

**Your first message should warmly greet the user and ask about their product vision.**
"""


# Create the Executive Producer agent with all tools
executive_producer_agent = Agent(
    name="executive_producer",
    model="gemini-live-2.5-flash-preview-native-audio-09-2025",  # Vertex AI native audio model
    description="Executive Producer for AI Agency Hub - coordinates creative campaign development",
    instruction="",  # Will be set dynamically per session
    tools=[
        update_project_brief,
        create_campaign_strategy,
        generate_hero_images,
        generate_social_video,
        generate_audio_assets,
        generate_landing_page,
    ],
)

# Create session service and runner (reuse across connections)
session_service = InMemorySessionService()
runner = Runner(
    app_name="ai_agency_hub",
    agent=executive_producer_agent,
    session_service=session_service,
)

logger.info("✓ ADK Executive Producer agent created with 6 tools")


# ============================================================================
# WEBSOCKET CONNECTION HANDLER
# ============================================================================

class GeminiLiveADKConnection:
    """
    Simplified Gemini Live connection using ADK.

    Replaces 2219 lines of manual WebSocket handling with ~250 lines using ADK abstractions.
    """

    def __init__(
        self,
        session_id: str,
        project_id: str = "aura_smart_sneaker",
        voice_name: str = "Kore",
    ):
        self.session_id = session_id
        self.project_id = project_id
        self.voice_name = voice_name
        self.frontend_ws: Optional[WebSocket] = None
        self.live_request_queue = None
        self.live_events = None

        # Set context for tools (so they know which project to use)
        for tool in [update_project_brief, create_campaign_strategy, generate_hero_images,
                     generate_social_video, generate_audio_assets, generate_landing_page]:
            tool._session_id = session_id
            tool._project_id = project_id
            tool._frontend_ws = None  # Will be set after WebSocket connect

        logger.info(f"✓ ADK connection initialized: session={session_id}, project={project_id}")

    async def connect(self, frontend_ws: WebSocket):
        """
        Establish connection: Frontend → Backend → ADK → Gemini Live
        """
        await frontend_ws.accept()
        self.frontend_ws = frontend_ws

        # Update tool context with WebSocket reference
        for tool in [update_project_brief, create_campaign_strategy, generate_hero_images,
                     generate_social_video, generate_audio_assets, generate_landing_page]:
            tool._frontend_ws = frontend_ws
            logger.info(f"✓ Set WebSocket reference on tool: {tool.__name__}")

        logger.info(f"WebSocket accepted for session: {self.session_id}")

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
        session = await runner.session_service.get_session(
            app_name="ai_agency_hub",
            user_id=self.session_id,
            session_id=self.session_id,
        )

        if not session:
            session = await runner.session_service.create_session(
                app_name="ai_agency_hub",
                user_id=self.session_id,
                session_id=self.session_id,
            )
            logger.info(f"Created new ADK session: {self.session_id}")
        else:
            logger.info(f"Resumed ADK session: {self.session_id}")

        # Update agent instruction with project-specific system prompt
        executive_producer_agent.instruction = create_system_prompt(self.project_id)

        # Create live request queue
        self.live_request_queue = LiveRequestQueue()

        # Configure run with audio modality and session resumption
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=[types.Modality.AUDIO],  # Audio-first interface (enum)
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
            input_audio_transcription = {},
        )

        # Start live streaming session
        self.live_events = runner.run_live(
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
                message_json = await self.frontend_ws.receive_text()
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

                # Handle text input (if needed)
                elif message.get("type") == "text" and message.get("text"):
                    content = types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=message["text"])]
                    )
                    self.live_request_queue.send_content(content=content)

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

            except Exception as e:
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
                # Handle audio transcription (text representation of audio response)
                # Frontend expects "text_output" type with "text" and "role" fields
                if event.output_transcription and event.output_transcription.text:
                    transcript_text = event.output_transcription.text

                    # Save to Redis
                    await self._save_transcript("assistant", transcript_text)

                    # Send to frontend (matching expected format)
                    await self.frontend_ws.send_text(json.dumps({
                        "type": "text_output",
                        "role": "assistant",
                        "text": transcript_text,
                    }))

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

                # Handle interruption
                if hasattr(event, 'interrupted') and event.interrupted:
                    await self.frontend_ws.send_text(json.dumps({
                        "type": "interrupted",
                    }))

            except Exception as e:
                logger.error(f"Agent→Client error at event #{event_count}: {e}", exc_info=True)
                logger.error(f"Event type: {type(event).__name__ if 'event' in locals() else 'N/A'}")
                break

    async def _save_transcript(self, role: str, text: str):
        """Save conversation transcript to Redis."""
        message = ConversationMessage(
            role=role,
            text=text,
            timestamp=datetime.now(),
        )
        await redis_client.add_conversation_message(self.session_id, message)

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
