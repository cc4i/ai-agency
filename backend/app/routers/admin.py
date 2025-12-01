"""Admin API Router.

Provides endpoints for system configuration and management.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.redis_client import redis_client
from app.services.gemini_live_adk import create_system_prompt, get_system_prompt_template

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# Redis key for custom system prompt
SYSTEM_PROMPT_KEY = "config:system_prompt"


# ============ Request/Response Models ============


class SystemPromptResponse(BaseModel):
    """Response containing system prompt."""

    prompt: str
    is_custom: bool
    character_count: int


class UpdateSystemPromptRequest(BaseModel):
    """Request to update system prompt."""

    prompt: str


class UpdateSystemPromptResponse(BaseModel):
    """Response from updating system prompt."""

    success: bool
    message: str
    character_count: int


# ============ Endpoints ============


@router.get("/system-prompt", response_model=SystemPromptResponse)
async def get_system_prompt(project_id: str = "default"):
    """
    Get the current system prompt.

    Returns custom prompt if set, otherwise returns the default prompt.

    Args:
        project_id: Project ID to include in the prompt template

    Returns:
        Current system prompt with metadata
    """
    try:
        # Check for custom prompt in Redis
        custom_prompt = await redis_client.client.get(SYSTEM_PROMPT_KEY)

        if custom_prompt:
            prompt = custom_prompt
            is_custom = True
            logger.debug(f"Retrieved custom system prompt ({len(prompt)} chars)")
        else:
            # Return default prompt TEMPLATE (with {project_id} placeholder intact)
            prompt = get_system_prompt_template()
            is_custom = False
            logger.debug(f"Using default system prompt template ({len(prompt)} chars)")

        return SystemPromptResponse(
            prompt=prompt,
            is_custom=is_custom,
            character_count=len(prompt),
        )

    except Exception as e:
        logger.error(f"Failed to get system prompt: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get system prompt: {e}")


@router.put("/system-prompt", response_model=UpdateSystemPromptResponse)
async def update_system_prompt(request: UpdateSystemPromptRequest):
    """
    Update the system prompt.

    The custom prompt will be used for all new sessions until reset.

    Args:
        request: New system prompt content

    Returns:
        Success status and character count
    """
    try:
        prompt = request.prompt.strip()

        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")

        # Warn if prompt is very long (may impact performance)
        if len(prompt) > 15000:
            logger.warning(f"System prompt is very long ({len(prompt)} chars)")

        # Save to Redis (no expiry - persists until deleted)
        await redis_client.client.set(SYSTEM_PROMPT_KEY, prompt)

        logger.info(f"Updated system prompt ({len(prompt)} chars)")

        return UpdateSystemPromptResponse(
            success=True,
            message="System prompt updated successfully",
            character_count=len(prompt),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update system prompt: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update system prompt: {e}")


@router.delete("/system-prompt")
async def reset_system_prompt():
    """
    Reset to the default system prompt.

    Deletes any custom prompt, causing the system to use the built-in default.

    Returns:
        Success status
    """
    try:
        # Delete custom prompt from Redis
        deleted = await redis_client.client.delete(SYSTEM_PROMPT_KEY)

        if deleted:
            logger.info("Reset system prompt to default")
            return {"success": True, "message": "System prompt reset to default"}
        else:
            return {"success": True, "message": "Already using default prompt"}

    except Exception as e:
        logger.error(f"Failed to reset system prompt: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reset system prompt: {e}")


@router.get("/system-prompt/default", response_model=SystemPromptResponse)
async def get_default_system_prompt():
    """
    Get the default system prompt template (ignoring any custom prompt).

    Returns the template with {project_id} placeholder intact for editing.
    The placeholder is substituted at session initialization time.

    Returns:
        Default system prompt template
    """
    prompt = get_system_prompt_template()

    return SystemPromptResponse(
        prompt=prompt,
        is_custom=False,
        character_count=len(prompt),
    )
