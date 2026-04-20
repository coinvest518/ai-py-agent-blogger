"""Google Drive upload helper for generated videos.

Uses Composio GOOGLEDRIVE_* slugs via the shared Composio client. Uploads a local
MP4 (or any file), makes it public, and returns a direct-download link suitable
for embedding in upload-post payloads or blog email HTML.

Gracefully returns {"success": False, ...} when COMPOSIO_ENTITY_ID is unset
or any step fails — callers must fall back to local path only.
"""

import logging
import os
from pathlib import Path

from src.agent.core.config import COMPOSIO_ENTITY_ID
from src.agent.tools.composio_tools import get_composio_client, _execute_with_fallback

logger = logging.getLogger(__name__)

GDRIVE_FOLDER_ID = os.getenv("GDRIVE_VIDEO_FOLDER_ID")


def _direct_link(file_id: str) -> str:
    # Thumbnail endpoint streams actual image bytes for any public file.
    # The /uc?export=download path returns an HTML virus-scan page for
    # files >~100KB, which breaks Buffer/Pinterest image-dimension fetch.
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w2000"


def _web_link(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view"


def upload_and_share(path: str | Path, mime_type: str = "video/mp4") -> dict:
    """Upload `path` to Drive, mark public, return link payload.

    Returns:
        {"success": True, "file_id", "web_link", "direct_link"} on success
        {"success": False, "error"} otherwise
    """
    # Allow operator to disable video generation/upload entirely
    if os.getenv("DISABLE_VIDEO_GEN", "false").lower() in ("1", "true", "yes"):
        return {"success": False, "error": "Video generation disabled by DISABLE_VIDEO_GEN"}

    if not COMPOSIO_ENTITY_ID:
        return {"success": False, "error": "COMPOSIO_ENTITY_ID not set"}

    p = Path(path)
    if not p.exists():
        return {"success": False, "error": f"File not found: {p}"}

    client = get_composio_client()
    entity = COMPOSIO_ENTITY_ID

    upload_args = {"file_to_upload": str(p.resolve()), "mime_type": mime_type}
    if GDRIVE_FOLDER_ID:
        upload_args["parent_id"] = GDRIVE_FOLDER_ID

    try:
        resp = _execute_with_fallback("GOOGLEDRIVE_UPLOAD_FILE", upload_args, entity)
    except Exception as e:
        logger.exception("GDrive upload failed: %s", e)
        return {"success": False, "error": str(e)}

    if not resp.get("successful"):
        return {"success": False, "error": resp.get("error", "Upload failed")}

    data = resp.get("data", {}) or {}
    file_id = data.get("id") or data.get("file_id") or (data.get("response_data") or {}).get("id")
    if not file_id:
        return {"success": False, "error": f"No file_id in response: {data}"}

    try:
        _execute_with_fallback(
            "GOOGLEDRIVE_ADD_FILE_SHARING_PREFERENCE",
            {"file_id": file_id, "role": "reader", "type": "anyone"},
            entity,
        )
    except Exception as e:
        logger.warning("GDrive sharing toggle failed (%s) — returning link anyway", e)

    return {
        "success": True,
        "file_id": file_id,
        "web_link": _web_link(file_id),
        "direct_link": _direct_link(file_id),
    }
