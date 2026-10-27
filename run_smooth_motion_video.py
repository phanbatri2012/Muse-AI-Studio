# -*- coding: utf-8 -*-
"""
Script tạo video với kỹ thuật Kinematic Monoflow & Chuyển Động Siêu Mượt (Ultra Smooth Motion).
Giải quyết triệt để vấn đề video bị giật / cảm giác ghép nhiều ảnh bằng:
1. Prompt động học đơn trục (Monoflow): FPV Drone lướt êm trên sông băng ngọc bích.
2. Từ khóa neo khử giật (Anti-stutter keywords): buttery smooth continuous forward glide, zero camera shake.
3. Tùy chọn hậu kỳ nội suy quang học (Motion Interpolation 60fps) qua FFmpeg.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muse_api_client import MuseAPIClient
from muse_service_manager import MUSE2API_KEY, MuseServiceManager


def smooth_video_ffmpeg(input_path: Path, output_path: Path, target_fps: int = 60) -> bool:
    """Nội suy chuyển động bù trừ quang học (MCI) qua FFmpeg để khử sạch hiện tượng giật."""
    print(f"\n⚡ [HẬU KỲ] Đang nội suy khung hình quang học lên {target_fps}fps qua FFmpeg...")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", f"minterpolate=fps={target_fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "copy",
        str(output_path),
    ]
    t0 = time.time()
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
        elapsed = round(time.time() - t0, 1)
        print(f"✅ Đã tạo video 60fps siêu mượt thành công sau {elapsed}s! File: {output_path.name}")
        return True
    else:
        print(f"⚠️ Hậu kỳ nội suy không thành công: {res.stderr[-300:]}")
        return False


def main():
    print("=" * 75)
    print("🌊 [ULTRA SMOOTH VIDEO] TẠO VIDEO CHUYỂN ĐỘNG SIÊU MƯỢT KHÔNG GIẬT")
    print("=" * 75)

    if not MuseServiceManager.is_service_ready():
        MuseServiceManager.start_service(timeout=20, log_callback=print)

    client = MuseAPIClient(
        base_url=MuseServiceManager.get_api_base_url(),
        api_key=MUSE2API_KEY,
        log_callback=print,
    )

    # Prompt thiết kế theo nguyên lý Kinematic Monoflow:
    # 1 trục chuyển động camera tịnh tiến duy nhất (Forward tracking glide), loại bỏ các vật thể chuyển động chéo nhau
    smooth_prompt = (
        "An FPV drone gliding smoothly and seamlessly forward through a breathtaking alpine mountain canyon at golden hour, "
        "flying low and steadily over a crystal clear turquoise glacial river, buttery smooth continuous forward motion, "
        "ultra fluid gimbal glide, seamless motion blur, zero camera shake, cinematic slow-motion 60fps, "
        "perfect temporal coherence, hyper-realistic 8k"
    )

    print(f"\n🎬 [PROMPT SIÊU MƯỢT]:\n\"{smooth_prompt}\"\n")
    print("📐 Cấu hình: 9:16 (Dọc TikTok/Shorts), Thời lượng: 6 giây")

    task_res = client.create_video_task(
        prompt=smooth_prompt,
        aspect_ratio="9:16",
        duration=6,
        timeout_seconds=360,
    )
    task_id = task_res.get("id") or task_res.get("task_id")
    print(f"✅ Đã tạo task: {task_id}")

    def on_progress(p):
        status = p.get("status")
        progress = p.get("progress", 0)
        elapsed = p.get("elapsed", "")
        print(f"  [TIẾN ĐỘ] Status: {status} | Progress: {progress}% | Elapsed: {elapsed}s", flush=True)

    result = client.poll_video_task(task_id, timeout=360, on_progress=on_progress)
    if result.get("status") != "completed":
        print(f"❌ Sinh video thất bại: {result.get('error')}")
        sys.exit(1)

    video_url = (result.get("video") or {}).get("url") or result.get("url")
    if not video_url and result.get("result"):
        video_url = result["result"].get("url")

    out_dir = ROOT / "DOWNLOADS" / "smooth_gallery"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_file = client.download_video(video_url, out_dir, suggested_name=f"smooth_fpv_{task_id[:10]}.mp4")
    print(f"\n✅ Video gốc từ AI đã lưu tại: {raw_file}")
    print(f"  Dung lượng: {raw_file.stat().st_size / (1024*1024):.2f} MB")

    # Tùy chọn nâng cấp lên 60fps nội suy quang học
    smooth_60fps_file = out_dir / f"smooth_fpv_{task_id[:10]}_60fps.mp4"
    smooth_video_ffmpeg(raw_file, smooth_60fps_file, target_fps=60)

    print("\n" + "=" * 75)
    print("🎉 HOÀN THÀNH QUY TRÌNH TẠO VIDEO CHUYỂN ĐỘNG SIÊU MƯỢT!")
    print(f"1. Bản gốc (AI Native Smooth): {raw_file}")
    print(f"2. Bản nâng cấp (60fps Interpolated): {smooth_60fps_file}")
    print("=" * 75)


if __name__ == "__main__":
    main()
