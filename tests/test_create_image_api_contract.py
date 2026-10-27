from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from muse2api_backend import app as app_module
from tests.test_muse2api_video_idempotency import _MemoryStore


class MuseImageApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = _MemoryStore()

    def _request(self, prompt: str = "A cinematic still frame") -> app_module.ImageRequest:
        return app_module.ImageRequest(
            prompt=prompt,
            model="muse-image",
            size="1920x1080",
        )

    def test_image_task_idempotency_deduplicates_same_payload(self) -> None:
        request = self._request()
        with (
            patch.object(app_module, "store", self.store),
            patch.object(app_module.threading, "Thread") as thread_cls,
        ):
            first = app_module._queue_image(request, request.prompt, None, "image-key")
            second = app_module._queue_image(request, request.prompt, None, "image-key")

        self.assertEqual(first.body, second.body)
        self.assertEqual(len(self.store.tasks), 1)
        thread_cls.assert_called_once()

    def test_image_task_idempotency_rejects_changed_payload(self) -> None:
        with (
            patch.object(app_module, "store", self.store),
            patch.object(app_module.threading, "Thread"),
        ):
            app_module._queue_image(
                self._request("first prompt"),
                "first prompt",
                None,
                "image-key",
            )
            with self.assertRaises(HTTPException) as raised:
                app_module._queue_image(
                    self._request("different prompt"),
                    "different prompt",
                    None,
                    "image-key",
                )

        self.assertEqual(raised.exception.status_code, 409)

    def test_public_image_task_does_not_expose_prompt_or_internal_fields(self) -> None:
        task = {
            "id": "image-1",
            "kind": "image",
            "status": "failed",
            "progress": 20,
            "created_at": 1,
            "prompt": "private full prompt",
            "api_prompt": "private normalized prompt",
            "reference_image": r"C:\private\reference.png",
            "error": r"token=secret C:\private\trace.log",
            "error_code": "generation_failed",
            "retryable": False,
            "runtime_id": "runtime-1",
        }

        public = app_module._public_task(task)
        serialized = str(public)
        self.assertNotIn("private full prompt", serialized)
        self.assertNotIn("private normalized prompt", serialized)
        self.assertNotIn("reference.png", serialized)
        self.assertNotIn("secret", serialized)
        self.assertIn("[REDACTED]", public["error"])
        self.assertIn("[REDACTED_PATH]", public["error"])


if __name__ == "__main__":
    unittest.main()
