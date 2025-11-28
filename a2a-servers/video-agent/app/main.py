"""A2A Video Producer Agent Server.

A standalone A2A-compliant video generation agent with SSE streaming support.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import a2a, a2a_stream, agent_card

app = FastAPI(
    title="A2A Video Producer Agent",
    description=(
        "A2A-compliant video generation agent with SSE streaming support. "
        "Creates 15-second social media videos from text prompts and brand guidelines."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agent_card.router, tags=["Agent Card"])
app.include_router(a2a.router, tags=["A2A JSON-RPC"])
app.include_router(a2a_stream.router, tags=["A2A Streaming"])


@app.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns:
        Health status and agent identifier
    """
    return {
        "status": "healthy",
        "agent": settings.agent_id,
        "version": "0.1.0",
    }


@app.get("/")
async def root() -> dict:
    """
    Root endpoint with basic info.

    Returns:
        Agent info and available endpoints
    """
    return {
        "name": settings.agent_name,
        "description": settings.agent_description,
        "agent_card": f"{settings.base_url}/.well-known/agent.json",
        "a2a_endpoint": f"{settings.base_url}/a2a",
        "a2a_stream_endpoint": f"{settings.base_url}/a2a/stream",
        "docs": f"{settings.base_url}/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
