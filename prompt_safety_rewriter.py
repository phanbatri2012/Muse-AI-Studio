from __future__ import annotations

import json
import re

from prompt_utils import detect_prompt_schema, parse_prompt_json, serialize_scene_prompt


_TEXT_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bHulk\b", re.IGNORECASE), "gamma-powered giant"),
    (re.compile(r"\bBruce Banner\b", re.IGNORECASE), "scientist inside the gamma-powered giant"),
    (re.compile(r"\bThor\b", re.IGNORECASE), "storm-wielding armored warrior"),
    (re.compile(r"\bMjolnir\b", re.IGNORECASE), "rune-etched war hammer"),
    (re.compile(r"\bAsgard(?:ian)?\b", re.IGNORECASE), "mythic sky-realm"),
    (re.compile(r"\bAvengers?\b", re.IGNORECASE), "legendary hero team"),
    (re.compile(r"\bMarvel\b", re.IGNORECASE), "comic-book-inspired"),
    (re.compile(r"\bto the death\b", re.IGNORECASE), "in a high-stakes survival clash"),
    (re.compile(r"\bthe bloodiest\b", re.IGNORECASE), "the most intense"),
    (re.compile(r"\bbloodiest\b", re.IGNORECASE), "most intense"),
    (re.compile(r"\bno peaceful scenes\b", re.IGNORECASE), "keep the pacing relentless and tense"),
    (re.compile(r"\bblood[- ]?spatter(?:ing)?\b", re.IGNORECASE), "mud and water spray"),
    (re.compile(r"\bblood[- ]?splatter(?:ing)?\b", re.IGNORECASE), "mud and water spray"),
    (re.compile(r"\bblood\b", re.IGNORECASE), "mud and spray"),
    (re.compile(r"\bbloody\b", re.IGNORECASE), "chaotic"),
    (re.compile(r"\bfangs sinking deep into flesh\b", re.IGNORECASE), "jaws clamping onto prey in a tense struggle"),
    (re.compile(r"\bsinking deep into flesh\b", re.IGNORECASE), "making forceful contact in a tense struggle"),
    (re.compile(r"\bflesh\b", re.IGNORECASE), "hide"),
    (re.compile(r"\bcrushing the bones of\b", re.IGNORECASE), "overwhelming"),
    (re.compile(r"\bbones\b", re.IGNORECASE), "frame"),
    (re.compile(r"\bstripping a carcass clean\b", re.IGNORECASE), "swarming around prey in frantic motion"),
    (re.compile(r"\bstripping a prey clean\b", re.IGNORECASE), "swarming around prey in frantic motion"),
    (re.compile(r"\bcarcass\b", re.IGNORECASE), "prey"),
    (re.compile(r"\bfeeding frenzy\b", re.IGNORECASE), "chaotic rush"),
    (re.compile(r"\bmassacre\b", re.IGNORECASE), "relentless clash"),
    (re.compile(r"\bbrutal\b", re.IGNORECASE), "intense"),
    (re.compile(r"\bbrutally\b", re.IGNORECASE), "intensely"),
    (re.compile(r"\bviolent explosion\b", re.IGNORECASE), "sudden fiery burst"),
    (re.compile(r"\bcatastrophic explosions?\b", re.IGNORECASE), "dangerous flare-ups"),
    (re.compile(r"\bexplosions?\b", re.IGNORECASE), "flare-ups"),
    (re.compile(r"\bblood must be spilled\b", re.IGNORECASE), "survival must be earned"),
    (re.compile(r"\bmust be spilled\b", re.IGNORECASE), "must be endured"),
    (re.compile(r"\bkill(?:ing|ed|s)?\b", re.IGNORECASE), "overpower"),
    (re.compile(r"\bdeath\b", re.IGNORECASE), "survival"),
]

_REFERENCE_MODE_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bdivine\b", re.IGNORECASE), "mythic"),
    (re.compile(r"\bgod\b", re.IGNORECASE), "champion"),
    (re.compile(r"\bhammer\b", re.IGNORECASE), "charged weapon"),
    (re.compile(r"\bthunder(?:bolt|ous)?\b", re.IGNORECASE), "storm energy"),
]

_SAFETY_SUFFIX = (
    "Keep the scene non-graphic and cinematic. No visible blood, gore, exposed wounds, broken bones, "
    "carcasses, or explicit killing. Focus on tension, motion, reaction shots, and atmospheric aftermath. "
    "Any young character remains safe and unharmed on screen."
)


