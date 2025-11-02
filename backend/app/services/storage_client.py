"""Google Cloud Storage client for asset uploads.

Handles uploading generated assets (videos, audio, images) to GCS
and managing signed URLs for secure access.
"""

import logging
import uuid
from datetime import timedelta
from typing import Optional

from google.cloud import storage

from app.config import settings

logger = logging.getLogger(__name__)


class StorageClient:
    """Client for Google Cloud Storage operations."""

    def __init__(self):
        """Initialize GCS client."""
        self.bucket_name = settings.gcs_bucket_name
        self.client: Optional[storage.Client] = None

    def _get_client(self) -> storage.Client:
        """Get or create GCS client."""
        if not self.client:
            self.client = storage.Client(project=settings.google_cloud_project)
        return self.client

    async def upload_video(
        self,
        video_data: bytes,
        asset_id: Optional[str] = None,
        content_type: str = "video/mp4",
    ) -> tuple[str, str]:
        """
        Upload video to Google Cloud Storage.

        Args:
            video_data: Video bytes
            asset_id: Optional asset ID (generates if not provided)
            content_type: MIME type

        Returns:
            Tuple of (asset_id, public_url)
        """
        if not asset_id:
            asset_id = f"vid_{uuid.uuid4().hex[:12]}"

        try:
            client = self._get_client()
            bucket = client.bucket(self.bucket_name)
            blob_name = f"videos/{asset_id}.mp4"
            blob = bucket.blob(blob_name)

            logger.info(f"Uploading video to GCS: gs://{self.bucket_name}/{blob_name}")
            logger.info(f"Video size: {len(video_data)} bytes")

            # Upload video
            blob.upload_from_string(video_data, content_type=content_type)

            # Return backend API URL instead of GCS public URL
            # Frontend will access via: /api/assets/videos/{asset_id}
            url = f"{settings.backend_url}/api/assets/videos/{asset_id}"

            logger.info(f"Video uploaded successfully to GCS: gs://{self.bucket_name}/{blob_name}")
            logger.info(f"Video accessible via: {url}")

            return asset_id, url

        except Exception as e:
            logger.error(f"GCS upload error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def upload_audio(
        self,
        audio_data: bytes,
        asset_id: Optional[str] = None,
        content_type: str = "audio/mpeg",
    ) -> tuple[str, str]:
        """
        Upload audio to Google Cloud Storage.

        Args:
            audio_data: Audio bytes
            asset_id: Optional asset ID
            content_type: MIME type

        Returns:
            Tuple of (asset_id, public_url)
        """
        if not asset_id:
            asset_id = f"audio_{uuid.uuid4().hex[:12]}"

        try:
            client = self._get_client()
            bucket = client.bucket(self.bucket_name)
            blob_name = f"audio/{asset_id}.mp3"
            blob = bucket.blob(blob_name)

            logger.info(f"Uploading audio to GCS: gs://{self.bucket_name}/{blob_name}")

            # Upload audio
            blob.upload_from_string(audio_data, content_type=content_type)

            # Return backend API URL instead of GCS public URL
            url = f"{settings.backend_url}/api/assets/audio/{asset_id}"

            logger.info(f"Audio uploaded successfully to GCS: gs://{self.bucket_name}/{blob_name}")
            logger.info(f"Audio accessible via: {url}")

            return asset_id, url

        except Exception as e:
            logger.error(f"GCS audio upload error: {e}")
            raise

    async def upload_image(
        self,
        image_data: bytes,
        asset_id: Optional[str] = None,
        content_type: str = "image/png",
    ) -> tuple[str, str]:
        """
        Upload image to Google Cloud Storage.

        Args:
            image_data: Image bytes
            asset_id: Optional asset ID
            content_type: MIME type

        Returns:
            Tuple of (asset_id, public_url)
        """
        if not asset_id:
            asset_id = f"img_{uuid.uuid4().hex[:12]}"

        try:
            client = self._get_client()
            bucket = client.bucket(self.bucket_name)

            # Determine extension from content type
            ext = "png" if "png" in content_type else "jpg"
            blob_name = f"images/{asset_id}.{ext}"
            blob = bucket.blob(blob_name)

            logger.info(f"Uploading image to GCS: gs://{self.bucket_name}/{blob_name}")

            # Upload image
            blob.upload_from_string(image_data, content_type=content_type)

            # Return backend API URL instead of GCS public URL
            url = f"{settings.backend_url}/api/assets/images/{asset_id}"

            logger.info(f"Image uploaded successfully to GCS: gs://{self.bucket_name}/{blob_name}")
            logger.info(f"Image accessible via: {url}")

            return asset_id, url

        except Exception as e:
            logger.error(f"GCS image upload error: {e}")
            raise


# Global storage client instance
storage_client = StorageClient()
