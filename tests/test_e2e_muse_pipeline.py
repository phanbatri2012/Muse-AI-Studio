# -*- coding: utf-8 -*-
"""
End-to-End (E2E) Verification Script for Muse AI Video Generation Pipeline.
Tests the full lifecycle:
1. HTTP session check & Cloud VM wake (/api/session).
2. Playwright CDP connection to Chrome.
3. Context isolation & aspect ratio prompt enhancement.
4. Fast React 18 prompt injection and submission.
5. Real-time generation waiting & strict video detection.
6. Media download and ISO BMFF MP4 magic bytes verification.
"""

import asyncio
import os
import sys
from pathlib import Path

# Thêm thư mục gốc vào PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from muse_auth import MuseAuthManager
from muse_client import MuseClient
from muse_media import process_and_save_media_async, verify_video_file_integrity
from prompt_motion_enhancer import MotionLevel, PromptMotionEnhancer
from runtime_paths import MUSE_DOWNLOADS_DIR


def p(*args, **kwargs):
    print(*args, **kwargs, flush=True)


async def run_e2e_test(prompt_text: str = "A cute neon robotic cat running through a cyber street, 4k", timeout: int = 360):
    p("=" * 70)
    p("🚀 [E2E TEST] BẮT ĐẦU KIỂM THỬ TOÀN DIỆN QUY TRÌNH MUSE AI")
    p("=" * 70)

    # BƯỚC 1: Kiểm tra & Gia hạn session + Wake Cloud VM
    p("\n[BƯỚC 1] ⚡ Kiểm tra & gia hạn Cloud VM session qua HTTP...")
    renew_res = await MuseAuthManager.renew_session_http(log_callback=p)
    p("Kết quả gia hạn session:", renew_res)
    assert renew_res.get("success") is True, f"Lỗi gia hạn session: {renew_res.get('error')}"
    assert renew_res.get("status") == "assigned", f"Session chưa được gán: {renew_res.get('status')}"
    p("✅ BƯỚC 1 HOÀN TẤT: Cloud VM đang ở trạng thái RUNNING!")

    # BƯỚC 2: Định dạng Prompt Cô Lập & Tỉ Lệ Khung Hình 9:16
    p("\n[BƯỚC 2] 📝 Định dạng Prompt tối ưu (9:16, 6s, Context Isolation)...")
    effective_prompt = PromptMotionEnhancer.format_isolated_prompt(
        prompt=prompt_text,
        aspect_ratio="9:16",
        duration=6,
        motion_level=MotionLevel.ACTION,
        isolate_context=True,
        motion_boost=True,
    )
    p("Effective Prompt:", effective_prompt)
    assert "全新文生视频创作" in effective_prompt
    assert "9:16" in effective_prompt
    p("✅ BƯỚC 2 HOÀN TẤT: Prompt chuẩn hóa chính xác!")

    client = None
    try:
        # BƯỚC 3: Kết nối Playwright CDP tới Chrome
        p("\n[BƯỚC 3] 🔌 Khởi tạo kết nối Playwright CDP tới Chrome...")
        client = await MuseClient.create(
            profile_name="MUSE_PROFILE_1",
            ensure_browser=True,
            log_callback=p,
        )
        p("✅ BƯỚC 3 HOÀN TẤT: Đã kết nối Chrome CDP thành công!")

        # BƯỚC 4: Gửi Prompt và Chờ Sinh Video
        p(f"\n[BƯỚC 4] 🎬 Bắt đầu gửi prompt và chờ AI sinh video (Timeout: {timeout}s)...")
        def on_progress(p_info):
            status = p_info.get("status")
            elapsed = p_info.get("elapsed", 0)
            media_count = p_info.get("media_found", 0)
            p(f"  [Progress] Status: {status} | Đã trôi qua: {elapsed:.1f}s | Thẻ video tìm thấy: {media_count}")

        result = await client.generate_with_retry(
            prompt=effective_prompt,
            new_thread=True,
            max_retries=1,
            timeout_seconds=timeout,
            progress_callback=on_progress,
        )
        result.prompt = prompt_text

        p(f"\nKết quả sinh video:")
        p(f"  Success: {result.success}")
        p(f"  Status: {result.status}")
        p(f"  Elapsed: {result.duration_seconds:.1f}s")
        p(f"  Video URLs: {result.video_urls}")
        p(f"  Image URLs: {result.image_urls}")
        if result.error:
            p(f"  Error: {result.error}")

        assert result.success is True, f"Sinh video thất bại: {result.error}"
        assert len(result.video_urls) > 0, "Không trích xuất được URL video"
        p("✅ BƯỚC 4 HOÀN TẤT: AI đã sinh video thực sự (bỏ qua ảnh poster tĩnh)!")

        # BƯỚC 5: Tải Media và Kiểm Định Magic Bytes
        p("\n[BƯỚC 5] ⬇️ Tải video về ổ cứng và kiểm tra Magic Bytes MP4...")
        test_output_dir = MUSE_DOWNLOADS_DIR / "e2e_test_output"
        test_output_dir.mkdir(parents=True, exist_ok=True)

        saved_info = await process_and_save_media_async(
            result=result,
            output_dir=test_output_dir,
            prompt_index=1,
            client=client,
            max_videos=1,
            log_callback=p,
        )

        primary_video = saved_info.get("primary_video")
        p("Primary Video Path:", primary_video)
        assert primary_video is not None, "Không tìm thấy video đã tải về"

        # Kiểm tra tính toàn vẹn nhị phân
        v_path = Path(primary_video)
        assert v_path.exists(), f"File video không tồn tại: {v_path}"
        is_valid, msg = verify_video_file_integrity(v_path)
        p(f"Xác thực tính toàn vẹn file video: {is_valid} ({msg})")
        assert is_valid is True, f"File video không hợp lệ: {msg}"
        p(f"Kích thước file: {v_path.stat().st_size:,} bytes")
        p("✅ BƯỚC 5 HOÀN TẤT: Video MP4 hợp lệ 100%!")

        p("\n" + "=" * 70)
        p("🎉 TẤT CẢ CÁC BƯỚC KIỂM THỬ E2E ĐÃ THÀNH CÔNG VƯỢT TRỘI!")
        p("=" * 70)
        return True

    finally:
        if client is not None:
            await MuseAuthManager.safe_disconnect(client.playwright, client.browser, log_callback=p)


if __name__ == "__main__":
    test_prompt = "A high-speed cyber motorcycle racing through neon city streets, 4k hyper-realistic."
    if len(sys.argv) > 1:
        test_prompt = " ".join(sys.argv[1:])
    try:
        asyncio.run(run_e2e_test(test_prompt))
    except KeyboardInterrupt:
        p("\n⏹️ Đã dừng kiểm thử bởi người dùng.")
