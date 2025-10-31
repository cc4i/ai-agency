"""Gemini Live WebSocket Connection - Bidirectional audio streaming.

Manages the WebSocket connection to Gemini Live API for:
- Real-time audio streaming (user → Gemini Live)
- Real-time audio playback (Gemini Live → user)
- Text transcript streaming (simultaneous with audio)
- Turn-taking and conversation flow
"""

import asyncio
import base64
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# Monkey-patch websockets library to use longer ping timeouts for Vertex AI
# Vertex AI streaming can be slow to respond to keepalive pings during audio processing
import websockets.asyncio.client as ws_client
_original_connect = ws_client.connect

def patched_connect(*args, **kwargs):
    """WebSocket connect with extended ping timeout for Vertex AI streaming."""
    # Override default ping parameters if not explicitly set
    if 'ping_interval' not in kwargs:
        kwargs['ping_interval'] = 60  # Send ping every 60 seconds (default: 20)
    if 'ping_timeout' not in kwargs:
        kwargs['ping_timeout'] = 120  # Wait 2 minutes for pong (default: 20)
    if 'close_timeout' not in kwargs:
        kwargs['close_timeout'] = 60  # Wait 1 minute for close frame (default: 10)
    return _original_connect(*args, **kwargs)

ws_client.connect = patched_connect

from google import genai
from google.genai.types import (
    LiveConnectConfig,
    SpeechConfig,
    VoiceConfig,
    PrebuiltVoiceConfig,
    Blob,
    HttpOptions,
    RealtimeInputConfig,
    AutomaticActivityDetection,
    StartSensitivity,
    EndSensitivity,
    SessionResumptionConfig,
)
from fastapi import WebSocket

from app.config import settings
from app.models.brief import ConversationMessage
from app.services.redis_client import redis_client # Import redis_client

logger = logging.getLogger(__name__)
logger.info("✓ WebSocket library patched with extended timeouts (ping: 60s, timeout: 120s)")


