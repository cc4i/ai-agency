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
        self.model_name = "imagen-4.0-generate-001"

    async def generate_images(
        self,
        prompt: str,
        number_of_images: int = 1,
        aspect_ratio: str = "16:9",
    ) -> List[bytes]:
        """
        Generate images using Imagen 4.

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
                    image_obj = response.images[0]
                    logger.info(f"Imagen: Image object type: {type(image_obj)}")
                    logger.info(f"Imagen: Image object attributes: {dir(image_obj)}")

                    # Try different ways to access image data
                    if hasattr(image_obj, '_image_bytes'):
                        image_bytes = image_obj._image_bytes
                    elif hasattr(image_obj, 'image_bytes'):
                        image_bytes = image_obj.image_bytes
                    elif hasattr(image_obj, 'data'):
                        image_bytes = image_obj.data
                    elif hasattr(image_obj, 'image') and hasattr(image_obj.image, 'data'):
                        image_bytes = image_obj.image.data
                    else:
                        raise AttributeError(f"Cannot find image data in Image object. Available attributes: {[a for a in dir(image_obj) if not a.startswith('_')]}")

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
        self.model_name = "veo-3.1-generate-preview"

    async def generate_video(
        self,
        prompt: str,
        reference_image: Optional[str] = None,
        duration_seconds: int = 8,
    ) -> bytes:
        """
        Generate video using Veo 3.1 via REST API (long-running operation).

        Args:
            prompt: Video generation prompt
            reference_image: Optional reference image (data URI or URL)
            duration_seconds: Video duration (4, 6, or 8 seconds)

        Returns:
            Generated video as bytes

        Raises:
            ValueError: Invalid input parameters
            RuntimeError: Video generation failed
        """
        try:
            logger.info(f"Veo: Generating {duration_seconds}s video with prompt: {prompt[:50]}...")

            # Build Veo 3.1 API request
            instance = {
                "prompt": prompt,
            }

            # Add reference image if provided (for image-to-video)
            if reference_image:
                # Check if it's a data URI (base64 encoded)
                if reference_image.startswith("data:"):
                    # Extract base64 data from data URI
                    # Format: data:image/png;base64,iVBORw0KG...
                    try:
                        header, img_b64 = reference_image.split(",", 1)
                        mime_type = header.split(":")[1].split(";")[0] if ":" in header else "image/png"
                        logger.info(f"Veo: Using data URI reference image (mime: {mime_type}, size: {len(img_b64)} base64 chars)")
                    except Exception as e:
                        logger.error(f"Error parsing data URI: {e}")
                        raise ValueError(f"Invalid data URI format: {e}")
                else:
                    # Download reference image from URL
                    import httpx
                    async with httpx.AsyncClient() as http_client:
                        img_response = await http_client.get(reference_image)
                        img_response.raise_for_status()
                        img_data = img_response.content

                    # Encode as base64
                    img_b64 = base64.b64encode(img_data).decode('utf-8')
                    mime_type = "image/jpeg"
                    logger.info(f"Veo: Downloaded reference image from URL ({len(img_data)} bytes)")

                # Add image to instance (Veo 3.1 format)
                instance["image"] = {
                    "bytesBase64Encoded": img_b64,
                    "mimeType": mime_type
                }

            # Build parameters (Veo 3.1 format)
            # Include storageUri to have Veo save videos to GCS instead of returning base64
            # This is more efficient (no 5-10MB base64 strings in response)
            import uuid
            video_id = f"veo_{uuid.uuid4().hex[:12]}"
            storage_uri = f"gs://{settings.gcs_bucket_name}/veo_videos/{video_id}"

            parameters = {
                "sampleCount": 1,
                "durationSeconds": duration_seconds,
                "generateAudio": False,  # Required for Veo 3.1
                "storageUri": storage_uri,  # Save to GCS instead of returning base64
            }

            logger.info(f"Veo: Requesting video save to: {storage_uri}")

            # Make direct REST API call to Vertex AI
            from google.auth import default
            from google.auth.transport.requests import Request
            import httpx

            # Get credentials
            credentials, project = default()
            if not credentials.valid:
                credentials.refresh(Request())

            # Build API endpoint for long-running operation
            location = settings.google_cloud_location
            endpoint = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/{self.model_name}:predictLongRunning"
            logger.info(f"Veo: Using endpoint: {endpoint}")

            # Build request body (Veo 3.1 format)
            request_body = {
                "instances": [instance],
                "parameters": parameters
            }

            # Make initial request to start operation
            headers = {
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json"
            }

            logger.info("Veo: Starting long-running video generation operation...")
            async with httpx.AsyncClient(timeout=300.0) as http_client:
                response = await http_client.post(
                    endpoint,
                    json=request_body,
                    headers=headers
                )
                response.raise_for_status()
                operation_response = response.json()

            # Extract operation name
            if "name" not in operation_response:
                raise RuntimeError(f"No operation name in response: {operation_response}")

            operation_name = operation_response["name"]
            logger.info(f"Veo: Operation started: {operation_name}")

            # Poll operation until complete
            video_bytes = await self._poll_operation(operation_name, credentials, project, location)

            logger.info(f"Veo: Successfully generated video ({len(video_bytes)} bytes)")
            return video_bytes

        except Exception as e:
            logger.error(f"Veo error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def _poll_operation(
        self,
        operation_name: str,
        credentials,
        project: str,
        location: str,
        max_wait_seconds: int = 300,
        poll_interval_seconds: int = 5,
    ) -> bytes:
        """
        Poll long-running operation until complete and return video bytes.

        Args:
            operation_name: Full operation name from initial response
            credentials: Google auth credentials
            project: GCP project ID
            location: GCP location
            max_wait_seconds: Maximum time to wait for completion (default 5 minutes)
            poll_interval_seconds: Time between polling requests (default 5 seconds)

        Returns:
            Generated video as bytes

        Raises:
            RuntimeError: Operation failed or timed out
        """
        import httpx
        import asyncio
        from datetime import datetime, timedelta

        # Build fetch operation endpoint
        fetch_endpoint = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/publishers/google/models/{self.model_name}:fetchPredictOperation"

        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json"
        }

        start_time = datetime.now()
        deadline = start_time + timedelta(seconds=max_wait_seconds)
        poll_count = 0

        logger.info(f"Veo: Polling operation (max wait: {max_wait_seconds}s, interval: {poll_interval_seconds}s)")

        async with httpx.AsyncClient(timeout=60.0) as http_client:
            while datetime.now() < deadline:
                poll_count += 1

                # Refresh credentials if needed
                if not credentials.valid:
                    from google.auth.transport.requests import Request
                    credentials.refresh(Request())
                    headers["Authorization"] = f"Bearer {credentials.token}"

                # Fetch operation status
                request_body = {"operationName": operation_name}

                try:
                    response = await http_client.post(
                        fetch_endpoint,
                        json=request_body,
                        headers=headers
                    )
                    response.raise_for_status()
                    result = response.json()
                except httpx.HTTPError as e:
                    logger.warning(f"Veo: Poll #{poll_count} failed: {e}, retrying...")
                    await asyncio.sleep(poll_interval_seconds)
                    continue

                # Check if operation is complete
                if result.get("done"):
                    logger.info(f"Veo: Operation complete after {poll_count} polls ({(datetime.now() - start_time).total_seconds():.1f}s)")

                    # Check for errors
                    if "error" in result:
                        error_msg = result["error"].get("message", str(result["error"]))
                        raise RuntimeError(f"Veo operation failed: {error_msg}")

                    # Debug: Log full response structure
                    logger.info(f"Veo: Full response keys: {result.keys()}")
                    if "response" in result:
                        logger.info(f"Veo: Response content keys: {result['response'].keys()}")

                    # Extract video from response
                    # Response structure: {"done": true, "response": {"videos": [{"video": {...}}]}}
                    if "response" in result:
                        response_data = result["response"]

                        # Check for videos list (new format)
                        if "videos" in response_data and len(response_data["videos"]) > 0:
                            video_entry = response_data["videos"][0]
                            logger.info(f"Veo: Video entry keys: {video_entry.keys()}")

                            # Try to extract video data - check multiple possible structures
                            video_obj = None

                            # NEW FORMAT (2025-01): Video data directly in entry
                            if "gcsUri" in video_entry or "bytesBase64Encoded" in video_entry:
                                logger.info("Veo: Using direct video entry format (2025-01)")
                                video_obj = video_entry
                            # OLD FORMAT: Video data wrapped in "video" field
                            elif "video" in video_entry:
                                logger.info("Veo: Using wrapped video format (legacy)")
                                video_obj = video_entry["video"]
                                logger.info(f"Veo: Video object keys: {video_obj.keys()}")

                            if video_obj:
                                # Video should be in GCS (since we provided storageUri)
                                # But fallback to base64 if GCS URI not present
                                if "gcsUri" in video_obj:
                                    gcs_uri = video_obj["gcsUri"]
                                    logger.info(f"Veo: Downloading video from GCS: {gcs_uri}")
                                    video_bytes = await self._download_from_gcs(gcs_uri)
                                    return video_bytes
                                elif "bytesBase64Encoded" in video_obj:
                                    # Fallback: base64 response (shouldn't happen with storageUri)
                                    logger.warning("Veo: Received base64 response despite storageUri request")
                                    video_b64 = video_obj["bytesBase64Encoded"]
                                    video_bytes = base64.b64decode(video_b64)
                                    logger.info(f"Veo: Decoded video from base64 ({len(video_bytes)} bytes)")
                                    return video_bytes
                                else:
                                    raise RuntimeError(f"No video data in video object: {video_obj.keys()}")
                            else:
                                raise RuntimeError(f"No video data found in entry: {video_entry.keys()}")

                        # Fallback: Check for old predictions format
                        elif "predictions" in response_data:
                            logger.warning("Veo: Using legacy 'predictions' format")
                            predictions = response_data["predictions"]
                            if len(predictions) > 0:
                                prediction = predictions[0]

                                if "bytesBase64Encoded" in prediction:
                                    video_b64 = prediction["bytesBase64Encoded"]
                                    video_bytes = base64.b64decode(video_b64)
                                    return video_bytes
                                elif "gcsUri" in prediction:
                                    gcs_uri = prediction["gcsUri"]
                                    logger.info(f"Veo: Downloading video from GCS: {gcs_uri}")
                                    video_bytes = await self._download_from_gcs(gcs_uri)
                                    return video_bytes
                                else:
                                    raise RuntimeError(f"No video data in prediction: {prediction.keys()}")

                        raise RuntimeError(f"No 'videos' or 'predictions' in response: {response_data.keys()}")

                    raise RuntimeError(f"No 'response' in operation result: {result.keys()}")

                # Operation still running
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(f"Veo: Poll #{poll_count} - operation still running ({elapsed:.1f}s elapsed)")
                await asyncio.sleep(poll_interval_seconds)

        # Timeout
        raise RuntimeError(f"Veo operation timed out after {max_wait_seconds}s")

    async def _download_from_gcs(self, gcs_uri: str) -> bytes:
        """
        Download video from Google Cloud Storage.

        Args:
            gcs_uri: GCS URI (e.g., gs://bucket-name/path/to/video.mp4)

        Returns:
            Video bytes
        """
        try:
            # Parse GCS URI: gs://bucket-name/path/to/file
            if not gcs_uri.startswith("gs://"):
                raise ValueError(f"Invalid GCS URI: {gcs_uri}")

            parts = gcs_uri[5:].split("/", 1)
            bucket_name = parts[0]
            blob_name = parts[1] if len(parts) > 1 else ""

            logger.info(f"Veo: Downloading from GCS bucket '{bucket_name}', blob '{blob_name}'")

            # Use GCS client to download
            from google.cloud import storage
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)

            video_bytes = blob.download_as_bytes()
            logger.info(f"Veo: Downloaded {len(video_bytes)} bytes from GCS")

            return video_bytes

        except Exception as e:
            logger.error(f"Error downloading from GCS: {e}")
            raise RuntimeError(f"Failed to download video from GCS: {e}")


class LyriaClient:
    """Client for Lyria audio generation API (music and TTS)."""

    def __init__(self):
        """Initialize Lyria client."""
        self.project_id = settings.google_cloud_project
        self.location = settings.google_cloud_location

    async def generate_music(
        self, prompt: str, duration_seconds: int = 10, negative_prompt: str = None, seed: int = None
    ) -> bytes:
        """
        Generate music using Lyria (lyria-002 model).

        Args:
            prompt: Music generation prompt (US English)
            duration_seconds: Music duration (note: Lyria generates 30s fixed)
            negative_prompt: Optional prompt describing elements to exclude
            seed: Optional seed for deterministic output (incompatible with sample_count)

        Returns:
            Generated audio as bytes (WAV format, 48 kHz)
        """
        try:
            logger.info(f"Lyria: Generating music with prompt: {prompt[:100]}...")

            # Import Vertex AI Prediction API
            from google.cloud import aiplatform
            from google.protobuf import json_format
            from google.protobuf.struct_pb2 import Value
            import base64

            # Initialize Vertex AI
            aiplatform.init(project=self.project_id, location=self.location)

            # Prepare request payload
            instance = {
                "prompt": prompt
            }
            if negative_prompt:
                instance["negative_prompt"] = negative_prompt
            if seed is not None:
                instance["seed"] = seed

            # Parameters (sample_count if no seed)
            parameters = {}
            if seed is None:
                parameters["sample_count"] = 1

            logger.info(f"Lyria: Calling lyria-002 model in {self.location}...")

            # Create endpoint URL
            endpoint = f"projects/{self.project_id}/locations/{self.location}/publishers/google/models/lyria-002"

            # Use PredictionServiceClient for synchronous predict
            from google.cloud.aiplatform_v1.services.prediction_service import PredictionServiceClient

            # Create client
            client = PredictionServiceClient(
                client_options={"api_endpoint": f"{self.location}-aiplatform.googleapis.com"}
            )

            # Prepare instances and parameters as Value objects
            instances_value = [json_format.ParseDict(instance, Value())]
            parameters_value = json_format.ParseDict(parameters, Value()) if parameters else None

            # Call predict API synchronously (in executor to avoid blocking)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.predict(
                    endpoint=endpoint,
                    instances=instances_value,
                    parameters=parameters_value
                )
            )

            # Extract audio from response
            if not response.predictions:
                logger.warning("Lyria: No predictions in response")
                return b""

            # Get first prediction
            prediction = response.predictions[0]

            # Extract audioContent (base64-encoded WAV)
            audio_content_b64 = None
            if hasattr(prediction, 'audioContent'):
                audio_content_b64 = prediction.audioContent
            elif isinstance(prediction, dict) and 'audioContent' in prediction:
                audio_content_b64 = prediction['audioContent']
            else:
                # Try to access as struct
                try:
                    audio_content_b64 = prediction.get('audioContent')
                except:
                    logger.error(f"Lyria: Could not extract audioContent from prediction: {type(prediction)}")
                    return b""

            if not audio_content_b64:
                logger.warning("Lyria: No audioContent in prediction")
                return b""

            # Decode base64 to bytes
            audio_bytes = base64.b64decode(audio_content_b64)
            logger.info(f"Lyria: Generated {len(audio_bytes)} bytes of music (WAV, 48kHz, 30s)")

            return audio_bytes

        except Exception as e:
            logger.error(f"Lyria music generation error: {e}", exc_info=True)
            # Return empty bytes instead of raising to allow graceful degradation
            logger.warning("Lyria: Returning empty bytes due to error")
            return b""

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
