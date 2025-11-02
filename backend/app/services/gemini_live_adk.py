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
# HELPER FUNCTIONS - WebSocket broadcasting utilities
# ============================================================================

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
            logger.info(f"[WebSocket] ✓ Successfully broadcasted {message_type} to frontend: {data}")
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
        # Store as ImageAsset format
        updates["selected_image"] = {"url": selected_image_url, "type": "hero"}
        logger.info(f"[TOOL] User selected image: {selected_image_url}")

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

    return {
        "success": True,
        "message": f"Updated project brief for {product_name or 'product'}",
        "updated_fields": list(updates.keys()),
        "brief": brief.model_dump(mode="json")
    }


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
    from app.services.orchestration import AgentOrchestrator

    orchestrator = AgentOrchestrator()
    project_id = getattr(create_campaign_strategy, '_project_id', 'default')

    logger.info(f"[TOOL] create_campaign_strategy called for {project_id}")

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

    return {
        "success": True,
        "message": "Strategy Agent has created campaign personas and slogans",
        "result": result
    }


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
    from app.services.orchestration import AgentOrchestrator

    orchestrator = AgentOrchestrator()
    project_id = getattr(generate_hero_images, '_project_id', 'default')

    logger.info(f"[TOOL] generate_hero_images called for {project_id}")

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

    return {
        "success": True,
        "message": "Art Director has created hero images",
        "result": result
    }


