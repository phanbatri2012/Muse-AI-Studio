# -*- coding: utf-8 -*-
"""
Shorts TTS & Subtitle Engine using Edge-TTS and FFprobe.
Converts voiceover text into natural speech MP3 and generates synchronized SRT subtitles.
Supports high-quality Vietnamese and English neural voices with zero API costs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from runtime_media import resolve_ffmpeg_executable

logger = logging.getLogger("shorts_tts_engine")

SUPPORTED_VOICES = {
    "vi-VN-HoaiMyNeural": "Nữ Việt Nam (Hoài My - Ấm áp, truyền cảm)",
    "vi-VN-NamMinhNeural": "Nam Việt Nam (Nam Minh - Phóng sự, lôi cuốn)",
    "en-US-ChristopherNeural": "Nam Tiếng Anh (Christopher - Điện ảnh)",
    "en-US-JennyNeural": "Nữ Tiếng Anh (Jenny - Năng động, tự nhiên)",
    "en-US-GuyNeural": "Nam Tiếng Anh (Guy - Trầm hùng)",
}

DEFAULT_VOICE = "vi-VN-HoaiMyNeural"


def _format_srt_time(ms: int) -> str:
    """Đổi mili-giây thành định dạng thời gian SRT: 00:00:00,000"""
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    milliseconds = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


class ShortsTTSEngine:
    """Bộ chuyển đổi văn bản thành giọng đọc và phụ đề đồng bộ cho video ngắn."""

    def __init__(self, log_callback: Callable[[str], None] | None = None) -> None:
        self.log_callback = log_callback

    def _log(self, msg: str) -> None:
        if callable(self.log_callback):
            try:
                self.log_callback(msg)
                return
            except Exception:
                pass
        print(f"[SHORTS_TTS] {msg}")

    def generate_speech(
        self,
        text: str,
        output_audio_path: Path,
        output_sub_path: Path | None = None,
        voice: str = DEFAULT_VOICE,
        rate: str = "+0%",
        volume: str = "+0%",
    ) -> float:
        """
        Sinh file âm thanh MP3 và file phụ đề SRT từ văn bản.
        Trả về thời lượng thực tế của file âm thanh (tính bằng giây).
        """
        text_clean = text.strip()
        if not text_clean:
            raise ValueError("Văn bản câu thoại không được để trống")

        output_audio_path.parent.mkdir(parents=True, exist_ok=True)
        if output_sub_path:
            output_sub_path.parent.mkdir(parents=True, exist_ok=True)

        self._log(f"🎙️ Đang tạo giọng đọc ({voice}): \"{text_clean[:40]}...\"")

        try:
            asyncio.run(
                self._async_generate(
                    text=text_clean,
                    output_audio=output_audio_path,
                    output_sub=output_sub_path,
                    voice=voice,
                    rate=rate,
                    volume=volume,
                )
            )
        except Exception as e:
            self._log(f"❌ Lỗi sinh âm thanh qua Edge-TTS: {e}")
            raise RuntimeError(f"Edge-TTS failed: {e}") from e

        duration = self.get_audio_duration(output_audio_path)
        self._log(f"✅ Đã tạo âm thanh thành công ({duration:.2f}s) tại: {output_audio_path.name}")
        return duration

    async def _async_generate(
        self,
        text: str,
        output_audio: Path,
        output_sub: Path | None,
        voice: str,
        rate: str,
        volume: str,
    ) -> None:
        import edge_tts

        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, volume=volume)
        submaker = edge_tts.SubMaker() if output_sub else None

        with open(output_audio, "wb") as audio_file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_file.write(chunk["data"])
                elif submaker and chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                    submaker.feed(chunk)

        # Xuất file phụ đề SRT nếu được yêu cầu
        if output_sub and submaker:
            srt_content = submaker.get_srt()
            if not srt_content.strip():
                # Fallback nếu không có boundary chunk
                dur = self.get_audio_duration(output_audio)
                dur_ms = int(dur * 1000)
                srt_content = f"1\n00:00:00,100 --> {_format_srt_time(dur_ms)}\n{text}\n"
            output_sub.write_text(srt_content, encoding="utf-8")

    @classmethod
    def get_audio_duration(cls, audio_path: Path | str) -> float:
        """Đo thời lượng file audio bằng FFprobe hoặc thư viện liên quan."""
        ffmpeg_bin = resolve_ffmpeg_executable()
        ffprobe_bin = "ffprobe"
        if ffmpeg_bin:
            candidate = Path(ffmpeg_bin).parent / "ffprobe.exe"
            if candidate.exists():
                ffprobe_bin = str(candidate)

        cmd = [
            ffprobe_bin,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(res.stdout.strip())
        except Exception:
            # Fallback tính toán thô nếu ffprobe không đọc được
            size = Path(audio_path).stat().st_size
            # Ước lượng mp3 128kbps = 16000 bytes/s
            return max(1.0, size / 16000.0)
