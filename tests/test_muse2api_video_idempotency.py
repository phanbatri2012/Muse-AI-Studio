from __future__ import annotations

import asyncio
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi import HTTPException

from muse2api_backend import app as app_module


class _MemoryStore:
    def __init__(self) -> None:
        self.tasks: dict[str, dict] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def create_task(self, kind: str, prompt: str) -> dict:
        with self._lock:
            self._counter += 1
            task = {
                "id": f"task-{self._counter}",
                "kind": kind,
                "prompt": prompt,
                "status": "queued",
                "progress": 0,
                "created_at": self._counter,
            }
            self.tasks[task["id"]] = task
            return task

    def update_task(self, task_id: str, **changes) -> dict:
        with self._lock:
            self.tasks[task_id].update(changes)
            return dict(self.tasks[task_id])


def _request(
    prompt: str = "Animate from the first frame to the last frame",
    *,
    end_image: str = "end-scene.png",
) -> app_module.VideoRequest:
    return app_module.VideoRequest(
        prompt=prompt,
        model="muse-video",
        duration=10,
        aspect_ratio="16:9",
        resolution="1920x1080",
        start_image="start-scene.png",
        end_image=end_image,
    )


class Muse2ApiVideoIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = _MemoryStore()

    def _queue(self, request: app_module.VideoRequest, key: str | None):
        images, _ = app_module._resolve_video_images(request)
        return app_module._queue_video(
            request,
            app_module.build_video_prompt(request),
            images,
            key,
        )

    def test_same_key_and_payload_returns_existing_task(self) -> None:
        with (
            patch.object(app_module, "store", self.store),
            patch.object(app_module.threading, "Thread") as thread_cls,
        ):
            first = self._queue(_request(), "stable-key")
            second = self._queue(_request(), "stable-key")

        self.assertEqual(first["task_id"], second["task_id"])
        self.assertEqual(first["runtime_id"], second["runtime_id"])
        self.assertEqual(len(self.store.tasks), 1)
        thread_cls.assert_called_once()

    def test_same_key_with_different_payload_returns_conflict(self) -> None:
        with (
            patch.object(app_module, "store", self.store),
            patch.object(app_module.threading, "Thread"),
        ):
            self._queue(_request("first prompt"), "stable-key")
            with self.assertRaises(HTTPException) as raised:
                self._queue(_request("different prompt"), "stable-key")

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(len(self.store.tasks), 1)

    def test_same_key_with_changed_end_frame_returns_conflict(self) -> None:
        with (
            patch.object(app_module, "store", self.store),
            patch.object(app_module.threading, "Thread"),
        ):
            self._queue(_request(end_image="end-a.png"), "stable-key")
            with self.assertRaises(HTTPException) as raised:
                self._queue(_request(end_image="end-b.png"), "stable-key")

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(len(self.store.tasks), 1)

    def test_missing_key_keeps_creating_new_tasks(self) -> None:
        with (
            patch.object(app_module, "store", self.store),
            patch.object(app_module.threading, "Thread"),
        ):
            first = self._queue(_request(), None)
            second = self._queue(_request(), None)

        self.assertNotEqual(first["task_id"], second["task_id"])
        self.assertEqual(len(self.store.tasks), 2)

    def test_concurrent_same_key_creates_one_task(self) -> None:
        request = _request()
        with (
            patch.object(app_module, "store", self.store),
            patch.object(
                app_module,
                "_run_generation",
                return_value=({"filename": "clip.mp4", "size": 1, "kind": "video"}, "acc-1"),
            ),
        ):
            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(
                    executor.map(lambda _: self._queue(request, "stable-key"), range(8))
                )

        self.assertEqual({item["task_id"] for item in results}, {"task-1"})
        self.assertEqual(len(self.store.tasks), 1)

    def test_new_submit_preflights_once_and_returns_sanitized_summary(self) -> None:
        capacity = {
            "status": "ready",
            "eligible": 1,
            "unknown": 0,
            "exhausted": 0,
            "skipped": 0,
            "cache_hit": True,
            "checked_at": 1,
            "elapsed_seconds": 0.1,
            "api_key": "must-not-leak",  # pragma: allowlist secret
            "path": "must-not-leak",
        }
        with (
            patch.object(app_module, "store", self.store),
            patch.object(
                app_module,
                "_run_generation",
                return_value=(
                    {"filename": "clip.mp4", "size": 1, "kind": "video"},
                    "acc-1",
                ),
            ),
            patch.object(
                app_module,
                "_media_capacity_preflight",
                return_value=capacity,
            ) as preflight,
        ):
            response = asyncio.run(
                app_module.create_video(
                    _request(), idempotency_key="new-key", _=None
                )
            )

        preflight.assert_called_once_with()
        self.assertEqual(response["media_capacity"]["status"], "ready")
        self.assertNotIn("api_key", response["media_capacity"])
        self.assertNotIn("path", response["media_capacity"])

    def test_startup_marks_inflight_task_as_structured_retryable_failure(self) -> None:
        self.store.tasks["task-1"] = {
            "id": "task-1",
            "kind": "video",
            "status": "processing",
        }

        def close_coroutine(coroutine):
            coroutine.close()
            return None

        with (
            patch.object(app_module, "store", self.store),
            patch.object(app_module.CFG, "api_key", "test-key"),
            patch.object(app_module.asyncio, "create_task", side_effect=close_coroutine),
        ):
            asyncio.run(app_module._startup())

        task = self.store.tasks["task-1"]
        self.assertEqual(task["status"], "failed")
        self.assertEqual(task["error_code"], "service_restart_interrupted")
        self.assertTrue(task["retryable"])
        self.assertEqual(task["runtime_id"], app_module.RUNTIME_ID)

    def test_recovery_capability_is_gated_and_version_is_patch_release(self) -> None:
        self.assertEqual(app_module.MUSE2API_VERSION, "1.8.1")
        with patch.object(app_module, "TASK_RECOVERY_CAPABILITY_VERSION", 0):
            disabled = app_module.models(_=None)
        with patch.object(app_module, "TASK_RECOVERY_CAPABILITY_VERSION", 1):
            enabled = app_module.models(_=None)

        self.assertEqual(disabled["capabilities"]["task_recovery"], 0)
        self.assertEqual(enabled["capabilities"]["task_recovery"], 1)
        for response in (disabled, enabled):
            serialized = str(response).casefold()
            for secret in ("api_key", "cookie", "password", "prompt", "path"):
                self.assertNotIn(secret, serialized)

    def test_public_video_task_redacts_error_and_omits_prompt_and_paths(self) -> None:
        task = {
            "id": "video-1",
            "kind": "video",
            "status": "failed",
            "progress": 40,
            "created_at": 1,
            "prompt": "full private prompt",
            "api_prompt": "normalized private prompt",
            "start_image": r"C:\private\start.png",
            "error": r"Authorization=Bearer-secret C:\private\trace.log",
            "error_code": "generation_failed",
            "retryable": False,
            "runtime_id": "runtime-1",
        }

        public = app_module._public_task(task)
        serialized = str(public)
        self.assertNotIn("full private prompt", serialized)
        self.assertNotIn("normalized private prompt", serialized)
        self.assertNotIn("start.png", serialized)
        self.assertNotIn("Bearer-secret", serialized)
        self.assertIn("[REDACTED]", public["error"])
        self.assertIn("[REDACTED_PATH]", public["error"])


if __name__ == "__main__":
    unittest.main()
