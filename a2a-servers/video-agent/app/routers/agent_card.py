"""Agent Card endpoint for A2A discovery.

Exposes the Agent Card at /.well-known/agent.json per A2A specification.
"""

from fastapi import APIRouter

from app.config import settings
from app.models.a2a import (
    AgentCapabilities,
    AgentCard,
    AgentProvider,
    AgentSkill,
    SecurityScheme,
)

router = APIRouter()


@router.get("/.well-known/agent.json", response_model=AgentCard)
async def get_agent_card() -> AgentCard:
    """
    Return the Agent Card for this A2A server.

    The Agent Card is the discovery mechanism for A2A protocol.
    It describes the agent's capabilities, skills, and authentication requirements.
    """
    return AgentCard(
        id=settings.agent_id,
        name=settings.agent_name,
        description=settings.agent_description,
        protocolVersion="1.0",
        url=f"{settings.base_url}/a2a",
        provider=AgentProvider(
            name=settings.provider_name,
            url=settings.provider_url,
        ),
        capabilities=AgentCapabilities(
            streaming=True,
            pushNotifications=False,
        ),
        skills=[
            AgentSkill(
                id="video_generation",
                name="Video Generation",
                description=(
                    "Creates 15-second social media videos from text prompts "
                    "and brand guidelines"
                ),
                inputModes=["text/plain", "application/json"],
                outputModes=["video/mp4", "video/webm"],
                examples=[
                    {
                        "input": "Create a 15s video showcasing sneakers with Tokyo neon aesthetic",
                        "output": "video/mp4 artifact with neon-lit urban footage",
                    }
                ],
            )
        ],
        securitySchemes={
            "bearer": SecurityScheme(
                type="http",
                scheme="bearer",
                description="API key authentication",
            )
        },
        security=["bearer"],
        defaultInputModes=["text/plain", "application/json"],
        defaultOutputModes=["video/mp4"],
    )
