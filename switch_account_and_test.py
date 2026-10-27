# -*- coding: utf-8 -*-
"""
Script đổi tài khoản Muse AI:
1. Xóa sạch session, profile, cache của tài khoản cũ.
   Thông tin đăng nhập thử được đọc từ các biến môi trường MUSE_TEST_*.
3. Thực hiện đăng nhập tự động (Email + Password + TOTP 2FA) và thu hoạch cookies.
4. Đồng bộ cookies mới vào muse2api backend.
5. Khởi động lại dịch vụ muse2api REST API.
6. Test e2e tạo video qua API với tài khoản mới và làm mượt 60fps.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime_paths import (
    DATA_GENERAL_DIR,
    MUSE_SETTINGS_FILE,
    MUSE_SESSION_FILE,
)
from muse_chrome import (
    DEFAULT_MUSE_PROFILE,
    cleanup_all_muse_processes,
    kill_muse_chrome_by_profile,
    reset_muse_user_data,
    resolve_muse_profile_dir,
    open_muse_chrome,
    is_muse_chrome_running,
)
from muse_auth import MuseAuthManager, generate_totp_code
from muse_service_manager import (
    MUSE2API_ACCOUNTS_FILE,
    MUSE2API_KEY,
    MuseServiceManager,
    is_port_in_use,
)
from muse_api_client import MuseAPIClient
from video_motion_smoother import VideoMotionSmoother

NEW_ACCOUNT = {
    "email": os.getenv("MUSE_TEST_EMAIL", ""),
    "password": os.getenv("MUSE_TEST_PASSWORD", ""),
    "two_factor_secret": os.getenv("MUSE_TEST_TOTP_SECRET", "").replace(" ", ""),
}


def log(msg: str) -> None:
    now = time.strftime("%H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def stop_any_existing_muse2api_server() -> None:
    """Tắt các tiến trình uvicorn muse2api đang chạy để giải phóng tài nguyên."""
    log("🛑 Đang kiểm tra và tắt server muse2api cũ nếu có...")
    if os.name == "nt":
        ps = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -and ($_.CommandLine -match 'uvicorn.*app:app|muse2api_backend') } | "
            "ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                capture_output=True,
                check=False,
            )
        except Exception:
            pass
    time.sleep(1.0)


def purge_old_account_data() -> None:
    """Xóa bỏ triệt để mọi dữ liệu tài khoản cũ."""
    log("=" * 70)
    log("🧹 BƯỚC 1: XÓA BỎ HOÀN TOÀN TÀI KHOẢN CŨ")
    log("=" * 70)

    # 1. Tắt server API cũ
    stop_any_existing_muse2api_server()

    # 2. Tiêu diệt Chrome zombie của Muse AI
    cleanup_all_muse_processes()
    time.sleep(1.0)

    # 3. Xóa session cũ
    if MUSE_SESSION_FILE.exists():
        try:
            MUSE_SESSION_FILE.unlink()
            log(f"🗑️ Đã xóa file session cũ: {MUSE_SESSION_FILE}")
        except Exception as e:
            log(f"⚠️ Lỗi xóa muse_session.json: {e}")

    # 4. Xóa accounts.json cũ của backend
    if MUSE2API_ACCOUNTS_FILE.exists():
        try:
            MUSE2API_ACCOUNTS_FILE.write_text("[]", encoding="utf-8")
            log(f"🗑️ Đã reset danh sách tài khoản backend: {MUSE2API_ACCOUNTS_FILE}")
        except Exception as e:
            log(f"⚠️ Lỗi reset accounts.json: {e}")

    # 5. Xóa sạch thư mục profile Chrome cũ
    profile_dir = resolve_muse_profile_dir(DEFAULT_MUSE_PROFILE)
    log(f"🧹 Xóa profile Chrome cũ: {profile_dir}...")
    reset_muse_user_data(DEFAULT_MUSE_PROFILE)
    log("✅ Đã dọn dẹp sạch sẽ hồ sơ Chrome cũ!")

    # 6. Cập nhật muse_settings.json với tài khoản mới
    settings_data = {
        "target_url": "https://muse.ai/",
        "current_profile": DEFAULT_MUSE_PROFILE,
        "max_concurrent_tasks": 3,
        "task_timeout_seconds": 249,
        "download_dir": str(ROOT / "downloads" / "muse"),
        "email": NEW_ACCOUNT["email"],
        "password": NEW_ACCOUNT["password"],
        "two_factor_secret": NEW_ACCOUNT["two_factor_secret"],
        "max_retries": 4,
    }
    DATA_GENERAL_DIR.mkdir(parents=True, exist_ok=True)
    MUSE_SETTINGS_FILE.write_text(json.dumps(settings_data, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"💾 Đã lưu cấu hình tài khoản mới vào: {MUSE_SETTINGS_FILE.name}")


async def do_login_new_account() -> dict:
    """Tự động đăng nhập tài khoản mới bằng Playwright CDP."""
    log("=" * 70)
    log("🔑 BƯỚC 2: TỰ ĐỘNG ĐĂNG NHẬP VỚI TÀI KHOẢN MỚI")
    log(f"   Email: {NEW_ACCOUNT['email']}")
    log(f"   Password: {'*' * len(NEW_ACCOUNT['password'])}")
    totp_sample = generate_totp_code(NEW_ACCOUNT["two_factor_secret"])
    log(f"   2FA TOTP hiện tại: {totp_sample}")
    log("=" * 70)

    res = await MuseAuthManager.auto_login(
        email=NEW_ACCOUNT["email"],
        password=NEW_ACCOUNT["password"],
        two_factor_secret=NEW_ACCOUNT["two_factor_secret"],
        profile_name=DEFAULT_MUSE_PROFILE,
        timeout_seconds=120,
        log_callback=log,
    )
    return res


def sync_and_start_api() -> bool:
    """Đồng bộ session mới vào muse2api backend và khởi động dịch vụ."""
    log("=" * 70)
    log("🔄 BƯỚC 3: ĐỒNG BỘ COOKIES VÀ KHỞI ĐỘNG MUSE2API")
    log("=" * 70)

    # 1. Đồng bộ session từ đĩa
    synced = MuseServiceManager.sync_session_from_disk(log_callback=log)
    if not synced:
        log("❌ Đồng bộ session từ disk thất bại! Kiểm tra lại file muse_session.json.")
        return False

    # 2. Khởi động backend uvicorn
    started = MuseServiceManager.start_service(timeout=30, log_callback=log)
    if not started:
        log("❌ Khởi động dịch vụ Muse2API thất bại!")
        return False

    log("🟢 Muse2API Service đã hoạt động sẵn sàng!")
    return True


def test_video_generation_via_api() -> Path | None:
    """Tạo video qua REST API với tài khoản mới và làm mượt 60fps."""
    log("=" * 70)
    log("🎬 BƯỚC 4: TẠO VIDEO TEST QUA REST API VỚI TÀI KHOẢN MỚI")
    log("=" * 70)

    client = MuseAPIClient(
        base_url=MuseServiceManager.get_api_base_url(),
        api_key=MUSE2API_KEY,
        log_callback=log,
    )

    test_prompt = (
        "A cute golden retriever puppy happily running across a vibrant green meadow on a sunny day, "
        "cinematic lighting, photorealistic, 4k resolution, high detailed, smooth motion"
    )
    log(f"📝 Prompt: \"{test_prompt}\"")
    log("📐 Tỉ lệ: 16:9 | Thời lượng: 6 giây")

    # 1. Tạo task video
    log("🚀 Gửi yêu cầu sinh video lên API...")
    task_res = client.create_video_task(
        prompt=test_prompt,
        aspect_ratio="16:9",
        duration=6,
        timeout_seconds=600,
    )
    task_id = task_res.get("id") or task_res.get("task_id")
    log(f"✅ Đã tiếp nhận task! ID: {task_id}")

    # 2. Polling tiến độ
    def on_progress(p: dict) -> None:
        status = p.get("status")
        progress = p.get("progress", 0)
        elapsed = p.get("elapsed", "")
        log(f"  [TIẾN ĐỘ] Status: {status} | Progress: {progress}% | Elapsed: {elapsed}s")

    log("⏳ Đang render trên Cloud GPU của Meta AI với tài khoản mới...")
    result = client.poll_video_task(task_id, timeout=600, on_progress=on_progress)

    status = result.get("status")
    if status != "completed":
        log(f"❌ Render video thất bại: {result.get('error')}")
        return None

    # 3. Tải video thành phẩm
    video_url = (result.get("video") or {}).get("url") or result.get("url")
    if not video_url and result.get("result"):
        video_url = result["result"].get("url")

    out_dir = ROOT / "DOWNLOADS" / "test_new_account"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_name = f"new_account_{task_id[:10]}.mp4"
    raw_file = client.download_video(video_url, out_dir, suggested_name=raw_name)
    raw_size_mb = raw_file.stat().st_size / (1024 * 1024)
    log(f"✅ Video gốc tải về: {raw_file} ({raw_size_mb:.2f} MB)")

    # 4. Khử giật làm mượt 60fps qua FFmpeg MCI
    if VideoMotionSmoother.is_ffmpeg_available():
        smooth_name = f"new_account_{task_id[:10]}_smooth60fps.mp4"
        smooth_file = out_dir / smooth_name
        try:
            log("⚡ Đang nội suy khử giật lên 60fps qua FFmpeg...")
            VideoMotionSmoother.interpolate_to_60fps(
                input_video=raw_file,
                output_video=smooth_file,
                target_fps=60,
                log_callback=log,
            )
            log(f"🎉 Video 60fps siêu mượt: {smooth_file}")
            return smooth_file
        except Exception as e:
            log(f"⚠️ Nội suy 60fps gặp lỗi: {e}")

    return raw_file


def main() -> None:
    print("=" * 75)
    print("🚀 BẮT ĐẦU QUY TRÌNH ĐỔI TÀI KHOẢN VÀ TẠO VIDEO QUA API")
    print("=" * 75)

    # 1. Xóa sạch tài khoản cũ
    purge_old_account_data()

    # 2. Đăng nhập tài khoản mới
    login_result = asyncio.run(do_login_new_account())
    if not login_result.get("success"):
        log(f"❌ Đăng nhập tài khoản mới thất bại: {login_result.get('error')}")
        sys.exit(1)

    log("🎉 Đăng nhập tài khoản mới thành công và đã thu hoạch session!")

    # 3. Tắt Chrome profile đăng nhập trước khi chạy API backend
    cleanup_all_muse_processes()
    time.sleep(1.5)

    # 4. Đồng bộ session và khởi động backend
    if not sync_and_start_api():
        sys.exit(1)

    # 5. Tạo video test qua REST API
    video_path = test_video_generation_via_api()
    if not video_path:
        log("❌ Quy trình tạo video qua API thất bại!")
        sys.exit(1)

    print("\n" + "=" * 75)
    print("🎉 [HOÀN TẤT XUẤT SẮC] ĐÃ ĐỔI TÀI KHOẢN MỚI VÀ TẠO VIDEO THÀNH CÔNG!")
    print(f"📁 Video thành phẩm: {video_path}")
    print("=" * 75)


if __name__ == "__main__":
    main()
