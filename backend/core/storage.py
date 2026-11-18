"""Private local/S3 storage foundation; M1 deliberately exposes no upload endpoint."""

from pathlib import PurePosixPath
from uuid import UUID, uuid4


def attachment_key(tenant_id: UUID, site_id: UUID, filename: str) -> str:
    extension = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    if extension not in {".pdf", ".jpg", ".jpeg", ".png", ".wav", ".mp3"}:
        raise ValueError("Unsupported attachment extension")
    return f"tenants/{UUID(str(tenant_id))}/sites/{UUID(str(site_id))}/{uuid4()}{extension}"
