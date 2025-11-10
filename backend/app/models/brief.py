"""Project Brief models for the AI Agency system."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.models.assets import (
    CampaignPlan,
    CustomerPersona,
    GenerationSnapshot,
    ImageAsset,
    ImageRefinementHistory,
)


class ProjectBrief(BaseModel):
    """
    Project Brief - User-visible living document that updates in real-time.

    This is the central data structure that tracks campaign state and is
    synchronized to the frontend via WebSocket events.
    """

    # Identifiers
    project_id: str
    session_id: str

    # Campaign basics (PRODUCT-AGNOSTIC)
    product_name: str
    product_category: str  # "footwear", "beverage", "electronics", etc.
    theme: str
    key_features: List[str]
    brand_tone: str  # "futuristic", "luxury", "playful", "edgy", etc.
    target_market: str
    initial_sketch_url: Optional[str] = None
    reference_images: List[ImageAsset] = []  # User-uploaded reference images for Art Director

    # Strategy outputs
    personas: List[CustomerPersona] = []
    slogans: List[str] = []
    selected_slogan: Optional[str] = None

    # Art outputs
    hero_images: List[ImageAsset] = []
    selected_image: Optional[ImageAsset] = None

    # Image refinement tracking (within current generation)
    image_refinement_history: Dict[str, ImageRefinementHistory] = {}  # {image_asset_id: history}

    # Generation tracking (NEW - production level)
    current_generation: int = 1  # Which generation we're on (1, 2, 3...)
    generation_history: List[GenerationSnapshot] = []  # Previous complete generations

    # Execution plan
    campaign_plan: Optional[CampaignPlan] = None
    plan_approved: bool = False

    # Asset tracking
    completed_assets: Dict[str, Any] = {}  # {agent_id: asset}

    # Metadata
    version: int = 1
    created_at: datetime
    updated_at: datetime
    status: str = "planning"  # planning, executing, completed

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class SessionState(BaseModel):
    """Session state stored in Redis."""

    session_id: str
    user_id: str
    created_at: datetime
    last_active: datetime
    status: str  # "active", "paused", "completed"

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class ConversationMessage(BaseModel):
    """Single message in conversation history."""

    role: str  # "user" or "assistant"
    text: str
    timestamp: datetime
    is_partial: bool = False  # For streaming text

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}
