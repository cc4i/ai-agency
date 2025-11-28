"""Configuration settings for A2A Video Agent Server."""

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Server settings
    base_url: str = "http://localhost:8001"
    host: str = "0.0.0.0"
    port: int = 8001

    # Authentication
    api_key: str = "test_api_key_123"

    # CORS settings
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Agent metadata
    agent_id: str = "video_producer_a2a"
    agent_name: str = "Video Producer Agent"
    agent_description: str = (
        "A2A-compliant video generation agent. "
        "Creates 15-second social media videos from text prompts and brand guidelines."
    )
    provider_name: str = "AI Agency"
    provider_url: str = "https://ai-agency.example.com"

    # Task settings
    mock_processing_delay: float = 0.8  # Seconds between progress updates
    mock_video_url: str = "https://storage.example.com/videos/sample.mp4"


settings = Settings()
