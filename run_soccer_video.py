# -*- coding: utf-8 -*-
"""
Script chạy Text-to-Video với prompt bóng đá mới của người dùng (nguyên bản 100%).
Prompt:
"A professional soccer player and several defending players, skillfully dribbling a soccer ball, dodging tackles with swift moves, and finishing with a powerful strike into the net, on a lush green stadium pitch with a cheering crowd in the background. Dynamic tracking shot following the player's movement. Cinematic lighting. Photorealistic, highly detailed, realistic motion, 4k resolution."
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muse_api_client import MuseAPIClient
from muse_service_manager import MUSE2API_KEY, MuseServiceManager
from video_motion_smoother import VideoMotionSmoother


def main():
    print("=" * 75)
    print("⚽ [TEXT-TO-VIDEO V2] TẠO VIDEO BÓNG ĐÁ VỚI PROMPT MỚI NGUYÊN BẢN")
    print("=" * 75)

    # 1. Đảm bảo server đang chạy
    if not MuseServiceManager.is_service_ready():
        print("🔄 Khởi động dịch vụ Muse2API...")
        MuseServiceManager.start_service(timeout=25, log_callback=print)

    print("🟢 Muse2API Service sẵn sàng tại:", MuseServiceManager.get_api_base_url())

    client = MuseAPIClient(
        base_url=MuseServiceManager.get_api_base_url(),
        api_key=MUSE2API_KEY,
        log_callback=print,
    )

    # 2. Prompt mới nguyên bản 100% của người dùng
    user_prompt_v2 = (
        "A professional soccer player and several defending players, skillfully dribbling a soccer ball, "
        "dodging tackles with swift moves, and finishing with a powerful strike into the net, "
        "on a lush green stadium pitch with a cheering crowd in the background. "
        "Dynamic tracking shot following the player's movement. Cinematic lighting. "
        "Photorealistic, highly detailed, realistic motion, 4k resolution."
    )

    print(f"\n🎬 [PROMPT MỚI]:\n\"{user_prompt_v2}\"\n")
    print("📐 Cấu hình: 16:9 (Widescreen 1280x720), Thời lượng: 6 giây")

    # 3. Gửi yêu cầu sinh video lên REST API
    task_res = client.create_video_task(
        prompt=user_prompt_v2,
        aspect_ratio="16:9",
        duration=6,
        timeout_seconds=600,
    )
    task_id = task_res.get("id") or task_res.get("task_id")
    print(f"✅ Đã tiếp nhận tác vụ thành công! Task ID: {task_id}")

    # 4. Polling tiến độ thời gian thực
    def on_progress(p):
        status = p.get("status")
        progress = p.get("progress", 0)
        elapsed = p.get("elapsed", "")
        print(f"  [TIẾN ĐỘ] Status: {status} | Progress: {progress}% | Elapsed: {elapsed}s", flush=True)

    print("\n⏳ Đang render trên Cloud GPU của Meta AI...")
    result = client.poll_video_task(task_id, timeout=600, on_progress=on_progress)

    status = result.get("status")
    if status != "completed":
        print(f"\n❌ Tác vụ thất bại: {result.get('error')}")
        sys.exit(1)

    # 5. Tải video MP4 về thư mục DOWNLOADS/soccer_v2
    video_url = (result.get("video") or {}).get("url") or result.get("url")
    if not video_url and result.get("result"):
        video_url = result["result"].get("url")

    out_dir = ROOT / "DOWNLOADS" / "soccer_new_account"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_file = client.download_video(video_url, out_dir, suggested_name=f"soccer_v2_{task_id[:10]}.mp4")
    raw_size_mb = raw_file.stat().st_size / (1024 * 1024)
    print(f"\n✅ Video bản gốc (30fps) đã tải về: {raw_file}")
    print(f"  Dung lượng: {raw_size_mb:.2f} MB")

    # 6. Tự động nội suy chuyển động 60fps qua FFmpeg
    if VideoMotionSmoother.is_ffmpeg_available():
        smooth_file = out_dir / f"soccer_v2_{task_id[:10]}_smooth60fps.mp4"
        try:
            VideoMotionSmoother.interpolate_to_60fps(
                input_video=raw_file,
                output_video=smooth_file,
                target_fps=60,
                log_callback=print,
            )
            print(f"✅ Video 60fps siêu mượt: {smooth_file}")
        except Exception as e:
            print(f"⚠️ Nội suy 60fps không thành công: {e}")

    print("\n" + "=" * 75)
    print("🎉 [THÀNH CÔNG RỰC RỠ] HOÀN TẤT TẠO VIDEO BÓNG ĐÁ V2!")
    print(f"📁 Thư mục lưu: {out_dir}")
    print("=" * 75)


if __name__ == "__main__":
    main()
