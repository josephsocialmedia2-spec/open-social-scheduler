# F1 Graphic Engines

This package isolates external graphic-generation engines from the publishing pipeline.

## Rule

The rest of F1 must consume only the final immutable JPG/PNG/MP4 asset. No publisher,
queue or scheduler may depend directly on ComfyUI, OpenAI, Canva or another provider.

## Current adapters

- `comfyui_adapter.py` — calls a configured ComfyUI HTTP server and saved workflow.
- `openai_adapter.py` — wraps the existing F1 OpenAI visual engine.
- `local_renderer_adapter.py` — uses the repository's own Renderer V2 as emergency fallback.
- `engine_router.py` — tries engines in order and returns the first valid final asset.

Default order:

`comfyui -> openai -> local-renderer`

Override with:

`F1_GRAPHIC_ENGINE_ORDER=comfyui,openai,local-renderer`

ComfyUI configuration:

- `COMFYUI_URL`
- `COMFYUI_WORKFLOW`

Secrets and model files are not stored in this repository.

## Portability

If one engine disappears, add or replace only its adapter. Content specs, final asset
library, queue, Cloudinary/Buffer publishing and social connections remain unchanged.

Third-party projects themselves are not vendored here by default. We keep our own
integration modules and saved workflow/configuration so upstream engines can be updated
or replaced without rebuilding F1 from zero.
