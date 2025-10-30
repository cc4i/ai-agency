"""Google AI API client integrations.

This module provides client wrappers for:
- Gemini Live API (WebSocket streaming conversation)
- Gemini Pro API (text generation)
- Gemini Pro Vision API (image analysis)
- Imagen API (image generation)
- Veo API (video generation)
- Lyria API (audio generation - music and TTS)
- Chirp API (audio transcription)
"""

import base64
import json
import logging
from typing import Any, Dict, List, Optional
import asyncio

from google import genai

from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Google Genai client with Vertex AI
# Supports: Text, Vision, Live API, Image generation, Video generation
try:
    genai_client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    )
    logger.info(f"Google GenAI client initialized with Vertex AI (project: {settings.google_cloud_project}, location: {settings.google_cloud_location})")
except Exception as e:
    logger.warning(f"GenAI client initialization failed: {e}")
    genai_client = None


class GeminiLiveClient:
    """
    Client for Gemini Live streaming conversation API.

    Handles bidirectional audio streaming and real-time conversation.
    """

    def __init__(self):
        """Initialize Gemini Live client."""
        self.api_key = settings.gemini_api_key
        self.ws_url = f"{settings.gemini_live_ws_url}?key={self.api_key}"
        self.websocket: Optional[Any] = None

    async def connect(self) -> Any:
        """
        Establish WebSocket connection to Gemini Live.

        Returns:
            WebSocket connection object
        """
        try:
            import websockets

            logger.info(f"Gemini Live: Connecting to {settings.gemini_live_ws_url}")

            # Connect to Gemini Live WebSocket
            self.websocket = await websockets.connect(
                self.ws_url,
                additional_headers={
                    "Content-Type": "application/json",
                },
            )

            logger.info("Gemini Live: Connection established")

            # Send initial setup message
            setup_message = {
                "setup": {
                    "model": "models/gemini-live-2.5-flash-preview-native-audio-09-2025",
                    "generation_config": {
                        "response_modalities": ["AUDIO"],
                        "speech_config": {
                            "voice_config": {
                                "prebuilt_voice_config": {
                                    "voice_name": "Aoede"  # Professional female voice
                                }
                            }
                        }
                    }
                }
            }

            await self.websocket.send(json.dumps(setup_message))
            logger.info("Gemini Live: Setup message sent")

            return self.websocket

        except Exception as e:
            logger.error(f"Gemini Live connection error: {e}")
            raise

    async def send_audio_chunk(self, audio_data: bytes) -> None:
        """
        Send audio chunk to Gemini Live.

        Args:
            audio_data: Raw audio bytes (PCM16, 16kHz, mono)
        """
        try:
            if not self.websocket:
                raise RuntimeError("WebSocket not connected")

            # Encode audio as base64
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')

            # Send real-time input message
            message = {
                "realtime_input": {
                    "media_chunks": [
                        {
                            "mime_type": "audio/pcm",
                            "data": audio_b64
                        }
                    ]
                }
            }

            await self.websocket.send(json.dumps(message))
            logger.debug(f"Gemini Live: Sent {len(audio_data)} bytes of audio")

        except Exception as e:
            logger.error(f"Gemini Live send error: {e}")
            raise

    async def send_text(self, text: str) -> None:
        """
        Send text message to Gemini Live.

        Args:
            text: Text message to send
        """
        try:
            if not self.websocket:
                raise RuntimeError("WebSocket not connected")

            message = {
                "client_content": {
                    "turns": [
                        {
                            "role": "user",
                            "parts": [{"text": text}]
                        }
                    ],
                    "turn_complete": True
                }
            }

            await self.websocket.send(json.dumps(message))
            logger.info(f"Gemini Live: Sent text: {text[:50]}...")

        except Exception as e:
            logger.error(f"Gemini Live send text error: {e}")
            raise

    async def receive_response(self) -> Dict[str, Any]:
        """
        Receive response from Gemini Live.

        Returns:
            Response with audio and/or text
        """
        try:
            if not self.websocket:
                raise RuntimeError("WebSocket not connected")

            # Receive message
            raw_message = await self.websocket.recv()
            message = json.loads(raw_message)

            # Parse response
            result = {
                "type": "unknown",
                "audio": b"",
                "text": "",
            }

            # Handle server content (audio/text response)
            if "serverContent" in message:
                content = message["serverContent"]

                # Extract text
                if "modelTurn" in content:
                    parts = content["modelTurn"].get("parts", [])
                    text_parts = [p.get("text", "") for p in parts if "text" in p]
                    result["text"] = " ".join(text_parts)
                    result["type"] = "text"

                # Extract audio
                if "turnComplete" in content and content.get("turnComplete"):
                    result["type"] = "turn_complete"

            # Handle audio output
            if "audioOut" in message:
                audio_b64 = message["audioOut"].get("data", "")
                if audio_b64:
                    result["audio"] = base64.b64decode(audio_b64)
                    result["type"] = "audio"

            return result

        except Exception as e:
            logger.error(f"Gemini Live receive error: {e}")
            raise

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            logger.info("Gemini Live: Disconnected")


