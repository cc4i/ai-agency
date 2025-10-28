"""FastAPI application entry point."""

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.redis_client import redis_client

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting AI Agency backend...")
    await redis_client.connect()
    logger.info("Redis connected successfully")

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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.websocket("/ws/{session_id}/{project_id}")
async def gemini_live_websocket(websocket: WebSocket, session_id: str, project_id: str):
    """
    WebSocket endpoint for Gemini Live streaming conversation.

    This endpoint handles:
    - Bidirectional audio streaming (user <-> Gemini Live)
    - Text transcript streaming (simultaneous with audio)
    - Project brief updates
    - Agent status updates
    - Asset delivery events

    Args:
        websocket: FastAPI WebSocket connection
        session_id: Unique session identifier
        project_id: Project identifier
    """
    from app.services.gemini_live import GeminiLiveConnection

    logger.info(f"WebSocket connection request for session: {session_id}, project: {project_id}")

    # Create Gemini Live connection
    gemini_connection = GeminiLiveConnection(
        session_id=session_id,
        voice_name="Aoede"  # Professional female voice
    )

    try:
        # Establish connection: Frontend → Backend → Gemini Live
        await gemini_connection.connect(websocket)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
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


@app.post("/api/assets/upload")
async def upload_asset():
    """Upload an asset (sketch, image, etc.)."""
    import uuid

    # For now, return placeholder
    # In production, this would upload to Google Cloud Storage
    asset_id = f"asset_{uuid.uuid4().hex[:12]}"

    return {
        "asset_id": asset_id,
        "url": f"https://storage.googleapis.com/{settings.gcs_bucket_name}/{asset_id}",
        "status": "uploaded"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
