# -*- coding: utf-8 -*-
"""
Automated Unit Tests for End-to-End Shorts Studio Pipeline.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from muse_api_client import MuseAPIClient
from muse_service_manager import MUSE2API_KEY, MuseServiceManager
from shorts_composer import ShortsComposer
from shorts_script_engine import SceneItem, ShortsScriptEngine
from shorts_tts_engine import ShortsTTSEngine


@pytest.fixture(scope="session", autouse=True)
def ensure_muse_service():
    """Đảm bảo Muse2API service sẵn sàng trước khi chạy test."""
    if not MuseServiceManager.is_service_ready():
        MuseServiceManager.start_service(timeout=20)


def test_muse_chat_completions():
    """Kiểm tra Muse AI Chat API (POST /v1/chat/completions) trả lời đúng chuẩn OpenAI."""
    client = MuseAPIClient(
        base_url=MuseServiceManager.get_api_base_url(),
        api_key=MUSE2API_KEY,
    )
    res = client.chat_completions(
        messages=[{"role": "user", "content": "1 + 1 bằng mấy? Trả lời 1 từ duy nhất."}],
        timeout=60,
    )
    assert res is not None
    assert len(res.strip()) > 0
    assert "2" in res or "hai" in res.lower()


def test_shorts_script_parsing():
    """Kiểm tra parser Storyboard bóc tách JSON thành SceneItem."""
    engine = ShortsScriptEngine()
    mock_raw = """
    ```json
    [
      {
        "scene_index": 1,
        "voice_text": "Bạn có biết bí mật về hố đen vũ trụ?",
        "visual_prompt": "Cinematic vertical 9:16 shot of black hole accretion disk",
        "bgm_mood": "hook"
      },
      {
        "scene_index": 2,
        "voice_text": "Trọng lực ở đây mạnh tới mức ánh sáng cũng không thoát ra được.",
        "visual_prompt": "Hyper-realistic vertical 9:16 space distortion with glowing stars",
        "bgm_mood": "evidence"
      }
    ]
    ```
    """
    scenes = engine._parse_json_scenes(mock_raw, scene_count=2)
    assert len(scenes) == 2
    assert scenes[0].scene_index == 1
    assert "hố đen" in scenes[0].voice_text
    assert scenes[1].scene_index == 2
    assert scenes[1].bgm_mood == "evidence"


def test_shorts_tts_generation(tmp_path):
    """Kiểm tra Edge-TTS sinh file MP3 và file SRT đồng bộ."""
    tts = ShortsTTSEngine()
    audio_out = tmp_path / "test_voice.mp3"
    srt_out = tmp_path / "test_voice.srt"

    dur = tts.generate_speech(
        text="Xin chào các bạn, đây là video thử nghiệm hệ thống Shorts tự động.",
        output_audio_path=audio_out,
        output_sub_path=srt_out,
        voice="vi-VN-HoaiMyNeural",
    )
    assert audio_out.exists()
    assert audio_out.stat().st_size > 1000
    assert dur > 1.0
    assert srt_out.exists()
    srt_text = srt_out.read_text(encoding="utf-8")
    assert "-->" in srt_text
    assert "Xin chào" in srt_text


def test_shorts_composer_pipeline(tmp_path):
    """Kiểm tra ghép nối và mix BGM qua FFmpeg."""
    composer = ShortsComposer()
    tts = ShortsTTSEngine()

    audio_file = tmp_path / "scene_audio.mp3"
    sub_file = tmp_path / "scene_sub.srt"
    dur = tts.generate_speech("Khám phá vũ trụ bao la.", audio_file, sub_file)

    # Sử dụng video có sẵn trong DOWNLOADS nếu có
    sample_videos = list(Path("DOWNLOADS").rglob("*.mp4"))
    if not sample_videos:
        pytest.skip("Chưa có video MP4 mẫu trong thư mục DOWNLOADS để test ghép")

    v_sample = sample_videos[0]
    out_scene = tmp_path / "composed_scene.mp4"
    res_scene = composer.compose_single_scene(
        video_input=v_sample,
        audio_input=audio_file,
        output_scene=out_scene,
        audio_duration=dur,
        srt_input=sub_file,
        burn_subtitles=True,
    )
    assert res_scene.exists()
    assert res_scene.stat().st_size > 50000

    # Ghép 2 scene và mix BGM
    final_out = tmp_path / "final_stitched.mp4"
    bgm_path = Path("ah_bgm/hook/hook_01.mp3")
    res_final = composer.stitch_all_scenes(
        scene_videos=[res_scene, res_scene],
        output_final_video=final_out,
        bgm_path=bgm_path if bgm_path.exists() else None,
        bgm_volume=0.15,
    )
    assert res_final.exists()
    assert res_final.stat().st_size > res_scene.stat().st_size