class GeminiProClient:
    """Client for Gemini Pro text generation API using new google.genai SDK."""

    def __init__(self):
        """Initialize Gemini Pro client."""
        self.client = genai_client
        self.model_name = "gemini-2.5-flash"

    async def generate_content(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate text content using Gemini Pro.

        Args:
            prompt: User prompt
            system_prompt: Optional system instructions

        Returns:
            Generated text
        """
        try:
            if not self.client:
                raise RuntimeError("GenAI client not initialized")

            logger.info(f"Gemini Pro: Generating content for prompt: {prompt[:50]}...")

            # Build config
            config = {
                'temperature': 0.7,
                'top_p': 0.95,
                'top_k': 40,
                'max_output_tokens': 2048,
            }

            # Build contents with system instruction if provided
            contents = prompt
            if system_prompt:
                config['system_instruction'] = system_prompt

            # Generate content using new SDK
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config
            )

            result = response.text
            logger.info(f"Gemini Pro: Generated {len(result)} characters")
            return result

        except Exception as e:
            logger.error(f"Gemini Pro error: {e}")
            raise


class GeminiProVisionClient:
    """Client for Gemini Pro Vision API using new google.genai SDK."""

    def __init__(self):
        """Initialize Gemini Pro Vision client."""
        self.client = genai_client
        self.model_name = "gemini-2.5-flash"  # Supports vision

    async def analyze_image(self, image_url: str, prompt: str) -> str:
        """
        Analyze image with Gemini Pro Vision.

        Args:
            image_url: URL to image
            prompt: Analysis instructions

        Returns:
            Analysis result
        """
        try:
            if not self.client:
                raise RuntimeError("GenAI client not initialized")

            logger.info(f"Gemini Pro Vision: Analyzing image: {image_url}")

            # Download image
            import httpx
            async with httpx.AsyncClient() as client:
                image_response = await client.get(image_url)
                image_response.raise_for_status()
                image_data = image_response.content

            # Encode image as base64
            import base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')

            # Configure generation
            config = {
                'temperature': 0.4,
                'top_p': 0.95,
                'top_k': 32,
                'max_output_tokens': 1024,
            }

            # Build contents with image
            from google.genai.types import Part
            contents = [
                Part(text=prompt),
                Part(inline_data={'mime_type': 'image/jpeg', 'data': image_b64})
            ]

            # Analyze image using new SDK
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config
            )

            result = response.text
            logger.info(f"Gemini Pro Vision: Analysis complete ({len(result)} chars)")
            return result

        except Exception as e:
            logger.error(f"Gemini Pro Vision error: {e}")
            raise


class ImagenClient:
    """Client for Imagen image generation API using google.genai."""

    def __init__(self):
        """Initialize Imagen client."""
        self.client = genai_client
        self.model_name = "imagen-3.0-generate-001"

    async def generate_images(
        self,
        prompt: str,
        number_of_images: int = 1,
        aspect_ratio: str = "16:9",
    ) -> List[bytes]:
        """
        Generate images using Imagen 3.

        Args:
            prompt: Image generation prompt
            number_of_images: Number of images to generate
            aspect_ratio: Image aspect ratio (1:1, 3:4, 4:3, 9:16, 16:9)

        Returns:
            List of generated images as bytes
        """
        try:
            if not self.client:
                raise RuntimeError("GenAI client not initialized")

            logger.info(f"Imagen: Generating {number_of_images} images with prompt: {prompt[:50]}...")

            images = []
            for i in range(number_of_images):
                # Generate image using genai SDK
                response = await self.client.aio.models.generate_images(
                    model=self.model_name,
                    prompt=prompt,
                    config={
                        "number_of_images": 1,
                        "aspect_ratio": aspect_ratio,
                        "safety_filter_level": "block_some",
                        "person_generation": "allow_adult",
                    }
                )

                # Extract image bytes
                if response.images:
                    image_bytes = response.images[0].image.data
                    images.append(image_bytes)
                    logger.info(f"Imagen: Generated image {i+1}/{number_of_images}")

            logger.info(f"Imagen: Successfully generated {len(images)} images")
            return images

        except Exception as e:
            logger.error(f"Imagen error: {e}")
            raise


class VeoClient:
    """Client for Veo video generation API using google.genai."""

    def __init__(self):
        """Initialize Veo client."""
        self.client = genai_client
        self.model_name = "veo-002"

    async def generate_video(
        self,
        prompt: str,
        reference_image: Optional[str] = None,
        duration_seconds: int = 8,
    ) -> bytes:
        """
        Generate video using Veo 2.

        Args:
            prompt: Video generation prompt
            reference_image: Optional reference image URL
            duration_seconds: Video duration (max 8s for Veo 2)

        Returns:
            Generated video as bytes
        """
        try:
            if not self.client:
                raise RuntimeError("GenAI client not initialized")

            logger.info(f"Veo: Generating {duration_seconds}s video with prompt: {prompt[:50]}...")

            # Build config
            config = {
                "aspect_ratio": "16:9",
                "duration_seconds": duration_seconds,
            }

            # Add reference image if provided
            if reference_image:
                # Download reference image
                import httpx
                async with httpx.AsyncClient() as http_client:
                    img_response = await http_client.get(reference_image)
                    img_response.raise_for_status()
                    img_data = img_response.content

                # Encode as base64
                img_b64 = base64.b64encode(img_data).decode('utf-8')
                config["reference_image"] = {
                    "mime_type": "image/jpeg",
                    "data": img_b64
                }

            # Generate video using genai SDK
            response = await self.client.aio.models.generate_video(
                model=self.model_name,
                prompt=prompt,
                config=config
            )

            # Extract video bytes
            video_bytes = response.video.data if response.video else b""
            logger.info(f"Veo: Successfully generated video ({len(video_bytes)} bytes)")
            return video_bytes

        except Exception as e:
            logger.error(f"Veo error: {e}")
            raise


class LyriaClient:
    """Client for Lyria audio generation API (music and TTS)."""

    def __init__(self):
        """Initialize Lyria client."""
        self.project_id = settings.google_cloud_project
        self.location = settings.google_cloud_location

    async def generate_music(
        self, prompt: str, duration_seconds: int = 10
    ) -> bytes:
        """
        Generate music using Lyria/MusicLM.

        Args:
            prompt: Music generation prompt
            duration_seconds: Music duration

        Returns:
            Generated audio as bytes
        """
        try:
            logger.info(f"Lyria: Generating {duration_seconds}s music with prompt: {prompt[:50]}...")

            # Note: MusicLM/Lyria API not yet publicly available via genai SDK
            # Placeholder implementation for when API becomes available
            logger.warning("Lyria/MusicLM API not yet publicly available. Returning placeholder.")

            # Future implementation would use genai client:
            # response = await self.client.aio.models.generate_audio(
            #     model="lyria-music-generation",
            #     prompt=prompt,
            #     config={"duration_seconds": duration_seconds}
            # )
            # return response.audio.data

            # Return empty audio bytes for now
            return b""

        except Exception as e:
            logger.error(f"Lyria music generation error: {e}")
            raise

    async def synthesize_speech(self, text: str, voice: str = "en-US-Studio-O") -> bytes:
        """
        Synthesize speech using Google Cloud Text-to-Speech.

        Args:
            text: Text to synthesize
            voice: Voice name (e.g., en-US-Studio-O, en-US-Neural2-F)

        Returns:
            Generated audio as bytes
        """
        try:
            logger.info(f"TTS: Synthesizing speech for: {text[:50]}...")

            from google.cloud import texttospeech

            # Create TTS client
            client = texttospeech.TextToSpeechClient()

            # Set the text input
            synthesis_input = texttospeech.SynthesisInput(text=text)

            # Build voice parameters
            voice_params = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name=voice
            )

            # Select audio file type
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0,
                pitch=0.0
            )

            # Perform synthesis asynchronously
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.synthesize_speech(
                    input=synthesis_input,
                    voice=voice_params,
                    audio_config=audio_config
                )
            )

            audio_bytes = response.audio_content
            logger.info(f"TTS: Generated {len(audio_bytes)} bytes of audio")
            return audio_bytes

        except Exception as e:
            logger.error(f"TTS error: {e}")
            raise


class ChirpClient:
    """Client for Chirp audio transcription API (Google Cloud Speech-to-Text)."""

    def __init__(self):
        """Initialize Chirp client."""
        self.project_id = settings.google_cloud_project

    async def transcribe(
        self, audio_url: str, format: str = "txt", language: str = "en-US"
    ) -> Dict[str, Any]:
        """
        Transcribe audio using Google Cloud Speech-to-Text (Chirp model).

        Args:
            audio_url: URL to audio file
            format: Output format (srt, vtt, txt)
            language: Target language code (e.g., en-US)

        Returns:
            Transcription result
        """
        try:
            logger.info(f"Chirp: Transcribing audio: {audio_url}")

            from google.cloud import speech_v1 as speech

            # Create Speech client
            client = speech.SpeechClient()

            # Download audio file
            import httpx
            async with httpx.AsyncClient() as http_client:
                audio_response = await http_client.get(audio_url)
                audio_response.raise_for_status()
                audio_content = audio_response.content

            # Configure recognition
            audio = speech.RecognitionAudio(content=audio_content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=language,
                enable_automatic_punctuation=True,
                enable_word_time_offsets=(format in ["srt", "vtt"]),
                model="chirp",  # Use Chirp model
            )

            # Perform transcription asynchronously
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.recognize(config=config, audio=audio)
            )

            # Extract transcription
            transcripts = []
            for result in response.results:
                transcripts.append(result.alternatives[0].transcript)

            full_text = " ".join(transcripts)
            logger.info(f"Chirp: Transcribed {len(full_text)} characters")

            return {
                "text": full_text,
                "language": language,
                "format": format,
            }

        except Exception as e:
            logger.error(f"Chirp transcription error: {e}")
            raise


class GeminiCodeAssistClient:
    """Client for Gemini Code Assist API using new google.genai SDK."""

    def __init__(self):
        """Initialize Code Assist client."""
        self.client = genai_client
        self.model_name = "gemini-2.5-flash"

    async def generate_code(
        self, prompt: str, language: str = "html"
    ) -> str:
        """
        Generate code using Gemini Code Assist.

        Args:
            prompt: Code generation instructions
            language: Target language (html, javascript, python, etc.)

        Returns:
            Generated code
        """
        try:
            if not self.client:
                raise RuntimeError("GenAI client not initialized")

            logger.info(f"Code Assist: Generating {language} code")

            # Create code-focused system prompt
            system_prompt = f"""You are an expert {language} developer. Generate clean, production-ready code.
Follow these guidelines:
- Write semantic, accessible, and performant code
- Include proper comments
- Use modern best practices
- Return ONLY the code, no explanations
- Make it visually appealing and professional
"""

            # Configure for code generation
            config = {
                'temperature': 0.3,  # Lower temperature for more deterministic code
                'top_p': 0.95,
                'top_k': 40,
                'max_output_tokens': 4096,  # Allow longer code outputs
                'system_instruction': system_prompt
            }

            # Generate code using new SDK
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )

            code = response.text

            # Remove markdown code fences if present
            if code.startswith("```"):
                lines = code.split("\n")
                code = "\n".join(lines[1:-1]) if len(lines) > 2 else code

            logger.info(f"Code Assist: Generated {len(code)} characters of {language} code")
            return code

        except Exception as e:
            logger.error(f"Code Assist error: {e}")
            raise


# Global client instances
gemini_live_client = GeminiLiveClient()
gemini_pro_client = GeminiProClient()
gemini_vision_client = GeminiProVisionClient()
imagen_client = ImagenClient()
veo_client = VeoClient()
lyria_client = LyriaClient()
chirp_client = ChirpClient()
code_assist_client = GeminiCodeAssistClient()
