# -*- coding: utf-8 -*-
"""
Workflow Text-to-Video hàng loạt cho Muse AI sử dụng REST API của muse2api.
Thay thế hoàn toàn Playwright, không còn phụ thuộc node.exe, hoạt động ổn định và tin cậy.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import time
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal as Signal

from muse_api_client import MuseAPIClient, MuseAPIError
from muse_service_manager import MuseServiceManager
from prompt_motion_enhancer import MotionLevel, PromptMotionEnhancer
from runtime_paths import MUSE_DOWNLOADS_DIR
from video_motion_smoother import VideoMotionSmoother


MAX_MUSE_DURATION_SECONDS = 10


def parse_prompt_directives(prompt: str, default_ar: str = "16:9", default_dur: int = 6) -> tuple[str, int]:
    """Tự động trích xuất tỉ lệ (16:9, 9:16) và thời lượng (số giây) từ đầu prompt nếu có.

    Quy chuẩn mô hình Muse AI: Tối ưu nhất ở 4–6 giây, tối đa giới hạn cứng là 10 giây/shot.
    Nếu người dùng nhập >10s (ví dụ 30s), hệ thống tự động clamp về trần 10s.

    Ví dụ:
        '[4K, 16:9, 6 giây]. Cảnh đồng hồ...' -> ('16:9', 6)
        '[9:16, 5s]. Nữ barista...' -> ('9:16', 5)
        '[16:9, 30 giây]. Cảnh quay dài...' -> ('16:9', 10)  # Tự động clamp về 10s
        'Chim bay lượn...' -> (default_ar, default_dur)
    """
    ar = default_ar if default_ar and default_ar != "auto" else "16:9"
    dur = default_dur if default_dur and default_dur > 0 else 6
    if dur > MAX_MUSE_DURATION_SECONDS:
        dur = MAX_MUSE_DURATION_SECONDS

    # Chỉ quét 80 ký tự đầu tiên của prompt (nơi chứa tiền tố đạo diễn [DURATION + RATIO])
    prefix = prompt[:80].lower()

    # 1. Quét aspect ratio
    if any(k in prefix for k in ("9:16", "9/16", "vertical", "portrait", "dọc")):
        ar = "9:16"
    elif any(k in prefix for k in ("16:9", "16/9", "horizontal", "landscape", "ngang", "2.39:1", "widescreen")):
        ar = "16:9"

    # 2. Quét duration
    m_dur = re.search(r"(\d+)\s*(?:giây|giay|s\b|sec|seconds?)\b", prefix)
    if m_dur:
        try:
            val = int(m_dur.group(1))
            if 1 <= val <= MAX_MUSE_DURATION_SECONDS:
                dur = val
            elif val > MAX_MUSE_DURATION_SECONDS:
                dur = MAX_MUSE_DURATION_SECONDS
        except ValueError:
            pass

    return ar, dur


class MuseTextToVideoWorkflow(QThread):
    """Workflow tự động hóa Text-to-Video hàng loạt bằng REST API của muse2api."""

    log_message = Signal(str)
    video_updated = Signal(dict)
    automation_complete = Signal()
    video_folder_updated = Signal(str)

    def __init__(
        self,
        project_name: str | None = None,
        project_data: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.project_name = str(project_name or (project_data or {}).get("project_name", "muse_default")).strip()
        self.project_data = dict(project_data or {})
        self.STOP = 0

        raw_prompts = self.project_data.get("prompts", [])
        self.prompts: list[dict[str, Any]] = []
        for i, p in enumerate(raw_prompts, start=1):
            if isinstance(p, dict):
                self.prompts.append(p)
            elif isinstance(p, str) and p.strip():
                self.prompts.append({"id": str(i), "prompt": p.strip()})
        self.timeout_seconds = int(self.project_data.get("timeout_seconds") or 360)
        self.aspect_ratio = str(self.project_data.get("aspect_ratio") or "9:16").strip()
        self.duration_seconds_target = int(self.project_data.get("duration") or 6)
        self.motion_boost = bool(self.project_data.get("motion_boost", True))
        self.motion_level = str(self.project_data.get("motion_level") or MotionLevel.SMOOTH).strip()
        self.context_isolation = bool(self.project_data.get("context_isolation", True))
        self.auto_smooth_60fps = bool(self.project_data.get("auto_smooth_60fps", False) or self.project_data.get("smooth_60fps", False))
        self.account_id = str(self.project_data.get("account_id") or "").strip() or None
        self.account_mode = str(self.project_data.get("account_mode") or "rotation").strip()

        custom_dir = str(self.project_data.get("download_dir") or "").strip()
        if custom_dir:
            self.download_dir = Path(custom_dir)
        else:
            self.download_dir = MUSE_DOWNLOADS_DIR / self.project_name
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def _log(self, message: str) -> None:
        self.log_message.emit(str(message or ""))

    def stop(self) -> None:
        """Dừng khẩn cấp workflow."""
        self.STOP = 1
        self.requestInterruption()
        self._log("🛑 Đang gửi tín hiệu dừng quy trình Muse AI...")

    def _should_stop(self) -> bool:
        return bool(self.STOP != 0 or self.isInterruptionRequested())

    def run(self) -> None:
        """EntryPoint của QThread chạy độc lập."""
        self._log(f"🎬 Bắt đầu chạy Muse AI Workflow qua REST API: '{self.project_name}' ({len(self.prompts)} prompts)...")
        self.video_folder_updated.emit(str(self.download_dir))

        try:
            self._run_api_pipeline()
        except Exception as exc:
            self._log(f"❌ Lỗi ngoài ý muốn trong quá trình thực thi: {exc}")
        finally:
            self._log("✨ Quy trình Muse AI Workflow đã kết thúc.")
            self.automation_complete.emit()

    def _run_api_pipeline(self) -> None:
        # 1. Đảm bảo Service Muse2API đang chạy
        if not MuseServiceManager.is_service_ready():
            self._log("🚀 Khởi động dịch vụ Muse2API Server ngầm...")
            ok = MuseServiceManager.start_service(timeout=15, log_callback=self._log)
            if not ok:
                self._log("❌ Không thể kết nối tới dịch vụ Muse2API Local Server.")
                return

        api_client = MuseAPIClient(log_callback=self._log)
        total = len(self.prompts)

        for idx, item in enumerate(self.prompts, start=1):
            if self._should_stop():
                self._log("⏹️ Người dùng đã yêu cầu dừng quy trình.")
                break

            prompt_id = str(item.get("id", idx))
            prompt_text = str(item.get("prompt") or "").strip()

            if not prompt_text:
                self._log(f"⏭️ Bỏ qua prompt #{idx} vì nội dung trống.")
                continue

            self._log(f"\n========================================================")
            self._log(f"🚀 [{idx}/{total}] Đang xử lý Prompt #{prompt_id}: {prompt_text[:80]}...")
            self._log(f"========================================================")

            self.video_updated.emit({
                "prompt_idx": prompt_id,
                "id": prompt_id,
                "prompt": prompt_text,
                "status": "PROCESSING",
                "progress": 10,
                "updated_at": datetime.now().strftime("%H:%M:%S"),
            })

            def on_progress(p_info: dict[str, Any]):
                self.video_updated.emit({
                    "prompt_idx": prompt_id,
                    "id": prompt_id,
                    "status": p_info.get("status", "PROCESSING"),
                    "progress": p_info.get("progress", 10),
                    "elapsed": p_info.get("elapsed", 0),
                    "updated_at": datetime.now().strftime("%H:%M:%S"),
                })

            effective_prompt = prompt_text
            if self.motion_boost:
                effective_prompt = PromptMotionEnhancer.enhance_motion(prompt_text, self.motion_level)

            # Tự động nhận diện tỉ lệ và thời lượng từ tiền tố prompt (tránh xung đột chỉ thị)
            eff_ar, eff_dur = parse_prompt_directives(
                prompt_text,
                default_ar=self.aspect_ratio,
                default_dur=self.duration_seconds_target,
            )

            # Ghi nhận log nếu người dùng nhập thời lượng vượt trần mô hình
            m_chk = re.search(r"(\d+)\s*(?:giây|giay|s\b|sec|seconds?)\b", prompt_text[:80].lower())
            if m_chk:
                try:
                    raw_val = int(m_chk.group(1))
                    if raw_val > MAX_MUSE_DURATION_SECONDS:
                        self._log(f"💡 Nhắc nhở: Mô hình Muse AI sinh tối đa 10s/shot. Đã tự động điều chỉnh từ {raw_val}s về {MAX_MUSE_DURATION_SECONDS}s.")
                except ValueError:
                    pass

            try:
                # 2. Gửi request tạo video lên REST API
                ref_img = item.get("reference_image") or self.project_data.get("reference_image") or self.project_data.get("reference_images")
                task_resp = api_client.create_video_task(
                    prompt=effective_prompt,
                    aspect_ratio=eff_ar,
                    duration=eff_dur,
                    timeout_seconds=self.timeout_seconds,
                    reference_image=ref_img,
                    account_id=self.account_id,
                )
                task_id = task_resp.get("id") or task_resp.get("task_id")

                # 3. Polling chờ server sinh xong
                task_res = api_client.wait_for_video(
                    task_id=task_id,
                    timeout_seconds=self.timeout_seconds,
                    on_progress=on_progress,
                    stop_check=self._should_stop,
                )

                status = str(task_res.get("status") or "").lower()
                if status in ("completed", "success", "succeeded", "done"):
                    video_url = task_res.get("url") or (task_res.get("video") or {}).get("url")
                    if not video_url and task_res.get("result"):
                        video_url = task_res["result"].get("url")

                    if not video_url:
                        raise MuseAPIError("Server báo completed nhưng không tìm thấy media URL")

                    clean_name = re.sub(r"[^\w\s-]", "", prompt_text[:30]).strip().replace(" ", "_")
                    filename = f"muse_{idx:03d}_{clean_name}.mp4"

                    saved_path = api_client.download_video(
                        media_url=video_url,
                        dest_dir=self.download_dir,
                        suggested_name=filename,
                    )

                    # Tùy chọn nội suy chuyển động 60fps khử giật
                    if self.auto_smooth_60fps and VideoMotionSmoother.is_ffmpeg_available():
                        try:
                            self._log("⚡ Đang tự động nội suy chuyển động quang học lên 60fps qua FFmpeg...")
                            smooth_path = VideoMotionSmoother.interpolate_to_60fps(
                                input_video=saved_path,
                                target_fps=60,
                                log_callback=self._log,
                            )
                            saved_path = smooth_path
                        except Exception as exc:
                            self._log(f"⚠️ Nội suy 60fps không thành công (vẫn giữ video gốc): {exc}")

                    self.video_updated.emit({
                        "prompt_idx": prompt_id,
                        "id": prompt_id,
                        "status": "SUCCESS",
                        "progress": 100,
                        "account": task_res.get("account") or task_res.get("account_id") or "",
                        "video_file": str(saved_path),
                        "duration": self.duration_seconds_target,
                        "elapsed": task_res.get("elapsed", 0),
                        "updated_at": datetime.now().strftime("%H:%M:%S"),
                    })
                else:
                    err = task_res.get("error") or "Tạo video thất bại trên server"
                    self._log(f"❌ Thất bại ở Prompt #{prompt_id}: {err}")
                    self.video_updated.emit({
                        "prompt_idx": prompt_id,
                        "id": prompt_id,
                        "status": "FAILED",
                        "error": err,
                        "updated_at": datetime.now().strftime("%H:%M:%S"),
                    })

            except Exception as e:
                self._log(f"❌ Lỗi xử lý Prompt #{prompt_id}: {e}")
                self.video_updated.emit({
                    "prompt_idx": prompt_id,
                    "id": prompt_id,
                    "status": "FAILED",
                    "error": str(e),
                    "updated_at": datetime.now().strftime("%H:%M:%S"),
                })

            if not self._should_stop() and idx < total:
                time.sleep(2.0)
