---
name: image_hosting
description: How generated image bytes get turned into a public HTTPS URL for Pinterest / Instagram / LinkedIn / X.
---

# Image hosting cascade

Generator tier (bytes) and hosting tier (URL) are separate. Generation
already cascades through NVIDIA FLUX → Pollinations → Freepik → HuggingFace
and returns raw bytes. Hosting then runs `host_image_bytes(image_bytes)` in
`src/agent/pollinations_image_gen.py`, which cascades:

1. **ImgBB** — `upload_to_imgbb()`. Needs `IMGBB_API_KEY`. Primary.
   Fails on payloads >32MB or occasionally on malformed bytes.
2. **Imgur (anonymous)** — `src/agent/hf_image_gen.upload_to_imgur()`.
   No API key needed (uses public Client-ID). Second try.
3. **Google Drive (Composio)** — `src/agent/video_gen/gdrive_upload.upload_and_share`
   with `mime_type="image/png"`. Returns
   `https://drive.google.com/uc?export=download&id={file_id}` which
   Pinterest / Instagram / LinkedIn accept as a public image URL.
   Requires `COMPOSIO_ENTITY_ID`.

First success wins. Return shape: `{"success": True, "url": "...", "provider": "imgbb|imgur|gdrive"}`.
Only caller today is `generate_image_node` in `graph.py`.

If all three fail, `image_url` stays `None` and downstream platforms
that require an image (Pinterest, IG image path) will skip with
`no-image` reason.
