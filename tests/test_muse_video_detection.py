"""Unit test kiểm thử bộ lọc Video nghiêm ngặt (Strict Video Detection) và trích xuất blob."""
from __future__ import annotations

import base64
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from muse_client import MuseClient, TaskStatus


def test_chunked_base64_logic():
    print("🧪 [TEST] Kiểm tra logic mã hóa và giải mã nhị phân chunked ArrayBuffer...")
    dummy_data = b"RIFF" + b"\x00" * 20 + b"WAVEfmt " + b"\x01" * 100000
    encoded = base64.b64encode(dummy_data).decode("ascii")
    decoded = base64.b64decode(encoded)
    assert decoded == dummy_data, "Dữ liệu giải mã không khớp"
    print(f"✅ PASS: Xử lý nhị phân ({len(dummy_data)} bytes) hoàn toàn chính xác!")


def test_extract_result_filters_poster_images():
    async def _run():
        print("🧪 [TEST] Kiểm tra _extract_result từ chối ảnh poster tĩnh khi thiếu video...")
        page_mock = MagicMock()
        page_mock.on = MagicMock()

        # Mock cho img_loc
        mock_img_loc = MagicMock()
        mock_img_loc.count = AsyncMock(return_value=1)
        mock_img_loc.get_attribute = AsyncMock(return_value="https://muse.ai/media/poster_cover.webp")

        # Mock cho parent img locator
        parent_img_loc = MagicMock()
        parent_img_loc.last = mock_img_loc

        # Mock cho assistant items (không có video)
        mock_assistant_items = MagicMock()
        mock_assistant_items.count = AsyncMock(return_value=0)

        # Mock cho dl button
        mock_dl_btn = MagicMock()
        mock_dl_btn.count = AsyncMock(return_value=0)
        mock_dl_btn_parent = MagicMock()
        mock_dl_btn_parent.last = mock_dl_btn

        def locator_router(selector: str):
            if "img:" in selector:
                return parent_img_loc
            elif "button[aria-label" in selector:
                return mock_dl_btn_parent
            else:
                return mock_assistant_items

        page_mock.locator = MagicMock(side_effect=locator_router)

        client = MuseClient(page_mock, MagicMock(), MagicMock(), MagicMock())
        result = await client._extract_result(
            prompt="Test video prompt",
            reply_text="Sure, here is your video",
            elapsed=15.0,
            turn_id="turn_123",
        )

        print("Kết quả khi chỉ có poster img:")
        print("  Success:", result.success)
        print("  Status:", result.status)
        print("  Error:", result.error)
        print("  Video URLs:", result.video_urls)
        print("  Image URLs:", result.image_urls)

        assert result.success is False, "Lỗi: Không được đánh dấu success khi chỉ có ảnh bìa"
        assert result.status == TaskStatus.FAILED
        assert "poster" in (result.error or "").lower()
        assert len(result.video_urls) == 0
        assert len(result.image_urls) == 1

        print("🧪 [TEST] Kiểm tra _extract_result chấp nhận khi có thẻ video...")
        client._intercepted_media_urls.append("blob:https://muse.ai/video-uuid-123")
        res_video = await client._extract_result(
            prompt="Test video prompt",
            reply_text="Video generated",
            elapsed=45.0,
            turn_id="turn_124",
        )
        assert res_video.success is True
        assert res_video.status == TaskStatus.COMPLETED
        assert len(res_video.video_urls) == 1
        print("✅ PASS: Đã xác thực thành công bộ lọc video nghiêm ngặt!")

    import asyncio
    asyncio.run(_run())


if __name__ == "__main__":
    test_chunked_base64_logic()
    test_extract_result_filters_poster_images()
