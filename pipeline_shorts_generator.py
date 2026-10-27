# -*- coding: utf-8 -*-
"""
End-to-End Shorts Generator Pipeline.
Orchestrates the entire automated workflow:
Topic -> Muse AI Chat Script -> Edge-TTS Audio/Subtitles -> Muse AI Video -> 60fps MCI -> FFmpeg BGM Composer -> Final Video.
100% powered by local muse2api backend, Edge-TTS, and FFmpeg.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muse_api_client import MuseAPIClient
from muse_service_manager import MUSE2API_KEY, MuseServiceManager
from shorts_composer import ShortsComposer
from shorts_script_engine import SceneItem, ShortsScriptEngine
from shorts_tts_engine import DEFAULT_VOICE, SUPPORTED_VOICES, ShortsTTSEngine
from video_motion_smoother import VideoMotionSmoother

logger = logging.getLogger("pipeline_shorts_generator")


def _pick_bgm(mood: str = "hook") -> Path | None:
    """Chọn ngẫu nhiên một bản nhạc nền từ thư viện ah_bgm tương ứng với mood."""
    bgm_dir = ROOT / "ah_bgm"
    target_folder = bgm_dir / mood
    if not target_folder.exists():
        target_folder = bgm_dir / "hook"
    if not target_folder.exists():
        return None

    mp3_files = list(target_folder.glob("*.mp3"))
    if mp3_files:
        return random.choice(mp3_files)
    return None


class PipelineShortsGenerator:
    """Bộ điều phối sản xuất video ngắn tự động toàn diện từ A-Z."""

    def __init__(
        self,
        log_callback: Callable[[str], None] | None = None,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> None:
        self.log_callback = log_callback
        self.progress_callback = progress_callback

        # Đảm bảo dịch vụ Muse2API sẵn sàng
        if not MuseServiceManager.is_service_ready():
            self._log("🔄 Khởi động Muse2API service...")
            MuseServiceManager.start_service(timeout=25, log_callback=self.log_callback)

        self.api_client = MuseAPIClient(
            base_url=MuseServiceManager.get_api_base_url(),
            api_key=MUSE2API_KEY,
            log_callback=self.log_callback,
        )
        self.script_engine = ShortsScriptEngine(api_client=self.api_client, log_callback=self.log_callback)
        self.tts_engine = ShortsTTSEngine(log_callback=self.log_callback)
        self.composer = ShortsComposer(log_callback=self.log_callback)

    def _log(self, msg: str) -> None:
        if callable(self.log_callback):
            try:
                self.log_callback(msg)
                return
            except Exception:
                pass
        print(f"[SHORTS_PIPELINE] {msg}")

    def _set_progress(self, percent: float, status_msg: str) -> None:
        self._log(f"📊 [{int(percent)}%] {status_msg}")
        if callable(self.progress_callback):
            try:
                self.progress_callback(percent, status_msg)
            except Exception:
                pass

    def run(
        self,
        topic: str = "",
        custom_scenes: list[SceneItem] | None = None,
        scene_count: int = 3,
        aspect_ratio: str = "9:16",
        voice: str = DEFAULT_VOICE,
        bgm_mood: str = "hook",
        smooth_60fps: bool = False,
        burn_subtitles: bool = True,
        output_dir: Path | None = None,
        video_timeout_per_scene: int = 480,
    ) -> Path:
        """
        Thực thi toàn bộ quy trình sản xuất video Shorts từ đầu đến cuối.
        """
        out_root = output_dir or (ROOT / "DOWNLOADS" / "shorts_studio")
        session_id = f"shorts_{time.strftime('%Y%m%d_%H%M%S')}"
        work_dir = out_root / session_id
        work_dir.mkdir(parents=True, exist_ok=True)

        self._log("=" * 70)
        self._log(f"🚀 BẮT ĐẦU SẢN XUẤT VIDEO SHORTS: '{topic or 'Custom Script'}'")
        self._log(f"📁 Thư mục tác vụ: {work_dir}")
        self._log("=" * 70)

        # -------------------------------------------------------------
        # Bước 1: Kịch bản Storyboard (10%)
        # -------------------------------------------------------------
        self._set_progress(5, "Đang khởi tạo kịch bản phân cảnh...")
        if custom_scenes:
            scenes = custom_scenes
            self._log(f"📝 Sử dụng kịch bản người dùng cung cấp ({len(scenes)} cảnh).")
        else:
            if not topic.strip():
                raise ValueError("Cần cung cấp chủ đề hoặc danh sách kịch bản phân cảnh.")
            scenes = self.script_engine.generate_storyboard(
                topic=topic,
                scene_count=scene_count,
                aspect_ratio=aspect_ratio,
            )

        # Lưu storyboard.json
        storyboard_file = work_dir / "storyboard.json"
        storyboard_data = [s.to_dict() for s in scenes]
        storyboard_file.write_text(json.dumps(storyboard_data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._set_progress(15, f"Đã lưu kịch bản {len(scenes)} phân cảnh.")

        # -------------------------------------------------------------
        # Bước 2: Sinh Voiceover Audio & Subtitles (25%)
        # -------------------------------------------------------------
        audio_durations: list[float] = []
        for s in scenes:
            self._set_progress(
                15 + (s.scene_index / len(scenes)) * 10,
                f"Đang tạo giọng đọc cảnh {s.scene_index}/{len(scenes)}...",
            )
            audio_path = work_dir / f"scene_{s.scene_index:02d}_voice.mp3"
            sub_path = work_dir / f"scene_{s.scene_index:02d}_sub.srt"

            dur = self.tts_engine.generate_speech(
                text=s.voice_text,
                output_audio_path=audio_path,
                output_sub_path=sub_path,
                voice=voice,
            )
            s.audio_path = str(audio_path)
            s.sub_path = str(sub_path)
            s.estimated_seconds = dur
            audio_durations.append(dur)

        total_audio_sec = sum(audio_durations)
        self._log(f"🎙️ Tổng thời lượng giọng đọc: {total_audio_sec:.1f} giây.")

        # -------------------------------------------------------------
        # Bước 3: Sinh Video từ Muse AI API (70%)
        # -------------------------------------------------------------
        time.sleep(2.0)
        raw_video_paths: list[Path] = []
        for idx, s in enumerate(scenes, start=1):
            progress_base = 25 + (idx - 1) / len(scenes) * 45
            self._set_progress(
                progress_base,
                f"Đang gửi yêu cầu sinh video cảnh {idx}/{len(scenes)} lên Muse AI...",
            )

            # Cơ chế Self-Healing Retry (tối đa 2 lần nếu Cloud AI trục trặc)
            poll_res = None
            max_attempts = 2
            for attempt in range(1, max_attempts + 1):
                if attempt > 1:
                    self._log(f"🔄 Đang tự động thử lại cảnh {idx} (Lần {attempt}/{max_attempts})...")
                    time.sleep(3.0)

                task_res = self.api_client.create_video_task(
                    prompt=s.visual_prompt,
                    aspect_ratio=aspect_ratio,
                    duration=6,
                    timeout_seconds=video_timeout_per_scene,
                    reference_image=getattr(s, "reference_image", None),
                )
                task_id = task_res.get("id") or task_res.get("task_id")
                self._log(f"🎬 Cảnh {idx} đã tiếp nhận (Task ID: {task_id}). Đang chờ Cloud GPU render...")

                def _on_poll(p):
                    pct = p.get("progress", 0)
                    sub_progress = progress_base + (pct / 100.0) * (45.0 / len(scenes))
                    self._set_progress(
                        sub_progress,
                        f"Cảnh {idx}/{len(scenes)} render: {pct}%...",
                    )

                poll_res = self.api_client.poll_video_task(
                    task_id=task_id,
                    timeout=video_timeout_per_scene,
                    on_progress=_on_poll,
                )

                if poll_res.get("status") == "completed":
                    break
                else:
                        self._log(f"⚠️ Cảnh {idx} gặp sự cố ở lần {attempt}: {poll_res.get('error')}")

            if not poll_res or poll_res.get("status") != "completed":
                    raise RuntimeError(f"Cảnh {idx} thất bại sau {max_attempts} lần thử: {poll_res.get('error') if poll_res else 'Unknown'}")

            v_url = (poll_res.get("video") or {}).get("url") or poll_res.get("url")
            raw_v_file = self.api_client.download_video(
                media_url=v_url,
                dest_dir=work_dir,
                suggested_name=f"scene_{idx:02d}_raw.mp4",
            )

            # Làm mượt 60fps qua FFmpeg MCI nếu được chọn
            if smooth_60fps and VideoMotionSmoother.is_ffmpeg_available():
                self._log(f"⚡ Đang nội suy quang học 60fps cho cảnh {idx}...")
                smooth_file = work_dir / f"scene_{idx:02d}_smooth60.mp4"
                try:
                    VideoMotionSmoother.interpolate_to_60fps(
                        input_video=raw_v_file,
                        output_video=smooth_file,
                        target_fps=60,
                        log_callback=self._log,
                    )
                    s.video_path = str(smooth_file)
                    raw_video_paths.append(smooth_file)
                except Exception as e:
                    self._log(f"⚠️ Nội suy 60fps cảnh {idx} lỗi ({e}), dùng bản gốc.")
                    s.video_path = str(raw_v_file)
                    raw_video_paths.append(raw_v_file)
            else:
                s.video_path = str(raw_v_file)
                raw_video_paths.append(raw_v_file)

        # -------------------------------------------------------------
        # Bước 4: Dựng & Đồng bộ từng phân cảnh (85%)
        # -------------------------------------------------------------
        composed_scene_paths: list[Path] = []
        for idx, s in enumerate(scenes, start=1):
            self._set_progress(70 + (idx / len(scenes)) * 15, f"Đang dựng và khớp phụ đề cảnh {idx}...")
            composed_out = work_dir / f"scene_{idx:02d}_composed.mp4"
            out_c = self.composer.compose_single_scene(
                video_input=s.video_path,
                audio_input=s.audio_path,
                output_scene=composed_out,
                audio_duration=s.estimated_seconds,
                srt_input=s.sub_path if burn_subtitles else None,
                burn_subtitles=burn_subtitles,
            )
            composed_scene_paths.append(out_c)

        # -------------------------------------------------------------
        # Bước 5: Ghép toàn bộ và mix BGM Audio Ducking (100%)
        # -------------------------------------------------------------
        self._set_progress(90, "Đang ghép nối toàn bộ phân cảnh và hòa âm nhạc nền...")
        final_video_name = f"{session_id}_final_completed.mp4"
        final_video_path = out_root / final_video_name

        bgm_file = _pick_bgm(mood=bgm_mood)
        final_out = self.composer.stitch_all_scenes(
            scene_videos=composed_scene_paths,
            output_final_video=final_video_path,
            bgm_path=bgm_file,
            bgm_volume=0.15,
        )

        self._set_progress(100, f"Hoàn tất! Video đã lưu tại: {final_out.name}")
        self._log("=" * 70)
        self._log(f"🎉 [XUẤT SẮC] ĐÃ TẠO THÀNH CÔNG VIDEO SHORTS HOÀN CHỈNH!")
        self._log(f"📁 Video thành phẩm: {final_out}")
        self._log(f"⏱️ Tổng thời lượng: {total_audio_sec:.1f}s | Dung lượng: {final_out.stat().st_size / (1024*1024):.2f} MB")
        self._log("=" * 70)
        return final_out


def main():
    parser = argparse.ArgumentParser(description="End-to-End Shorts Generator với Muse AI API")
    parser.add_argument("--topic", type=str, default="Bí ẩn tam giác quỷ Bermuda", help="Chủ đề video")
    parser.add_argument("--scenes", type=int, default=3, help="Số phân cảnh (mặc định: 3)")
    parser.add_argument("--voice", type=str, default=DEFAULT_VOICE, choices=list(SUPPORTED_VOICES.keys()), help="Giọng đọc Edge-TTS")
    parser.add_argument("--mood", type=str, default="hook", choices=["hook", "evidence", "concrete_scene", "modern_mirror"], help="Mood nhạc nền")
    parser.add_argument("--smooth", action="store_true", default=False, help="Nội suy làm mượt 60fps MCI")
    parser.add_argument("--no-sub", action="store_true", help="Không burn phụ đề")
    args = parser.parse_args()

    pipeline = PipelineShortsGenerator(log_callback=print)
    pipeline.run(
        topic=args.topic,
        scene_count=args.scenes,
        voice=args.voice,
        bgm_mood=args.mood,
        smooth_60fps=args.smooth,
        burn_subtitles=not args.no_sub,
    )


if __name__ == "__main__":
    main()
