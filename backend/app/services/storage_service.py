import os
import shutil
from typing import Optional

from app.config import settings


class StorageService:
    """
    File storage abstraction. Uses the local filesystem by default and S3 when
    STORAGE_BACKEND is set to "s3".
    """

    def __init__(self):
        self.backend = settings.STORAGE_BACKEND
        self.base_path = settings.LOCAL_STORAGE_PATH
        os.makedirs(self.base_path, exist_ok=True)

    def path_for(self, *parts: str) -> str:
        """Build a path inside the storage root, creating parent directories."""
        full = os.path.join(self.base_path, *parts)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        return full

    def save(self, source_path: str, destination: str) -> str:
        """Store a local file and return its final location or URL."""
        if self.backend == "s3":
            return self._upload_to_s3(source_path, destination)

        target = self.path_for(destination)
        if os.path.abspath(source_path) != os.path.abspath(target):
            shutil.copy2(source_path, target)
        return target

    def delete(self, path: str) -> bool:
        """Remove a stored file. Returns True when something was deleted."""
        if self.backend == "s3":
            return self._delete_from_s3(path)

        if path and os.path.exists(path):
            os.remove(path)
            return True
        return False

    def _client(self):
        import boto3

        return boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

    def _upload_to_s3(self, source_path: str, key: str) -> str:
        self._client().upload_file(source_path, settings.S3_BUCKET_NAME, key)
        return "https://%s.s3.%s.amazonaws.com/%s" % (
            settings.S3_BUCKET_NAME,
            settings.AWS_REGION,
            key,
        )

    def _delete_from_s3(self, key: str) -> bool:
        self._client().delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        return True

    def presigned_url(self, key: str, expires_in: int = 3600) -> Optional[str]:
        """Temporary download URL. Only meaningful for the S3 backend."""
        if self.backend != "s3":
            return None
        return self._client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": key},
            ExpiresIn=expires_in,
        )