class GeminiLiveConnection:
    """
    Manages bidirectional connection: Frontend ↔ Backend ↔ Gemini Live

    Architecture:
    ┌──────────┐         ┌──────────┐         ┌──────────────┐
    │ Frontend │◄───────►│ FastAPI  │◄───────►│ Gemini Live  │
    │  (Next)  │ WebSocket│ Backend  │ WebSocket│     API      │
    └──────────┘         └──────────┘         └──────────────┘

    Handles:
    - User audio input → Gemini Live
    - Gemini Live audio output → User
    - Gemini Live text transcript → User (simultaneous)
    - User text transcript (from STT) → Display
    - Agent function calls → AgentOrchestrator
    """

    def __init__(
        self,
        session_id: str,
        project_id: str = "aura_smart_sneaker",
        system_prompt: Optional[str] = None,
        voice_name: str = "Aoede",  # Options: Puck, Charon, Kore, Fenrir, Aoede
    ):
        """
        Initialize Gemini Live connection.

        Args:
            session_id: User session identifier
            project_id: Project identifier for agent tasks
            system_prompt: System instructions for Gemini Live
            voice_name: Voice to use for TTS (Puck, Charon, Kore, Fenrir, Aoede)
        """
        self.session_id = session_id
        self.project_id = project_id
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        self.voice_name = voice_name

        self.frontend_ws: Optional[WebSocket] = None
        self.gemini_session: Optional[Any] = None
        self._session_handle: Optional[str] = None  # Track session handle for resumption

        # Initialize genai client with Vertex AI
        # Configure with extended timeout and keepalive for live streaming
        import httpx

        # Create custom async client with longer timeouts and keepalive
        async_client = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=60.0, read=300.0, write=300.0, pool=300.0),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=300.0,  # Keep connections alive for 5 minutes
            ),
        )

        self.genai_client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
            http_options=HttpOptions(
                timeout=300,  # 5 minutes for client-level timeout
                httpx_async_client=async_client,
            ),
        )

        self.is_connected = False
        self.conversation_history: list[ConversationMessage] = []
        self.turn_count = 0  # Track conversation turns
        self._turn_ready_for_increment = False  # Track if we can increment on next user input
        self._current_turn_started = False  # Track if user has started speaking in current turn

        # Audio debugging - save audio chunks to file
        self.audio_file_handle = None
        if settings.save_audio_debug:
            debug_dir = Path(settings.audio_debug_dir)
            debug_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_file_path = debug_dir / f"audio_input_{session_id[:8]}_{timestamp}.pcm"
            self.audio_file_handle = open(audio_file_path, "wb")
            self._log("info", f"💾 Saving audio to: {audio_file_path}")

        # Callbacks
        self.on_text_received: Optional[Callable[[str, str], None]] = None
        self.on_turn_complete: Optional[Callable[[], None]] = None

        # Result listener for async agent tasks
        self._result_listener_task: Optional[asyncio.Task] = None

    def _log(self, level: str, message: str) -> None:
        """Log with session context."""
        prefix = f"[Session: {self.session_id[:8]}...] [Turn: {self.turn_count}]"
        full_message = f"{prefix} {message}"
        if level == "info":
            logger.info(full_message)
        elif level == "error":
            logger.error(full_message)
        elif level == "warning":
            logger.warning(full_message)
        elif level == "debug":
            logger.debug(full_message)

    def _get_agent_tools(self) -> list:
        """
        Define agent function tools for Gemini Live function calling.

        Returns:
            List of function declarations
        """
        return [
            {
                "name": "update_project_brief",
                "description": "Update the project brief with information learned from the conversation. Call this IMMEDIATELY when you learn product details from the user (name, category, theme, features, target market, etc.). This keeps the brief in sync with the conversation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_name": {
                            "type": "string",
                            "description": "Product name if mentioned"
                        },
                        "product_category": {
                            "type": "string",
                            "description": "Product category (footwear, beverage, electronics, toy, fashion, beauty, automotive, food, etc.)"
                        },
                        "theme": {
                            "type": "string",
                            "description": "Campaign theme or visual concept"
                        },
                        "key_features": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key product features to highlight"
                        },
                        "brand_tone": {
                            "type": "string",
                            "description": "Brand tone (futuristic, luxury, playful, edgy, professional, energetic, etc.)"
                        },
                        "target_market": {
                            "type": "string",
                            "description": "Target market description"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "create_campaign_strategy",
                "description": "Task the Strategy Agent to create campaign personas, slogans, and market positioning. Call this when the user explicitly requests strategy/personas/slogans. You can call this even if you don't have all the details - missing fields will be pulled from the project brief.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_name": {
                            "type": "string",
                            "description": "Name of the product (optional - will use project brief if not provided)"
                        },
                        "product_category": {
                            "type": "string",
                            "description": "Product category (optional - will use project brief if not provided)"
                        },
                        "theme": {
                            "type": "string",
                            "description": "Campaign theme or concept (optional)"
                        },
                        "key_features": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key product features to highlight (optional)"
                        },
                        "brand_tone": {
                            "type": "string",
                            "description": "Brand tone (optional)"
                        },
                        "target_market": {
                            "type": "string",
                            "description": "Target market description (optional)"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "generate_hero_images",
                "description": "Task the Art Director Agent to create hero images for the campaign. Call this ONLY when: (1) The Strategy Agent has completed and generated slogans, AND (2) The user has explicitly SELECTED one slogan, AND (3) The user requests images/visuals to be created. Do NOT call automatically - wait for user to choose a slogan and request images.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "slogan": {
                            "type": "string",
                            "description": "The selected campaign slogan chosen by the user"
                        },
                        "product_name": {
                            "type": "string",
                            "description": "Name of the product from the brief"
                        },
                        "product_category": {
                            "type": "string",
                            "description": "Product category (footwear, beverage, electronics, etc.)"
                        },
                        "theme": {
                            "type": "string",
                            "description": "Visual theme from the brief"
                        },
                        "brand_tone": {
                            "type": "string",
                            "description": "Brand tone from the brief"
                        },
                        "key_features": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key product features to highlight in images"
                        }
                    },
                    "required": ["slogan", "product_name"]
                }
            },
            {
                "name": "generate_social_video",
                "description": "Task the Video Producer Agent to create a 15-second social media video clip. Call this ONLY when: (1) Hero images have been generated by the Art Director, AND (2) User has selected one image, AND (3) User requests a video to be created. Do NOT call automatically - wait for user to select an image and request video.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_asset_id": {
                            "type": "string",
                            "description": "The asset_id of the selected hero image to use for video generation"
                        },
                        "product_name": {
                            "type": "string",
                            "description": "Name of the product from the brief"
                        },
                        "theme": {
                            "type": "string",
                            "description": "Visual theme from the brief"
                        },
                        "key_features": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key product features to highlight in the video"
                        },
                        "slogan": {
                            "type": "string",
                            "description": "The selected campaign slogan"
                        }
                    },
                    "required": ["image_asset_id", "product_name"]
                }
            },
            {
                "name": "generate_audio_assets",
                "description": "Task the Audio Team Agent to create audio assets (jingle, podcast ad, voiceover). Call this when user requests audio content or music for the campaign. Can be called after strategy is complete.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_name": {
                            "type": "string",
                            "description": "Name of the product from the brief"
                        },
                        "slogan": {
                            "type": "string",
                            "description": "The selected campaign slogan"
                        },
                        "theme": {
                            "type": "string",
                            "description": "Campaign theme from the brief"
                        },
                        "brand_tone": {
                            "type": "string",
                            "description": "Brand tone from the brief"
                        },
                        "product_category": {
                            "type": "string",
                            "description": "Product category"
                        }
                    },
                    "required": ["product_name", "theme"]
                }
            },
            {
                "name": "generate_landing_page",
                "description": "Task the Web Dev Agent to create a landing page with HTML/CSS/JS code. Call this ONLY when: (1) Hero images exist, AND (2) User has selected an image, AND (3) User requests a landing page or website. The page will feature the selected hero image and slogan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_asset_id": {
                            "type": "string",
                            "description": "The asset_id of the selected hero image to feature on the landing page"
                        },
                        "product_name": {
                            "type": "string",
                            "description": "Name of the product from the brief"
                        },
                        "slogan": {
                            "type": "string",
                            "description": "The selected campaign slogan"
                        },
                        "theme": {
                            "type": "string",
                            "description": "Visual theme from the brief"
                        },
                        "brand_tone": {
                            "type": "string",
                            "description": "Brand tone from the brief"
                        },
                        "product_category": {
                            "type": "string",
                            "description": "Product category"
                        },
                        "key_features": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key product features to highlight"
                        }
                    },
                    "required": ["image_asset_id", "product_name", "slogan"]
                }
            },
            {
                "name": "check_workflow_status",
                "description": "Check current campaign progress and get recommendation for next step. Call this when user asks to 'continue', 'resume', 'what's next', or 'where are we'. Returns current state of slogans, images, and completed agents.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]

    def _get_default_system_prompt(self) -> str:
        """
        Get default system prompt for Executive Producer personality.

        Returns:
            System prompt
        """
        return """
        You are the Executive Producer of a creative AI agency engaging in a multi-turn conversation with the Creative Director (user).

        Your role is to:
        1. CONTINUOUSLY UPDATE the Project Brief as you learn information from the conversation
        2. CALL check_workflow_status() before delegating tasks to check for existing work
        3. ASK THE USER if they want to use existing work or regenerate when work already exists
        4. Delegate tasks to specialist agents ONLY when user explicitly requests regeneration OR work doesn't exist
        5. Provide status updates as agents work
        6. Evaluate agent outputs and present them to the user
        7. Guide the conversation through campaign creation

        IMPORTANT: STATE AWARENESS - CHECK BEFORE EXECUTING

        Before calling any agent function (create_campaign_strategy, generate_hero_images, etc.), YOU MUST:
        1. CALL check_workflow_status() to see if work already exists
        2. Inform the user of existing results from the status check
        3. Ask if they want to USE EXISTING or REGENERATE
        4. ONLY call the agent function if user explicitly wants to regenerate OR if work doesn't exist

        Examples of state-aware responses:

        User: "Can you create slogans?"
        → CALL check_workflow_status() first
        → If slogans exist: "I see we already have 5 slogans from a previous session:
                            1. Run Your Future
                            2. Step Into Tomorrow
                            3. Motion Meets Intelligence
                            4. Stride Into the Future
                            5. Your Pace, Your Power

                            Would you like to:
                            A) Use these existing slogans and move forward
                            B) Generate new slogans

                            Let me know!"
        → If NO slogans: "I'll call our Strategy Agent to create slogans for you now." [THEN call create_campaign_strategy]

        User: "Can you create images?"
        → CALL check_workflow_status() first
        → If slogan selected AND images exist: "We already have 4 hero images generated with the slogan 'Run Your Future'. Would you like to review them or generate new ones?"
        → If slogan selected AND no images: "Great! I'll call our Art Director to create hero images with your selected slogan." [THEN call generate_hero_images]
        → If NO slogan selected: "First, I need to know which slogan to use. Looking at our slogans, which one do you prefer?"

        User: "Let's continue where we left off"
        → CALL check_workflow_status()
        → Example response: "Looking at our progress:
                            ✅ Product brief complete
                            ✅ 5 slogans generated (you selected: 'Run Your Future')
                            ✅ 4 hero images created
                            ❌ Video not yet created
                            ❌ Landing page not yet created

                            Would you like me to create a video from one of the images?"

        CRITICAL WORKFLOW - FOLLOW THIS ORDER:

        PHASE 1: GATHER INFORMATION (Use update_project_brief)
        - As the user talks, IMMEDIATELY call update_project_brief() when you learn ANY detail
        - Update fields: product_name, product_category, theme, key_features, brand_tone, target_market
        - Call it multiple times as conversation progresses
        - Example: User says "eco-friendly water bottle for athletes"
          → CALL update_project_brief(product_name="eco-friendly water bottle", product_category="beverage", target_market="athletes")

        PHASE 2: CREATE STRATEGY (Use create_campaign_strategy)
        - Call this IMMEDIATELY when user explicitly asks for slogans/personas/strategy
        - User says "create slogans", "make some slogans", "generate personas" → CALL IT NOW
        - Don't worry about missing fields - they'll be pulled from the project brief
        - Examples:
          User: "can you create some campaign slogans?" → CALL create_campaign_strategy() immediately
          User: "make some personas" → CALL create_campaign_strategy() immediately
          User: "I need strategy" → CALL create_campaign_strategy() immediately

        PHASE 3: CREATE VISUALS (Use generate_hero_images)
        - ONLY call when ALL of these are true:
          1. Strategy Agent has completed and you have slogans
          2. User has EXPLICITLY CHOSEN one slogan (e.g., "I like #3", "Use the first one", "Go with the second slogan")
          3. User REQUESTS images/visuals (e.g., "create images", "generate visuals", "show me what it looks like")
        - Do NOT call until user selects AND requests
        - Examples:
          User: "I like slogan #3" → DON'T call yet, ask if they want to see images
          User: "I like slogan #3, can you create images for it?" → NOW call generate_hero_images(slogan="...", ...)
          User: "Use the second one and show me visuals" → NOW call generate_hero_images(slogan="...", ...)

        PHASE 4: CREATE VIDEO (Use generate_social_video)
        - ONLY call when ALL of these are true:
          1. Art Director has completed and you have hero images
          2. User has EXPLICITLY CHOSEN one image (e.g., "I like image #2", "Use the first image", "Go with image 3")
          3. User REQUESTS a video (e.g., "create a video", "make a video from this", "generate video")
        - Do NOT call until user selects an image AND requests video
        - You need the image_asset_id from the selected image
        - Examples:
          User: "I like image #2" → DON'T call yet, ask if they want a video
          User: "I like image #2, can you create a video from it?" → NOW call generate_social_video(image_asset_id="img_...", ...)
          User: "Use image 3 and make a video" → NOW call generate_social_video(image_asset_id="img_...", ...)

        Tone: Professional, collaborative, action-oriented
        Voice: First-person ("I'm updating the brief...", "I've called our Strategy team...")
        Style: Announce what you're doing as you do it

        Important Rules:
        - Agent functions execute in the BACKGROUND - keep talking while they work
        - update_project_brief: Call it OFTEN as you learn information
        - create_campaign_strategy: Call it ONLY when user requests personas/slogans
        - generate_hero_images: Call it ONLY after user selects a slogan AND requests images
        - generate_social_video: Call it ONLY after user selects an image AND requests video
        - generate_audio_assets: Call it when user requests audio/music (jingle, podcast ad, voiceover)
        - generate_landing_page: Call it ONLY after user selects an image AND requests a website/landing page
        - Always respond naturally to user - don't wait silently

        Example conversation:
        User: "I want to create a campaign for smart sneakers"
        You: "Fantastic! Let me update our project brief with that. [CALL update_project_brief(product_name="smart sneakers", product_category="footwear")] Tell me more - what's the target audience?"

        User: "Urban runners who like technology"
        You: "Perfect! Updating that now. [CALL update_project_brief(target_market="urban runners who like technology")] What key features should we highlight?"

        User: "Can you create some campaign slogans?"
        You: "Absolutely! I'm calling our Strategy Agent now. [CALL create_campaign_strategy(...)] They'll create personas and slogans - should take a moment..."
        [Strategy Agent completes and returns 5 slogans]
        You: "Great news! Our Strategy Agent has created 5 campaign slogans: [presents slogans]. Which one resonates with you?"

        User: "I like number 3"
        You: "Excellent choice! Would you like me to call our Art Director to create hero images based on that slogan?"

        User: "Yes, create the images"
        You: "Perfect! I'm calling our Art Director now. [CALL generate_hero_images(slogan="Run Your Future", product_name="smart sneakers", ...)] They'll generate 4 photorealistic hero images..."
        [Art Director completes and returns 4 images]
        You: "Fantastic! Our Art Director created 4 hero images. [presents images]. Which one stands out to you?"

        User: "I like image #2, can you create a video from it?"
        You: "Great choice! I'm calling our Video Producer now. [CALL generate_social_video(image_asset_id="img_abc123", ...)] They'll create a 15-second social media video clip..."

        Always be conversational, proactive with updates, and ready to continue the dialogue.
        """

    async def _check_workflow_state(self) -> Dict[str, Any]:
        """
        Check current workflow state and determine next steps.

        Returns:
            {
                "has_slogans": bool,
                "slogans_count": int,
                "slogans": List[str],
                "selected_slogan": Optional[str],
                "has_images": bool,
                "images_count": int,
                "selected_image": Optional[str],
                "completed_agents": List[str],
                "next_recommended_step": str,
                "resume_message": str,
            }
        """
        brief = await redis_client.get_project_brief(self.project_id)
        if not brief:
            return {
                "has_slogans": False,
                "slogans_count": 0,
                "slogans": [],
                "selected_slogan": None,
                "has_images": False,
                "images_count": 0,
                "selected_image": None,
                "completed_agents": [],
                "next_recommended_step": "create_brief",
                "resume_message": "No project brief found. Start by gathering product information."
            }

        # Check strategy state
        has_slogans = len(brief.slogans) > 0
        selected_slogan = brief.selected_slogan

        # Check art state
        has_images = len(brief.hero_images) > 0
        selected_image = brief.selected_image

        # Check completed assets
        completed_agents = list(brief.completed_assets.keys())

        # Determine next step
        if not has_slogans:
            next_step = "create_strategy"
        elif not selected_slogan:
            next_step = "select_slogan"
        elif not has_images:
            next_step = "generate_images"
        elif not selected_image:
            next_step = "select_image"
        elif "video_producer" not in completed_agents:
            next_step = "generate_video"
        elif "web_dev" not in completed_agents:
            next_step = "generate_landing_page"
        else:
            next_step = "campaign_complete"

        # Build resume message
        status_lines = []
        status_lines.append("Current Progress:")
        status_lines.append(f"{'✅' if has_slogans else '❌'} Strategy: {len(brief.slogans)} slogans")
        if has_slogans and selected_slogan:
            status_lines.append(f"✅ Selected slogan: '{selected_slogan}'")
        elif has_slogans:
            status_lines.append("❌ No slogan selected yet")

        status_lines.append(f"{'✅' if has_images else '❌'} Images: {len(brief.hero_images)} hero images")
        if has_images and selected_image:
            status_lines.append(f"✅ Selected image: {selected_image.asset_id if selected_image else 'None'}")
        elif has_images:
            status_lines.append("❌ No image selected yet")

        status_lines.append(f"{'✅' if 'video_producer' in completed_agents else '❌'} Video created")
        status_lines.append(f"{'✅' if 'audio_team' in completed_agents else '❌'} Audio created")
        status_lines.append(f"{'✅' if 'web_dev' in completed_agents else '❌'} Landing page created")
        status_lines.append(f"\nNext step: {next_step}")

        resume_message = "\n".join(status_lines)

        return {
            "has_slogans": has_slogans,
            "slogans_count": len(brief.slogans),
            "slogans": brief.slogans,
            "selected_slogan": selected_slogan,
            "has_images": has_images,
            "images_count": len(brief.hero_images),
            "selected_image": selected_image.asset_id if selected_image else None,
            "completed_agents": completed_agents,
            "next_recommended_step": next_step,
            "resume_message": resume_message,
        }

    async def _initialize_project_brief(self) -> None:
        """
        Initialize or load project brief and send to frontend.
        """
        from app.models.brief import ProjectBrief
        from datetime import datetime

        # Try to load existing brief
        brief = await redis_client.get_project_brief(self.project_id)

        # If no brief exists, create a default one
        if not brief:
            self._log("info", f"📋 Creating new project brief for {self.project_id}")
            brief = ProjectBrief(
                project_id=self.project_id,
                session_id=self.session_id,
                product_name="Aura Smart Sneaker" if self.project_id == "aura_smart_sneaker" else "",
                product_category="footwear" if self.project_id == "aura_smart_sneaker" else "",
                theme="futuristic urban athlete" if self.project_id == "aura_smart_sneaker" else "",
                key_features=["glowing sole", "smart tracking", "adaptive cushioning"] if self.project_id == "aura_smart_sneaker" else [],
                brand_tone="innovative, energetic, tech-forward" if self.project_id == "aura_smart_sneaker" else "",
                target_market="Urban athletes aged 18-35" if self.project_id == "aura_smart_sneaker" else "",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            # Save to Redis
            await redis_client.save_project_brief(brief)
        else:
            self._log("info", f"📋 Loaded existing project brief for {self.project_id}")

        # Send brief to frontend
        if self.frontend_ws:
            try:
                await self.frontend_ws.send_json({
                    "type": "brief_init",
                    "data": {
                        "brief": brief.model_dump(mode="json"),
                    },
                })
                self._log("info", f"📤 Sent project brief to frontend")
            except Exception as e:
                logger.error(f"Error sending brief to frontend: {e}")

    async def connect(self, frontend_websocket: WebSocket) -> None:
        """
        Establish connection chain: Frontend → Backend → Gemini Live

        Args:
            frontend_websocket: WebSocket from frontend
        """
        self._log("info", "🔌 Establishing Gemini Live connection")

        # Accept frontend connection
        await frontend_websocket.accept()
        self.frontend_ws = frontend_websocket

        # Initialize project brief
        await self._initialize_project_brief()

        # Connect to Gemini Live API
        try:
            self.gemini_session = await self._connect_to_gemini_live()
            self.is_connected = True

            self._log("info", "✓ Gemini Live connection established")

            # Start the agent result listener
            self._start_result_listener()

            # Start bidirectional streaming
            await asyncio.gather(
                self._handle_frontend_to_gemini(),
                self._handle_gemini_to_frontend(),
                return_exceptions=True,
            )

        except Exception as e:
            self._log("error", f"✗ Connection error: {e}")
            self.is_connected = False
            if self.frontend_ws:
                await self.frontend_ws.close(code=1011, reason=f"Connection error: {e}")

    async def _extend_session(self) -> None:
        """
        Extend the Gemini Live session by reconnecting with session resumption.
        Called when a go_away message is received.
        """
        try:
            self._log("info", "🔄 Extending session with resumption...")

            # Close current session
            if hasattr(self, '_session_context') and self._session_context:
                try:
                    await self._session_context.__aexit__(None, None, None)
                except Exception as e:
                    self._log("warning", f"Error closing old session: {e}")

            # Reconnect with session resumption
            old_handle = self._session_handle
            self.gemini_session = await self._connect_to_gemini_live(resume_handle=old_handle)

            self._log("info", "✓ Session extended successfully")

        except Exception as e:
            self._log("error", f"✗ Failed to extend session: {e}")
            import traceback
            self._log("error", f"Traceback: {traceback.format_exc()}")

    async def _connect_to_gemini_live(self, resume_handle: Optional[str] = None):
        """
        Establish connection to Gemini Live API using google.genai SDK (Vertex AI).

        Args:
            resume_handle: Optional session handle to resume previous session

        Returns:
            Gemini Live session
        """
        if resume_handle:
            self._log("info", f"🔗 Reconnecting to Gemini Live API with session resumption")
            self._log("warning", "⚠️ Session resumption may not preserve function calling tools!")
            self._log("warning", "⚠️ Consider starting fresh session instead of resuming for tool availability")
        else:
            self._log("info", "🔗 Connecting to Gemini Live API (Vertex AI)")

        # Define agent tools for function calling
        agent_tools = self._get_agent_tools()

        # Create LiveConnectConfig with voice, tools, and automatic VAD
        # Note: Timeout is configured at client level (see __init__)
        config = LiveConnectConfig(
            response_modalities=["AUDIO"], # Text is enabled via output_audio_transcription
            output_audio_transcription={},
            input_audio_transcription={},
            speech_config=SpeechConfig(
                voice_config=VoiceConfig(
                    prebuilt_voice_config=PrebuiltVoiceConfig(
                        voice_name=self.voice_name
                    )
                )
            ),
            # Configure automatic Voice Activity Detection
            realtime_input_config=RealtimeInputConfig(
                automatic_activity_detection=AutomaticActivityDetection(
                    disabled=False,  # Enable automatic VAD
                    start_of_speech_sensitivity=StartSensitivity.START_SENSITIVITY_LOW,  # Detect speech quickly
                    end_of_speech_sensitivity=EndSensitivity.END_SENSITIVITY_LOW,  # Wait longer before ending (don't cut off user)
                    silence_duration_ms=100,  # 1.5 seconds of silence before considering turn complete
                    prefix_padding_ms=20,  # Include 300ms before detected speech starts
                )
            ),
        )

        # Add system instruction if provided
        if self.system_prompt and self.system_prompt.strip():
            config.system_instruction = {
                "parts": [{"text": self.system_prompt.strip()}]
            }

        # Add function calling tools (always, even during resumption)
        # NOTE: Resumed sessions may ignore tool configuration changes
        if agent_tools:
            config.tools = [{"function_declarations": agent_tools}]
            tool_names = [tool["name"] for tool in agent_tools]
            self._log("info", f"🔧 Registered {len(agent_tools)} tools: {', '.join(tool_names)}")
            if resume_handle:
                self._log("warning", "⚠️ Tools added to resumed session config, but API may ignore them")

        # Add session resumption if handle provided
        if resume_handle:
            config.session_resumption = SessionResumptionConfig(handle=resume_handle)
            self._log("info", f"🔄 Using session resumption with handle")

        # Model name for Vertex AI
        # Vertex AI uses: "gemini-live-2.5-flash-preview-native-audio-09-2025"
        # Google AI API uses: "gemini-2.5-flash-native-audio-preview-09-2025"
        model_name = "gemini-live-2.5-flash-preview-native-audio-09-2025"

        self._log("info", f"📤 Connecting with model: {model_name}")
        self._log("info", f"📤 Voice: {self.voice_name}")
        self._log("info", f"🎤 VAD: Enabled (start: HIGH, end: LOW, silence: 1.5s)")

        # Connect to Gemini Live using the SDK (returns context manager)
        session_context = self.genai_client.aio.live.connect(
            model=model_name,
            config=config,
        )

        # Enter the context manager
        session = await session_context.__aenter__()

        self._log("info", "✓ Gemini Live session established successfully")
        self._log("info", "🎤 Connection ready - waiting for audio input...")

        # Store context manager for cleanup
        self._session_context = session_context

        return session

    async def _handle_frontend_to_gemini(self) -> None:
        """Forward user input (audio) to Gemini Live."""
        if not self.frontend_ws:
            return

        self._log("info", "👂 Started listening for frontend messages...")
        audio_chunk_count = 0

        try:
            async for message in self.frontend_ws.iter_json():
                message_type = message.get("type")

                if message_type == "audio_input":
                    # User speaking - forward to Gemini Live
                    audio_data = message.get("data")
                    if audio_data and self.gemini_session:
                        # Check if this is the start of a NEW turn
                        if not self._current_turn_started:
                            # This is the first chunk of a new turn
                            self._current_turn_started = True
                            audio_chunk_count = 1  # Reset counter for new turn

                            # Increment turn if previous turn completed
                            if self._turn_ready_for_increment:
                                self.turn_count += 1
                                self._turn_ready_for_increment = False
                            self._log("info", f"🎤 Starting new audio input (Turn: {self.turn_count}, Chunk #1)")
                        else:
                            # Continue current turn
                            audio_chunk_count += 1
                            if audio_chunk_count % 50 == 0:
                                self._log("info", f"🎤 Audio chunk #{audio_chunk_count} (size: {len(audio_data)} base64 chars)")

                        await self._send_audio_to_gemini(audio_data)

                elif message_type == "turn_complete":
                    # User finished speaking - mark turn as ready to restart
                    self._log("info", f"🎤 User stopped speaking (sent {audio_chunk_count} audio chunks), waiting for Gemini response...")
                    self._current_turn_started = False  # Allow next audio to start a new turn
                    audio_chunk_count = 0  # Reset for next turn

                elif message_type == "text_input":
                    # Text fallback mode
                    text = message.get("text")
                    if text and self.gemini_session:
                        logger.info(f"Text input from user: {text}")
                        await self._send_text_to_gemini(text)

        except Exception as e:
            logger.error(f"Frontend to Gemini error: {e}")

    async def _send_audio_to_gemini(self, audio_base64: str) -> None:
        """
        Send audio chunk to Gemini Live using google.genai SDK.

        Args:
            audio_base64: Base64 encoded audio data
        """
        if not self.gemini_session:
            self._log("error", "✗ Cannot send audio: no Gemini session")
            return

        # Check if connection is still alive
        if not self.is_connected:
            if not hasattr(self, '_connection_dead_logged'):
                self._log("warning", "⚠️ Connection closed, stopping audio transmission")
                self._connection_dead_logged = True
            return

        try:
            audio_data = base64.b64decode(audio_base64)

            # Save audio to file for debugging (if enabled)
            if self.audio_file_handle:
                self.audio_file_handle.write(audio_data)
                self.audio_file_handle.flush()  # Ensure data is written immediately

            # Check audio energy to detect if it's silence
            if not hasattr(self, '_audio_send_count'):
                self._audio_send_count = 0
            self._audio_send_count += 1

            # Analyze first chunk for diagnostics
            if self._audio_send_count == 1:
                # Convert bytes to int16 array to check energy
                import array
                pcm_data = array.array('h', audio_data)  # 'h' = signed short (int16)
                max_amplitude = max(abs(sample) for sample in pcm_data) if pcm_data else 0
                avg_amplitude = sum(abs(sample) for sample in pcm_data) / len(pcm_data) if pcm_data else 0
                self._log("info", f"🔊 Audio diagnostics - Max amplitude: {max_amplitude}, Avg: {avg_amplitude:.1f} (max possible: 32768)")

            # Send audio using google.genai SDK
            await self.gemini_session.send_realtime_input(
                audio=Blob(
                    data=audio_data,
                    mime_type="audio/pcm;rate=16000"
                )
            )

            # Log periodically to confirm forwarding
            if self._audio_send_count == 1:
                self._log("info", f"📤 Sent first audio chunk to Gemini ({len(audio_data)} bytes, Turn: {self.turn_count})")
            elif self._audio_send_count % 25 == 0:
                self._log("info", f"📤 Audio chunk #{self._audio_send_count} sent ({len(audio_data)} bytes, Turn: {self.turn_count})")

        except Exception as e:
            # Mark connection as dead on timeout/connection errors
            if "keepalive" in str(e).lower() or "1011" in str(e) or "closed" in str(e).lower():
                self.is_connected = False
                if not hasattr(self, '_keepalive_timeout_logged'):
                    self._log("error", f"✗ Connection lost (keepalive timeout). Full error: {type(e).__name__}: {e}")
                    import traceback
                    self._log("error", f"Traceback: {traceback.format_exc()}")
                    self._keepalive_timeout_logged = True
            else:
                self._log("error", f"✗ Error sending audio to Gemini: {type(e).__name__}: {e}")
                import traceback
                self._log("error", f"Traceback: {traceback.format_exc()}")

    async def _send_turn_complete(self) -> None:
        """
        DEPRECATED: Do not use for audio streaming.

        Gemini Live automatically detects turn completion from silence in the audio stream.
        Sending additional messages causes 1007 "invalid argument" errors.

        This method is kept for potential future text-based turn completion.
        """
        # DO NOT send anything for audio streaming
        # Gemini's built-in VAD handles turn detection
        pass

    async def _send_text_to_gemini(self, text: str) -> None:
        """
        Send text message to Gemini Live using google.genai SDK.

        Args:
            text: Text message to send
        """
        if not self.gemini_session:
            return

        try:
            # Send text using the SDK
            await self.gemini_session.send(text, end_of_turn=True)
            logger.info(f"Sent text to Gemini Live: {text[:50]}...")

        except Exception as e:
            logger.error(f"Error sending text to Gemini: {e}")

    async def _handle_gemini_to_frontend(self) -> None:
        """Receive from Gemini Live and forward BOTH audio and text to frontend."""
        if not self.gemini_session:
            self._log("error", "✗ No Gemini session")
            return

        self._log("info", "🎧 Started listening for Gemini responses...")
        message_count = 0
        last_message_time = None

        try:
            import time
            import asyncio

            # Loop to handle multiple turns, restarting the listener each time
            while self.is_connected:
                self._log("info", "🎧 Starting new listener for Gemini responses...")

                async for response in self.gemini_session.receive():
                    current_time = time.time()
                    if last_message_time and self.turn_count > 0:
                        gap = current_time - last_message_time
                        if gap > 2.0:  # Log gaps longer than 2 seconds during turn 1+
                            self._log("info", f"   ⏱ Gap of {gap:.1f}s since last message")
                    last_message_time = current_time
                    message_count += 1

                    # Log periodically when waiting for responses in turn 1+
                    if self.turn_count > 0 and message_count % 5 == 0:
                        self._log("info", f"   Still receiving (message #{message_count}, turn {self.turn_count})")
                    # Log every 10th message, or all messages for turn > 0 to debug multi-turn issues
                    if message_count % 10 == 1 or self.turn_count > 0:
                        self._log("info", f"📥 Message #{message_count} from Gemini (Turn: {self.turn_count})")
                    try:

                        # Track session handle for resumption
                        if hasattr(response, 'setup_complete') and response.setup_complete:
                            if hasattr(response.setup_complete, 'handle'):
                                self._session_handle = response.setup_complete.handle
                                self._log("info", f"📋 Session handle captured for resumption")

                        # Handle go_away message - session expiration warning
                        if hasattr(response, 'go_away') and response.go_away:
                            time_left = getattr(response.go_away, 'time_left', None)
                            if time_left is not None:
                                self._log("warning", f"⏰ Session expiring in {time_left}s - will reconnect with resumption...")
                                # Extend session synchronously and break from receive loop
                                await self._extend_session()
                                # Break from receive loop to restart with new session
                                self._log("info", "🔄 Breaking receive loop to use new session")
                                break

                        # Handle server content (audio and/or text)
                        if hasattr(response, 'server_content') and response.server_content:
                            # Check for waiting_for_input state
                            if hasattr(response.server_content, 'waiting_for_input') and response.server_content.waiting_for_input:
                                self._log("info", "🎤 Gemini is waiting for input")

                            # Extract model turn data for audio
                            if hasattr(response.server_content, 'model_turn'):
                                model_turn = response.server_content.model_turn
                                if hasattr(model_turn, 'parts'):
                                    for part in model_turn.parts:
                                        if hasattr(part, 'inline_data') and part.inline_data:
                                            audio_b64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                                            mime_type = part.inline_data.mime_type or "audio/pcm"
                                            await self._send_audio_to_frontend(audio_b64, mime_type)

                            # Extract transcript from the correct field
                            if hasattr(response.server_content, 'output_transcription') and response.server_content.output_transcription:
                                transcript_text = response.server_content.output_transcription.text
                                if transcript_text:
                                    self._log("info", f"📝 Assistant Transcript: {transcript_text}")
                                    await self._send_text_to_frontend(transcript_text, "assistant")

                            # Extract user's input transcript
                            if hasattr(response.server_content, 'input_transcription') and response.server_content.input_transcription:
                                transcript_text = response.server_content.input_transcription.text
                                if transcript_text:
                                    self._log("info", f"📝 User Transcript: {transcript_text}")
                                    await self._send_text_to_frontend(transcript_text, "user")

                            # Handle interrupted state
                            if hasattr(response.server_content, 'interrupted') and response.server_content.interrupted:
                                self._log("info", "⚠ Model turn was interrupted")
                                if self.frontend_ws:
                                    await self.frontend_ws.send_json({"type": "interrupted"})

                        # Handle turn complete
                        # Check both top-level and server_content.turn_complete
                        turn_complete = False
                        if hasattr(response, 'turn_complete') and response.turn_complete:
                            turn_complete = True
                        elif hasattr(response, 'server_content') and response.server_content:
                            if hasattr(response.server_content, 'turn_complete') and response.server_content.turn_complete:
                                turn_complete = True

                        if turn_complete:
                            self._log("info", "✓ Gemini turn complete")
                            await self._handle_turn_complete()
                            # Break from the inner `async for` to allow the `while` loop to restart the listener
                            break

                        # Handle tool calls
                        if hasattr(response, 'tool_call') and response.tool_call:
                            self._log("info", "🔧🔧🔧 TOOL CALL RECEIVED FROM GEMINI 🔧🔧🔧")
                            self._log("info", f"🔧 Tool call object: {response.tool_call}")
                            await self._handle_tool_call_genai(response.tool_call)
                        else:
                            # Debug: Check if this message has tool call in a different field
                            if hasattr(response, '__dict__'):
                                response_dict = {k: v for k, v in response.__dict__.items() if not k.startswith('_')}
                                if any('tool' in str(k).lower() or 'function' in str(k).lower() for k in response_dict.keys()):
                                    self._log("warning", f"⚠️ Response has tool-related fields but tool_call is None: {list(response_dict.keys())}")

                        # Debug: Check if response has other tool-related attributes
                        if hasattr(response, '__dict__'):
                            response_attrs = [attr for attr in dir(response) if not attr.startswith('_')]
                            if any('tool' in attr.lower() or 'function' in attr.lower() for attr in response_attrs):
                                self._log("debug", f"🔍 Response has tool-related attrs: {[attr for attr in response_attrs if 'tool' in attr.lower() or 'function' in attr.lower()]}")

                    except Exception as e:
                        self._log("error", f"✗ Response processing error: {e}")
                        import traceback
                        self._log("error", f"Traceback: {traceback.format_exc()}")

        except Exception as e:
            error_msg = str(e)

            # Handle normal WebSocket close during session extension
            if "ConnectionClosedOK" in str(type(e).__name__) or "1000 (OK)" in error_msg:
                self._log("info", "🔄 WebSocket closed normally (likely during session extension)")
                # Don't break the main loop - let it continue and restart with the new session
                # Just continue the while loop without setting is_connected = False
                pass

            # Log different types of errors appropriately
            elif "1011" in error_msg and "internal error" in error_msg.lower():
                self._log("error", f"✗ Gemini Live server error (1011): {error_msg}")
                self._log("warning", "⚠️ This is a server-side error from Gemini Live API")
                self._log("warning", "⚠️ Possible causes: function call triggered server bug, session timeout, or service issue")
                # If a major error occurs, break the main loop
                self.is_connected = False
            else:
                self._log("error", f"✗ Gemini to Frontend error: {e}")
                import traceback
                self._log("error", f"Traceback: {traceback.format_exc()}")
                # If a major error occurs, break the main loop
                self.is_connected = False

    async def _safe_send_to_frontend(self, message: dict) -> bool:
        """
        Safely send a message to the frontend WebSocket.

        Args:
            message: Message dictionary to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.frontend_ws:
            return False

        try:
            from starlette.websockets import WebSocketState
            if self.frontend_ws.client_state == WebSocketState.CONNECTED:
                await self.frontend_ws.send_json(message)
                return True
            else:
                return False
        except Exception:
            return False

    async def _send_audio_to_frontend(self, audio_base64: str, mime_type: str) -> None:
        """
        Send audio to frontend for playback.

        Args:
            audio_base64: Base64 encoded audio
            mime_type: Audio MIME type
        """
        await self._safe_send_to_frontend({
            "type": "audio_output",
            "data": audio_base64,
            "mime_type": mime_type,
        })

    async def _send_text_to_frontend(self, text: str, role: str) -> None:
        """
        Send text transcript to frontend.

        Args:
            text: Text content
            role: Message role (user or assistant)
        """
        from datetime import datetime

        await self._safe_send_to_frontend({
            "type": "text_output",
            "text": text,
            "role": role,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def _send_announcement_to_frontend(self, message: str, type: str = "info") -> None:
        """
        Send a status announcement to the frontend.

        Args:
            message: The announcement message content.
            type: The type of announcement (e.g., 'info', 'success', 'error').
        """
        await self._safe_send_to_frontend({
            "type": "producer_announcement",
            "data": {
                "message": message,
                "announcement_type": type,
            },
        })

    async def _send_agent_status(self, agent_id: str, status: str, current_task: Optional[str] = None) -> None:
        """
        Send agent status update to the frontend.

        Args:
            agent_id: Agent identifier
            status: Status (idle, thinking, complete, error)
            current_task: Current task description
        """
        success = await self._safe_send_to_frontend({
            "type": "agent_status",
            "data": {
                "agent_id": agent_id,
                "status": status,
                "current_task": current_task,
            },
        })
        if success:
            self._log("info", f"📤 Sent agent status: {agent_id} = {status}")

    async def _send_asset_to_frontend(self, agent_id: str, asset_data: Dict[str, Any]) -> None:
        """
        Send asset data to the frontend for display.

        Args:
            agent_id: Agent identifier
            asset_data: Asset data from agent execution
        """
        success = await self._safe_send_to_frontend({
            "type": "asset_added",
            "data": {
                "agent_id": agent_id,
                "asset_type": "result",
                "asset_data": asset_data,
            },
        })
        if success:
            self._log("info", f"📤 Sent asset for agent: {agent_id}")

    def _create_result_summary(self, agent_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a compact summary of agent result for Gemini (without large data like base64 images).

        Args:
            agent_id: Agent identifier
            result: Full agent result

        Returns:
            Compact summary suitable for sending to Gemini
        """
        if agent_id == "strategy":
            # Strategy: Include slogans and persona summaries
            return {
                "slogans": result.get("slogans", []),
                "personas": [
                    {
                        "name": p.get("name"),
                        "age_range": p.get("age_range"),
                        "description": p.get("description")
                    }
                    for p in result.get("personas", [])
                ],
                "market_analysis": result.get("market_analysis", "")[:200] + "...",  # Truncate
            }

        elif agent_id == "art_director":
            # Art Director: Strip out base64 image URLs and generation_params, keep metadata only
            images = result.get("images", [])
            return {
                "status": "completed",
                "image_count": len(images),
                "images": [
                    {
                        "asset_id": img.get("asset_id"),
                        "description": img.get("description"),
                        # REMOVE url field - it contains massive base64 data URI (can be 1-2MB)
                        # REMOVE generation_params - it contains large prompt text
                    }
                    for img in images
                ],
                "style_guide": result.get("style_guide", "")[:200] + "..."  # Truncate
            }

        elif agent_id == "video_producer":
            # Video Producer: Strip out video URL and generation_params (contains reference_image base64), keep metadata only
            video = result.get("video", {})
            return {
                "status": "completed",
                "video": {
                    "asset_id": video.get("asset_id"),
                    "duration_seconds": video.get("duration_seconds"),
                    "revision_number": video.get("revision_number", 0),
                    # REMOVE url field - it may contain large data
                    # REMOVE generation_params - it contains reference_image base64 data URI
                },
                "revision_count": len(result.get("revision_history", [])),
                "critique_notes": result.get("critique_notes", "")[:200] if result.get("critique_notes") else None
            }

        elif agent_id == "audio_team":
            # Audio Team: Strip out audio URLs, keep metadata
            podcast_script = result.get("podcast_ad", {}).get("script", "")
            suggestion = result.get("proactive_suggestion", "")

            return {
                "status": "completed",
                "jingle": {
                    "asset_id": result.get("jingle", {}).get("asset_id"),
                    "description": result.get("jingle", {}).get("description"),
                },
                "podcast_ad": {
                    "asset_id": result.get("podcast_ad", {}).get("asset_id"),
                    "script": (podcast_script[:200] + "...") if podcast_script else None
                },
                "proactive_suggestion": (suggestion[:200] + "...") if suggestion else None
            }

        elif agent_id == "web_dev":
            # Web Dev: Strip out full code, keep metadata
            code = result.get("code", {})
            return {
                "status": "completed",
                "code": {
                    "asset_id": code.get("asset_id"),
                    "description": "Landing page with HTML/CSS/JS",
                    "framework": result.get("framework", "vanilla"),
                },
                "deployment_status": result.get("deployment_status", "preview")
            }

        else:
            # Default: Return a simple success message
            return {
                "status": "completed",
                "agent_id": agent_id,
                "message": f"{agent_id} task completed successfully"
            }

    async def _update_brief_from_agent_result(self, agent_id: str, result: Dict[str, Any], task: Dict[str, Any]) -> None:
        """
        Update project brief based on agent execution results.

        Args:
            agent_id: Agent identifier
            result: Agent execution result
            task: Task parameters that were used
        """
        from datetime import datetime

        try:
            # Get current brief
            brief = await redis_client.get_project_brief(self.project_id)
            if not brief:
                self._log("warning", f"No brief found for project {self.project_id}")
                return

            updates = {}
            changed_fields = []

            # Update brief based on agent type
            if agent_id == "strategy":
                # Strategy agent might refine product info from task
                if task.get("product_name") and not brief.product_name:
                    updates["product_name"] = task.get("product_name")
                    changed_fields.append("product_name")
                if task.get("product_category") and not brief.product_category:
                    updates["product_category"] = task.get("product_category")
                    changed_fields.append("product_category")
                if task.get("theme") and not brief.theme:
                    updates["theme"] = task.get("theme")
                    changed_fields.append("theme")
                if task.get("brand_tone") and not brief.brand_tone:
                    updates["brand_tone"] = task.get("brand_tone")
                    changed_fields.append("brand_tone")
                if task.get("target_market") and not brief.target_market:
                    updates["target_market"] = task.get("target_market")
                    changed_fields.append("target_market")
                if task.get("key_features") and not brief.key_features:
                    updates["key_features"] = task.get("key_features")
                    changed_fields.append("key_features")

                # Save slogans and personas from strategy agent
                if "slogans" in result:
                    updates["slogans"] = result.get("slogans", [])
                    changed_fields.append("slogans")
                    self._log("info", f"📋 Saved {len(result.get('slogans', []))} slogans to brief")

                if "personas" in result:
                    from app.models.brief import CustomerPersona
                    personas_data = result.get("personas", [])
                    # Convert dict personas to CustomerPersona objects
                    personas = []
                    for p_data in personas_data:
                        if isinstance(p_data, dict):
                            personas.append(CustomerPersona(**p_data))
                        else:
                            personas.append(p_data)
                    updates["personas"] = personas
                    changed_fields.append("personas")
                    self._log("info", f"📋 Saved {len(personas)} personas to brief")

                # Mark strategy as completed
                if brief.completed_assets is None:
                    brief.completed_assets = {}
                brief.completed_assets["strategy"] = {
                    "slogans_count": len(result.get("slogans", [])),
                    "personas_count": len(result.get("personas", [])),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                updates["completed_assets"] = brief.completed_assets
                changed_fields.append("completed_assets")

            elif agent_id == "art_director":
                # Art director uses selected slogan
                if task.get("slogan") and brief.selected_slogan != task.get("slogan"):
                    updates["selected_slogan"] = task.get("slogan")
                    changed_fields.append("selected_slogan")

                # Save hero images from art director
                if "images" in result:
                    from app.models.brief import ImageAsset
                    images_data = result.get("images", [])
                    # Convert dict images to ImageAsset objects
                    hero_images = []
                    for img_data in images_data:
                        if isinstance(img_data, dict):
                            hero_images.append(ImageAsset(**img_data))
                        else:
                            hero_images.append(img_data)
                    updates["hero_images"] = hero_images
                    changed_fields.append("hero_images")
                    self._log("info", f"📋 Saved {len(hero_images)} hero images to brief")

                # Mark art director as completed
                if brief.completed_assets is None:
                    brief.completed_assets = {}
                brief.completed_assets["art_director"] = {
                    "images_count": len(result.get("images", [])),
                    "slogan": task.get("slogan"),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                updates["completed_assets"] = brief.completed_assets
                changed_fields.append("completed_assets")

            elif agent_id == "video_producer":
                # Mark video producer as completed
                if brief.completed_assets is None:
                    brief.completed_assets = {}
                brief.completed_assets["video_producer"] = {
                    "video_asset_id": result.get("video", {}).get("asset_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                updates["completed_assets"] = brief.completed_assets
                changed_fields.append("completed_assets")

            elif agent_id == "audio_team":
                # Mark audio team as completed
                if brief.completed_assets is None:
                    brief.completed_assets = {}
                brief.completed_assets["audio_team"] = {
                    "jingle_asset_id": result.get("jingle", {}).get("asset_id"),
                    "podcast_asset_id": result.get("podcast_ad", {}).get("asset_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                updates["completed_assets"] = brief.completed_assets
                changed_fields.append("completed_assets")

            elif agent_id == "web_dev":
                # Mark web dev as completed
                if brief.completed_assets is None:
                    brief.completed_assets = {}
                brief.completed_assets["web_dev"] = {
                    "code_asset_id": result.get("code", {}).get("asset_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                updates["completed_assets"] = brief.completed_assets
                changed_fields.append("completed_assets")

            # Apply updates if any
            if updates:
                updates["updated_at"] = datetime.utcnow()
                brief_updated = await redis_client.update_project_brief(self.project_id, updates)

                # Send brief update to frontend
                if self.frontend_ws:
                    await self.frontend_ws.send_json({
                        "type": "brief_update",
                        "data": {
                            "brief": brief_updated.model_dump(mode="json"),
                            "changed_fields": changed_fields,
                        },
                    })
                    self._log("info", f"📋 Updated project brief, changed fields: {changed_fields}")

        except Exception as e:
            logger.error(f"Error updating brief from agent result: {e}")

    def _start_result_listener(self) -> None:
        """
        Starts an asyncio task to listen for agent results on a Redis Pub/Sub channel.
        """
        if self._result_listener_task and not self._result_listener_task.done():
            self._log("warning", "⚠️ Result listener already running.")
            return

        self._log("info", "🎧 Starting agent result listener task...")
        self._result_listener_task = asyncio.create_task(self._listen_for_agent_results())
        self._log("info", "✓ Result listener task created - will receive agent results via Redis Pub/Sub")

    async def _listen_for_agent_results(self) -> None:
        """
        Listens for agent results on a Redis Pub/Sub channel and sends them to Gemini.
        """
        channel_name = f"agent_results:{self.session_id}"
        self._log("info", f"Subscribing to Redis channel: {channel_name} for agent results.")

        try:
            pubsub = redis_client.client.pubsub()  # type: ignore
            await pubsub.subscribe(channel_name)
            self._log("info", f"Successfully subscribed to {channel_name}.")

            while self.is_connected:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message['type'] == 'message':
                    try:
                        # Handle both bytes and string data
                        message_data = message['data']
                        if isinstance(message_data, bytes):
                            message_data = message_data.decode('utf-8')

                        data = json.loads(message_data)
                        agent_id = data.get("agent_id")
                        call_id = data.get("call_id")
                        result = data.get("result")
                        status = data.get("status")

                        self._log("info", f"Received agent result for {agent_id} (Call ID: {call_id}, Status: {status})")

                        if call_id and self.gemini_session:
                            if status == "completed":
                                await self.gemini_session.send_tool_response(
                                    function_responses=[
                                        {
                                            "id": call_id,
                                            "response": result
                                        }
                                    ]
                                )
                                self._log("info", f"📤 Sent agent result for {agent_id} (Call ID: {call_id}) to Gemini.")
                            elif status == "failed":
                                await self.gemini_session.send_tool_response(
                                    function_responses=[
                                        {
                                            "id": call_id,
                                            "response": {"error": f"Agent {agent_id} failed: {result.get("error", "Unknown error")}"}
                                        }
                                    ]
                                )
                                self._log("error", f"📤 Sent agent failure for {agent_id} (Call ID: {call_id}) to Gemini.")

                    except json.JSONDecodeError as e:
                        self._log("error", f"Error decoding agent result message: {e}")
                    except Exception as e:
                        self._log("error", f"Error processing agent result: {e}")
                await asyncio.sleep(0.1) # Prevent busy-waiting

        except asyncio.CancelledError:
            self._log("info", "Agent result listener task cancelled.")
        except Exception as e:
            self._log("error", f"Error in agent result listener: {e}")
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
            self._log("info", f"Unsubscribed from Redis channel: {channel_name}.")

    async def _execute_agent_with_result_publishing(
        self,
        orchestrator: Any,
        agent_id: str,
        task: Dict[str, Any],
        project_id: str,
        session_id: str,
        call_id: Optional[str] = None,
    ) -> None:
        """
        Execute agent and publish result to Redis Pub/Sub for Gemini Live.

        Args:
            orchestrator: AgentOrchestrator instance
            agent_id: Agent to execute
            task: Task parameters
            project_id: Project identifier
            session_id: Session identifier for Redis channel
            call_id: Function call ID from Gemini
        """
        self._log("info", f"🚀 _execute_agent_with_result_publishing STARTED for agent: {agent_id}")
        # Log task summary without potentially large data (image URLs can be 2MB base64)
        task_summary = {k: (v[:50] + "..." if isinstance(v, str) and len(v) > 50 else v) for k, v in task.items() if k not in ["image_url"]}
        if "image_url" in task:
            task_summary["image_url"] = "data URI" if task["image_url"] and task["image_url"].startswith("data:") else task["image_url"][:50]
        self._log("info", f"🚀 Task summary: {task_summary}")
        self._log("info", f"🚀 Project ID: {project_id}, Session ID: {session_id}, Call ID: {call_id}")
        self._log("info", f"🚀 This is running in BACKGROUND task - Gemini should continue talking")

        try:
            # Send agent status: thinking
            await self._send_agent_status(agent_id, "thinking", f"Executing {agent_id} task...")

            # Execute the agent
            self._log("info", f"🚀 Calling orchestrator.execute_agent for {agent_id}...")
            result = await orchestrator.execute_agent(
                agent_id=agent_id,
                task=task,
                project_id=project_id,
                with_critique=False,
                announcement_callback=self._send_announcement_to_frontend,
            )

            self._log("info", f"🚀 Agent {agent_id} execution completed successfully")
            self._log("info", f"🚀 Result: {str(result)[:200]}...")

            # Send asset to frontend for display
            await self._send_asset_to_frontend(agent_id, result)

            # Update project brief based on agent results
            await self._update_brief_from_agent_result(agent_id, result, task)

            # Send agent status: complete
            await self._send_agent_status(agent_id, "complete", None)

            # Create a compact summary for Gemini (without large base64 image data)
            result_summary = self._create_result_summary(agent_id, result)

            # Log the size of the summary for debugging
            import sys
            summary_size = sys.getsizeof(json.dumps(result_summary))
            self._log("info", f"📊 Result summary size for {agent_id}: {summary_size} bytes ({summary_size/1024:.2f} KB)")

            # Publish result to Redis Pub/Sub channel for the session
            channel_name = f"agent_results:{session_id}"
            result_message = {
                "agent_id": agent_id,
                "call_id": call_id,
                "result": result_summary,  # Use summary instead of full result
                "status": "completed",
            }

            # Log total message size
            message_size = sys.getsizeof(json.dumps(result_message))
            self._log("info", f"📊 Total result message size: {message_size} bytes ({message_size/1024:.2f} KB)")

            await redis_client.client.publish(  # type: ignore
                channel_name,
                json.dumps(result_message)
            )

            self._log("info", f"✓ Published {agent_id} result to {channel_name} (Call ID: {call_id})")

        except Exception as e:
            self._log("error", f"✗ Agent {agent_id} execution failed: {e}")
            import traceback
            self._log("error", f"Traceback: {traceback.format_exc()}")

            # Send agent status: error
            await self._send_agent_status(agent_id, "error", f"Failed: {str(e)}")

            # Publish failure to Redis
            channel_name = f"agent_results:{session_id}"
            error_message = {
                "agent_id": agent_id,
                "call_id": call_id,
                "result": {"error": str(e)},
                "status": "failed",
            }

            await redis_client.client.publish(  # type: ignore
                channel_name,
                json.dumps(error_message)
            )

            self._log("info", f"✓ Published {agent_id} error to {channel_name} (Call ID: {call_id})")

    async def _handle_tool_call_genai(self, tool_call: Any) -> None:
        """
        Handle tool call from genai SDK - execute agent and send response.

        Args:
            tool_call: Tool call object from genai SDK
        """
        self._log("info", "📞 _handle_tool_call_genai called")
        self._log("info", f"📞 tool_call type: {type(tool_call)}")
        self._log("info", f"📞 tool_call attributes: {dir(tool_call)}")

        await self._send_announcement_to_frontend(
            message="Tool call received from Gemini. Routing to the appropriate agent...",
            type="info"
        )
        try:
            # Extract function calls from genai SDK format
            function_calls = []
            if hasattr(tool_call, 'function_calls'):
                function_calls = tool_call.function_calls
                self._log("info", f"📞 Found function_calls: {function_calls}")

            if not function_calls:
                self._log("warning", "⚠️ Tool call with no function calls")
                self._log("warning", f"⚠️ tool_call content: {tool_call}")
                return

            self._log("info", f"📞 Processing {len(function_calls)} function calls")
            for func_call in function_calls:
                function_name = func_call.name if hasattr(func_call, 'name') else func_call.get('name')
                function_args = func_call.args if hasattr(func_call, 'args') else func_call.get('args', {})

                # Try multiple ways to get call_id
                call_id = None
                if hasattr(func_call, 'id'):
                    call_id = func_call.id
                elif hasattr(func_call, 'get'):
                    call_id = func_call.get('id')

                # Debug: check all attributes to find the ID
                self._log("info", f"📞 func_call attributes: {[attr for attr in dir(func_call) if not attr.startswith('_')]}")

                # Generate a temporary call_id if none exists
                if not call_id:
                    import uuid
                    call_id = f"temp_{uuid.uuid4().hex[:8]}"
                    self._log("warning", f"⚠️ No call_id found, generated temporary: {call_id}")

                self._log("info", f"🔧 Dispatching agent for function: {function_name} (Call ID: {call_id}) with args: {function_args}")

                # Route to appropriate agent. This now runs in the background.
                # For sync agents, we send the result immediately.
                # For async agents, we send an acknowledgment now and the actual result later via listener.
                result = await self._execute_agent_function(function_name, function_args, call_id)

                # Send immediate response to Gemini (acknowledgment for async, actual result for sync)
                if result and self.gemini_session:
                    await self.gemini_session.send_tool_response(
                        function_responses=[
                            {
                                "id": call_id,
                                "response": result
                            }
                        ]
                    )
                    self._log("info", f"📤 Sent immediate response for {function_name} (Call ID: {call_id})")

        except Exception as e:
            self._log("error", f"✗ Tool call error: {e}")
            import traceback
            self._log("error", f"Traceback: {traceback.format_exc()}")

    async def _handle_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """
        Handle tool call from Gemini Live - execute agent and send response.

        Args:
            tool_call: Tool call message from Gemini
        """
        try:
            function_calls = tool_call.get("functionCalls", [])
            if not function_calls:
                self._log("warning", "Tool call with no function calls")
                return

            for func_call in function_calls:
                function_name = func_call.get("name")
                function_args = func_call.get("args", {})
                call_id = func_call.get("id")

                self._log("info", f"🔧 Executing function: {function_name} with args: {function_args}")

                # Route to appropriate agent
                result = await self._execute_agent_function(function_name, function_args)

                # Send function response back to Gemini
                await self._send_function_response(call_id, result)

        except Exception as e:
            self._log("error", f"✗ Tool call error: {e}")
            import traceback
            self._log("error", f"Traceback: {traceback.format_exc()}")

    async def _execute_agent_function(
        self, function_name: str, args: Dict[str, Any], call_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute agent based on function call.

        Args:
            function_name: Name of the function called
            args: Function arguments
            call_id: Function call ID from Gemini (for async result matching)

        Returns:
            Agent execution result
        """
        await self._send_announcement_to_frontend(f"Routing to agent for function: {function_name}...", type="info")
        from app.services.orchestration import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        # Store call_id in task for result publishing
        session_id = self.session_id
        call_id_for_task = call_id

        try:
            self._log("info", f"🎯 _execute_agent_function called with: {function_name}")
            self._log("info", f"🎯 Function args: {args}")
            self._log("info", f"🎯 Call ID: {call_id_for_task}")

            if function_name == "check_workflow_status":
                self._log("info", "📊 Matched check_workflow_status function")

                # Check workflow state and return to Gemini
                state = await self._check_workflow_state()

                self._log("info", f"📊 Workflow state: {state['next_recommended_step']}")
                return state

            elif function_name == "update_project_brief":
                self._log("info", "📋 Matched update_project_brief function")

                # Update the project brief with any provided fields
                from datetime import datetime

                brief = await redis_client.get_project_brief(self.project_id)
                if not brief:
                    self._log("warning", f"No brief found for project {self.project_id}")
                    return {"status": "error", "message": "Project brief not found"}

                updates = {}
                changed_fields = []

                # Update only fields that are provided in args
                if args.get("product_name"):
                    updates["product_name"] = args.get("product_name")
                    changed_fields.append("product_name")
                if args.get("product_category"):
                    updates["product_category"] = args.get("product_category")
                    changed_fields.append("product_category")
                if args.get("theme"):
                    updates["theme"] = args.get("theme")
                    changed_fields.append("theme")
                if args.get("brand_tone"):
                    updates["brand_tone"] = args.get("brand_tone")
                    changed_fields.append("brand_tone")
                if args.get("target_market"):
                    updates["target_market"] = args.get("target_market")
                    changed_fields.append("target_market")
                if args.get("key_features"):
                    updates["key_features"] = args.get("key_features")
                    changed_fields.append("key_features")

                if updates:
                    updates["updated_at"] = datetime.utcnow()
                    brief_updated = await redis_client.update_project_brief(self.project_id, updates)

                    # Send brief update to frontend
                    if self.frontend_ws:
                        await self.frontend_ws.send_json({
                            "type": "brief_update",
                            "data": {
                                "brief": brief_updated.model_dump(mode="json"),
                                "changed_fields": changed_fields,
                            },
                        })
                        self._log("info", f"📋 Updated project brief, changed fields: {changed_fields}")

                    return {"status": "success", "updated_fields": changed_fields}
                else:
                    self._log("info", "📋 No fields to update in brief")
                    return {"status": "success", "message": "No fields to update"}

            elif function_name == "create_campaign_strategy":
                self._log("info", "🎯 Matched create_campaign_strategy function")
                self._log("info", f"🎯 Function args: {args}")

                # Get brief for fallback values (but always execute fresh when function is called)
                brief = await redis_client.get_project_brief(self.project_id)

                self._log("info", "🎯 Executing Strategy Agent (always fresh when explicitly requested)")

                # Build task from args, with fallback to project brief
                task = {
                    "task_id": f"strategy_{self.session_id}",
                    "product_name": args.get("product_name") or (brief.product_name if brief else "Product"),
                    "product_category": args.get("product_category") or (brief.product_category if brief else "product"),
                    "theme": args.get("theme") or (brief.theme if brief else "modern"),
                    "key_features": args.get("key_features") or (brief.key_features if brief else []),
                    "brand_tone": args.get("brand_tone") or (brief.brand_tone if brief else "professional"),
                    "target_market": args.get("target_market") or (brief.target_market if brief else "general audience"),
                }

                # Log task summary without potentially large data
                self._log("info", f"🎯 Built task for: {task.get('product_name')}, category: {task.get('product_category')}")

                # Execute agent in background and publish result to Redis
                asyncio.create_task(
                    self._execute_agent_with_result_publishing(
                        orchestrator=orchestrator,
                        agent_id="strategy",
                        task=task,
                        project_id=self.project_id,
                        session_id=session_id,
                        call_id=call_id_for_task,
                    )
                )

                self._log("info", f"✓ Strategy Agent dispatched")

                # Don't return anything - result will be sent via Redis Pub/Sub when agent completes
                # Returning None here allows Gemini to continue the conversation while agent works
                return

            elif function_name == "generate_hero_images":
                self._log("info", "🎨 Matched generate_hero_images function")
                self._log("info", f"🎨 Function args: {args}")

                self._log("info", "🎨 Executing Art Director Agent (always fresh when explicitly requested)")

                # Build task from args
                task = {
                    "task_id": f"art_director_{self.session_id}",
                    "product_name": args.get("product_name"),
                    "slogan": args.get("slogan"),
                    "theme": args.get("theme", "modern"),
                    "brand_tone": args.get("brand_tone", "professional"),
                    "product_category": args.get("product_category", "product"),
                    "key_features": args.get("key_features", []),
                }

                # Don't log full task as it may contain large data
                self._log("info", f"🎨 Built task for: {task.get('product_name')}, slogan: {task.get('slogan', '')[:50]}")

                # Execute agent in background and publish result to Redis
                asyncio.create_task(
                    self._execute_agent_with_result_publishing(
                        orchestrator=orchestrator,
                        agent_id="art_director",
                        task=task,
                        project_id=self.project_id,
                        session_id=session_id,
                        call_id=call_id_for_task,
                    )
                )

                self._log("info", f"✓ Art Director Agent dispatched")
                return # No direct result returned

            elif function_name == "generate_social_video":
                self._log("info", "🎬 Matched generate_social_video function")
                self._log("info", f"🎬 Function args: {args}")

                # Look up the selected image from art director results
                image_asset_id = args.get("image_asset_id")
                image_url = None

                if image_asset_id:
                    # Try to get art director results from Redis
                    art_director_result = await redis_client.get_agent_result("art_director", f"art_director_{self.session_id}")
                    if art_director_result and "images" in art_director_result:
                        # Find the image with matching asset_id
                        for img in art_director_result["images"]:
                            if img.get("asset_id") == image_asset_id:
                                image_url = img.get("url")
                                self._log("info", f"🎬 Found image URL for asset_id: {image_asset_id}")
                                break

                    if not image_url:
                        self._log("warning", f"🎬 Could not find image with asset_id: {image_asset_id}")
                        # Return error to Gemini
                        return {"error": f"Image not found: {image_asset_id}"}
                else:
                    self._log("warning", "🎬 No image_asset_id provided")
                    return {"error": "No image_asset_id provided"}

                # Build task from args - video producer expects image_url, not image_asset_id
                task = {
                    "task_id": f"video_producer_{self.session_id}",
                    "image_url": image_url,  # Pass URL, not asset_id
                    "product_name": args.get("product_name"),
                    "theme": args.get("theme", "modern"),
                    "key_features": args.get("key_features", []),
                    "slogan": args.get("slogan", ""),
                    "product_category": args.get("product_category", "product"),
                }

                # Log task summary without full image URL (could be large base64)
                image_summary = "data URI" if image_url and image_url.startswith("data:") else (image_url[:50] if image_url else "None")
                self._log("info", f"🎬 Built task for: {task.get('product_name')}, image: {image_summary}")

                # Execute agent in background and publish result to Redis
                # Use None for call_id so the listener doesn't send the result back to Gemini
                # (we're sending an immediate acknowledgment instead)
                asyncio.create_task(
                    self._execute_agent_with_result_publishing(
                        orchestrator=orchestrator,
                        agent_id="video_producer",
                        task=task,
                        project_id=self.project_id,
                        session_id=session_id,
                        call_id=None,  # Don't send result back to Gemini via listener
                    )
                )

                self._log("info", f"✓ Video Producer Agent dispatched")
                # Return immediate acknowledgment (will be sent to Gemini in _handle_tool_call_genai)
                return {
                    "status": "dispatched",
                    "message": "Video Producer Agent is creating your social media video. This will take about 60-90 seconds. I'll let you know when it's ready!"
                }

            elif function_name == "generate_audio_assets":
                self._log("info", "🎵 Matched generate_audio_assets function")
                self._log("info", f"🎵 Function args: {args}")

                # Build task from args
                task = {
                    "task_id": f"audio_team_{self.session_id}",
                    "product_name": args.get("product_name"),
                    "slogan": args.get("slogan", ""),
                    "theme": args.get("theme", "modern"),
                    "brand_tone": args.get("brand_tone", "professional"),
                    "product_category": args.get("product_category", "product"),
                }

                # Log task summary
                self._log("info", f"🎵 Built task for: {task.get('product_name')}, theme: {task.get('theme')}")

                # Execute agent in background and publish result to Redis
                asyncio.create_task(
                    self._execute_agent_with_result_publishing(
                        orchestrator=orchestrator,
                        agent_id="audio_team",
                        task=task,
                        project_id=self.project_id,
                        session_id=session_id,
                        call_id=call_id_for_task,
                    )
                )

                self._log("info", f"✓ Audio Team Agent dispatched")
                return # No direct result returned

            elif function_name == "generate_landing_page":
                self._log("info", "💻 Matched generate_landing_page function")
                self._log("info", f"💻 Function args: {args}")

                # Look up the selected image from art director results
                image_asset_id = args.get("image_asset_id")
                image_url = None

                if image_asset_id:
                    # Try to get art director results from Redis
                    art_director_result = await redis_client.get_agent_result("art_director", f"art_director_{self.session_id}")
                    if art_director_result and "images" in art_director_result:
                        # Find the image with matching asset_id
                        for img in art_director_result["images"]:
                            if img.get("asset_id") == image_asset_id:
                                image_url = img.get("url")
                                self._log("info", f"💻 Found image URL for asset_id: {image_asset_id}")
                                break

                    if not image_url:
                        self._log("warning", f"💻 Could not find image with asset_id: {image_asset_id}")
                        return {"error": f"Image not found: {image_asset_id}"}
                else:
                    self._log("warning", "💻 No image_asset_id provided")
                    return {"error": "No image_asset_id provided"}

                # Build task from args
                task = {
                    "task_id": f"web_dev_{self.session_id}",
                    "image_url": image_url,  # Pass URL, not asset_id
                    "product_name": args.get("product_name"),
                    "slogan": args.get("slogan"),
                    "theme": args.get("theme", "modern"),
                    "brand_tone": args.get("brand_tone", "professional"),
                    "product_category": args.get("product_category", "product"),
                    "key_features": args.get("key_features", []),
                }

                # Log task summary without full image URL
                image_summary = "data URI" if image_url and image_url.startswith("data:") else (image_url[:50] if image_url else "None")
                self._log("info", f"💻 Built task for: {task.get('product_name')}, image: {image_summary}")

                # Execute agent in background and publish result to Redis
                asyncio.create_task(
                    self._execute_agent_with_result_publishing(
                        orchestrator=orchestrator,
                        agent_id="web_dev",
                        task=task,
                        project_id=self.project_id,
                        session_id=session_id,
                        call_id=call_id_for_task,
                    )
                )

                self._log("info", f"✓ Web Dev Agent dispatched")
                return # No direct result returned

            else:
                self._log("warning", f"Unknown function: {function_name}")
                # For unknown functions, we might still want to return an error to Gemini
                # For now, just return None
                return

        except Exception as e:
            self._log("error", f"Agent execution error: {e}")
            # For now, just return None on error
            return

    async def _send_function_response(self, call_id: str, result: Dict[str, Any]) -> None:
        """
        DEPRECATED: Legacy method for manual WebSocket function responses.
        Use _handle_tool_call_genai() with SDK's send_tool_response() instead.

        Args:
            call_id: Function call ID
            result: Execution result
        """
        if not self.gemini_session:
            return

        try:
            # NOTE: This method is deprecated and should not be used with the new SDK
            # The new SDK uses gemini_session.send_tool_response() instead
            self._log("warning", "⚠️ Using deprecated _send_function_response method")

            response_message = {
                "toolResponse": {
                    "functionResponses": [
                        {
                            "id": call_id,
                            "response": result
                        }
                    ]
                }
            }

            # This won't work with new SDK - gemini_session is not a WebSocket
            # Kept for reference only
            self._log("error", "Cannot send manual WebSocket messages with new SDK")

        except Exception as e:
            self._log("error", f"Error sending function response: {e}")

    async def _handle_turn_complete(self) -> None:
        """Handle turn completion event from Gemini."""
        # Turn is complete when Gemini finishes responding
        # Set flags so next user input will be detected as a new turn
        self._turn_ready_for_increment = True
        self._current_turn_started = False  # Reset so next audio is detected as new turn

        self._log("info", f"✓ Turn {self.turn_count} complete - Ready for next user input")

        # Reset audio send count for clean logging in next turn
        if hasattr(self, '_audio_send_count'):
            self._log("info", f"   Resetting audio counter (was {self._audio_send_count} chunks)")
            self._audio_send_count = 0

        # Check if session is still active
        if self.gemini_session:
            self._log("info", f"   Session status: Active, waiting for next audio input")
        else:
            self._log("error", f"   Session status: DEAD - this is a bug!")

        if self.frontend_ws:
            try:
                # Check if WebSocket is still open before sending
                from starlette.websockets import WebSocketState
                if self.frontend_ws.client_state == WebSocketState.CONNECTED:
                    await self.frontend_ws.send_json({"type": "turn_complete"})
                else:
                    self._log("warning", f"⚠️ Frontend WebSocket not connected (state: {self.frontend_ws.client_state})")
            except Exception as e:
                self._log("warning", f"⚠️ Could not send turn_complete to frontend: {e}")

        if self.on_turn_complete:
            self.on_turn_complete()

    async def disconnect(self) -> None:
        """Close all connections."""
        logger.info(f"Disconnecting Gemini Live session: {self.session_id}")

        self.is_connected = False

        # Cancel the result listener task if it's running
        if self._result_listener_task:
            self._result_listener_task.cancel()
            try:
                await self._result_listener_task  # Await cancellation to complete
            except asyncio.CancelledError:
                self._log("info", "Result listener task successfully cancelled.")
            except Exception as e:
                self._log("error", f"Error awaiting cancelled result listener: {e}")
            self._result_listener_task = None

        # Exit the context manager properly
        if hasattr(self, '_session_context') and self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error closing Gemini session: {e}")

        self.gemini_session = None

        # Close audio debug file if open
        if self.audio_file_handle:
            try:
                self.audio_file_handle.close()
                logger.info(f"💾 Closed audio debug file for session: {self.session_id}")
            except Exception as e:
                logger.error(f"Error closing audio debug file: {e}")
            self.audio_file_handle = None

        if self.frontend_ws:
            try:
                await self.frontend_ws.close()
            except RuntimeError:
                # WebSocket may already be closed
                pass
