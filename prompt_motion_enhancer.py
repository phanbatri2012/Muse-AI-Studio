# -*- coding: utf-8 -*-
"""
Prompt Motion Enhancer for Meta Muse AI Video Generation.
Transforms static or subtle prompts into high-energy, dynamic kinematic prompts
that force Meta AI to generate real full-body movement and continuous camera action
instead of static cinemagraphs.
Incorporates Context Isolation templates derived from reverse-engineering muse.ai.
"""

from __future__ import annotations

import re


class MotionLevel:
    SMOOTH = "smooth"        # Chuyển động lướt siêu mượt (Buttery smooth, zero jitter, fluid glide)
    ACTION = "action"        # Chuyển động cơ thể mạnh (Sprinting, galloping, running)
    TRACKING = "tracking"    # Camera Tracking bám sát theo chủ thể
    DRONE = "drone"          # Flycam lướt nhanh, góc quay rộng lượn sóng


class AspectRatio:
    PORTRAIT_9_16 = "9:16"   # Dọc (TikTok, Shorts, Reels, 720x1280 / 1080x1920)
    LANDSCAPE_16_9 = "16:9"  # Ngang (YouTube, Widescreen, 1280x720 / 1920x1080)
    SQUARE_1_1 = "1:1"       # Vuông (Instagram Post)


# Các cụm từ thừa thường gặp ở đầu prompt
_REDUNDANT_PREFIXES = [
    r"^tạo\s+video(?:\s+\d+\s*(?:giây|s))?[\s:,.-]*",
    r"^làm\s+video(?:\s+\d+\s*(?:giây|s))?[\s:,.-]*",
    r"^quay\s+video(?:\s+\d+\s*(?:giây|s))?[\s:,.-]*",
    r"^video\s+(?:về|của|quay)?[\s:,.-]*",
    r"^generate\s+(?:a\s+)?video(?:\s+of)?[\s:,.-]*",
    r"^create\s+(?:a\s+)?video(?:\s+of)?[\s:,.-]*",
    r"^make\s+(?:a\s+)?video(?:\s+of)?[\s:,.-]*",
    r"^video\s+of[\s:,.-]*",
]

# Từ khóa nhận diện hành động chạy / di chuyển
_RUNNING_KEYWORDS = [
    "chạy", "nhảy", "phi", "đuổi", "vồ", "bước",
    "run", "running", "sprint", "sprinting", "chase", "chasing", "jump", "jumping", "gallop"
]


