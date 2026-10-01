#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import random
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "publisher"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PUBLISHER))

from publisher.manual_asset_inbox import server as inbox  # noqa: E402
import final_asset_publisher as final_pub  # noqa: E402


def png_bytes() -> bytes:
    buffer = BytesIO()
    rng = random.Random(20261001)
    raw = rng.randbytes(1080 * 1350 * 3)
    Image.frombytes("RGB", (1080, 1350), raw).save(buffer, "PNG")
    data = buffer.getvalue()
    assert len(data) > 20_000
    return data


def assert_manual_config() -> None:
    cfg = json.loads((PUBLISHER / "clients" / "f1-immobiliare.json").read_text(encoding="utf-8"))
    assert cfg["graphics_source"] == "manual_only"
    assert cfg["ai_image_generation"] is False
    assert cfg["automatic_brand_layer"] is False
    assert cfg["automatic_rendering"] is False
    assert cfg["manual_asset_required"] is True
    assert cfg["publish_only"] is True
    assert cfg["require_media"] is True
    assert cfg["approval_required"] is True
    assert (cfg.get("runtime_mode") or {}).get("pixel_in_pixel_out") is True


def assert_manual_ingest_and_pixel_identity() -> None:
    data = png_bytes()
    digest = hashlib.sha256(data).hexdigest()
    info = inbox.validate_image_bytes(data, "ci-final.png")
    assert info["format"] == "PNG"
    assert (info["width"], info["height"]) == (1080, 1350)

    queue = {"jobs": []}
    rows = inbox._prepare_records(
        [{
            "data": data,
            "filename": "ci-final.png",
            "meta": {
                "content_id": "F1-CI-MANUAL-001",
                "title": "CI manual asset",
                "caption": "Caption manuale esatta.",
                "platforms": ["facebook", "instagram"],
                "territory": "Avigliana",
                "scope": "territory",
                "scheduled_at": "2099-01-01T10:30:00+01:00",
                "approved": True,
            },
        }],
        queue,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["digest"] == digest
    assert row["data"] == data
    assert row["status"] == "READY"
    assert row["publication_status"] == "READY_TO_PUBLISH"

    ci_dir = PUBLISHER / "final_assets" / "manual_inbox" / "_ci"
    ci_dir.mkdir(parents=True, exist_ok=True)
    target = ci_dir / "F1-CI-MANUAL-001.png"
    try:
        target.write_bytes(row["data"])
        assert hashlib.sha256(target.read_bytes()).hexdigest() == digest
        rel = target.relative_to(ROOT).as_posix()
        job = inbox.build_queue_job(row, rel, inbox.now_iso())
        assert final_pub.is_manual_f1_job(job) is True
        assert job["graphics_source"] == "manual_only"
        assert job["ai_image_generation"] is False
        assert job["automatic_brand_layer"] is False
        assert job["automatic_rendering"] is False
        assert job["pixel_in_pixel_out"] is True
        assert job["caption"] == "Caption manuale esatta."

        buffer_job, paths = final_pub.prepare_job(job)
        assert paths == [target]
        assert buffer_job["media"] == rel
        assert buffer_job["asset_sha256"] == [digest]
        assert buffer_job["ai_assisted"] is False
        assert buffer_job["graphics_source"] == "manual_only"
        assert hashlib.sha256(target.read_bytes()).hexdigest() == digest

        legacy = {
            "id": "legacy-generated",
            "client_id": "f1-immobiliare",
            "source": "verified-f1-custom-gpt",
            "graphics_source": "generated",
            "status": "READY",
            "caption": "legacy",
            "format": "photo",
            "assets": [{"path": rel, "sha256": digest}],
            "platforms": ["facebook"],
            "scope": "territory",
            "territory": "Avigliana",
            "scheduled_at": "2099-01-01T09:00:00+01:00",
        }
        selected = final_pub.next_ready(
            {"jobs": [legacy, job]},
            manual_only=True,
        )
        assert selected is job, selected
    finally:
        target.unlink(missing_ok=True)
        try:
            ci_dir.rmdir()
        except OSError:
            pass



def assert_mock_publisher_end_to_end() -> None:
    data = png_bytes()
    digest = hashlib.sha256(data).hexdigest()
    row = inbox._prepare_records(
        [{
            "data": data,
            "filename": "e2e-final.png",
            "meta": {
                "content_id": "F1-CI-E2E-001",
                "title": "E2E manual asset",
                "caption": "Caption E2E fornita dall'operatore.",
                "platforms": ["facebook", "instagram"],
                "territory": "Avigliana",
                "scope": "territory",
                "scheduled_at": "2099-01-01T10:30:00+01:00",
                "approved": True,
            },
        }],
        {"jobs": []},
    )[0]

    ci_dir = PUBLISHER / "final_assets" / "manual_inbox" / "_ci"
    ci_dir.mkdir(parents=True, exist_ok=True)
    target = ci_dir / "F1-CI-E2E-001.png"
    target.write_bytes(data)
    rel = target.relative_to(ROOT).as_posix()
    job = inbox.build_queue_job(row, rel, inbox.now_iso())
    queue = {"jobs": [job]}

    states = [x["state"] for x in job.get("state_history") or []]
    assert states == ["CARICATO", "APPROVATO", "PROGRAMMATO", "READY_TO_PUBLISH"]
    assert job["status"] == "READY"
    assert job["publication_status"] == "READY_TO_PUBLISH"

    originals = {
        "persist_queue": final_pub.persist_queue,
        "resolve_job_channels": final_pub.territory_router.resolve_job_channels,
        "ensure_cloudinary_assets": final_pub.base.ensure_cloudinary_assets,
        "create_buffer_post": final_pub.base.create_buffer_post,
        "get_buffer_post": final_pub.base.get_buffer_post,
    }

    try:
        final_pub.persist_queue = lambda _queue: None
        final_pub.territory_router.resolve_job_channels = lambda _key, _job: (
            "org-ci",
            {
                "facebook": {"id": "channel-facebook"},
                "instagram": {"id": "channel-instagram"},
            },
        )
        final_pub.base.ensure_cloudinary_assets = lambda _job, _cloud: [
            {"url": "https://cdn.example.test/f1-ci-e2e.png"}
        ]

        def fake_create(_key, channel_id, service, _buffer_job, _hosted, _now):
            return {
                "post_id": f"post-{service}",
                "service": service,
                "channel_id": channel_id,
                "buffer_status": "pending",
            }

        def fake_get(_key, post_id):
            service = "facebook" if "facebook" in post_id else "instagram"
            return {
                "post_id": post_id,
                "buffer_status": "sent",
                "sent_at": "2099-01-01T10:31:00Z",
                "external_link": f"https://social.example.test/{service}/F1-CI-E2E-001",
                "channel_id": f"channel-{service}",
            }

        final_pub.base.create_buffer_post = fake_create
        final_pub.base.get_buffer_post = fake_get

        before = hashlib.sha256(target.read_bytes()).hexdigest()
        rc = final_pub.publish_job(queue, job, "buffer-ci-key", "cloudinary://ci", dry_run=False)
        after = hashlib.sha256(target.read_bytes()).hexdigest()

        assert rc == 0
        assert before == digest == after
        assert job["published_asset_sha256"] == [digest]
        assert job["status"] == "PUBLISHED_VERIFIED"
        assert job["provider"] == "buffer"
        assert len(job.get("remote_post_ids") or []) == 2
        assert len(job.get("published_urls") or []) == 2
        assert job["remote_post_url"].startswith("https://social.example.test/")
        assert set(job.get("buffer_scheduled_platforms") or []) == {"facebook", "instagram"}
    finally:
        final_pub.persist_queue = originals["persist_queue"]
        final_pub.territory_router.resolve_job_channels = originals["resolve_job_channels"]
        final_pub.base.ensure_cloudinary_assets = originals["ensure_cloudinary_assets"]
        final_pub.base.create_buffer_post = originals["create_buffer_post"]
        final_pub.base.get_buffer_post = originals["get_buffer_post"]
        target.unlink(missing_ok=True)
        try:
            ci_dir.rmdir()
        except OSError:
            pass


def assert_caption_missing_holds() -> None:
    data = png_bytes()
    rows = inbox._prepare_records(
        [{
            "data": data,
            "filename": "caption-missing.png",
            "meta": {
                "content_id": "F1-CI-CAPTION-MISSING",
                "caption": "",
                "platforms": ["facebook"],
                "approved": True,
            },
        }],
        {"jobs": []},
    )
    assert rows[0]["status"] == "HOLD"
    assert rows[0]["publication_status"] == "CAPTION_MISSING"


def assert_corrupt_file_rejected() -> None:
    try:
        inbox.validate_image_bytes(b"not-an-image", "broken.png")
    except ValueError:
        return
    raise AssertionError("Corrupt image was accepted")


def assert_no_generation_in_manual_runtime() -> None:
    server_text = (PUBLISHER / "manual_asset_inbox" / "server.py").read_text(encoding="utf-8").lower()
    index_text = (PUBLISHER / "manual_asset_inbox" / "index.html").read_text(encoding="utf-8").lower()
    for forbidden in (
        "generatore-grafica-f1",
        "free_provider_router",
        "generate_visual",
        "/api/generated",
        "ingest-generated",
        "auto_caption",
        "_launch_communication_worker",
    ):
        assert forbidden not in server_text, forbidden
        assert forbidden not in index_text, forbidden

    final_workflow = (ROOT / ".github" / "workflows" / "f1-final-assets-publisher.yml").read_text(encoding="utf-8")
    final_lower = final_workflow.lower()
    assert "--manual-only" in final_workflow
    for forbidden in (
        "generate_next_villar_asset.py",
        "chatgpt_query_runner",
        "openai_api_key",
        "leonardo",
        "firefly",
        "generate_visual",
    ):
        assert forbidden not in final_lower, forbidden

    archived = [
        "f1-chatgpt-creative.yml",
        "f1-daily-creative-pc-immediate.yml",
        "f1-daily-creative-5-minute-watch.yml",
        "f1-news-5-minute-watch.yml",
        "f1-news-browser-control.yml",
        "f1-news-pc-immediate.yml",
        "f1-valle-susa-news.yml",
        "f1-qualified-14d.yml",
        "f1-feed-preview.yml",
        "f1-golden-master-smoke.yml",
        "f1-preview-today.yml",
        "renderer-v2-qualified-smoke.yml",
        "social-preview-weekly-index.yml",
        "f1-design-v2.yml",
        "renderer-v2-ci.yml",
    ]
    for name in archived:
        text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert "ARCHIVED - F1 MANUAL PUBLISH ONLY" in text
        assert "\n  schedule:" not in text
        assert "\n  push:" not in text

    social = (ROOT / ".github" / "workflows" / "social-engine-daily.yml").read_text(encoding="utf-8")
    assert "assert len(f1)==0" in social
    assert "F1_AUTOMATIC_GRAPHICS_DISABLED" in social

    worker = (PUBLISHER / "chatgpt_query_runner" / "worker.py").read_text(encoding="utf-8")
    assert "f1_generation_disabled()" in worker
    assert "F1 MANUAL PUBLISH ONLY: image generation worker is disabled" in worker

    hourly = (PUBLISHER / "f1_graphics_hourly" / "worker.py").read_text(encoding="utf-8")
    assert "hourly graphic generation is disabled" in hourly

    buffer_code = (PUBLISHER / "buffer_twice_daily.py").read_text(encoding="utf-8")
    assert "job.get('ai_assisted') is False" in buffer_code

    installer = (PUBLISHER / "f1_graphics_automation" / "INSTALLA_AUTOMAZIONE_23.ps1").read_text(encoding="utf-8")
    assert "Unregister-ScheduledTask" in installer
    for task in ("F1_Grafiche_23", "F1_News_ValleSusa", "F1_News_GitHub_Poller"):
        assert task in installer
    assert "New-ScheduledTaskTrigger -Daily -At 23:00" not in installer
    assert "chatgpt_query_runner\\requirements.txt" not in installer

    start_inbox = (PUBLISHER / "f1_graphics_automation" / "START_INBOX.ps1").read_text(encoding="utf-8")
    assert "manual-publish-only" in start_inbox
    for forbidden in ("ENSURE_F1_NEWS_POLLER", "ENSURE_F1_GITHUB_RUNNER", "free_browser_router", "chatgpt_query_runner.worker"):
        assert forbidden not in start_inbox

    for relative in (
        "RUN_NOTTURNO_23.ps1",
        "RUN_F1_DAILY_CREATIVE_TEST.ps1",
        "RUN_F1_NEWS_SLOT.ps1",
        "RUN_F1_NEWS_POLLER.ps1",
    ):
        text = (PUBLISHER / "f1_graphics_automation" / relative).read_text(encoding="utf-8")
        assert "MANUAL PUBLISH ONLY" in text
        for forbidden in ("chatgpt_query_runner.worker", "free_browser_router", "F1_CREATIVE_BACKEND"):
            assert forbidden not in text

    content_engine = (PUBLISHER / "rendering" / "content_engine.py").read_text(encoding="utf-8")
    assert "Renderer V2 cannot create or modify F1 graphics" in content_engine

    openai_visual = (PUBLISHER / "rendering" / "openai_visual_engine.py").read_text(encoding="utf-8")
    assert "OpenAI Images is disabled for F1 before API-key lookup" in openai_visual

    premium = (PUBLISHER / "f1_premium_renderer.py").read_text(encoding="utf-8")
    assert "premium renderer installation skipped" in premium

    server_text_exact = (PUBLISHER / "manual_asset_inbox" / "server.py").read_text(encoding="utf-8")
    assert '@app.post("/api/archive")' in server_text_exact
    assert '"state_history": state_history' in server_text_exact

    workspace = (ROOT / "f1-content-hub" / "client-workspace.js").read_text(encoding="utf-8")
    assert 'client.slug==="f1-immobiliare"' in workspace
    assert "Nessuna grafica o caption viene generata automaticamente." in workspace
    assert 'manualF1?String(base||"").trim():captionFor' in workspace
    assert 'F1 Immobiliare è in modalità manual publish-only' in workspace


def main() -> int:
    assert_manual_config()
    assert_manual_ingest_and_pixel_identity()
    assert_mock_publisher_end_to_end()
    assert_caption_missing_holds()
    assert_corrupt_file_rejected()
    assert_no_generation_in_manual_runtime()
    print("F1_MANUAL_PUBLISH_ONLY_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