def _apply_replacements(text: str) -> str:
    value = str(text or "")
    for pattern, replacement in _TEXT_REPLACEMENTS:
        value = pattern.sub(replacement, value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value.strip()


def _append_suffix(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return _SAFETY_SUFFIX
    if _SAFETY_SUFFIX.lower() in value.lower():
        return value
    joiner = " " if not value.endswith((".", "!", "?")) else " "
    return f"{value}{joiner}{_SAFETY_SUFFIX}".strip()


def _sanitize_json_like(obj, *, key: str = "", path: tuple[str, ...] = ()):
    normalized_key = str(key or "")
    current_path = path
    if normalized_key and (not path or path[-1] != normalized_key):
        current_path = path + (normalized_key,)
    if isinstance(obj, dict):
        out = {}
        for raw_key, raw_value in obj.items():
            child_key = str(raw_key or "")
            out[raw_key] = _sanitize_json_like(raw_value, key=child_key, path=current_path)
        for note_key in ("summary", "visual_style", "lip_sync_director_note"):
            if isinstance(out.get(note_key), str):
                out[note_key] = _append_suffix(str(out.get(note_key) or ""))
        action_obj = out.get("action")
        if isinstance(action_obj, dict):
            for action_key in ("primary_action", "secondary_motion"):
                if isinstance(action_obj.get(action_key), str):
                    action_obj[action_key] = _append_suffix(str(action_obj.get(action_key) or ""))
        return out
    if isinstance(obj, list):
        return [_sanitize_json_like(item, key=key, path=current_path) for item in obj]
    if isinstance(obj, str):
        sanitized = _apply_replacements(obj)
        if current_path[-2:] == ("constraints", "negative_prompt"):
            return sanitized
        if str(key or "") in {"summary", "visual_style", "lip_sync_director_note"}:
            sanitized = _append_suffix(sanitized)
        if current_path[-2:] == ("action", "primary_action") or current_path[-2:] == ("action", "secondary_motion"):
            sanitized = _append_suffix(sanitized)
        return sanitized
    return obj


def rewrite_prompt_for_content_filter(text: str) -> tuple[str, bool]:
    original = str(text or "")
    stripped = original.strip()
    if not stripped:
        return original, False

    parsed = parse_prompt_json(stripped)
    schema_kind = detect_prompt_schema(parsed or stripped)

    if parsed is not None:
        sanitized = _sanitize_json_like(parsed)
        if schema_kind == "v2":
            rewritten = serialize_scene_prompt(sanitized)
        else:
            rewritten = json.dumps(sanitized, ensure_ascii=False)
    else:
        rewritten = _append_suffix(_apply_replacements(stripped))

    return rewritten, rewritten.strip() != stripped


def _collect_reference_alias_tokens(reference_aliases: list[str] | None) -> list[tuple[str, str]]:
    ordered: list[tuple[str, str]] = []
    seen_tokens: set[str] = set()
    label_by_root: dict[str, str] = {}
    for raw_alias in list(reference_aliases or []):
        alias = str(raw_alias or "").strip()
        if not alias:
            continue
        stem = str(alias.split("_", 1)[0] or alias).strip()
        root_key = stem.lower()
        label = label_by_root.get(root_key)
        if not label:
            label = f"reference subject {chr(ord('A') + min(len(label_by_root), 25))}"
            label_by_root[root_key] = label
        for candidate in (alias, stem):
            key = candidate.lower()
            if key in seen_tokens:
                continue
            seen_tokens.add(key)
            ordered.append((candidate, label))
    return ordered


def rewrite_reference_prompt_for_content_filter(text: str, reference_aliases: list[str] | None = None) -> tuple[str, bool]:
    original = str(text or "")
    rewritten, _changed = rewrite_prompt_for_content_filter(original)
    value = str(rewritten or "")

    alias_tokens = _collect_reference_alias_tokens(reference_aliases)
    for alias, label in alias_tokens:
        escaped = re.escape(alias)
        value = re.sub(rf"\bcharacter\s+{escaped}\b", label, value, flags=re.IGNORECASE)
        value = re.sub(rf"\b{escaped}\b", label, value, flags=re.IGNORECASE)

    for pattern, replacement in _REFERENCE_MODE_REPLACEMENTS:
        value = pattern.sub(replacement, value)

    value = re.sub(r"[ \t]{2,}", " ", value).strip()
    return value, value.strip() != original.strip()
