# -*- coding: utf-8 -*-
"""
Muse API Client for RUN_VEO_V1.1 Desktop Application.
Communicates directly with the local muse2api REST API service (FastAPI on port 18610).
Eliminates Playwright, node.exe, and browser automation overhead completely.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable
import urllib.request
from urllib.error import HTTPError, URLError

from muse_media import verify_video_file_integrity
from muse_service_manager import MUSE2API_HOST, MUSE2API_KEY, MUSE2API_PORT, MuseServiceManager

logger = logging.getLogger("muse_api_client")


class MuseAPIError(RuntimeError):
    pass


class MuseAPIClient:
    """REST API Client for muse2api backend service."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str = MUSE2API_KEY,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.base_url = (base_url or f"http://{MUSE2API_HOST}:{MUSE2API_PORT}").rstrip("/")
        self.api_key = api_key
        self.log_callback = log_callback

    def _log(self, message: str) -> None:
        if callable(self.log_callback):
            try:
                self.log_callback(message)
                return
            except Exception:
                pass
        print(f"[{time.strftime('%H:%M:%S')}] [MUSE_API] {message}")

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MUSE-STUDIO-Desktop/1.1",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def create_video_task(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        duration: int = 6,
        timeout_seconds: int = 360,
        reference_image: str | list[str] | None = None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        """Gửi yêu cầu tạo video qua REST API (POST /v1/videos)."""
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("Prompt không được để trống")

        endpoint = f"{self.base_url}/v1/videos"
        payload = {
            "prompt": clean_prompt,
            "model": "muse-video",
            "aspect_ratio": aspect_ratio,
            "duration": duration,
            "timeout": timeout_seconds,
        }
        if reference_image:
            payload["reference_image"] = reference_image
        if account_id:
            payload["account_id"] = str(account_id).strip()

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data, headers=self._get_headers(), method="POST")

        acc_info = f", Acc: {account_id}" if account_id else ""
        self._log(f"🚀 Gửi yêu cầu sinh video lên API: '{clean_prompt[:70]}...' ({aspect_ratio}, {duration}s{acc_info})")

        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                res_body = json.loads(resp.read().decode("utf-8"))
                task_id = res_body.get("id") or res_body.get("task_id")
                self._log(f"✅ Đã tiếp nhận tác vụ thành công! Task ID: {task_id}")
                return res_body
        except HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            raise MuseAPIError(f"HTTP {e.code} từ /v1/videos: {err_msg}") from e
        except Exception as exc:
            raise MuseAPIError(f"Lỗi kết nối tới /v1/videos: {exc}") from exc

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Truy vấn trạng thái tác vụ qua REST API (GET /v1/videos/{task_id})."""
        endpoint = f"{self.base_url}/v1/videos/{task_id}"
        req = urllib.request.Request(endpoint, headers=self._get_headers(), method="GET")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            raise MuseAPIError(f"HTTP {e.code} khi truy vấn task {task_id}: {err_msg}") from e
        except Exception as exc:
            raise MuseAPIError(f"Lỗi kết nối task {task_id}: {exc}") from exc

    def wait_for_video(
        self,
        task_id: str,
        timeout_seconds: int = 360,
        poll_interval: float = 2.0,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
        stop_check: Callable[[], bool] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Polling liên tục cho tới khi video hoàn thành hoặc hết thời gian chờ."""
        effective_timeout = kwargs.get("timeout", timeout_seconds)
        deadline = time.time() + float(effective_timeout)
        start_time = time.time()

        while time.time() < deadline:
            if callable(stop_check) and stop_check():
                self._log("⏹️ Nhận tín hiệu dừng từ người dùng.")
                return {"status": "stopped", "error": "Người dùng đã dừng tác vụ"}

            task_info = self.get_task_status(task_id)
            raw_status = str(task_info.get("status") or "").lower()
            progress = int(task_info.get("progress") or 10)
            elapsed = round(time.time() - start_time, 1)

            if callable(on_progress):
                try:
                    on_progress({
                        "task_id": task_id,
                        "status": raw_status.upper(),
                        "progress": progress,
                        "elapsed": elapsed,
                        "url": task_info.get("url"),
                    })
                except Exception:
                    pass

            if raw_status in ("completed", "success", "succeeded", "done"):
                self._log(f"🎉 Tác vụ {task_id} đã hoàn tất sau {elapsed}s!")
                return task_info

            if raw_status in ("failed", "error"):
                error_msg = task_info.get("error") or "Không xác định lỗi từ server"
                self._log(f"❌ Tác vụ {task_id} thất bại: {error_msg}")
                return task_info

            time.sleep(poll_interval)

        self._log(f"⚠️ Quá thời gian chờ ({timeout_seconds}s) cho task {task_id}")
        return {
            "status": "timeout",
            "error": f"Timeout sau {timeout_seconds}s khi chờ sinh video",
            "task_id": task_id,
        }

    # Alias for convenience
    poll_video_task = wait_for_video

    def download_video(
        self,
        media_url: str,
        dest_dir: Path,
        suggested_name: str | None = None,
    ) -> Path:
        """Tải file video MP4 từ media_url về ổ đĩa và kiểm định tính toàn vẹn magic bytes."""
        dest_dir.mkdir(parents=True, exist_ok=True)

        full_url = media_url
        if not full_url.startswith("http://") and not full_url.startswith("https://"):
            full_url = f"{self.base_url}/{media_url.lstrip('/')}"

        raw_filename = full_url.split("/")[-1].split("?")[0]
        if not raw_filename.endswith(".mp4") and not raw_filename.endswith(".webm"):
            raw_filename = f"{raw_filename}.mp4"

        final_name = suggested_name or raw_filename
        if not final_name.endswith(".mp4"):
            final_name += ".mp4"

        target_path = dest_dir / final_name

        self._log(f"⬇️ Đang tải video từ {full_url} về {target_path.name}...")

        req = urllib.request.Request(full_url, headers=self._get_headers())
        with urllib.request.urlopen(req, timeout=60) as resp, open(target_path, "wb") as f:
            shutil.copyfileobj(resp, f)

        # Kiểm định tính toàn vẹn MP4 Magic Bytes
        is_valid, msg = verify_video_file_integrity(target_path)
        if not is_valid:
            if target_path.exists():
                try:
                    target_path.unlink()
                except Exception:
                    pass
            raise MuseAPIError(f"File video tải về không hợp lệ: {msg}")

        self._log(f"✅ Video hợp lệ ({target_path.stat().st_size:,} bytes) đã lưu tại: {target_path.name}")
        return target_path

    def chat_completions(
        self,
        messages: list[dict[str, Any]],
        model: str = "muse-spark",
        timeout: int = 60,
    ) -> str:
        """Gọi OpenAI-compatible Chat API (POST /v1/chat/completions) và trả về text nội dung."""
        endpoint = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data, headers=self._get_headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res_body = json.loads(resp.read().decode("utf-8"))
                choices = res_body.get("choices", [])
                if choices and isinstance(choices[0], dict):
                    msg = choices[0].get("message", {})
                    return str(msg.get("content") or "").strip()
                return str(res_body).strip()
        except HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="replace")
            raise MuseAPIError(f"HTTP Error {e.code}: {err_msg}") from e
        except URLError as e:
            raise MuseAPIError(f"Connection Error: {e.reason}") from e

    def get(self, path: str, timeout: int = 30) -> dict[str, Any]:
        """Gửi GET request tới REST API."""
        clean_path = path.lstrip("/")
        endpoint = f"{self.base_url}/{clean_path}" if not path.startswith("http") else path
        req = urllib.request.Request(endpoint, headers=self._get_headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="replace")
            raise MuseAPIError(f"HTTP Error {e.code} ({path}): {err_msg}") from e
        except URLError as e:
            raise MuseAPIError(f"Connection Error ({path}): {e.reason}") from e

    def post(self, path: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
        """Gửi POST request tới REST API."""
        clean_path = path.lstrip("/")
        endpoint = f"{self.base_url}/{clean_path}" if not path.startswith("http") else path
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data, headers=self._get_headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw.strip() else {}
        except HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="replace")
            raise MuseAPIError(f"HTTP Error {e.code} ({path}): {err_msg}") from e
        except URLError as e:
            raise MuseAPIError(f"Connection Error ({path}): {e.reason}") from e
