# -*- coding: utf-8 -*-
"""
Video Motion Smoother: Bộ xử lý làm mượt khung hình quang học (Optical Flow Frame Interpolation)
sử dụng FFmpeg minterpolate để chuyển đổi video AI từ 15-30fps thành 60fps mượt mà,
loại bỏ triệt để hiện tượng giật cục / ghép ảnh (slideshow / stop-motion effect).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

from runtime_media import resolve_ffmpeg_executable


class VideoMotionSmoother:
    """Xử lý nội suy khung hình chuyển động (Motion Compensation Interpolation) qua FFmpeg."""

    @classmethod
    def is_ffmpeg_available(cls) -> bool:
        return bool(resolve_ffmpeg_executable())

    @classmethod
    def interpolate_to_60fps(
        cls,
        input_video: Path | str,
        output_video: Path | str | None = None,
        target_fps: int = 60,
        crf: int = 18,
        preset: str = "fast",
        log_callback: Callable[[str], None] | None = None,
    ) -> Path:
        """Nội suy chuyển động bù trừ quang học (MCI/AOBMC) để tạo video 60fps siêu mượt."""
        ffmpeg_bin = resolve_ffmpeg_executable()
        if not ffmpeg_bin:
            raise RuntimeError("Không tìm thấy executable FFmpeg trên hệ thống.")

        input_path = Path(input_video).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file video nguồn: {input_path}")

        if output_video is None:
            output_path = input_path.parent / f"{input_path.stem}_smooth{target_fps}fps.mp4"
        else:
            output_path = Path(output_video).resolve()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        def _log(msg: str):
            if callable(log_callback):
                try:
                    log_callback(msg)
                except Exception:
                    pass
            print(msg)

        _log(f"⚡ [SMOOTH] Bắt đầu nội suy quang học khử giật lên {target_fps}fps: {input_path.name}...")
        t0 = time.time()

        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(input_path),
            "-vf", f"minterpolate=fps={target_fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            str(output_path),
        ]

        extra_kwargs = {}
        if os.name == "nt":
            extra_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **extra_kwargs)
        if res.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
            err = res.stderr[-400:] if res.stderr else "Lỗi không xác định từ ffmpeg"
            _log(f"❌ Nội suy thất bại: {err}")
            raise RuntimeError(f"FFmpeg motion interpolation error: {err}")

        elapsed = round(time.time() - t0, 1)
        orig_mb = input_path.stat().st_size / (1024 * 1024)
        new_mb = output_path.stat().st_size / (1024 * 1024)
        _log(f"🎉 Đã làm mượt thành công video 60fps ({elapsed}s)! Dung lượng: {orig_mb:.2f}MB ➡️ {new_mb:.2f}MB")
        _log(f"📁 File thành phẩm siêu mượt: {output_path.name}")
        return output_path
