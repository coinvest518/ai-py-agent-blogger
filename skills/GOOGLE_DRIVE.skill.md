# GOOGLE_DRIVE (Composio toolkit)

Used by `src/agent/video_gen/gdrive_upload.py` to host generated MP4s publicly
so upload-post and blog email can embed them.

## Tool slugs

### `GOOGLEDRIVE_UPLOAD_FILE`
Upload a local file to Drive.
```python
client.tools.execute(
    "GOOGLEDRIVE_UPLOAD_FILE",
    arguments={
        "file_to_upload": "/abs/path/to/file.mp4",
        "mime_type": "video/mp4",
        "parent_id": "<optional folder id>",
    },
    user_id=COMPOSIO_ENTITY_ID,
)
```
Returns `{"data": {"id": "<file_id>", ...}, "successful": True}`.

### `GOOGLEDRIVE_ADD_FILE_SHARING_PREFERENCE`
Make an uploaded file publicly readable by link.
```python
client.tools.execute(
    "GOOGLEDRIVE_ADD_FILE_SHARING_PREFERENCE",
    arguments={
        "file_id": "<id>",
        "role": "reader",
        "type": "anyone",
    },
    user_id=COMPOSIO_ENTITY_ID,
)
```

### `GOOGLEDRIVE_GET_FILE_METADATA`
Fetch metadata (size, quota usage, link).
```python
arguments={"file_id": "<id>"}
```

## Link shapes
- Web viewer: `https://drive.google.com/file/d/<file_id>/view`
- Direct download (embeddable in `<video src>`): `https://drive.google.com/uc?export=download&id=<file_id>`

## Env
- `COMPOSIO_ENTITY_ID` — required (auto-resolves connected Google account)
- `GDRIVE_VIDEO_FOLDER_ID` — optional; if set, uploads go inside that folder for easier cleanup
- `COMPOSIO_TOOLKIT_VERSION_GOOGLEDRIVE` — pin if you hit NONEXISTENT_VERSION errors

## Quota
Free tier = 15GB shared with Gmail + Photos. Prune old videos via
`scripts/prune_drive_videos.py` (30-day retention) to stay under cap.
