from __future__ import annotations

import copy
import json
import re
from typing import Any

# ============================================================================
# Prompt quality & cleanup helpers (Google VEO 3.1 / Imagen)
# ============================================================================

EXAGGERATED_WORDS: frozenset[str] = frozenset({
    "stunning", "amazing", "incredible", "perfect", "flawless",
    "mind-blowing", "breathtaking", "ultimate", "extraordinary",
    "phenomenal", "spectacular", "awesome", "best",
})

_EXAGGERATED_PHRASES: tuple[str, ...] = (
    "hyper-realistic beyond imagination",
    "ultra-mega",
    "insanely detailed",
    "godlike quality",
    "beyond human comprehension",
    "absolutely stunning masterpiece",
    "jaw-dropping",
    "unbelievably realistic",
    "next level quality",
    "the most beautiful",
    "perfect in every way",
)

_EXAGGERATED_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in EXAGGERATED_WORDS) + r")\b",
    re.IGNORECASE,
)
_EXAGGERATED_PHRASE_PATTERN = re.compile(
    r"(" + "|".join(re.escape(p) for p in _EXAGGERATED_PHRASES) + r")",
    re.IGNORECASE,
)

_AUDIO_INSTRUCTION_PATTERN = re.compile(
    r"\b(music|voiceover|voice over|narration|narrator says|"
    r"background music|generated music|soundtrack|theme song)\b"
    r"\s*[:\-][^.!?]*[.!?]?",
    re.IGNORECASE,
)


def _ensure_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _f(v: Any) -> str:
    return str(v).strip() if v else ""


def _a(lst: list, v: Any) -> None:
    s = _f(v)
    if s:
        lst.append(s)


def _clean_assembled(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "")
    cleaned = re.sub(r"\s*,\s*,", ",", cleaned)
    cleaned = re.sub(r"\s*,\s*\.", ".", cleaned)
    return cleaned.strip(" ,.")


def _strip_markdown_fence(text: str) -> str:
    value = str(text or "").strip()
    if value.startswith("```"):
        parts = value.split("```")
        if len(parts) >= 3:
            value = parts[1]
            if value.lstrip().startswith("json"):
                value = value.lstrip()[4:]
    return value.strip()


def _sanitize_json_text(text: str) -> str:
    value = _strip_markdown_fence(text)
    value = value.replace("\ufeff", "")
    value = value.replace("“", '"').replace("”", '"').replace("’", "'")
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
    return value.strip()


def parse_prompt_json(prompt_text: Any) -> dict | list | None:
    if isinstance(prompt_text, (dict, list)):
        return prompt_text
    if not isinstance(prompt_text, str):
        return None
    raw = _sanitize_json_text(prompt_text)
    if not raw or not (raw.startswith("{") or raw.startswith("[")):
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, (dict, list)) else None
    except Exception:
        return None


def detect_prompt_schema(prompt_obj_or_text: Any) -> str:
    if isinstance(prompt_obj_or_text, str):
        parsed = parse_prompt_json(prompt_obj_or_text)
    elif isinstance(prompt_obj_or_text, (dict, list)):
        parsed = prompt_obj_or_text
    else:
        return "plaintext"
    if isinstance(parsed, dict):
        if parsed.get("schema_version") == "2.0" or "scene_id" in parsed:
            return "v2"
        return "v1"
    return "plaintext"


