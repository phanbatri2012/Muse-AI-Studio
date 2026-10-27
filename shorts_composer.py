# -*- coding: utf-8 -*-
"""
Shorts Composer using FFmpeg.
Assembles AI video clips, voiceover audio, dynamic subtitles, and background music (BGM).
Features smart temporal sync, audio ducking, and TikTok/Shorts style subtitle styling.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from runtime_media import resolve_ffmpeg_executable

logger = logging.getLogger("shorts_composer")


def _get_ffmpeg() -> str:
    exe = resolve_ffmpeg_executable()
    if not exe:
        raise RuntimeError("Không tìm thấy executable FFmpeg trên hệ thống.")
    return exe


def _escape_path_for_ffmpeg_filter(path: Path | str) -> str:
    """Escape đường dẫn file cho các filter FFmpeg trên Windows (subtitles=...)."""
    p = str(Path(path).resolve()).replace("\\", "/")
    # Escape dấu hai chấm sau ổ đĩa C: -> C\:
    if len(p) >= 2 and p[1] == ":":
        p = p[0] + "\\:" + p[2:]
    return p


def _run_ffmpeg_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    """Chạy lệnh FFmpeg ẩn cửa sổ console trên Windows."""
    kwargs: dict[str, Any] = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"}
    if os.name == "nt":
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            kwargs["startupinfo"] = si
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        except Exception:
            pass
    return subprocess.run(cmd, **kwargs)


class ShortsComposer:
    """Bộ dựng và hoàn thiện video ngắn đa phân cảnh bằng FFmpeg."""

    def __init__(self, log_callback: Callable[[str], None] | None = None) -> None:
        self.log_callback = log_callback

    def _log(self, msg: str) -> None:
        if callable(self.log_callback):
            try:
                self.log_callback(msg)
                return
            except Exception:
                pass
        print(f"[SHORTS_COMPOSER] {msg}")

    def compose_single_scene(
        self,
        video_input: Path | str,
        audio_input: Path | str,
        output_scene: Path | str,
        audio_duration: float,
        srt_input: Path | str | None = None,
        burn_subtitles: bool = True,
    ) -> Path:
        """
        Đồng bộ 1 phân cảnh: Cắt/loop video theo đúng độ dài audio, ghép âm thanh và burn phụ đề.
        """
        ffmpeg = _get_ffmpeg()
        v_in = Path(video_input).resolve()
        a_in = Path(audio_input).resolve()
        out = Path(output_scene).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        dur_str = f"{audio_duration:.3f}"
        self._log(f"🎬 Đang dựng phân cảnh ({dur_str}s): {v_in.name} + {a_in.name}...")

        # Xây dựng video filter
        vf_filters = []
        if burn_subtitles and srt_input and Path(srt_input).exists():
            esc_srt = _escape_path_for_ffmpeg_filter(srt_input)
            # Phong cách phụ đề Shorts/TikTok: Chữ vàng viền đen đậm, font to, căn giữa 75% chiều cao màn hình
            sub_style = (
                "FontSize=18,FontName=Arial,Bold=1,PrimaryColour=&H00FFFF,"
                "OutlineColour=&H000000,BorderStyle=1,Outline=2.5,Shadow=0.5,"
                "Alignment=2,MarginV=70"
            )
            vf_filters.append(f"subtitles='{esc_srt}':force_style='{sub_style}'")

        cmd = [ffmpeg, "-y"]

        # Nếu audio dài hơn 6s, cho video loop để không bị đen màn hình
        if audio_duration > 6.0:
            cmd.extend(["-stream_loop", "-1"])

        cmd.extend([
            "-i", str(v_in),
            "-i", str(a_in),
            "-t", dur_str,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
        ])

        if vf_filters:
            cmd.extend(["-vf", ",".join(vf_filters)])

        cmd.append(str(out))

        res = _run_ffmpeg_cmd(cmd)
        if res.returncode != 0 or not out.exists():
            err_msg = (res.stderr or "Unknown error")[-500:]
            raise RuntimeError(f"Lỗi dựng phân cảnh ({v_in.name}): {err_msg}")

        self._log(f"✅ Hoàn tất phân cảnh: {out.name} ({out.stat().st_size:,} bytes)")
        return out

    def stitch_all_scenes(
        self,
        scene_videos: list[Path | str],
        output_final_video: Path | str,
        bgm_path: Path | str | None = None,
        bgm_volume: float = 0.15,
    ) -> Path:
        """
        Nối tất cả các phân cảnh thành 1 video hoàn chỉnh và trộn nhạc nền (BGM Audio Ducking).
        """
        if not scene_videos:
            raise ValueError("Danh sách phân cảnh không được để trống")

        ffmpeg = _get_ffmpeg()
        final_out = Path(output_final_video).resolve()
        final_out.parent.mkdir(parents=True, exist_ok=True)

        self._log(f"🎞️ Đang ghép nối {len(scene_videos)} phân cảnh thành video thành phẩm...")

        # Tạo file danh sách concat
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as tf:
            concat_list = tf.name
            for s in scene_videos:
                safe_path = str(Path(s).resolve()).replace("'", "'\\''")
                tf.write(f"file '{safe_path}'\n")

        temp_stitched = final_out.parent / f"_temp_stitched_{final_out.name}"

        try:
            # 1. Ghép nối các phân cảnh
            cmd_concat = [
                ffmpeg, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list,
                "-c", "copy",
                str(temp_stitched),
            ]
            res_c = _run_ffmpeg_cmd(cmd_concat)
            if res_c.returncode != 0 or not temp_stitched.exists():
                # Re-encode fallback nếu copy thất bại
                cmd_reencode = [
                    ffmpeg, "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_list,
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-c:a", "aac",
                    str(temp_stitched),
                ]
                res_re = _run_ffmpeg_cmd(cmd_reencode)
                if res_re.returncode != 0 or not temp_stitched.exists():
                    raise RuntimeError(f"Ghép video thất bại: {res_re.stderr[-400:]}")

            # 2. Trộn nhạc nền BGM nếu có
            if bgm_path and Path(bgm_path).exists():
                bgm_p = Path(bgm_path).resolve()
                self._log(f"🎵 Đang trộn nhạc nền ({bgm_p.name}) với âm lượng ducking {int(bgm_volume * 100)}%...")

                # Filter amix: Voiceover 100% + BGM ducking, kết thúc đúng lúc hết video
                filter_complex = (
                    f"[0:a]volume=1.0[a_voice];"
                    f"[1:a]volume={bgm_volume:.2f}[a_bgm];"
                    f"[a_voice][a_bgm]amix=inputs=2:duration=first:dropout_transition=2[a_out]"
                )

                cmd_bgm = [
                    ffmpeg, "-y",
                    "-i", str(temp_stitched),
                    "-stream_loop", "-1",
                    "-i", str(bgm_p),
                    "-filter_complex", filter_complex,
                    "-map", "0:v:0",
                    "-map", "[a_out]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    str(final_out),
                ]
                res_bgm = _run_ffmpeg_cmd(cmd_bgm)
                if res_bgm.returncode == 0 and final_out.exists():
                    self._log(f"🎉 Hoàn tất trộn nhạc nền thành công!")
                else:
                    self._log(f"⚠️ Trộn BGM gặp lỗi, xuất video gốc: {res_bgm.stderr[-300:]}")
                    temp_stitched.rename(final_out)
            else:
                temp_stitched.rename(final_out)

        finally:
            if os.path.exists(concat_list):
                try:
                    os.remove(concat_list)
                except Exception:
                    pass
            if temp_stitched.exists():
                try:
                    temp_stitched.unlink()
                except Exception:
                    pass

        self._log(f"🏆 [HOÀN TẤT] Video Shorts hoàn chỉnh đã xuất tại: {final_out}")
        return final_out