async def generate_social_video(
    image_asset_id: str,
    product_name: str,
    theme: str = "",
    slogan: str = "",
    key_features: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Task the Video Producer Agent to create a 15-second social media video.

    Call ONLY when:
    1. Hero images have been generated
    2. User has selected one image
    3. User requests video
    """
    from app.services.orchestration import AgentOrchestrator

    orchestrator = AgentOrchestrator()
    project_id = getattr(generate_social_video, '_project_id', 'default')

    logger.info(f"[TOOL] generate_social_video called for {project_id}")

    task = {
        "task_id": "video_producer",
        "image_asset_id": image_asset_id,
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

    return {
        "success": True,
        "message": "Video Producer has created a social media video",
        "result": result
    }


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
    from app.services.orchestration import AgentOrchestrator

    orchestrator = AgentOrchestrator()
    project_id = getattr(generate_audio_assets, '_project_id', 'default')

    logger.info(f"[TOOL] generate_audio_assets called for {project_id}")

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

    return {
        "success": True,
        "message": "Audio Team has created audio assets",
        "result": result
    }


async def generate_landing_page(
    image_asset_id: str,
    product_name: str,
    slogan: str = "",
    brand_tone: str = "",
    key_features: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Task the Web Dev Agent to create a landing page.

    Call ONLY when:
    1. Hero images exist
    2. User has selected an image
    3. User requests landing page/website
    """
    from app.services.orchestration import AgentOrchestrator

    orchestrator = AgentOrchestrator()
    project_id = getattr(generate_landing_page, '_project_id', 'default')

    logger.info(f"[TOOL] generate_landing_page called for {project_id}")

    task = {
        "task_id": "web_dev",
        "image_asset_id": image_asset_id,
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

    return {
        "success": True,
        "message": "Web Dev Agent has created the landing page",
        "result": result
    }


# ============================================================================
# ADK AGENT & RUNNER SETUP
# ============================================================================

def create_system_prompt(project_id: str) -> str:
    """Create the Executive Producer system prompt."""
    return f"""# IDENTITY & ROLE

You are the **Executive Producer** of an AI-powered creative agency called "AI Agency Hub."

Your role is to:
1. **Understand the client's vision** through natural conversation
2. **Coordinate specialist agents** (Strategy, Art Director, Video Producer, Audio Team, Web Dev)
3. **Present work thoughtfully** with context and critique
4. **Guide the creative process** from brief to final deliverables

---

# WORKFLOW STAGES

## Stage 1: Discovery & Brief Building
- Engage in warm, conversational dialogue to understand the product
- Ask open-ended questions about product category, theme, target market, brand tone
- **CALL `update_project_brief`** as information is gathered (don't wait for all details)
- Summarize what you've learned and confirm understanding

## Stage 2: Strategy Development
- When the brief has sufficient detail, propose creating campaign strategy
- **CALL `create_campaign_strategy`** to generate personas and slogans
- Present the 3 slogan options with rationale
- Wait for user to select ONE slogan before proceeding
- **CALL `update_project_brief`** with `selected_slogan` when user chooses a slogan

## Stage 3: Visual Development
- After slogan selection, offer to create hero images
- **CALL `generate_hero_images`** with the selected slogan
- Present the 3 image options with creative critique
- Wait for user to select ONE image
- **CALL `update_project_brief`** with `selected_image_url` when user chooses an image

## Stage 4: Asset Production (Parallel)
User can now request any combination of:
- **Video**: `generate_social_video` (requires selected image)
- **Audio**: `generate_audio_assets` (requires slogan)
- **Landing Page**: `generate_landing_page` (requires selected image)

---

# VOICE & TONE

- **Warm and professional**: You're a trusted creative partner, not a robot
- **Concise but thoughtful**: Streaming audio means brevity matters
- **Visually descriptive**: Help users imagine the work before seeing it
- **Honest critique**: Point out strengths AND potential improvements
- **Proactive but patient**: Suggest next steps, but wait for user approval

---

# FUNCTION CALLING RULES

**CRITICAL**: You MUST call the appropriate function when:
1. User provides product information → `update_project_brief`
2. User requests strategy/personas/slogans → `create_campaign_strategy`
3. **User selects a slogan** → `update_project_brief` with `selected_slogan="<slogan_text>"`
4. User requests images → `generate_hero_images` (requires selected slogan)
5. **User selects an image** → `update_project_brief` with `selected_image_url="<image_url>"`
6. User requests video → `generate_social_video` (requires selected image)
7. User requests audio/music → `generate_audio_assets`
8. User requests landing page → `generate_landing_page` (requires selected image)

**DO NOT**:
- Narrate that you're calling a function—just call it
- Call functions speculatively—wait for user confirmation
- Skip prerequisite steps (e.g., don't generate images without a slogan)

---

# EXAMPLE INTERACTION FLOW

**User**: "I'm launching a smart sneaker called Aura."

**You**: *[Call `update_project_brief` with product_name="Aura", product_category="footwear"]*
"Fantastic! Aura—that's a great name for a smart sneaker. Tell me more about what makes it special. What features are you most excited about?"

**User**: "It has a glowing sole that changes color, and it tracks your runs."

**You**: *[Call `update_project_brief` with key_features=["glowing sole", "smart tracking"]]*
"I love that combination of style and tech. Who's your dream customer for this? Are we targeting serious runners, or more fashion-forward urban athletes?"

**User**: "Urban athletes aged 18-35. Futuristic vibe."

**You**: *[Call `update_project_brief` with target_market="Urban athletes aged 18-35", theme="futuristic"]*
"Perfect—futuristic, tech-forward, urban energy. We have enough to build a campaign strategy now. Should I have our Strategy Agent create some personas and slogan options?"

**User**: "Yes, let's see the slogans."

**You**: *[Call `create_campaign_strategy`]*
*[Wait for result, then present 3 slogans with rationale]*

**User**: "I like slogan 2, 'Step Into Your Aura'."

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
        while True:
            try:
                message_json = await self.frontend_ws.receive_text()
                message = json.loads(message_json)

                # Handle audio input (frontend sends "audio_input" type with "data" field)
                if message.get("type") == "audio_input" and message.get("data"):
                    audio_base64 = message["data"]
                    decoded_audio = base64.b64decode(audio_base64)

                    logger.debug(f"[ADK] Sending audio chunk: {len(decoded_audio)} bytes (base64: {len(audio_base64)} chars)")

                    # Send realtime audio to ADK
                    # IMPORTANT: Must specify sample rate - frontend sends 16kHz PCM
                    # Using audio/l16 as it's the standard for raw 16-bit PCM audio.
                    self.live_request_queue.send_realtime(
                        types.Blob(data=decoded_audio, mime_type="audio/l16;rate=16000")
                    )

                # Handle text input (if needed)
                elif message.get("type") == "text" and message.get("text"):
                    content = types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=message["text"])]
                    )
                    self.live_request_queue.send_content(content=content)

            except Exception as e:
                logger.error(f"Client→Agent error: {e}")
                break

    async def _agent_to_client_messaging(self):
        """Handle ADK → Frontend messaging."""
        async for event in self.live_events:
            try:
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
                logger.error(f"Agent→Client error: {e}")
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
