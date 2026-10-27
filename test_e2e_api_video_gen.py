# -*- coding: utf-8 -*-
"""
End-to-End Test: Tạo video thực tế qua REST API của Muse2API.
Quy trình:
1. Khởi động / Kết nối tới Muse2API Service (Port 18610).
2. Kiểm tra trạng thái tài khoản & Cloud VM.
3. Gửi yêu cầu POST /v1/videos với prompt thử nghiệm.
4. Polling GET /v1/videos/{task_id} theo dõi tiến độ thời gian thực.
5. Tải video MP4 về thư mục DOWNLOADS/test_e2e_api.
6. Xác thực Magic Bytes ISO BMFF và kích thước video.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Thêm root vào sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muse_api_client import MuseAPIClient
from muse_service_manager import MUSE2API_KEY, MuseServiceManager


def main():
    print("=" * 70)
    print("🚀 [E2E TEST] KIỂM THỬ TẠO VIDEO THỰC TẾ QUA REST API MUSE2API")
    print("=" * 70)

    # 1. Đồng bộ session và bật service
    print("\n[BƯỚC 1] 🔄 Kiểm tra và khởi động Muse2API Service...")
    MuseServiceManager.sync_session_from_disk(log_callback=print)
    started = MuseServiceManager.start_service(timeout=20, log_callback=print)
    if not started or not MuseServiceManager.is_service_ready():
        print("❌ Lỗi: Không thể khởi động hoặc kết nối tới Muse2API Server!")
        sys.exit(1)
    print("✅ Muse2API Service đang chạy tại:", MuseServiceManager.get_api_base_url())

    # 2. Khởi tạo API Client
    client = MuseAPIClient(
        base_url=MuseServiceManager.get_api_base_url(),
        api_key=MUSE2API_KEY,
        log_callback=print,
    )

    # 3. Tạo task video
    test_prompt = "A cinematic shot of a cute golden retriever puppy playing with bubbles in a sunlit garden, high quality, photorealistic"
    print(f"\n[BƯỚC 2] 🎬 Gửi yêu cầu sinh video qua POST /v1/videos...")
    print(f"  Prompt: \"{test_prompt}\"")
    print(f"  Aspect Ratio: 9:16, Duration: 6s")

    task_res = client.create_video_task(
        prompt=test_prompt,
        aspect_ratio="9:16",
        duration=6,
        timeout_seconds=300,
    )
    task_id = task_res.get("id") or task_res.get("task_id")
    print(f"✅ Đã tạo task thành công! Task ID: {task_id}")

    # 4. Polling tiến độ
    print("\n[BƯỚC 3] ⏳ Bắt đầu polling tiến độ từ server...")
    def on_progress(p):
        status = p.get("status")
        progress = p.get("progress", 0)
        elapsed = p.get("elapsed", "")
        print(f"  [TIẾN ĐỘ] Status: {status} | Progress: {progress}% | Elapsed: {elapsed}s")

    result = client.poll_video_task(task_id, timeout=360, on_progress=on_progress)
    print("\n📊 Kết quả xử lý Task:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    status = result.get("status")
    if status != "completed":
        print(f"\n❌ Task kết thúc với trạng thái không thành công: {status}")
        error = result.get("error")
        if error:
            print(f"  Chi tiết lỗi: {error}")
        sys.exit(1)

    # 5. Tải video MP4
    video_url = (result.get("video") or {}).get("url") or result.get("url")
    if not video_url and result.get("result"):
        video_url = result["result"].get("url")

    print(f"\n[BƯỚC 4] 📥 Tải video thành phẩm từ URL: {video_url}...")
    output_dir = ROOT / "DOWNLOADS" / "test_e2e_api"
    output_dir.mkdir(parents=True, exist_ok=True)

    dest_file = client.download_video(video_url, output_dir)
    print(f"✅ Video đã tải về: {dest_file}")
    file_size = dest_file.stat().st_size
    print(f"  Dung lượng: {file_size / (1024 * 1024):.2f} MB ({file_size} bytes)")

    # 6. Kiểm tra Magic Bytes
    with open(dest_file, "rb") as f:
        header = f.read(16)
    is_mp4 = b"ftyp" in header
    print(f"  Kiểm định Magic Bytes MP4 (ftyp): {'✅ HỢP LỆ' if is_mp4 else '❌ KHÔNG HỢP LỆ'}")

    assert file_size > 50000, "File video quá nhỏ!"
    assert is_mp4, "File không đúng định dạng MP4!"

    print("\n" + "=" * 70)
    print("🎉 [THÀNH CÔNG] TEST E2E TẠO VIDEO QUA REST API ĐẠT 100%!")
    print("=" * 70)


if __name__ == "__main__":
    main()
