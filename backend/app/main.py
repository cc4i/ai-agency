"""FastAPI application entry point."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.agents import router as agents_router
from app.services.redis_client import redis_client

# Configure logging - both console and file
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "backend.log"

# Create formatters
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(getattr(logging, settings.log_level))

# File handler - write to backend/logs/backend.log
file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)  # Capture everything to file

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[console_handler, file_handler]
)

logger = logging.getLogger(__name__)
logger.info(f"📝 Logging to file: {log_file}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting AI Agency backend...")
    await redis_client.connect()
    logger.info("Redis connected successfully")

    # Auto-seed demo data if needed
    try:
        from scripts.seed_demo_data import CAMPAIGNS, create_demo_campaign
        
        # Check if default project exists
        default_project_id = "aura_smart_sneaker"
        brief = await redis_client.get_project_brief(default_project_id)
        
        if not brief:
            logger.info(f"Default project '{default_project_id}' not found. Auto-seeding...")
            await create_demo_campaign(CAMPAIGNS["aura"], "aura")
            logger.info("✓ Auto-seeding complete")
        else:
            logger.info(f"✓ Default project '{default_project_id}' exists")
            
    except Exception as e:
        logger.error(f"Auto-seeding failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down AI Agency backend...")
    await redis_client.disconnect()
    logger.info("Redis disconnected")


# Create FastAPI app
app = FastAPI(
    title="AI Agency",
    description="Multi-agent creative campaign system",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS - Allow all origins for testing
# Note: allow_credentials must be False when allow_origins is ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # Cannot be True with wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(agents_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AI Agency API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test Redis connection
        await redis_client.client.ping()  # type: ignore
        redis_status = "connected"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_status = "disconnected"

    return {
        "status": "healthy",
        "redis": redis_status,
        "environment": settings.environment,
    }


@app.get("/api/config/models-voices")
async def get_models_and_voices():
    """
    Get available Gemini Live models and voices.

    Returns configuration options for the frontend selection UI.
    Voices are organized by personality groups for easier selection.
    """
    from app.voice_config import AVAILABLE_MODELS, VOICE_GROUPS, DEFAULT_MODEL, DEFAULT_VOICE

    return {
        "models": AVAILABLE_MODELS,
        "voiceGroups": VOICE_GROUPS,
        "defaults": {
            "model": DEFAULT_MODEL,
            "voice": DEFAULT_VOICE
        }
    }


@app.websocket("/ws/adk/{session_id}/{project_id}")
async def gemini_live_adk_websocket(
    websocket: WebSocket,
    session_id: str,
    project_id: str,
    model: str = None,  # Query parameter for model selection
    voice: str = None,  # Query parameter for voice selection
):
    """
    WebSocket endpoint for Gemini Live streaming conversation (ADK Implementation).

    This is the simplified ADK-based implementation that replaces 2,219 lines
    of manual WebSocket handling with ~536 lines using Google ADK abstractions.

    Benefits over manual implementation:
    - Automatic tool execution (no manual routing)
    - Built-in session resumption
    - Simplified audio streaming with LiveRequestQueue
    - Automatic transcription handling

    Args:
        websocket: FastAPI WebSocket connection
        session_id: Unique session identifier
        project_id: Project identifier
        model: Gemini Live model ID (query param, optional - defaults to stable)
        voice: Voice name for TTS (query param, optional - defaults to Kore)
    """
    from app.services.gemini_live_adk import GeminiLiveADKConnection
    from app.voice_config import (
        is_valid_model,
        is_valid_voice,
        DEFAULT_MODEL,
        DEFAULT_VOICE,
        get_all_models,
        get_all_voices
    )

    # Use defaults if not provided
    model = model or DEFAULT_MODEL
    voice = voice or DEFAULT_VOICE

    logger.info(
        f"[ADK] WebSocket connection request: session={session_id}, "
        f"project={project_id}, model={model}, voice={voice}"
    )

    # Validate model
    if not is_valid_model(model):
        logger.error(f"[ADK] Invalid model: {model}. Valid options: {get_all_models()}")
        await websocket.close(code=1008, reason=f"Invalid model: {model}")
        return

    # Validate voice
    if not is_valid_voice(voice):
        logger.error(f"[ADK] Invalid voice: {voice}. Valid options: {get_all_voices()}")
        await websocket.close(code=1008, reason=f"Invalid voice: {voice}")
        return

    # CRITICAL: Accept WebSocket IMMEDIATELY to prevent browser timeout
    # Heavy initialization (Agent creation) will happen after accept
    await websocket.accept()
    logger.info(f"[ADK] ✓ WebSocket accepted for session: {session_id}")

    # Send initialization status to frontend to keep connection alive
    try:
        await websocket.send_text(json.dumps({
            "type": "status",
            "message": "Initializing AI agent..."
        }))
    except Exception as e:
        logger.warning(f"[ADK] Failed to send initialization status: {e}")

    # Create ADK-based Gemini Live connection with user-selected settings
    # This is a heavy operation (creates Agent, Runner, Memory Bank)
    # Wrap with timeout to prevent indefinite hangs on Cloud Run cold starts
    logger.info(f"[ADK] Creating GeminiLiveADKConnection (this may take a few seconds)...")
    try:
        async with asyncio.timeout(30):  # 30 second max for initialization
            gemini_connection = GeminiLiveADKConnection(
                session_id=session_id,
                project_id=project_id,
                model_name=model,  # User-selected model
                voice_name=voice,  # User-selected voice
            )
        logger.info(f"[ADK] ✓ GeminiLiveADKConnection created successfully")
    except asyncio.TimeoutError:
        logger.error(f"[ADK] ❌ Initialization timed out after 30 seconds for session {session_id}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "AI initialization timed out. Please try again."
            }))
            await websocket.close(code=1011, reason="Initialization timeout")
        except Exception as e:
            logger.warning(f"[ADK] Failed to send timeout error to client: {e}")
        return
    except Exception as e:
        logger.error(f"[ADK] ❌ Initialization failed for session {session_id}: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason=f"Initialization failed: {str(e)}")
        except:
            pass
        return

    # Send ready status to frontend
    try:
        await websocket.send_text(json.dumps({
            "type": "status",
            "message": "AI agent ready"
        }))
    except Exception as e:
        logger.warning(f"[ADK] Failed to send ready status: {e}")

    try:
        # Establish connection: Frontend → Backend → ADK → Gemini Live
        logger.info(f"[ADK] Passing accepted WebSocket to connect() for session {session_id}")
        await gemini_connection.connect(websocket)

    except WebSocketDisconnect:
        logger.info(f"[ADK] WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"[ADK] WebSocket error for session {session_id}: {e}")
        try:
            await websocket.close(code=1011, reason=f"Connection error: {str(e)}")
        except:
            pass
    finally:
        # Clean up
        await gemini_connection.disconnect()


@app.websocket("/ws/project/{project_id}")
async def project_websocket(websocket: WebSocket, project_id: str):
    """
    WebSocket endpoint for project brief updates.

    This endpoint streams real-time project brief updates to the frontend.

    Args:
        websocket: FastAPI WebSocket connection
        project_id: Project identifier
    """
    await websocket.accept()
    logger.info(f"Project WebSocket connection established: {project_id}")

    try:
        # Subscribe to project events
        pubsub = await redis_client.subscribe_to_events(["brief_updated", "agent_completed"])

        async for message in pubsub.listen():
            if message["type"] == "message":
                # Forward event to frontend
                await websocket.send_text(message["data"])

    except WebSocketDisconnect:
        logger.info(f"Project WebSocket disconnected: {project_id}")
    except Exception as e:
        logger.error(f"Project WebSocket error for {project_id}: {e}")
        await websocket.close(code=1011, reason="Internal server error")


# API Routes (to be implemented in Phase 2+)


@app.post("/api/sessions")
async def create_session():
    """Create a new session."""
    import uuid
    from datetime import datetime

    session_id = f"session_{uuid.uuid4().hex[:12]}"

    # Store session in Redis
    session_data = {
        "session_id": session_id,
        "status": "created",
        "created_at": datetime.utcnow().isoformat(),
    }

    await redis_client.client.set(
        f"session:{session_id}",
        json.dumps(session_data),
        ex=86400  # 24 hour expiry
    )

    logger.info(f"Created session: {session_id}")
    return session_data


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    import json

    session_json = await redis_client.client.get(f"session:{session_id}")

    if not session_json:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")

    return json.loads(session_json)


@app.post("/api/projects")
async def create_project():
    """Create a new project."""
    import uuid
    from datetime import datetime

    project_id = f"project_{uuid.uuid4().hex[:12]}"

    # Create default project brief
    from app.models.brief import ProjectBrief

    brief = ProjectBrief(
        project_id=project_id,
        session_id="default",
        product_name="",
        product_category="",
        theme="",
        key_features=[],
        brand_tone="",
        target_market="",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    # Store in Redis
    await redis_client.save_project_brief(brief)

    logger.info(f"Created project: {project_id}")
    return {"project_id": project_id, "status": "created"}


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Get project details."""
    brief = await redis_client.get_project_brief(project_id)

    if not brief:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Project not found")

    return brief.model_dump()


