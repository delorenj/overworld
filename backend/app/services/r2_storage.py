"""Cloudflare R2 storage service for file uploads."""

import asyncio
from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO
from typing import BinaryIO
from uuid import UUID

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from app.core.config import settings


class R2StorageError(Exception):
    """Raised when R2 storage operation fails."""

    pass


class R2StorageService:
    """Service for uploading files to Cloudflare R2 storage."""

    def __init__(self):
        """Initialize R2 storage service with boto3 client."""
        self._client = None

    @property
    def client(self):
        """Get or create boto3 S3 client for R2."""
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.R2_ENDPOINT_URL,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4"),
                region_name="auto",  # R2 uses 'auto' region
            )
        return self._client

    def _generate_r2_path(
        self, user_id: UUID, filename: str, bucket_type: str = "uploads"
    ) -> str:
        """
        Generate R2 path for uploaded file.

        Path format: /{bucket_type}/{user_id}/{timestamp}/{filename}

        Args:
            user_id: User ID
            filename: Original filename
            bucket_type: Type of bucket (uploads, maps, themes, exports)

        Returns:
            R2 path string
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"{bucket_type}/{user_id}/{timestamp}/{filename}"

    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        user_id: int,
        mime_type: str,
        max_retries: int = 3,
    ) -> tuple[str, str]:
        """
        Upload file to R2 storage with retry logic.

        Args:
            file_content: File content as bytes
            filename: Original filename
            user_id: User ID (integer)
            mime_type: MIME type of the file
            max_retries: Maximum number of retry attempts

        Returns:
            Tuple of (r2_path, r2_url)

        Raises:
            R2StorageError: If upload fails after all retries
        """
        bucket_name = settings.R2_BUCKET_UPLOADS
        r2_path = self._generate_r2_path(user_id, filename, "uploads")

        # Try to upload with retries
        last_error = None
        for attempt in range(max_retries):
            try:
                # Create fresh BytesIO for each retry attempt
                file_obj = BytesIO(file_content)

                # Upload to R2 using boto3
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.upload_fileobj(
                        file_obj,
                        bucket_name,
                        r2_path,
                        ExtraArgs={"ContentType": mime_type},
                    ),
                )

                # Generate pre-signed URL (1-hour expiry)
                r2_url = await self.generate_presigned_url(bucket_name, r2_path)

                return r2_path, r2_url

            except (ClientError, EndpointConnectionError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Final attempt failed
                    break

        # All retries failed
        raise R2StorageError(
            f"Failed to upload file to R2 after {max_retries} attempts: {str(last_error)}"
        )

    async def generate_presigned_url(
        self, bucket_name: str, r2_path: str, expiry_seconds: int = 3600
    ) -> str:
        """
        Generate pre-signed URL for temporary file access.

        Args:
            bucket_name: Name of the R2 bucket
            r2_path: Path to the file in R2
            expiry_seconds: URL expiry time in seconds (default: 1 hour)

        Returns:
            Pre-signed URL string

        Raises:
            R2StorageError: If URL generation fails
        """
        try:
            url = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket_name, "Key": r2_path},
                    ExpiresIn=expiry_seconds,
                ),
            )
            return url
        except ClientError as e:
            raise R2StorageError(f"Failed to generate pre-signed URL: {str(e)}")

    async def delete_file(self, bucket_name: str, r2_path: str) -> None:
        """
        Delete file from R2 storage.

        Args:
            bucket_name: Name of the R2 bucket
            r2_path: Path to the file in R2

        Raises:
            R2StorageError: If deletion fails
        """
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.delete_object(Bucket=bucket_name, Key=r2_path),
            )
        except ClientError as e:
            raise R2StorageError(f"Failed to delete file from R2: {str(e)}")


@lru_cache
def get_r2_service() -> R2StorageService:
    """
    Get R2 storage service instance (cached).

    Returns:
        R2StorageService instance
    """
    return R2StorageService()
