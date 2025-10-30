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
)
from fastapi import WebSocket

from app.config import settings
from app.models.brief import ConversationMessage

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
        voice_name: str = "Kore",  # Options: Puck, Charon, Kore, Fenrir, Aoede
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
                "name": "create_campaign_strategy",
                "description": "Task the Strategy Agent to create campaign personas, slogans, and positioning. Call this when the user wants to create a marketing campaign.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_name": {
                            "type": "string",
                            "description": "Name of the product"
                        },
                        "product_category": {
                            "type": "string",
                            "description": "Product category (footwear, beverage, electronics, etc.)"
                        },
                        "theme": {
                            "type": "string",
                            "description": "Campaign theme or concept"
                        },
                        "key_features": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key product features to highlight"
                        },
                        "brand_tone": {
                            "type": "string",
                            "description": "Brand tone (futuristic, luxury, energetic, etc.)"
                        },
                        "target_market": {
                            "type": "string",
                            "description": "Target market description"
                        }
                    },
                    "required": ["product_name", "product_category"]
                }
            },
            {
                "name": "generate_hero_images",
                "description": "Task the Art Director Agent to create hero images for the campaign. Call this after a slogan has been selected.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "slogan": {
                            "type": "string",
                            "description": "The selected campaign slogan"
                        },
                        "product_name": {
                            "type": "string",
                            "description": "Name of the product"
                        },
                        "theme": {
                            "type": "string",
                            "description": "Visual theme"
                        },
                        "brand_tone": {
                            "type": "string",
                            "description": "Brand tone"
                        }
                    },
                    "required": ["slogan", "product_name"]
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
        1. Present clear, professional plans to the Creative Director
        2. Delegate tasks to specialist agents (Strategy, Art Director, Video, Audio, Web Dev)
        3. Provide status updates as agents work
        4. Evaluate agent outputs and request revisions when needed
        5. Explain your reasoning when critiquing work
        6. Continue the conversation across multiple turns, maintaining context

        Tone: Professional, collaborative, explanatory
        Voice: First-person ("I've tasked...", "I'm analyzing...")
        Style: Announce actions before performing them, explain agent roles

        Important:
        - This is a continuous conversation. Respond to each user input naturally.
        - When the user wants to create a campaign, use the create_campaign_strategy function.
        - When they select a slogan, use the generate_hero_images function.
        - Always listen for and respond to new user inputs throughout the conversation.

        Example dialogue:
        - "Welcome. I'm your Executive Producer. Let me task our Strategy team to analyze your product."
        - "Great! I'm calling our Strategy Agent now to create campaign options."
        - "Excellent choice. Now I'm sending this slogan to our Art Director Agent to create visuals."
        - "I'm analyzing the images against our brief. The theme is strong!"

        Always be conversational, professional, and ready to continue the dialogue.
        """

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

        # Connect to Gemini Live API
        try:
            self.gemini_session = await self._connect_to_gemini_live()
            self.is_connected = True

            self._log("info", "✓ Gemini Live connection established")

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

    async def _connect_to_gemini_live(self):
        """
        Establish connection to Gemini Live API using google.genai SDK (Vertex AI).

        Returns:
            Gemini Live session
        """
        self._log("info", "🔗 Connecting to Gemini Live API (Vertex AI)")

        # Define agent tools for function calling
        agent_tools = self._get_agent_tools()

        # Create LiveConnectConfig with voice, tools, and automatic VAD
        # Note: Timeout is configured at client level (see __init__)
        config = LiveConnectConfig(
            response_modalities=["AUDIO"], # Text is enabled via output_audio_transcription
            output_audio_transcription={},
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

        # Add function calling tools
        if agent_tools:
            config.tools = [{"function_declarations": agent_tools}]

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
                                    self._log("info", f"📝 Transcript received: {transcript_text}")
                                    await self._send_text_to_frontend(transcript_text, "assistant")
                                    # Save to conversation history
                                    from datetime import datetime, timezone
                                    message = ConversationMessage(
                                        role="assistant",
                                        text=transcript_text,
                                        timestamp=datetime.now(timezone.utc)
                                    )
                                    self.conversation_history.append(message)

                                    # Callback
                                    if self.on_text_received:
                                        self.on_text_received("assistant", transcript_text)

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
                            self._log("info", "🔧 Tool call received")
                            await self._handle_tool_call_genai(response.tool_call)

                    except Exception as e:
                        self._log("error", f"✗ Response processing error: {e}")
                        import traceback
                        self._log("error", f"Traceback: {traceback.format_exc()}")

        except Exception as e:
            self._log("error", f"✗ Gemini to Frontend error: {e}")
            import traceback
            self._log("error", f"Traceback: {traceback.format_exc()}")
            # If a major error occurs, break the main loop
            self.is_connected = False

    async def _send_audio_to_frontend(self, audio_base64: str, mime_type: str) -> None:
        """
        Send audio to frontend for playback.

        Args:
            audio_base64: Base64 encoded audio
            mime_type: Audio MIME type
        """
        if not self.frontend_ws:
            return

        try:
            await self.frontend_ws.send_json({
                "type": "audio_output",
                "data": audio_base64,
                "mime_type": mime_type,
            })
        except Exception as e:
            logger.error(f"Error sending audio to frontend: {e}")

    async def _send_text_to_frontend(self, text: str, role: str) -> None:
        """
        Send text transcript to frontend.

        Args:
            text: Text content
            role: Message role (user or assistant)
        """
        if not self.frontend_ws:
            return

        try:
            from datetime import datetime

            await self.frontend_ws.send_json({
                "type": "text_output",
                "text": text,
                "role": role,
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            logger.error(f"Error sending text to frontend: {e}")

    async def _handle_tool_call_genai(self, tool_call: Any) -> None:
        """
        Handle tool call from genai SDK - execute agent and send response.

        Args:
            tool_call: Tool call object from genai SDK
        """
        try:
            # Extract function calls from genai SDK format
            function_calls = []
            if hasattr(tool_call, 'function_calls'):
                function_calls = tool_call.function_calls

            if not function_calls:
                self._log("warning", "Tool call with no function calls")
                return

            for func_call in function_calls:
                function_name = func_call.name if hasattr(func_call, 'name') else func_call.get('name')
                function_args = func_call.args if hasattr(func_call, 'args') else func_call.get('args', {})
                call_id = func_call.id if hasattr(func_call, 'id') else func_call.get('id')

                self._log("info", f"🔧 Executing function: {function_name} with args: {function_args}")

                # Route to appropriate agent
                result = await self._execute_agent_function(function_name, function_args)

                # Send function response back to Gemini using SDK
                if self.gemini_session:
                    await self.gemini_session.send_tool_response(
                        function_responses=[
                            {
                                "id": call_id,
                                "response": result
                            }
                        ]
                    )
                    self._log("info", f"📤 Sent function response for call: {call_id}")

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
        self, function_name: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute agent based on function call.

        Args:
            function_name: Name of the function called
            args: Function arguments

        Returns:
            Agent execution result
        """
        from app.services.orchestration import AgentOrchestrator

        orchestrator = AgentOrchestrator()

        try:
            if function_name == "create_campaign_strategy":
                self._log("info", "🎯 Executing Strategy Agent")

                # Build task from args
                task = {
                    "task_id": f"strategy_{self.session_id}",
                    "product_name": args.get("product_name"),
                    "product_category": args.get("product_category"),
                    "theme": args.get("theme", "modern"),
                    "key_features": args.get("key_features", []),
                    "brand_tone": args.get("brand_tone", "professional"),
                    "target_market": args.get("target_market", "general audience"),
                }

                result = await orchestrator.execute_agent(
                    "strategy",
                    task=task,
                    project_id=self.project_id,
                    with_critique=False,
                )

                self._log("info", f"✓ Strategy Agent completed")

                # Send result to frontend
                if self.frontend_ws:
                    await self.frontend_ws.send_json({
                        "type": "agent_result",
                        "agent": "strategy",
                        "data": result
                    })

                return {
                    "success": True,
                    "agent": "strategy",
                    "result": result
                }

            elif function_name == "generate_hero_images":
                self._log("info", "🎨 Executing Art Director Agent")

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

                result = await orchestrator.execute_agent(
                    "art_director",
                    task=task,
                    project_id=self.project_id,
                    with_critique=False,
                )

                self._log("info", f"✓ Art Director Agent completed")

                # Send result to frontend
                if self.frontend_ws:
                    await self.frontend_ws.send_json({
                        "type": "agent_result",
                        "agent": "art_director",
                        "data": result
                    })

                return {
                    "success": True,
                    "agent": "art_director",
                    "result": result
                }

            else:
                self._log("warning", f"Unknown function: {function_name}")
                return {
                    "success": False,
                    "error": f"Unknown function: {function_name}"
                }

        except Exception as e:
            self._log("error", f"Agent execution error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

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
            await self.frontend_ws.send_json({"type": "turn_complete"})

        if self.on_turn_complete:
            self.on_turn_complete()

    async def disconnect(self) -> None:
        """Close all connections."""
        logger.info(f"Disconnecting Gemini Live session: {self.session_id}")

        self.is_connected = False

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