@app.post("/api/projects/{project_id}/reference-images")
async def add_reference_image(project_id: str, image: dict):
    """Add reference image to project brief (max 1)."""
    from fastapi import HTTPException
    from datetime import datetime

    # Get current brief
    brief = await redis_client.get_project_brief(project_id)
    if not brief:
        raise HTTPException(status_code=404, detail="Project not found")

    # Enforce max 1 reference image
    if len(brief.reference_images) >= 1:
        raise HTTPException(status_code=400, detail="Only 1 reference image allowed. Delete the existing one first.")

    # Add image to reference_images list
    from app.models.assets import ImageAsset
    image_asset = ImageAsset(**image)
    brief.reference_images.append(image_asset)
    brief.updated_at = datetime.utcnow()

    # Save to Redis
    await redis_client.save_project_brief(brief)

    # Broadcast WebSocket event (note: frontend expects "brief_update" not "brief_updated")
    await redis_client.client.publish(
        f"project:{project_id}:events",
        json.dumps({
            "type": "brief_update",
            "data": {
                "brief": brief.model_dump(mode="json"),
                "changed_fields": ["reference_images"]
            }
        })
    )

    logger.info(f"Added reference image {image_asset.asset_id} to project {project_id}")
    return {"status": "success", "image": image_asset.model_dump()}


