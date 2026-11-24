"""Thin wrapper over azure-storage-blob so business logic can be tested with a fake service."""

from __future__ import annotations

import json
from typing import Any

from azure.core import MatchConditions
from azure.core.exceptions import HttpResponseError, ResourceExistsError, ResourceNotFoundError

PRECONDITION_FAILED = 412


class BlobStore:
    """Entra-authenticated blob access. ``service`` is a BlobServiceClient (or a test double)."""

    def __init__(self, service: Any) -> None:
        self._service = service

    @classmethod
    def from_account_url(cls, account_url: str) -> BlobStore:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        return cls(BlobServiceClient(account_url, credential=DefaultAzureCredential()))

    def _blob(self, container: str, name: str) -> Any:
        return self._service.get_blob_client(container, name)

    def exists(self, container: str, name: str) -> bool:
        return bool(self._blob(container, name).exists())

    def read_text(self, container: str, name: str) -> str:
        return self._blob(container, name).download_blob().readall().decode("utf-8")

    def write_text(self, container: str, name: str, text: str, overwrite: bool = True) -> bool:
        """Upload text. Returns False only when overwrite=False and the blob already exists."""
        try:
            self._blob(container, name).upload_blob(text.encode("utf-8"), overwrite=overwrite)
        except ResourceExistsError:
            return False
        return True

    def list_names(self, container: str, prefix: str = "") -> list[str]:
        client = self._service.get_container_client(container)
        return sorted(b.name for b in client.list_blobs(name_starts_with=prefix))

    def read_json_with_etag(self, container: str, name: str) -> tuple[dict | None, str | None]:
        """Return (data, etag), or (None, None) when the blob does not exist."""
        try:
            downloader = self._blob(container, name).download_blob()
        except ResourceNotFoundError:
            return None, None
        data = json.loads(downloader.readall().decode("utf-8"))
        return data, downloader.properties.etag

    def write_json_if_match(self, container: str, name: str, data: dict, etag: str | None) -> bool:
        """Optimistic write. ``etag=None`` means create only if absent.

        Returns False when another writer got there first (HTTP 409/412).
        """
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        blob = self._blob(container, name)
        try:
            if etag is None:
                blob.upload_blob(body, overwrite=False)
            else:
                blob.upload_blob(
                    body, overwrite=True, etag=etag, match_condition=MatchConditions.IfNotModified
                )
        except ResourceExistsError:
            return False
        except HttpResponseError as exc:
            if exc.status_code == PRECONDITION_FAILED:
                return False
            raise
        return True