def strip_exaggerated_words(text: str) -> tuple[str, list[str]]:
    removed: list[str] = []

    def _replace_phrase(match: re.Match[str]) -> str:
        removed.append(match.group(0).lower())
        return ""

    cleaned = _EXAGGERATED_PHRASE_PATTERN.sub(_replace_phrase, text or "")

    def _replace_word(match: re.Match[str]) -> str:
        removed.append(match.group(0).lower())
        return ""

    cleaned = _EXAGGERATED_PATTERN.sub(_replace_word, cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s*,\s*,", ",", cleaned)
    cleaned = re.sub(r"\s*,\s*\.", ".", cleaned)
    cleaned = cleaned.strip(" ,.")
    return cleaned, removed


def strip_audio_instructions(text: str) -> tuple[str, int]:
    matches = list(_AUDIO_INSTRUCTION_PATTERN.finditer(text or ""))
    cleaned = _AUDIO_INSTRUCTION_PATTERN.sub("", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, len(matches)


def assess_prompt_quality(text: str, mode: str = "video") -> dict:
    text = str(text or "")
    n = len(text)
    if mode == "video":
        ideal_min, ideal_max, hard_min, hard_max = 200, 500, 150, 1200
    else:
        ideal_min, ideal_max, hard_min, hard_max = 150, 400, 100, 1500
    warning: str | None = None
    if n < hard_min:
        warning = f"Prompt quá ngắn ({n} chars, tối thiểu {hard_min}), output sẽ generic"
    elif n > hard_max:
        warning = f"Prompt quá dài ({n} chars, tối đa {hard_max}), tăng rủi ro silent reject"
    elif n < ideal_min:
        warning = f"Prompt hơi ngắn ({n} chars, lý tưởng {ideal_min}-{ideal_max})"
    elif n > ideal_max:
        warning = f"Prompt hơi dài ({n} chars, lý tưởng {ideal_min}-{ideal_max})"
    return {
        "char_count": n,
        "in_safe_range": hard_min <= n <= hard_max,
        "in_ideal_range": ideal_min <= n <= ideal_max,
        "warning": warning,
        "ideal_range": f"{ideal_min}-{ideal_max}",
    }


def looks_like_serialized_scene_prompt(prompt_text: Any) -> bool:
    if isinstance(prompt_text, dict):
        return True
    if not isinstance(prompt_text, str):
        return False
    raw = prompt_text.strip()
    return raw.startswith("{") and ("scene_id" in raw or "summary" in raw or "action" in raw or "character" in raw)


def _build_plaintext_from_dict(payload: dict) -> str:
    if "prompt" in payload and isinstance(payload["prompt"], str):
        return payload["prompt"]
    parts: list[str] = []

    # Summary / Description
    summary = payload.get("summary") or payload.get("description")
    if summary and isinstance(summary, str):
        parts.append(summary.strip())

    # Visual style
    style = payload.get("visual_style") or payload.get("style")
    if style and isinstance(style, str):
        parts.append(f"Style: {style.strip()}")

    # Action
    action = payload.get("action")
    if isinstance(action, dict):
        act_parts = [str(v).strip() for v in action.values() if isinstance(v, str) and str(v).strip()]
        if act_parts:
            parts.append(f"Action: {', '.join(act_parts)}")
    elif isinstance(action, str) and action.strip():
        parts.append(f"Action: {action.strip()}")

    # Camera
    camera = payload.get("camera")
    if isinstance(camera, dict):
        cam_parts = [str(v).strip() for v in camera.values() if isinstance(v, str) and str(v).strip()]
        if cam_parts:
            parts.append(f"Camera: {', '.join(cam_parts)}")
    elif isinstance(camera, str) and camera.strip():
        parts.append(f"Camera: {camera.strip()}")

    # Lighting
    lighting = payload.get("lighting")
    if isinstance(lighting, dict):
        lt_parts = [str(v).strip() for v in lighting.values() if isinstance(v, str) and str(v).strip()]
        if lt_parts:
            parts.append(f"Lighting: {', '.join(lt_parts)}")
    elif isinstance(lighting, str) and lighting.strip():
        parts.append(f"Lighting: {lighting.strip()}")

    # Constraints / Negative prompt / Avoid
    constraints = payload.get("constraints")
    if isinstance(constraints, dict):
        avoid_list = constraints.get("negative_prompt") or []
        if isinstance(avoid_list, list) and avoid_list:
            parts.append(f"Avoid: {', '.join(str(x) for x in avoid_list if str(x).strip())}")
    elif isinstance(payload.get("avoid"), (list, str)):
        av = payload.get("avoid")
        if isinstance(av, list):
            parts.append(f"Avoid: {', '.join(str(x) for x in av if str(x).strip())}")
        elif isinstance(av, str) and av.strip():
            parts.append(f"Avoid: {av.strip()}")

    neg = payload.get("negative_prompt")
    if isinstance(neg, list) and neg:
        parts.append(f"Avoid: {', '.join(str(x) for x in neg if str(x).strip())}")
    elif isinstance(neg, str) and neg.strip():
        parts.append(f"Avoid: {neg.strip()}")

    # Audio / Sound design
    audio = payload.get("audio")
    if isinstance(audio, dict):
        sound_items = []
        for k, v in audio.items():
            if isinstance(v, dict):
                sound_items.extend([str(val).strip() for val in v.values() if isinstance(val, str) and str(val).strip()])
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        sound_items.extend([str(val).strip() for val in item.values() if isinstance(val, str) and str(val).strip()])
                    elif isinstance(item, str) and item.strip():
                        sound_items.append(item.strip())
            elif isinstance(v, str) and v.strip():
                sound_items.append(v.strip())
        if sound_items:
            parts.append(f"Sound design: {', '.join(sound_items)}")
    elif isinstance(audio, str) and audio.strip():
        parts.append(f"Sound design: {audio.strip()}")

    # Rendering parameters
    render = payload.get("rendering_parameters") or payload.get("render")
    if isinstance(render, dict):
        render_items = [f"{k}: {v}" if isinstance(v, str) and not v.startswith(str(k)) else str(v) for k, v in render.items() if str(v).strip()]
        if render_items:
            parts.append(f"Render: {', '.join(render_items)}")
    elif isinstance(render, str) and render.strip():
        parts.append(f"Render: {render.strip()}")

    if not parts:
        for k, v in payload.items():
            if isinstance(v, str) and v.strip():
                parts.append(v.strip())
            elif isinstance(v, dict):
                sub_parts = [str(x).strip() for x in v.values() if isinstance(x, str) and str(x).strip()]
                if sub_parts:
                    parts.append(", ".join(sub_parts))

    return ". ".join(parts) if parts else json.dumps(payload, ensure_ascii=False)


def normalize_text_to_video_prompt(
    prompt_text: Any,
    *,
    prompt_v3: dict[str, Any] | None = None,
) -> str:
    text = ""
    if isinstance(prompt_v3, dict):
        creative_brief = prompt_v3.get("creative_brief") or {}
        shot_plan = prompt_v3.get("shot_plan") or {}
        merged = {}
        if isinstance(creative_brief, dict):
            merged.update(creative_brief)
        if isinstance(shot_plan, dict):
            merged.update(shot_plan)
        text = _build_plaintext_from_dict(merged)
    else:
        parsed_prompt = parse_prompt_json(prompt_text)
        if isinstance(parsed_prompt, dict):
            text = _build_plaintext_from_dict(parsed_prompt)
        elif not text:
            text = _ensure_text(prompt_text)

    text, _removed = strip_exaggerated_words(text)
    return text


def normalize_image_to_video_prompt(prompt_text: Any) -> str:
    return normalize_text_to_video_prompt(prompt_text)


def normalize_image_generation_prompt(prompt_text: Any) -> str:
    raw_text = _ensure_text(prompt_text)
    text = ""
    parsed = parse_prompt_json(prompt_text)
    if isinstance(parsed, dict):
        text = _build_plaintext_from_dict(parsed)
    if not text:
        text = raw_text
    text, _removed_audio = strip_audio_instructions(text)
    text, _removed_exag = strip_exaggerated_words(text)
    return text


def serialize_scene_prompt(scene_obj: dict) -> str:
    if isinstance(scene_obj, str):
        return scene_obj
    return json.dumps(scene_obj or {}, ensure_ascii=False)


class PromptBuilder:
    @staticmethod
    def build_image_prompt(json_input: dict) -> str:
        char = dict(json_input.get("character") or {})
        scene = dict(json_input.get("scene") or {})
        comp = dict(json_input.get("composition") or {})
        qual = dict(json_input.get("quality") or {})

        parts: list[str] = []
        _a(parts, char.get("description"))
        _a(parts, char.get("expression"))
        _a(parts, char.get("outfit"))
        _a(parts, scene.get("environment"))
        _a(parts, scene.get("lighting"))
        _a(parts, comp.get("shot_type"))
        _a(parts, comp.get("framing"))
        _a(parts, comp.get("depth"))
        _a(parts, scene.get("atmosphere"))
        _a(parts, qual.get("style"))
        _a(parts, char.get("style_lock"))
        _a(parts, qual.get("resolution"))
        _a(parts, qual.get("extra_boosters"))

        result = _clean_assembled(", ".join(parts))
        return result

    @staticmethod
    def build_i2v_prompt(json_input: dict) -> str:
        motion = dict(json_input.get("motion") or {})
        char = dict(json_input.get("character") or {})
        scene = dict(json_input.get("scene") or {})
        cam = dict(json_input.get("camera") or {})
        audio = dict(json_input.get("audio") or {})
        qual = dict(json_input.get("quality") or {})

        subject_action = _f(motion.get("subject_action"))
        if not subject_action:
            raise ValueError("motion.subject_action là bắt buộc — không được rỗng")

        parts: list[str] = [subject_action]
        _a(parts, char.get("description"))
        _a(parts, scene.get("environment"))
        _a(parts, scene.get("lighting"))
        _a(parts, cam.get("movement"))
        _a(parts, cam.get("shot_type"))
        _a(parts, cam.get("lens_behavior"))
        _a(parts, motion.get("speed"))
        _a(parts, motion.get("transition"))
        _a(parts, scene.get("atmosphere"))
        _a(parts, qual.get("style"))
        _a(parts, char.get("style_lock"))
        _a(parts, audio.get("ambient"))
        _a(parts, audio.get("music_style"))

        result = _clean_assembled(", ".join(parts))
        if not result.strip():
            raise ValueError("Prompt rỗng sau assembly — PROMPT_EMPTY")
        return result

    @staticmethod
    def build_i2v_startend_prompt(json_input: dict) -> str:
        td = _f(json_input.get("transition_description"))
        if not td:
            raise ValueError("transition_description là bắt buộc — không được rỗng")

        start = _f(json_input.get("start_scene"))
        end = _f(json_input.get("end_scene"))
        motion = dict(json_input.get("motion") or {})
        cam = dict(json_input.get("camera") or {})
        scene = dict(json_input.get("scene") or {})
        audio = dict(json_input.get("audio") or {})
        qual = dict(json_input.get("quality") or {})

        sentences: list[str] = []
        if start and end:
            sentences.append(f"From {start} to {end}.")
        sentences.append(td + ".")

        tail: list[str] = []
        for v in [
            motion.get("process"), motion.get("speed"),
            scene.get("lighting_change"), cam.get("movement"),
            scene.get("atmosphere"), qual.get("style"), audio.get("ambient"),
        ]:
            _a(tail, v)

        parts = sentences + ([", ".join(tail)] if tail else [])
        result = _clean_assembled(" ".join(parts))
        return result


def validate_character_consistency(prompts: list[dict]) -> dict:
    character_blocks: list[tuple[int, dict]] = []
    for i, prompt in enumerate(prompts):
        if isinstance(prompt, dict) and "character" in prompt:
            character_blocks.append((i, dict(prompt["character"])))

    if len(character_blocks) <= 1:
        return {"consistent": True, "warnings": [], "character_variations": {}}

    warnings: list[str] = []
    variations: dict[str, list[int]] = {}
    CRITICAL_FIELDS = ["description", "style_lock"]
    IMPORTANT_FIELDS = ["outfit"]

    base_idx, base_char = character_blocks[0]
    for scene_idx, char in character_blocks[1:]:
        for field in CRITICAL_FIELDS:
            base_val = str(base_char.get(field) or "").strip().lower()
            curr_val = str(char.get(field) or "").strip().lower()
            if base_val != curr_val:
                key = f"character.{field}"
                variations.setdefault(key, []).append(scene_idx)
                warnings.append(
                    f"⚠️ CHARACTER CONSISTENCY: character.{field} khác nhau giữa scene {base_idx} và {scene_idx}."
                )
        for field in IMPORTANT_FIELDS:
            base_val = str(base_char.get(field) or "").strip().lower()
            curr_val = str(char.get(field) or "").strip().lower()
            if base_val != curr_val:
                warnings.append(
                    f"ℹ️ CHARACTER NOTE: character.{field} khác nhau giữa scene {base_idx} và {scene_idx}."
                )

    return {
        "consistent": len(variations) == 0,
        "warnings": warnings,
        "character_variations": variations,
    }


def clone_character_to_all_scenes(
    prompts: list[dict], source_scene_index: int = 0
) -> list[dict]:
    result = copy.deepcopy(prompts)
    if source_scene_index >= len(result):
        return result
    source = result[source_scene_index]
    if not isinstance(source, dict) or "character" not in source:
        return result

    source_char = source["character"]
    CLONE_FIELDS = ["description", "style_lock"]
    for i, prompt in enumerate(result):
        if i == source_scene_index:
            continue
        if not isinstance(prompt, dict) or "character" not in prompt:
            continue
        for field in CLONE_FIELDS:
            if field in source_char:
                prompt["character"][field] = source_char[field]
    return result