@app.delete("/api/projects/{project_id}/reference-images/{asset_id}")
async def remove_reference_image(project_id: str, asset_id: str):
    """Remove reference image from project brief."""
    from fastapi import HTTPException
    from datetime import datetime

    # Get current brief
    brief = await redis_client.get_project_brief(project_id)
    if not brief:
        raise HTTPException(status_code=404, detail="Project not found")

    # Remove image with matching asset_id
    original_count = len(brief.reference_images)
    brief.reference_images = [
        img for img in brief.reference_images
        if img.asset_id != asset_id
    ]

    if len(brief.reference_images) == original_count:
        raise HTTPException(status_code=404, detail="Reference image not found")

    brief.updated_at = datetime.utcnow()

    # Save to Redis
    await redis_client.save_project_brief(brief)

    # Broadcast WebSocket event (note: frontend expects "brief_update" not "brief_updated")
    await redis_client.client.publish(
        f"project:{project_id}:events",
        json.dumps({
            "type": "brief_update",
            "data": {
                "brief": brief.model_dump(mode="json"),
                "changed_fields": ["reference_images"]
            }
        })
    )

    logger.info(f"Removed reference image {asset_id} from project {project_id}")
    return {"status": "success", "deleted": asset_id}


@app.post("/api/assets/upload")
async def upload_asset(file: UploadFile = File(...)):
    """Upload reference image and convert to base64 data URI."""
    from fastapi import HTTPException
    import base64
    import uuid
    from datetime import datetime

    # Validate file type
    allowed_types = ['image/png', 'image/jpeg', 'image/jpg']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only PNG/JPG images allowed")

    # Read and validate size (5MB limit)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    # Convert to base64 data URI
    base64_data = base64.b64encode(contents).decode('utf-8')
    data_uri = f"data:{file.content_type};base64,{base64_data}"

    # Return ImageAsset schema
    return {
        "asset_id": f"ref_{uuid.uuid4().hex[:12]}",
        "url": data_uri,
        "description": file.filename,
        "generation_params": {
            "uploaded_at": datetime.utcnow().isoformat()
        }
    }


