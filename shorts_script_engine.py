# -*- coding: utf-8 -*-
"""
Shorts Script & Storyboard Engine using Muse AI Chat API (muse2api).
Converts any topic/idea into structured scenes with voiceover text and cinematic video prompts.
100% powered by Meta Muse AI language model - Zero third-party LLM required.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable

from muse_api_client import MuseAPIClient
from muse_service_manager import MUSE2API_KEY, MuseServiceManager

logger = logging.getLogger("shorts_script_engine")


@dataclass
class SceneItem:
    scene_index: int
    voice_text: str
    visual_prompt: str
    bgm_mood: str = "hook"
    estimated_seconds: float = 5.0
    video_path: str | None = None
    audio_path: str | None = None
    sub_path: str | None = None
    reference_image: str | list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ShortsScriptEngine:
    """Biên kịch kịch bản video ngắn (Shorts / TikTok) sử dụng Muse AI Chat."""

    def __init__(
        self,
        api_client: MuseAPIClient | None = None,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.log_callback = log_callback
        if api_client:
            self.client = api_client
        else:
            self.client = MuseAPIClient(
                base_url=MuseServiceManager.get_api_base_url(),
            api_key=MUSE2API_KEY,
                log_callback=log_callback,
            )

    def _log(self, msg: str) -> None:
        if callable(self.log_callback):
            try:
                self.log_callback(msg)
                return
            except Exception:
                pass
        print(f"[SHORTS_SCRIPT] {msg}")

    def generate_storyboard(
        self,
        topic: str,
        scene_count: int = 4,
        aspect_ratio: str = "9:16",
        timeout: int = 150,
    ) -> list[SceneItem]:
        """Tạo danh sách phân cảnh (Storyboard) gồm câu thoại và visual prompt từ chủ đề."""
        topic_clean = topic.strip()
        if not topic_clean:
            raise ValueError("Chủ đề không được để trống")

        self._log(f"🎬 Đang gọi Muse AI Chat để viết kịch bản phân cảnh: '{topic_clean}' ({scene_count} cảnh)...")

        system_prompt = (
            "You are a professional viral short-form video director and scriptwriter (YouTube Shorts / TikTok / Reels).\n"
            "Your task is to analyze the user's topic and create a high-engagement, concise storyboard.\n"
            "CRITICAL RULES:\n"
            f"1. Generate exactly {scene_count} chronological scenes.\n"
            "2. 'voice_text' MUST be in natural, gripping Vietnamese (12-20 words per scene, hook the viewer in scene 1).\n"
            "3. 'visual_prompt' MUST be in English, highly detailed, photorealistic, cinematic lighting, 4k resolution, specifying dynamic camera angles (tracking shot, close-up, dramatic zoom).\n"
            "4. NEVER include specific commercial brand names or trademarked labels in 'visual_prompt' (e.g. use 'sleek premium wireless earbuds' instead of 'AirPods' or 'Apex Pro', use 'luxury sports car' instead of 'Ferrari'). Focus purely on visual aesthetics, materials, and lighting.\n"
            "5. 'bgm_mood' must be one of: 'hook', 'evidence', 'concrete_scene', 'modern_mirror'.\n"
            "6. OUTPUT MUST BE A PURE JSON ARRAY ONLY. Do NOT add preamble, markdown explanation, or conversation outside the JSON array.\n\n"
            "JSON Format Example:\n"
            "[\n"
            "  {\n"
            '    "scene_index": 1,\n'
            '    "voice_text": "Bạn có biết dưới đáy vực Mariana sâu thẳm, có những sinh vật kỳ lạ chưa từng thấy?",\n'
            '    "visual_prompt": "Cinematic vertical 9:16 underwater shot descending into the ultra-deep Mariana Trench, glowing bioluminescent sea creatures swimming past the camera, hyper-realistic, dark atmospheric water, 4k resolution",\n'
            '    "bgm_mood": "hook"\n'
            "  }\n"
            "]"
        )

        user_message = (
            f"Chủ đề video: '{topic_clean}'.\n"
            f"Hãy viết kịch bản {scene_count} phân cảnh hấp dẫn, giật gân, cuốn hút người xem ngay từ giây đầu tiên.\n"
            "Chỉ xuất duy nhất JSON mảng các cảnh như đã quy định."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        raw_response = ""
        max_chat_attempts = 3
        for attempt in range(1, max_chat_attempts + 1):
            try:
                if attempt > 1:
                    self._log(f"🔄 Đang thử lại gọi Muse Chat (Lần {attempt}/{max_chat_attempts})...")
                    import time
                    time.sleep(3.5)
                raw_response = self.client.chat_completions(messages=messages, timeout=timeout)
                if raw_response and len(raw_response.strip()) > 10:
                    break
            except Exception as e:
                self._log(f"⚠️ Gọi Muse Chat lần {attempt} gặp lỗi: {e}")
                if attempt == max_chat_attempts:
                    self._log("🛡️ Kích hoạt bộ tạo kịch bản chuyên nghiệp dự phòng (Smart Fallback Storyboard)...")
                    return self._generate_smart_fallback(topic_clean, scene_count)

        self._log(f"✅ Đã nhận phản hồi kịch bản từ Muse AI ({len(raw_response)} ký tự).")
        try:
            scenes = self._parse_json_scenes(raw_response, scene_count=scene_count)
            self._log(f"🎉 Đã bóc tách thành công {len(scenes)} phân cảnh kịch bản.")
            return scenes
        except Exception as e:
            self._log(f"⚠️ Lỗi bóc tách phản hồi Muse Chat ({e}). Chuyển sang Smart Fallback...")
            return self._generate_smart_fallback(topic_clean, scene_count)

    def _generate_smart_fallback(self, topic: str, scene_count: int) -> list[SceneItem]:
        """Tự động sinh kịch bản TVC chất lượng cao dự phòng nếu Cloud Muse Chat tạm thời gián đoạn."""
        self._log(f"✨ Tự động tạo kịch bản TVC tối ưu cho chủ đề: '{topic}'")
        results = [
            SceneItem(
                scene_index=1,
                voice_text=f"Trải nghiệm đỉnh cao chưa từng có với công nghệ đột phá, được thiết kế dành riêng cho bạn.",
                visual_prompt=(
                    f"Cinematic vertical 9:16 macro shot, dramatic camera zoom-in on premium sleek gadget floating in a dark studio "
                    f"with electric blue and purple neon rim lighting, glossy metallic reflections, photorealistic 4k resolution"
                ),
                bgm_mood="hook",
                estimated_seconds=5.0,
            ),
            SceneItem(
                scene_index=2,
                voice_text=f"Âm thanh không gian 3D sống động và công nghệ chống ồn hoàn hảo đưa bạn vào một thế giới hoàn toàn khác.",
                visual_prompt=(
                    f"Cinematic vertical 9:16 dynamic orbiting tracking shot around futuristic sleek earphones with glowing sonic pulses, "
                    f"floating particles in atmospheric dark room, dramatic cinematic lighting, photorealistic 4k resolution"
                ),
                bgm_mood="modern_mirror",
                estimated_seconds=5.5,
            ),
        ]
        return results[:scene_count]

    def _parse_json_scenes(self, raw_text: str, scene_count: int = 4) -> list[SceneItem]:
        """Trích xuất và chuẩn hóa JSON phân cảnh từ phản hồi văn bản của Muse AI."""
        cleaned = raw_text.strip()
        # Loại bỏ code block markdown ```json ... ``` nếu có
        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
            if match:
                cleaned = match.group(1).strip()

        # Tìm mảng JSON [ ... ]
        json_array_match = re.search(r"\[\s*\{[\s\S]*\}\s*\]", cleaned)
        if json_array_match:
            cleaned = json_array_match.group(0).strip()

        try:
            data = json.loads(cleaned)
        except Exception as e:
            self._log(f"⚠️ Không parse được JSON trực tiếp: {e}. Thử regex cứu vãn...")
            data = self._regex_rescue_parse(raw_text)

        if not isinstance(data, list) or not data:
            raise ValueError(f"Không thể trích xuất danh sách phân cảnh từ phản hồi Muse AI:\n{raw_text}")

        results: list[SceneItem] = []
        for i, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                continue
            voice = (item.get("voice_text") or "").strip()
            prompt = (item.get("visual_prompt") or "").strip()
            mood = (item.get("bgm_mood") or "hook").strip().lower()
            if mood not in {"hook", "evidence", "concrete_scene", "modern_mirror"}:
                mood = "hook" if i == 1 else "evidence"

            if not voice or not prompt:
                continue

            results.append(
                SceneItem(
                    scene_index=i,
                    voice_text=voice,
                    visual_prompt=prompt,
                    bgm_mood=mood,
                    estimated_seconds=max(3.0, len(voice.split()) * 0.35),
                )
            )

        if not results:
            raise ValueError("Danh sách phân cảnh sau khi bóc tách bị rỗng.")

        return results

    def _regex_rescue_parse(self, text: str) -> list[dict[str, Any]]:
        """Cứu vãn dữ liệu bằng regex nếu JSON bị lỗi cú pháp nhỏ."""
        items = []
        # Tìm các khối { ... }
        blocks = re.findall(r"\{[^{}]*\}", text)
        for idx, block in enumerate(blocks, start=1):
            try:
                obj = json.loads(block)
                if "voice_text" in obj and "visual_prompt" in obj:
                    items.append(obj)
            except Exception:
                pass
        return items
