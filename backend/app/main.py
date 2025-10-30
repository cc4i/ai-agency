"""FastAPI application entry point."""

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
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
    # Available voices: Puck, Charon (male), Kore, Aoede (female), Fenrir
    gemini_connection = GeminiLiveConnection(
        session_id=session_id,
        project_id=project_id,  # Pass project_id for agent integration
        voice_name="Kore"  # Female voice (alternative: "Aoede")
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