@app.get("/api/assets/videos/{asset_id}")
async def get_video_asset(asset_id: str):
    """
    Serve video asset from private GCS bucket.

    Args:
        asset_id: Video asset ID (e.g., vid_abc123)

    Returns:
        Video file streamed from GCS
    """
    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse
    from google.cloud import storage

    try:
        # Initialize GCS client
        client = storage.Client(project=settings.google_cloud_project)
        bucket = client.bucket(settings.gcs_bucket_name)
        blob_name = f"videos/{asset_id}.mp4"
        blob = bucket.blob(blob_name)

        # Check if blob exists
        if not blob.exists():
            logger.error(f"Video asset not found: {blob_name}")
            raise HTTPException(status_code=404, detail="Video not found")

        # Stream video from GCS
        logger.info(f"Serving video asset: {blob_name}")
        video_bytes = blob.download_as_bytes()

        return StreamingResponse(
            iter([video_bytes]),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"inline; filename={asset_id}.mp4",
                "Cache-Control": "public, max-age=3600"
            }
        )

    except Exception as e:
        logger.error(f"Error serving video asset {asset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve video")


@app.get("/api/assets/audio/{asset_id}")
async def get_audio_asset(asset_id: str):
    """
    Serve audio asset from private GCS bucket.

    Args:
        asset_id: Audio asset ID (e.g., audio_abc123)

    Returns:
        Audio file streamed from GCS
    """
    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse
    from google.cloud import storage

    try:
        # Initialize GCS client
        client = storage.Client(project=settings.google_cloud_project)
        bucket = client.bucket(settings.gcs_bucket_name)
        blob_name = f"audio/{asset_id}.mp3"
        blob = bucket.blob(blob_name)

        # Check if blob exists
        if not blob.exists():
            logger.error(f"Audio asset not found: {blob_name}")
            raise HTTPException(status_code=404, detail="Audio not found")

        # Stream audio from GCS
        logger.info(f"Serving audio asset: {blob_name}")
        audio_bytes = blob.download_as_bytes()

        return StreamingResponse(
            iter([audio_bytes]),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"inline; filename={asset_id}.mp3",
                "Cache-Control": "public, max-age=3600"
            }
        )

    except Exception as e:
        logger.error(f"Error serving audio asset {asset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audio")


@app.get("/api/assets/images/{asset_id}")
async def get_image_asset(asset_id: str):
    """
    Serve image asset from private GCS bucket.

    Args:
        asset_id: Image asset ID (e.g., img_abc123)

    Returns:
        Image file streamed from GCS
    """
    from fastapi import HTTPException
    from fastapi.responses import Response
    from google.cloud import storage

    try:
        # Initialize GCS client
        client = storage.Client(project=settings.google_cloud_project)
        bucket = client.bucket(settings.gcs_bucket_name)

        # Try both PNG and JPG extensions
        blob = None
        content_type = None
        for ext, mime in [("png", "image/png"), ("jpg", "image/jpeg")]:
            blob_name = f"images/{asset_id}.{ext}"
            test_blob = bucket.blob(blob_name)
            if test_blob.exists():
                blob = test_blob
                content_type = mime
                break

        if not blob:
            logger.error(f"Image asset not found: images/{asset_id}.*")
            raise HTTPException(status_code=404, detail="Image not found")

        # Stream image from GCS
        logger.info(f"Serving image asset: {blob.name}")
        image_bytes = blob.download_as_bytes()

        return Response(
            content=image_bytes,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=3600"
            }
        )

    except Exception as e:
        logger.error(f"Error serving image asset {asset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve image")


