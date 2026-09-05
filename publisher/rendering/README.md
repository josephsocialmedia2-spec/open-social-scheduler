# Renderer V2

Parallel replacement layer for the legacy Pillow/FFmpeg social renderer.

## Engines

- static / photo / carousel: SVG -> `@resvg/resvg-js` -> Sharp
- reel / story / video / UGC: Revideo
- encoding / probing: FFmpeg / ffprobe
- fallback: local Pillow renderer; video fallback wraps the fallback frame with FFmpeg

The public contract is `generate_content(content_spec)` in `content_engine.py`.
The renderer does not publish. It only produces deterministic media assets and metadata. Buffer, Cloudinary, scheduling, idempotency and social connections stay outside this layer.

## Migration rule

This package is introduced in parallel. The production pipeline must switch only after Renderer V2 CI passes for both the static and video primary engines. The legacy renderer remains available as fallback during migration.
