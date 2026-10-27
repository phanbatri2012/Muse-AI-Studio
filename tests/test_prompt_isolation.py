"""Unit test kiểm thử định dạng Prompt Cô lập Ngữ cảnh và Tỉ lệ Khung hình."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prompt_motion_enhancer import AspectRatio, MotionLevel, PromptMotionEnhancer


def test_prompt_formatting():
    print("🧪 [TEST] Kiểm tra định dạng prompt 9:16 (Dọc TikTok/Shorts)...")
    raw_prompt = "Tạo video 6 giây một chú mèo máy chạy đuổi theo quả bóng trên thảm cỏ xanh"
    p_916 = PromptMotionEnhancer.format_isolated_prompt(
        prompt=raw_prompt,
        aspect_ratio=AspectRatio.PORTRAIT_9_16,
        duration=6,
        motion_level=MotionLevel.ACTION,
        isolate_context=True,
        motion_boost=True,
    )
    print("Prompt 9:16:\n", p_916, "\n")
    assert "全新文生视频创作" in p_916, "Thiếu tiền tố cô lập context"
    assert "9:16 vertical portrait video" in p_916, "Thiếu định dạng dọc 9:16"
    assert "720x1280" in p_916, "Thiếu độ phân giải chuẩn 720x1280"
    assert "6 秒" in p_916, "Thiếu chỉ thị thời lượng 6 giây"
    assert "sprinting and running fast" in p_916, "Thiếu từ khóa động lực học chạy nhanh"

    print("🧪 [TEST] Kiểm tra định dạng prompt 16:9 (Ngang YouTube)...")
    p_169 = PromptMotionEnhancer.format_isolated_prompt(
        prompt="Siêu xe thể thao màu đỏ lướt trên đường cao tốc lúc hoàng hôn",
        aspect_ratio=AspectRatio.LANDSCAPE_16_9,
        duration=8,
        motion_level=MotionLevel.DRONE,
        isolate_context=True,
        motion_boost=True,
    )
    print("Prompt 16:9:\n", p_169, "\n")
    assert "16:9 widescreen landscape video" in p_169, "Thiếu định dạng ngang 16:9"
    assert "8 秒" in p_169, "Thiếu chỉ thị thời lượng 8 giây"
    assert "FPV drone video of" in p_169, "Thiếu góc quay drone"

    print("🧪 [TEST] Kiểm tra chế độ Image-to-Video tham chiếu ảnh...")
    p_i2v = PromptMotionEnhancer.format_isolated_prompt(
        prompt="Nhân vật bước đi mỉm cười",
        aspect_ratio=AspectRatio.PORTRAIT_9_16,
        duration=5,
        has_reference_image=True,
    )
    print("Prompt I2V:\n", p_i2v, "\n")
    assert "基于我本次上传的参考图片附件作为第一帧参考图" in p_i2v, "Thiếu tiền tố neo ảnh đầu tiên"

    print("✅ PASS: Toàn bộ kiểm thử định dạng Prompt hoàn tất thành công!")


if __name__ == "__main__":
    test_prompt_formatting()
