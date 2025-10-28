"""FastAPI application entry point."""

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


@app.websocket("/ws/live/{session_id}")
async def gemini_live_websocket(websocket: WebSocket, session_id: str):
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
    """
    await websocket.accept()
    logger.info(f"WebSocket connection established for session: {session_id}")

    try:
        # TODO: Initialize Gemini Live connection
        # TODO: Set up audio streaming pipeline
        # TODO: Set up event listeners for agent updates

        while True:
            # Receive message from frontend
            data = await websocket.receive_json()

            # Handle different message types
            message_type = data.get("type")

            if message_type == "audio_input":
                # User audio chunk
                audio_data = data.get("data")
                # TODO: Forward to Gemini Live
                logger.debug(f"Received audio chunk for session {session_id}")

            elif message_type == "text_input":
                # Text message (fallback mode)
                text = data.get("text")
                logger.info(f"Received text from user: {text}")
                # TODO: Process text input

            elif message_type == "ping":
                # Heartbeat
                await websocket.send_json({"type": "pong"})

            else:
                logger.warning(f"Unknown message type: {message_type}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        await websocket.close(code=1011, reason="Internal server error")


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
    # TODO: Implement session creation
    return {"session_id": "temp_session_id", "status": "created"}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    # TODO: Implement session retrieval
    return {"session_id": session_id, "status": "active"}


@app.post("/api/projects")
async def create_project():
    """Create a new project."""
    # TODO: Implement project creation
    return {"project_id": "temp_project_id", "status": "created"}


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Get project details."""
    # TODO: Implement project retrieval
    return {"project_id": project_id, "status": "planning"}


@app.post("/api/assets/upload")
async def upload_asset():
    """Upload an asset (sketch, image, etc.)."""
    # TODO: Implement asset upload to GCS
    return {"asset_id": "temp_asset_id", "url": "gs://bucket/asset.png"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
