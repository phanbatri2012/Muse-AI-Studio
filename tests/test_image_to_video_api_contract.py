from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from muse2api_backend import app as app_module
from muse2api_backend.engine import MuseEngine, MuseGenerationError


def _frame_request(**overrides) -> app_module.VideoRequest:
    values = {
        "prompt": "Move continuously from the opening state to the closing state",
        "model": "muse-video",
        "duration": 5,
        "aspect_ratio": "16:9",
        "resolution": "1920x1080",
        "start_image": "start-frame",
        "end_image": "end-frame",
    }
    values.update(overrides)
    return app_module.VideoRequest(**values)


class MuseStartEndFrameContractTests(unittest.TestCase):
    def test_pair_resolves_in_start_then_end_order(self) -> None:
        images, mode = app_module._resolve_video_images(_frame_request())

        self.assertEqual(images, ["start-frame", "end-frame"])
        self.assertEqual(mode, "start_end")

    def test_pair_requires_both_endpoints(self) -> None:
        for request in (
            _frame_request(end_image=None),
            _frame_request(start_image=None),
        ):
            with self.subTest(request=request):
                with self.assertRaises(HTTPException) as raised:
                    app_module._resolve_video_images(request)
                self.assertEqual(raised.exception.status_code, 400)

    def test_pair_rejects_legacy_image_fields(self) -> None:
        for field, value in (
            ("reference_image", ["legacy-reference"]),
            ("image", "legacy-image"),
            ("image_url", "https://example.invalid/image.png"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(HTTPException) as raised:
                    app_module._resolve_video_images(_frame_request(**{field: value}))
                self.assertEqual(raised.exception.status_code, 400)

    def test_pair_prompt_maps_images_without_multi_entity_semantics(self) -> None:
        prompt = app_module.build_video_prompt(_frame_request())

        self.assertIn("@Image1", prompt)
        self.assertIn("@Image2", prompt)
        self.assertIn("连续", prompt)
        self.assertNotIn("多个独立实体/角色与道具参考图", prompt)
        self.assertNotIn("多张参考图/角色Turnaround设定图", prompt)

    def test_legacy_reference_image_behavior_remains_available(self) -> None:
        request = app_module.VideoRequest(
            prompt="Animate this reference",
            reference_image=["legacy-reference"],
        )

        images, mode = app_module._resolve_video_images(request)
        prompt = app_module.build_video_prompt(request)

        self.assertEqual(images, ["legacy-reference"])
        self.assertEqual(mode, "legacy")
        self.assertIn("第一帧", prompt)
        self.assertNotIn("@Image2", prompt)

    def test_models_capabilities_are_versioned_and_non_sensitive(self) -> None:
        response = app_module.models(None)
        capability = response["capabilities"]

        self.assertEqual(
            capability,
            {
                "video_start_end_frames": 1,
                "task_recovery": 0,
                "account_relogin": 2,
            },
        )
        serialized = json.dumps(capability).casefold()
        for sensitive_name in ("token", "cookie", "path", "password"):
            self.assertNotIn(sensitive_name, serialized)

    def test_application_and_backend_versions_are_synchronized(self) -> None:
        version_path = Path(app_module.__file__).with_name("version.json")
        version_data = json.loads(version_path.read_text(encoding="utf-8"))

        self.assertEqual(app_module.app.version, app_module.MUSE2API_VERSION)
        self.assertEqual(version_data["version"], app_module.MUSE2API_VERSION)

    def test_readyz_exposes_only_sanitized_recovery_runtime_metadata(self) -> None:
        fake_store = MagicMock()
        fake_store.tasks = {
            "active": {
                "kind": "video",
                "status": "processing",
                "prompt": "must-not-leak",
            },
            "done": {"kind": "image", "status": "completed"},
        }
        fake_store.list_accounts.return_value = [{"enabled": True}]
        fake_store.media_capacity.return_value = {
            "status": "ready",
            "eligible": 1,
            "unknown": 0,
            "exhausted": 0,
        }
        with patch.object(app_module, "store", fake_store):
            response = app_module.readyz()

        self.assertEqual(response["active_media_tasks"], 1)
        self.assertEqual(response["runtime_id"], app_module.RUNTIME_ID)
        serialized = json.dumps(response).casefold()
        for sensitive_name in ("token", "cookie", "prompt", "path", "password"):
            self.assertNotIn(sensitive_name, serialized)


class MuseStartEndFrameApiTests(unittest.TestCase):
    def setUp(self) -> None:
        app_module.app.dependency_overrides[app_module.auth] = lambda: True
        self.client = TestClient(app_module.app)

    def tearDown(self) -> None:
        app_module.app.dependency_overrides.clear()
        self.client.close()

    def test_missing_end_frame_returns_http_400(self) -> None:
        response = self.client.post(
            "/v1/videos",
            json={"prompt": "transition", "start_image": "start-frame"},
        )

        self.assertEqual(response.status_code, 400)

    def test_mixing_start_end_with_legacy_field_returns_http_400(self) -> None:
        response = self.client.post(
            "/v1/videos",
            json={
                "prompt": "transition",
                "start_image": "start-frame",
                "end_image": "end-frame",
                "reference_image": ["legacy-reference"],
            },
        )

        self.assertEqual(response.status_code, 400)


class _AttachmentPage:
    def __init__(self) -> None:
        self.scripts: list[str] = []

    def js(self, script: str) -> str:
        self.scripts.append(script)
        if "filesData" in script:
            return json.dumps({"ok": True, "count": 2})
        return json.dumps({"removeCount": 2, "mediaCount": 2})


class MuseAttachmentOrderingTests(unittest.TestCase):
    def test_start_and_end_are_uploaded_with_stable_roles(self) -> None:
        engine = object.__new__(MuseEngine)
        engine.page = _AttachmentPage()

        with (
            patch.object(engine, "_clear_attachments", return_value=None),
            patch.object(
                engine,
                "_normalize_image",
                side_effect=[("c3RhcnQ=", "image/png"), ("ZW5k", "image/png")],
            ),
        ):
            engine._attach_image(
                ["start-frame", "end-frame"],
                attachment_roles=["start_frame", "end_frame"],
            )

        upload_script = engine.page.scripts[0]
        self.assertLess(upload_script.index("start_frame.png"), upload_script.index("end_frame.png"))

    def test_invalid_endpoint_prevents_partial_attachment_submission(self) -> None:
        engine = object.__new__(MuseEngine)
        engine.page = _AttachmentPage()

        with (
            patch.object(engine, "_clear_attachments", return_value=None) as clear,
            patch.object(
                engine,
                "_normalize_image",
                side_effect=[("c3RhcnQ=", "image/png"), (None, None)],
            ),
            self.assertRaises(MuseGenerationError),
        ):
            engine._attach_image(
                ["start-frame", "end-frame"],
                attachment_roles=["start_frame", "end_frame"],
            )

        clear.assert_not_called()


if __name__ == "__main__":
    unittest.main()