class PromptMotionEnhancer:
    """Tự động nâng cấp prompt để ép Meta Muse AI sinh chuyển động động học thực tế
    và định dạng tỷ lệ khung hình chuẩn hóa.
    """

    @classmethod
    def clean_prompt(cls, prompt: str) -> str:
        """Lọc bỏ các tiền tố mệnh lệnh thừa."""
        text = str(prompt or "").strip()
        for pat in _REDUNDANT_PREFIXES:
            text = re.sub(pat, "", text, flags=re.IGNORECASE).strip()
        # Xóa dấu câu thừa ở cuối
        return text.rstrip(".!?,; ")

    @classmethod
    def enhance_motion(
        cls,
        prompt: str,
        motion_level: str = MotionLevel.ACTION,
    ) -> str:
        """Thêm các từ khóa động học (kinematic) thúc đẩy chuyển động cơ thể và camera."""
        cleaned = cls.clean_prompt(prompt)
        if not cleaned:
            return prompt

        cleaned_lower = cleaned.lower()
        has_run = any(kw in cleaned_lower for kw in _RUNNING_KEYWORDS)

        if motion_level == MotionLevel.SMOOTH:
            prefix = "Cinematic steadycam footage of"
            suffix = "buttery smooth continuous fluid motion, steadycam gimbal tracking glide, seamless motion blur, zero camera shake, slow-motion 60fps, perfect temporal coherence"
        elif motion_level == MotionLevel.DRONE:
            prefix = "FPV drone video of"
            suffix = "fast camera gliding swiftly across the scene, buttery smooth cinematic movement, dynamic fluid motion"
        elif motion_level == MotionLevel.TRACKING:
            prefix = "Video of"
            suffix = "camera tracking shot smoothly following the subject, continuous dynamic movement, buttery smooth glide"
        else:  # MotionLevel.ACTION (Mặc định)
            prefix = "Video of"
            if has_run:
                suffix = "sprinting and running fast, legs vigorously moving, continuous full-body action, tracking camera shot, high motion"
            else:
                suffix = "with continuous dynamic physical movement, full-body action, camera tracking shot, high motion"

        return f"{prefix} {cleaned}, {suffix}"

    @classmethod
    def enhance(
        cls,
        prompt: str,
        motion_level: str = MotionLevel.ACTION,
        enabled: bool = True,
    ) -> str:
        """Hàm tương thích ngược với API cũ."""
        if not enabled:
            return cls.clean_prompt(prompt)
        return cls.enhance_motion(prompt, motion_level=motion_level)

    @classmethod
    def format_isolated_prompt(
        cls,
        prompt: str,
        aspect_ratio: str = AspectRatio.PORTRAIT_9_16,
        duration: int = 6,
        motion_level: str = MotionLevel.ACTION,
        isolate_context: bool = True,
        motion_boost: bool = True,
        has_reference_image: bool = False,
    ) -> str:
        """Tạo prompt hoàn chỉnh kết hợp Cô Lập Ngữ Cảnh, Ép Tỉ Lệ Khung Hình và Kích Hoạt Chuyển Động Động Học.

        Mẫu prompt được chuẩn hóa theo thực nghiệm thành công từ muse2api:
        - Tiền tố cô lập: '全新文生视频创作（纯文本全新生成，严禁参考任何历史图片或上下文）'
        - Chỉ thị tỉ lệ: 9:16 dọc điện thoại (720x1280) hoặc 16:9 ngang (1280x720)
        - Chỉ thị thời lượng: '时长严格为 {dur} 秒'
        """
        cleaned_user_prompt = cls.clean_prompt(prompt)
        if not cleaned_user_prompt:
            return prompt

        # 1. Tăng cường chuyển động động học nếu bật motion_boost
        if motion_boost:
            effective_content = cls.enhance_motion(cleaned_user_prompt, motion_level=motion_level)
        else:
            effective_content = cleaned_user_prompt

        if not isolate_context:
            return effective_content

        # 2. Xác định tỉ lệ hiển thị (ưu tiên nhận diện từ aspect_ratio hoặc prompt)
        ar_str = str(aspect_ratio or "").lower()
        prompt_lower = cleaned_user_prompt.lower()
        is_vertical = any(k in ar_str or k in prompt_lower for k in ("9:16", "9/16", "portrait", "dọc", "vertical", "720x1280", "1080x1920"))
        is_horizontal = any(k in ar_str or k in prompt_lower for k in ("16:9", "16/9", "landscape", "ngang", "horizontal", "1280x720", "1920x1080"))

        dur = max(3, min(duration, 15))

        if is_vertical or not is_horizontal:  # Mặc định là 9:16 dọc
            if has_reference_image:
                template = (
                    f"基于我本次上传的参考图片附件作为第一帧参考图（严禁使用历史图片或任何其他图像，必须严格以我当前刚刚上传并附带在此处的这张图片为起始帧）："
                    f"生成一个严格9:16竖屏手机满屏的动态图生视频（9:16 vertical portrait video，720x1280，高大于宽的手机全屏竖版画面，"
                    f"严格以附带的参考图为起始第一帧延续动作，严禁生成横屏或黑边，保持垂直构图，时长严格为 {dur} 秒）：{effective_content}"
                )
            else:
                template = (
                    f"全新文生视频创作（纯文本全新生成，严禁参考任何历史图片或上下文）："
                    f"生成一个严格9:16竖屏手机满屏视频（9:16 vertical portrait video，720x1280，高大于宽的手机全屏竖版画面，"
                    f"严禁生成横屏或带有左右黑边，保持垂直构图，时长严格为 {dur} 秒）：{effective_content}"
                )
        else:  # 16:9 ngang
            if has_reference_image:
                template = (
                    f"基于我本次上传的参考图片附件作为第一帧参考图（严禁使用历史图片或任何其他图像，必须严格以我当前刚刚上传并附带在此处的这张图片为起始帧）："
                    f"生成一个16:9宽屏横屏图生视频（16:9 widescreen landscape video，"
                    f"严格以附带的参考图为起始第一帧延续动作，时长严格为 {dur} 秒）：{effective_content}"
                )
            else:
                template = (
                    f"全新文生视频创作（纯文本全新生成，严禁参考任何历史图片或上下文）："
                    f"生成一个16:9横屏宽屏视频（16:9 widescreen landscape video，"
                    f"时长严格为 {dur} 秒）：{effective_content}"
                )

        return template
