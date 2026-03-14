"""
Cloud Storage Service
Lightweight wrapper for uploading media/report artifacts to GCS.
"""

import asyncio
import logging
from datetime import datetime

from config import settings
from google.cloud import storage

logger = logging.getLogger("maintenance-eye.storage")


class StorageService:
    """Uploads binary/json payloads to a configured GCS bucket."""

    def __init__(self):
        self.bucket_name = (settings.GCS_BUCKET or "").strip()
        self.project_id = settings.GCP_PROJECT_ID
        self._client: storage.Client | None = None
        self._bucket = None

    @property
    def enabled(self) -> bool:
        return bool(self.bucket_name)

    def _get_bucket(self):
        if not self.enabled:
            return None
        if self._bucket is None:
            self._client = storage.Client(project=self.project_id)
            self._bucket = self._client.bucket(self.bucket_name)
        return self._bucket

    async def upload_bytes(
        self,
        data: bytes,
        object_path: str,
        content_type: str,
    ) -> str | None:
        """Upload raw bytes to GCS and return gs:// URI."""
        if not self.enabled:
            return None

        def _upload() -> str:
            bucket = self._get_bucket()
            blob = bucket.blob(object_path)
            blob.upload_from_string(data, content_type=content_type)
            return f"gs://{self.bucket_name}/{object_path}"

        try:
            return await asyncio.to_thread(_upload)
        except Exception as exc:
            logger.debug(f"GCS upload skipped for {object_path}: {exc}")
            return None

    async def upload_json(self, payload: dict, object_path: str) -> str | None:
        """Upload JSON document to GCS and return gs:// URI."""
        import json

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return await self.upload_bytes(
            data=data,
            object_path=object_path,
            content_type="application/json",
        )

    def build_report_object_path(self, report_id: str) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d")
        return f"reports/{ts}/{report_id}.json"


_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
