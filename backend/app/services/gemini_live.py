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
from typing import Any, Callable, Dict, Optional

import websockets
from fastapi import WebSocket

from app.config import settings
from app.models.brief import ConversationMessage

logger = logging.getLogger(__name__)


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
    """

    def __init__(
        self,
        session_id: str,
        system_prompt: Optional[str] = None,
        voice_name: str = "Puck",
    ):
        """
        Initialize Gemini Live connection.

        Args:
            session_id: User session identifier
            system_prompt: System instructions for Gemini Live
            voice_name: Voice to use for TTS (Puck, Charon, Kore, Fenrir, Aoede)
        """
        self.session_id = session_id
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        self.voice_name = voice_name

        self.frontend_ws: Optional[WebSocket] = None
        self.gemini_ws: Optional[websockets.WebSocketClientProtocol] = None

        self.is_connected = False
        self.conversation_history: list[ConversationMessage] = []

        # Callbacks
        self.on_text_received: Optional[Callable[[str, str], None]] = None
        self.on_turn_complete: Optional[Callable[[], None]] = None

    def _get_default_system_prompt(self) -> str:
        """
        Get default system prompt for Executive Producer personality.

        Returns:
            System prompt
        """
        return """
        You are the Executive Producer of a creative AI agency. Your role is to:
        1. Present clear, professional plans to the Creative Director (user)
        2. Delegate tasks to specialist agents (Strategy, Art Director, Video, Audio, Web Dev)
        3. Provide status updates as agents work
        4. Evaluate agent outputs and request revisions when needed
        5. Explain your reasoning when critiquing work

        Tone: Professional, collaborative, explanatory
        Voice: First-person ("I've tasked...", "I'm analyzing...")
        Style: Announce actions before performing them, explain agent roles

        Example dialogue:
        - "Welcome. I'm your Executive Producer. Our first project is the 'Aura' Smart Sneaker launch."
        - "Okay, I've tasked our Strategy Agent [Gemini Pro] with analyzing the sketch."
        - "Excellent choice. Now, I'm sending this slogan to our Art Director Agent."
        - "I'm analyzing it against our brief. The theme is strong, but it doesn't show the glowing sole."

        Always be conversational, professional, and explain what you're doing.
        """

    async def connect(self, frontend_websocket: WebSocket) -> None:
        """
        Establish connection chain: Frontend → Backend → Gemini Live

        Args:
            frontend_websocket: WebSocket from frontend
        """
        logger.info(f"Establishing Gemini Live connection for session: {self.session_id}")

        # Accept frontend connection
        await frontend_websocket.accept()
        self.frontend_ws = frontend_websocket

        # Connect to Gemini Live API
        try:
            self.gemini_ws = await self._connect_to_gemini_live()
            self.is_connected = True

            logger.info("Gemini Live connection established")

            # Start bidirectional streaming
            await asyncio.gather(
                self._handle_frontend_to_gemini(),
                self._handle_gemini_to_frontend(),
                return_exceptions=True,
            )

        except Exception as e:
            logger.error(f"Gemini Live connection error: {e}")
            self.is_connected = False
            if self.frontend_ws:
                await self.frontend_ws.close(code=1011, reason=f"Connection error: {e}")

    async def _connect_to_gemini_live(self) -> websockets.WebSocketClientProtocol:
        """
        Establish WebSocket connection to Gemini Live API.

        Returns:
            WebSocket connection
        """
        logger.info("Connecting to Gemini Live API")

        # In production, use actual Gemini Live WebSocket URL
        # For now, this is a mock implementation
        gemini_ws_url = settings.gemini_live_ws_url

        # Note: Actual implementation would connect to real Gemini Live
        # This is a placeholder for the structure
        logger.warning("Using mock Gemini Live connection (implement real WebSocket)")

        # Mock connection setup
        # gemini_ws = await websockets.connect(
        #     gemini_ws_url,
        #     extra_headers={
        #         "Authorization": f"Bearer {settings.gemini_api_key}",
        #         "Content-Type": "application/json"
        #     }
        # )

        # Send initial configuration
        setup_message = {
            "setup": {
                "model": "gemini-2.0-flash-exp",
                "generation_config": {
                    "response_modalities": ["AUDIO", "TEXT"],  # Both audio and text
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {"voice_name": self.voice_name}
                        }
                    },
                },
                "system_instruction": {"parts": [{"text": self.system_prompt}]},
            }
        }

        # In production: await gemini_ws.send(json.dumps(setup_message))
        logger.info(f"Gemini Live configured with voice: {self.voice_name}")

        # Return mock connection for now
        # TODO: Replace with real WebSocket connection
        return None  # type: ignore

    async def _handle_frontend_to_gemini(self) -> None:
        """Forward user input (audio) to Gemini Live."""
        if not self.frontend_ws:
            return

        try:
            async for message in self.frontend_ws.iter_json():
                message_type = message.get("type")

                if message_type == "audio_input":
                    # User speaking - forward to Gemini Live
                    audio_data = message.get("data")
                    if audio_data and self.gemini_ws:
                        await self._send_audio_to_gemini(audio_data)

                elif message_type == "text_input":
                    # Text fallback mode
                    text = message.get("text")
                    if text:
                        logger.info(f"Text input from user: {text}")
                        # TODO: Send to Gemini Live as text

                elif message_type == "ping":
                    # Heartbeat
                    if self.frontend_ws:
                        await self.frontend_ws.send_json({"type": "pong"})

        except Exception as e:
            logger.error(f"Frontend to Gemini error: {e}")

    async def _send_audio_to_gemini(self, audio_base64: str) -> None:
        """
        Send audio chunk to Gemini Live.

        Args:
            audio_base64: Base64 encoded audio data
        """
        if not self.gemini_ws:
            return

        try:
            audio_data = base64.b64decode(audio_base64)

            # Format for Gemini Live
            message = {
                "realtime_input": {
                    "media_chunks": [
                        {"data": audio_base64, "mime_type": "audio/pcm"}
                    ]
                }
            }

            # In production: await self.gemini_ws.send(json.dumps(message))
            logger.debug(f"Sent {len(audio_data)} bytes to Gemini Live")

        except Exception as e:
            logger.error(f"Error sending audio to Gemini: {e}")

    async def _handle_gemini_to_frontend(self) -> None:
        """Receive from Gemini Live and forward BOTH audio and text to frontend."""
        if not self.gemini_ws:
            # Mock mode - generate sample responses
            await self._mock_gemini_responses()
            return

        try:
            async for message in self.gemini_ws:
                data = json.loads(message)

                # Handle server content
                if "serverContent" in data:
                    await self._process_server_content(data["serverContent"])

                # Handle turn complete
                if "turnComplete" in data:
                    await self._handle_turn_complete()

        except Exception as e:
            logger.error(f"Gemini to Frontend error: {e}")

    async def _process_server_content(self, content: Dict[str, Any]) -> None:
        """
        Process content from Gemini Live.

        Args:
            content: Server content message
        """
        if "modelTurn" not in content:
            return

        for part in content["modelTurn"].get("parts", []):
            # Audio stream
            if "inlineData" in part:
                audio_b64 = part["inlineData"]["data"]
                await self._send_audio_to_frontend(audio_b64, part["inlineData"]["mimeType"])

            # Text transcript (simultaneous with audio)
            if "text" in part:
                text_content = part["text"]
                await self._send_text_to_frontend(text_content, "assistant")

                # Save to conversation history
                from datetime import datetime

                message = ConversationMessage(
                    role="assistant", text=text_content, timestamp=datetime.utcnow()
                )
                self.conversation_history.append(message)

                # Callback
                if self.on_text_received:
                    self.on_text_received("assistant", text_content)

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

    async def _handle_turn_complete(self) -> None:
        """Handle turn completion event."""
        if self.frontend_ws:
            await self.frontend_ws.send_json({"type": "turn_complete"})

        if self.on_turn_complete:
            self.on_turn_complete()

    async def _mock_gemini_responses(self) -> None:
        """
        Generate mock responses for development.
        TODO: Remove when real Gemini Live is connected.
        """
        logger.info("Using mock Gemini Live responses")

        # Simulate initial greeting
        await asyncio.sleep(1)
        await self._send_text_to_frontend(
            "Welcome. I'm your Executive Producer. Ready to create something amazing?",
            "assistant",
        )

        # Keep connection alive
        while self.is_connected:
            await asyncio.sleep(10)
            # Heartbeat
            if self.frontend_ws:
                await self.frontend_ws.send_json({"type": "heartbeat"})

    async def disconnect(self) -> None:
        """Close all connections."""
        logger.info(f"Disconnecting Gemini Live session: {self.session_id}")

        self.is_connected = False

        if self.gemini_ws:
            await self.gemini_ws.close()

        if self.frontend_ws:
            await self.frontend_ws.close()