@app.get("/api/assets/html/{asset_id}")
async def get_html_asset(asset_id: str):
    """
    Serve HTML asset from private GCS bucket.

    Args:
        asset_id: HTML asset ID (e.g., landing_abc123)

    Returns:
        HTML file streamed from GCS
    """
    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse
    from google.cloud import storage

    try:
        # Initialize GCS client
        client = storage.Client(project=settings.google_cloud_project)
        bucket = client.bucket(settings.gcs_bucket_name)
        blob_name = f"landing-pages/{asset_id}.html"
        blob = bucket.blob(blob_name)

        # Check if blob exists
        if not blob.exists():
            logger.error(f"HTML asset not found: {blob_name}")
            raise HTTPException(status_code=404, detail="HTML page not found")

        # Stream HTML from GCS
        logger.info(f"Serving HTML asset: {blob_name}")
        html_bytes = blob.download_as_bytes()

        return StreamingResponse(
            iter([html_bytes]),
            media_type="text/html",
            headers={
                "Content-Disposition": "inline",
                "Cache-Control": "public, max-age=3600"
            }
        )

    except Exception as e:
        logger.error(f"Error serving HTML asset {asset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve HTML page")


# Test Endpoints for Agent System
@app.post("/api/test/trigger-strategy")
async def test_trigger_strategy(project_id: str = "aura_smart_sneaker"):
    """Test endpoint to manually trigger Strategy Agent."""
    from app.services.orchestration import AgentOrchestrator

    logger.info(f"TEST: Manually triggering Strategy Agent for project: {project_id}")

    orchestrator = AgentOrchestrator()

    task = {
        "task_id": "test_strategy",
        "product_name": "Aura Smart Sneaker",
        "product_category": "footwear",
        "theme": "futuristic urban athlete",
        "key_features": ["glowing sole", "smart tracking", "adaptive cushioning"],
        "brand_tone": "innovative, energetic, tech-forward",
        "target_market": "Urban athletes aged 18-35"
    }

    try:
        result = await orchestrator.execute_agent(
            "strategy",
            task=task,
            project_id=project_id,
            with_critique=False
        )

        logger.info(f"TEST: Strategy Agent completed successfully")
        return {
            "status": "success",
            "agent": "strategy",
            "result": result
        }
    except Exception as e:
        logger.error(f"TEST: Strategy Agent failed: {e}")
        return {
            "status": "error",
            "agent": "strategy",
            "error": str(e)
        }


@app.post("/api/test/trigger-art-director")
async def test_trigger_art_director(project_id: str = "aura_smart_sneaker"):
    """Test endpoint to manually trigger Art Director Agent."""
    from app.services.orchestration import AgentOrchestrator

    logger.info(f"TEST: Manually triggering Art Director Agent for project: {project_id}")

    orchestrator = AgentOrchestrator()

    task = {
        "task_id": "test_art_director",
        "product_name": "Aura Smart Sneaker",
        "product_category": "footwear",
        "slogan": "Step Into Your Aura",
        "theme": "futuristic urban athlete",
        "key_features": ["glowing sole", "smart tracking", "adaptive cushioning"],
        "brand_tone": "innovative, energetic, tech-forward"
    }

    try:
        result = await orchestrator.execute_agent(
            "art_director",
            task=task,
            project_id=project_id,
            with_critique=False
        )

        logger.info(f"TEST: Art Director Agent completed successfully")
        return {
            "status": "success",
            "agent": "art_director",
            "result": result
        }
    except Exception as e:
        logger.error(f"TEST: Art Director Agent failed: {e}")
        return {
            "status": "error",
            "agent": "art_director",
            "error": str(e)
        }


@app.get("/api/test/list-agents")
async def test_list_agents():
    """Test endpoint to list all registered agents."""
    from app.services.agent_registry import agent_registry

    agents = agent_registry.list_agents()

    return {
        "status": "success",
        "agents": agents,
        "count": len(agents)
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
