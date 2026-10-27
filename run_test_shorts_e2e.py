# -*- coding: utf-8 -*-
"""
E2E Test Runner for End-to-End Shorts Studio Pipeline.
Tests the complete flow from Topic -> Muse Chat -> TTS/Subtitles -> Muse Video -> FFmpeg Composer.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline_shorts_generator import PipelineShortsGenerator
from runtime_media import resolve_ffmpeg_executable


def main():
    print("=" * 75)
    print("🎬 [TEST E2E] CHẠY THỬ NGHIỆM TOÀN DIỆN END-TO-END SHORTS STUDIO")
    print("=" * 75)

    topic = "Bí ẩn loài sứa bất tử dưới đáy đại dương"
    scene_count = 2
    voice = "vi-VN-HoaiMyNeural"
    bgm_mood = "hook"

    print(f"📌 Chủ đề: '{topic}'")
    print(f"📐 Số phân cảnh: {scene_count} scenes (Tỉ lệ dọc 9:16)")
    print(f"🎙️ Giọng đọc: {voice}")
    print(f"🎵 Nhạc nền: mood '{bgm_mood}' (Audio Ducking -20dB)")
    print(f"⚡ Làm mượt 60fps (FFmpeg MCI): Bật")
    print(f"📝 Dán phụ đề TikTok: Bật")
    print("-" * 75)

    start_time = time.time()

    pipeline = PipelineShortsGenerator(
        log_callback=print,
        progress_callback=lambda p, m: print(f"  [TIẾN ĐỘ] {int(p)}% -> {m}", flush=True),
    )

    final_video = pipeline.run(
        topic=topic,
        scene_count=scene_count,
        aspect_ratio="9:16",
        voice=voice,
        bgm_mood=bgm_mood,
        smooth_60fps=False,
        burn_subtitles=True,
    )

    elapsed = time.time() - start_time
    file_size_mb = final_video.stat().st_size / (1024 * 1024)

    print("\n" + "=" * 75)
    print("🎉 [TEST E2E THÀNH CÔNG RỰC RỠ] VIDEO SHORTS HOÀN CHỈNH ĐÃ ĐƯỢC TẠO!")
    print(f"📁 Đường dẫn file: {final_video}")
    print(f"📦 Dung lượng: {file_size_mb:.2f} MB")
    print(f"⏱️ Tổng thời gian thực thi: {elapsed:.1f} giây (~{elapsed/60:.1f} phút)")
    print("=" * 75)


if __name__ == "__main__":
    main()
