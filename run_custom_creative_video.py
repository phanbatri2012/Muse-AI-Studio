# -*- coding: utf-8 -*-
"""
Script tạo video nghệ thuật / khác biệt qua REST API Muse2API.
Chủ đề: Cyberpunk Futuristic Metropolis với cá Koi phát quang ba chiều bơi trong không trung dưới mưa neon.
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


def main():
    print("=" * 75)
    print("🎨 [CREATIVE GENERATION] TẠO VIDEO NGHỆ THUẬT ĐỘC ĐÁO QUA REST API")
    print("=" * 75)

    # 1. Đảm bảo service đang chạy
    if not MuseServiceManager.is_service_ready():
        print("🔄 Dịch vụ chưa chạy, đang khởi động...")
        MuseServiceManager.start_service(timeout=20, log_callback=print)

    print("🟢 Muse2API Service sẵn sàng tại:", MuseServiceManager.get_api_base_url())

    client = MuseAPIClient(
        base_url=MuseServiceManager.get_api_base_url(),
        api_key=MUSE2API_KEY,
        log_callback=print,
    )

    # 2. Prompt nghệ thuật khác biệt, cinematic và giàu chi tiết thị giác
    creative_prompt = (
        "A cinematic tracking shot of a futuristic cyberpunk traveler in sleek obsidian armor walking "
        "through a rain-soaked neon metropolis at midnight, giant glowing holographic bioluminescent "
        "koi fish gracefully swimming through the misty air above, vibrant neon reflections glittering on "
        "wet asphalt, volumetric steam and soft rain splashes, anamorphic lens flare, 8k cinematic masterpiece"
    )

    print(f"\n🎬 [PROMPT]:\n\"{creative_prompt}\"\n")
    print("📐 Cấu hình: 9:16 (Vertical Fullscreen), 6 giây")

    # 3. Gửi yêu cầu API
    task_res = client.create_video_task(
        prompt=creative_prompt,
        aspect_ratio="9:16",
        duration=6,
        timeout_seconds=360,
    )
    task_id = task_res.get("id") or task_res.get("task_id")
    print(f"✅ Đã tiếp nhận tác vụ thành công! Task ID: {task_id}")

    # 4. Polling tiến độ
    def on_progress(p):
        status = p.get("status")
        progress = p.get("progress", 0)
        elapsed = p.get("elapsed", "")
        print(f"  [TIẾN ĐỘ] Status: {status} | Progress: {progress}% | Elapsed: {elapsed}s", flush=True)

    print("\n⏳ Đang render trên Cloud GPU của Meta AI...")
    result = client.poll_video_task(task_id, timeout=360, on_progress=on_progress)

    status = result.get("status")
    if status != "completed":
        print(f"\n❌ Tác vụ thất bại: {result.get('error')}")
        sys.exit(1)

    # 5. Tải video về
    video_url = (result.get("video") or {}).get("url") or result.get("url")
    if not video_url and result.get("result"):
        video_url = result["result"].get("url")

    out_dir = ROOT / "DOWNLOADS" / "creative_gallery"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📥 Đang tải video từ URL: {video_url}...")
    saved_file = client.download_video(video_url, out_dir, suggested_name=f"cyberpunk_koi_{task_id[:12]}.mp4")
    file_size_mb = saved_file.stat().st_size / (1024 * 1024)

    print(f"\n🎉 [THÀNH CÔNG RỰC RỠ] Video nghệ thuật đã được tạo xong!")
    print(f"📁 Đường dẫn file: {saved_file}")
    print(f"💾 Dung lượng: {file_size_mb:.2f} MB")
    print(f"⏱️ Tổng thời gian: {result.get('elapsed')} giây")
    print("=" * 75)


if __name__ == "__main__":
    main()
