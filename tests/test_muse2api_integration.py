# -*- coding: utf-8 -*-
"""
Integration test for Muse2API REST API Service & Client.
Verifies:
1. Service startup and health-check (/admin/status).
2. Automatic session synchronization into accounts.json.
3. Task creation via POST /v1/videos.
4. Task status polling via GET /v1/videos/{task_id}.
"""

import json
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from muse_api_client import MuseAPIClient
from muse_service_manager import MUSE2API_KEY, MuseServiceManager


def test_muse2api_service_and_client():
    print("=" * 65)
    print("🧪 [TEST] Kiểm tra tích hợp Muse2API REST Service & Client")
    print("=" * 65)

    # 1. Đồng bộ session từ disk
    print("\n[BƯỚC 1] 🔄 Đồng bộ session từ DATA_GENERAL/muse_session.json...")
    synced = MuseServiceManager.sync_session_from_disk(log_callback=print)
    print(f"Kết quả đồng bộ: {synced}")
    assert synced is True, "Đồng bộ session thất bại"

    # 2. Khởi động service
    print("\n[BƯỚC 2] 🚀 Khởi động dịch vụ Muse2API Server ngầm...")
    started = MuseServiceManager.start_service(timeout=15, log_callback=print)
    print(f"Kết quả khởi động: {started}")
    assert started is True, "Khởi động service thất bại"
    assert MuseServiceManager.is_service_ready() is True, "Service chưa sẵn sàng"

    # 3. Khởi tạo REST API Client
    print("\n[BƯỚC 3] 🔌 Kết nối REST API Client...")
    client = MuseAPIClient(
        base_url=MuseServiceManager.get_api_base_url(),
        api_key=MUSE2API_KEY,
        log_callback=print,
    )

    # 4. Gửi yêu cầu tạo video qua REST API
    print("\n[BƯỚC 4] 🎬 Gửi yêu cầu tạo video qua POST /v1/videos...")
    test_prompt = "A majestic neon lion roaring under starry night sky, 4k ultra-realistic"
    task_res = client.create_video_task(
        prompt=test_prompt,
        aspect_ratio="9:16",
        duration=6,
        timeout_seconds=120,
    )
    print("Phản hồi từ POST /v1/videos:", task_res)
    task_id = task_res.get("id") or task_res.get("task_id")
    assert task_id is not None, "Không nhận được task_id"
    assert task_res.get("status") in ("queued", "processing"), f"Status không hợp lệ: {task_res.get('status')}"

    # 5. Truy vấn trạng thái qua GET /v1/videos/{task_id}
    print(f"\n[BƯỚC 5] 📊 Truy vấn trạng thái qua GET /v1/videos/{task_id}...")
    status_info = client.get_task_status(task_id)
    print("Thông tin task:", status_info)
    assert status_info.get("id") == task_id or status_info.get("task_id") == task_id
    assert "status" in status_info
    print(f"Trạng thái hiện tại: {status_info.get('status')} (Progress: {status_info.get('progress')}%)")

    print("\n" + "=" * 65)
    print("✅ PASS: Tất cả các bước tích hợp REST API Client & Service thành công 100%!")
    print("=" * 65)


if __name__ == "__main__":
    try:
        test_muse2api_service_and_client()
    finally:
        print("\n🛑 Dọn dẹp: Dừng tiến trình Muse2API Service...")
        MuseServiceManager.stop_service(print)
