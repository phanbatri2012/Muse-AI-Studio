from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal as Signal

from A_workflow_get_token import TokenCollector
from chrome_process_manager import ChromeProcessManager
from settings_manager import SettingsManager, WORKFLOWS_DIR
import veo_client
from workflow_error_policy import (
    build_error_guidance,
    classify_api_error,
    is_content_filter_error,
    is_quota_exhausted_error,
    is_recaptcha_failed_error,
    is_retryable_api_error,
)
from workflow_run_control import get_max_in_flight, get_running_video_count


class BaseWorkflow(QThread):
    """Base class for all Google Veo 3.1 & Imagen 4 API Workflows."""

    log_message = Signal(str)
    video_updated = Signal(dict)
    automation_complete = Signal()
    video_folder_updated = Signal(str)

    def __init__(self, project_name: str | None = None, project_data: dict | None = None, parent=None):
        super().__init__(parent)
        self.project_name = str(project_name or (project_data or {}).get("project_name", "Unknown")).strip()
        self.project_data = dict(project_data or {})
        self.STOP = 0

        self._auto_noi_canh = bool(self.project_data.get("_auto_noi_canh"))
        self._keep_chrome_open = bool(self.project_data.get("_keep_chrome_open")) or self._auto_noi_canh
        self._close_chrome_after_token = bool(self.project_data.get("_close_chrome_after_token"))
        self._close_chrome_on_finish = bool(self.project_data.get("_close_chrome_on_finish", True))

        self._scene_status: dict[str, str] = {}
        self._scene_to_prompt: dict[str, Any] = {}
        self._prompt_scene_order: dict[str, int] = {}
        self._active_prompt_ids: set[str] = set()
        self._resend_items: list[dict] | None = None
        self._all_prompts_submitted = False
        self._automation_complete_emitted = False
        self._worker_controls_lifecycle = bool(self.project_data.get("_worker_controls_lifecycle", False))

        self._last_submit_ts = 0.0
        self._status_log_ts = 0.0
        self._pending_log_interval = 3
        self._status_poll_fail_streak = 0
        self._last_status_change_ts = 0.0
        self._in_flight_block_start_ts = 0.0
        self._scene_next_check_at: dict[str, float] = {}
        self._scene_status_change_ts: dict[str, float] = {}
        self._state_status_logged: set[str] = set()

    def _log(self, message: str) -> None:
        self.log_message.emit(str(message or ""))

    def stop(self) -> None:
        self.STOP = 1
        self.requestInterruption()

    def _should_stop(self) -> bool:
        return bool(self.STOP != 0 or self.isInterruptionRequested())

    def _get_project_dir(self) -> Path:
        p_dir = WORKFLOWS_DIR / self.project_name
        p_dir.mkdir(parents=True, exist_ok=True)
        return p_dir

    def _get_download_dir(self) -> Path:
        custom_out = str(self.project_data.get("video_output_dir") or "").strip()
        if custom_out and os.path.isdir(custom_out):
            d_dir = Path(custom_out)
        else:
            d_dir = self._get_project_dir() / "Download"
        d_dir.mkdir(parents=True, exist_ok=True)
        return d_dir

    def _load_auth_credentials(self) -> dict[str, Any]:
        config = SettingsManager.load_config() or {}
        account = config.get("account1", {}) if isinstance(config, dict) else {}
        return {
            "email": str(account.get("email") or "").strip(),
            "password": str(account.get("password") or "").strip(),
            "access_token": str(account.get("access_token") or "").strip(),
            "session_id": str(account.get("sessionId") or "").strip(),
            "project_id": str(account.get("projectId") or "").strip(),
            "cookie": str(account.get("cookie") or "").strip(),
            "type_account": str(account.get("type_account") or account.get("TYPE_ACCOUNT") or "ULTRA").strip().upper(),
        }

    async def _ensure_valid_token(self, force_refresh: bool = False) -> dict[str, Any]:
        creds = self._load_auth_credentials()
        if creds.get("access_token") and not force_refresh:
            return creds

        self._log("🔑 Token thiếu hoặc hết hạn, đang tự động thu thập token mới...")
        collector = TokenCollector(
            email=creds.get("email"),
            password=creds.get("password"),
            offscreen=bool(self.project_data.get("offscreen_chrome", True)),
        )
        success = await collector.collect_token_async()
        if not success:
            raise RuntimeError("Thu thập Token thất bại. Vui lòng kiểm tra lại tài khoản trong tab Cài đặt.")

        return self._load_auth_credentials()

    def _wait_for_in_flight_slot(self, delay_seconds: float = 1.0) -> None:
        while not self._should_stop():
            running = get_running_video_count()
            limit = get_max_in_flight()
            if running < limit:
                return
            time.sleep(max(0.2, delay_seconds))

    def _emit_video_updated(self, payload: dict) -> None:
        try:
            self.video_updated.emit(dict(payload or {}))
        except Exception:
            pass

    def _emit_complete_once(self) -> None:
        if not self._automation_complete_emitted:
            self._automation_complete_emitted = True
            self.automation_complete.emit()
