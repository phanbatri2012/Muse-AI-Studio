import asyncio
from datetime import datetime
from pathlib import Path
import sys

from muse_auth import MuseAuthManager
from muse_client import MuseClient, TaskStatus
from muse_media import process_and_save_media_async
from runtime_paths import MUSE_DOWNLOADS_DIR
from settings_manager import SettingsManager

TEST_PROMPT = "Tạo video 6 giây một chú mèo con lông vàng đáng yêu đang chơi bóng len trong phòng khách ấm cúng"

async def run_e2e_video_test():
    print("=" * 60)
    print("🎬 BẮT ĐẦU KIỂM THỬ E2E TẠO VIDEO TRÊN MUSE AI")
    print(f"📝 Test Prompt: {TEST_PROMPT}")
    print("=" * 60)

    # 1. Kết nối vào Chrome CDP đã đăng nhập
    print("[1/4] Kết nối vào trình duyệt Chrome qua CDP...")
    client = None
    try:
        client = await MuseClient.create(
            profile_name="MUSE_PROFILE_1",
            ensure_browser=True,
            log_callback=print,
        )
        # Kiểm tra xác thực
        auth = await MuseAuthManager.check_authentication(client.page)
        print(f"Trạng thái xác thực: {auth.get('authenticated')} ({auth.get('details')})")
        if not auth.get("authenticated"):
            print("❌ Phiên trình duyệt chưa đăng nhập! Vui lòng đăng nhập trước.")
            return False

        # 2. Gửi prompt sinh video (sử dụng thread hiện tại hoặc mở mới)
        print(f"[2/4] Gửi prompt tạo video vào khung chat...")
        baseline = await client.submit_prompt(TEST_PROMPT)

        # 3. Theo dõi tiến trình sinh video
        print("[3/4] Đang giám sát tiến trình AI sinh video...")

        def on_progress(p):
            print(f"  ⏳ [{p.get('elapsed')}s] Trạng thái: {p.get('status')} | Media: {p.get('media_found')} | {p.get('reply_preview')}")

        result = await client.wait_for_generation_complete(
            prompt=TEST_PROMPT,
            timeout_seconds=240,
            poll_interval=2.0,
            initial_video_count=baseline.get("initial_video_count", 0),
            initial_assistant_count=baseline.get("initial_assistant_count", 0),
            initial_dl_btn_count=baseline.get("initial_dl_btn_count", 0),
            progress_callback=on_progress,
        )

        print("-" * 60)
        print(f"Kết quả sinh: Success={result.success}, Status={result.status}")
        print(f"Thời gian: {round(result.duration_seconds, 1)}s")
        print(f"Video URLs tìm thấy: {len(result.video_urls)}")
        for u in result.video_urls:
            print(f" - {u[:80]}")
        print(f"Nội dung phản hồi: {result.reply_text[:200]}")
        print("-" * 60)

        if not result.success and not result.video_urls:
            print(f"❌ Không thể tạo video: {result.error}")
            return False

        # 4. Tải file video về máy
        print("[4/4] Bắt đầu tải và lưu trữ file video...")
        output_dir = MUSE_DOWNLOADS_DIR / "e2e_test"
        saved = await process_and_save_media_async(
            result=result,
            output_dir=output_dir,
            prompt_index=1,
            client=client,
            max_videos=1,
            log_callback=print,
        )

        print("=" * 60)
        print("TỔNG KẾT KẾT QUẢ TẢI:")
        print(f"Primary Video: {saved.get('primary_video')}")
        print(f"Primary Thumbnail: {saved.get('primary_thumbnail')}")
        print(f"Downloaded Count: {len(saved.get('downloaded_videos', []))}")
        print("=" * 60)

        if saved.get("primary_video"):
            v_file = Path(saved["primary_video"])
            if v_file.is_file() and v_file.stat().st_size > 1024:
                size_mb = round(v_file.stat().st_size / (1024 * 1024), 2)
                print(f"🎉 KIỂM THỬ E2E TẠO VIDEO THÀNH CÔNG RỰC RỠ! Kích thước file: {size_mb} MB")
                return True

        print("⚠️ Không tìm thấy file video hợp lệ sau khi tải.")
        return False

    finally:
        await client.close()

if __name__ == "__main__":
    success = asyncio.run(run_e2e_video_test())
    sys.exit(0 if success else 1)
