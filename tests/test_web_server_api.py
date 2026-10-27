from __future__ import annotations

import io
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_server = pytest.importorskip(
    "server",
    reason="legacy desktop web server is optional",
)
app = _server.app
event_hub = _server.event_hub
workflow_mgr = _server.workflow_mgr
send_range_file = _server.send_range_file
WORKFLOWS_DIR = _server.WORKFLOWS_DIR


class WebServerApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_get_system_status(self) -> None:
        response = self.client.get("/api/system/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("machine_id", data)
        self.assertIn("account_type", data)
        self.assertIn("is_workflow_running", data)

    def test_get_license_info(self) -> None:
        response = self.client.get("/api/system/license")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("machine_id", data)
        self.assertIn("is_licensed", data)

    def test_settings_roundtrip(self) -> None:
        # Get settings
        response = self.client.get("/api/settings")
        self.assertEqual(response.status_code, 200)
        cfg = response.json()
        self.assertIsInstance(cfg, dict)

        # Save updated settings
        test_payload = {
            **cfg,
            "veo_model": "Veo 3.1 - Fast",
            "video_aspect_ratio": "16:9",
            "duration_seconds": 8,
        }
        post_res = self.client.post("/api/settings", json=test_payload)
        self.assertEqual(post_res.status_code, 200)
        self.assertTrue(post_res.json().get("success"))

    def test_get_active_workflow(self) -> None:
        response = self.client.get("/api/workflows/active")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("is_running", data)
        self.assertIn("jobs", data)
        self.assertIn("logs", data)

    def test_gallery_empty_project(self) -> None:
        response = self.client.get("/api/gallery/test_nonexistent_project_123")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("videos"), [])
        self.assertEqual(data.get("images"), [])

    def test_spa_root_serves_html(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))

    def test_submit_workflows_validation_empty_prompts(self) -> None:
        # Text to video empty
        res = self.client.post("/api/workflows/text-to-video", json={"prompts": []})
        self.assertEqual(res.status_code, 400)

        # Image to video empty
        res = self.client.post("/api/workflows/image-to-video", json={"prompts": []})
        self.assertEqual(res.status_code, 400)

        # Character sync empty
        res = self.client.post("/api/workflows/character-sync", json={"prompts": [], "characters": []})
        self.assertEqual(res.status_code, 400)

        # Create image empty
        res = self.client.post("/api/workflows/create-image", json={"prompts": []})
        self.assertEqual(res.status_code, 400)

    @patch.object(workflow_mgr, "start_workflow")
    def test_submit_text_to_video_valid(self, mock_start: MagicMock) -> None:
        payload = {
            "project_name": "test_t2v_proj",
            "prompts": [{"id": "1", "description": "Cinematic shot of flying drone"}],
            "aspect_ratio": "16:9",
            "duration_seconds": 8,
            "veo_model": "Veo 3.1 - Fast",
        }
        res = self.client.post("/api/workflows/text-to-video", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("success"))
        self.assertEqual(res.json().get("job_count"), 1)
        mock_start.assert_called_once()

    def test_event_hub_broadcast_sync_from_worker_thread(self) -> None:
        error_holder = []

        def worker():
            try:
                event_hub.broadcast_sync("test_event", {"message": "hello from thread"})
            except Exception as exc:
                error_holder.append(exc)

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=2.0)

        self.assertEqual(len(error_holder), 0, f"broadcast_sync raised exception in worker: {error_holder}")

    def test_media_upload_temp_sanitizes_filename(self) -> None:
        file_content = b"fake image bytes"
        file_obj = io.BytesIO(file_content)

        res = self.client.post(
            "/api/media/upload-temp",
            data={"project_name": "test_upload_proj"},
            files={"file": ("../../malicious_file.png", file_obj, "image/png")},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("filename"), "malicious_file.png")
        self.assertNotIn("..", data.get("path"))

        # Clean up test project
        test_dir = WORKFLOWS_DIR / "test_upload_proj"
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_media_streaming_zero_byte_file(self) -> None:
        test_proj = "test_zero_byte_proj"
        proj_dir = WORKFLOWS_DIR / test_proj / "Download"
        proj_dir.mkdir(parents=True, exist_ok=True)
        zero_file = proj_dir / "zero.mp4"
        zero_file.write_bytes(b"")

        try:
            res = self.client.get(f"/api/media/video/{test_proj}/zero.mp4")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get("content-length"), "0")
        finally:
            shutil.rmtree(WORKFLOWS_DIR / test_proj, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
