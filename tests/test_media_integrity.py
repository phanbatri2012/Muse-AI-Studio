"""Unit test kiểm thử hàm xác thực định dạng Magic Bytes của Video (verify_video_file_integrity)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from muse_media import verify_video_file_integrity


def test_magic_bytes_detection():
    print("🧪 [TEST] Kiểm tra nhận diện Magic Bytes các định dạng media...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. File MP4 hợp lệ (4 bytes size + ftyp + isom + payload)
        mp4_file = tmp_path / "valid.mp4"
        mp4_content = b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41" + b"\x00" * (15 * 1024)
        mp4_file.write_bytes(mp4_content)
        ok, fmt = verify_video_file_integrity(mp4_file)
        print("  MP4:", ok, fmt)
        assert ok is True and "mp4" in fmt

        # 2. File WebM hợp lệ
        webm_file = tmp_path / "valid.webm"
        webm_content = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01" + b"\x00" * (15 * 1024)
        webm_file.write_bytes(webm_content)
        ok, fmt = verify_video_file_integrity(webm_file)
        print("  WebM:", ok, fmt)
        assert ok is True and "webm" in fmt

        # 3. File PNG (ảnh tĩnh bị giả danh làm video)
        png_file = tmp_path / "fake_video.png"
        png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * (20 * 1024)
        png_file.write_bytes(png_content)
        ok, fmt = verify_video_file_integrity(png_file)
        print("  PNG:", ok, fmt)
        assert ok is False and fmt == "image_png"

        # 4. File WebP (ảnh tĩnh bị giả danh làm video)
        webp_file = tmp_path / "fake_cover.webp"
        webp_content = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * (20 * 1024)
        webp_file.write_bytes(webp_content)
        ok, fmt = verify_video_file_integrity(webp_file)
        print("  WebP:", ok, fmt)
        assert ok is False and fmt == "image_webp"

        # 5. File quá nhỏ (< 10KB)
        tiny_file = tmp_path / "empty.mp4"
        tiny_file.write_bytes(b"\x00\x00\x00\x1cftypisom")
        ok, fmt = verify_video_file_integrity(tiny_file)
        print("  Tiny file:", ok, fmt)
        assert ok is False and "too_small" in fmt

    print("✅ PASS: Toàn bộ kiểm thử Magic Bytes Media hoàn tất chính xác!")


def test_real_saved_video():
    print("🧪 [TEST] Kiểm tra video Muse AI thực tế trong thư mục DATA_DOWNLOADS...")
    downloads_root = ROOT / "DATA_DOWNLOADS"
    real_videos = list(downloads_root.rglob("*.mp4"))
    if not real_videos:
        print("⚠️ Không tìm thấy video MP4 có sẵn trong DATA_DOWNLOADS để kiểm thử.")
        return

    real_vid = real_videos[0]
    print(f"  Kiểm tra file thực tế: {real_vid.name} ({round(real_vid.stat().st_size / (1024*1024), 2)} MB)")
    ok, fmt = verify_video_file_integrity(real_vid)
    print("  Kết quả:", ok, fmt)
    assert ok is True, f"File video thực tế không vượt qua kiểm định: {fmt}"
    print("✅ PASS: Video thực tế vượt qua kiểm định Magic Bytes thành công!")


if __name__ == "__main__":
    test_magic_bytes_detection()
    test_real_saved_video()
