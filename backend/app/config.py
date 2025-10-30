"""Application configuration management using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Google AI API Configuration
    google_application_credentials: str = ""
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    gemini_api_key: str = ""

    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # Celery Configuration
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Application Configuration
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Audio Configuration
    audio_sample_rate: int = 16000
    audio_encoding: str = "pcm_s16le"
    save_audio_debug: bool = False  # Save audio chunks to file for debugging
    audio_debug_dir: str = "/tmp/audio_debug"  # Directory to save debug audio files

    # Google Cloud Storage
    gcs_bucket_name: str = "ai-agency-demo"

    # Gemini Live WebSocket (Vertex AI)
    gemini_live_ws_url: str = (
        "wss://us-central1-aiplatform.googleapis.com/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent"
    )

    @property
    def redis_url(self) -> str:
        """Construct Redis URL from components."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


# Global settings instance
settings = Settings()
