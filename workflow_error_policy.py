from __future__ import annotations

import random

RETRYABLE_ERROR_CODES = {"403", "13", "53", "500", "429"}

CONTENT_FILTER_CODES = {"3"}

CONTENT_FILTER_TOKENS = (
    "PUBLIC_ERROR_DANGER_FILTER",
    "PUBLIC_ERROR_AUDIO_FILTERED",
    "PUBLIC_ERROR_AUDIO_FILTER",
    "PUBLIC_ERROR_IP_INPUT_IMAGE",
    "PUBLIC_ERROR_PROMINENT_PEOPLE_FILTER_FAILED",
    "PROMINENT_PEOPLE_FILTER",
    "PROMINENT_PEOPLE",
    "IP_INPUT_IMAGE",
    "DANGER_FILTER",
    "AUDIO_FILTER",
    "CONTENT_FILTER",
)

HIGH_TRAFFIC_TOKENS = (
    "PUBLIC_ERROR_HIGH_TRAFFIC",
    "HIGH_TRAFFIC",
    "RATE_LIMIT",
    "TOO_MANY_REQUESTS",
    "TEMPORARILY_UNAVAILABLE",
)

QUOTA_EXHAUSTED_TOKENS = (
    "RESOURCE HAS BEEN EXHAUSTED",
    "RESOURCE_EXHAUSTED",
    "CHECK QUOTA",
    "QUOTA EXCEEDED",
    "INSUFFICIENT QUOTA",
)

RECAPTCHA_FAILED_TOKENS = (
    "RECAPTCHA EVALUATION FAILED",
    "RECAPTCHA_FAILED",
    "RECAPTCHA FAILED",
)

ERROR_KIND_RECAPTCHA_FAILED = "recaptcha_failed"
ERROR_KIND_QUOTA_EXHAUSTED = "quota_exhausted"
ERROR_KIND_CONTENT_FILTER = "content_filter"
ERROR_KIND_TIMEOUT = "timeout"
ERROR_KIND_NETWORK = "network"
ERROR_KIND_RETRYABLE = "retryable"
ERROR_KIND_UNKNOWN = "unknown"

RECAPTCHA_BACKOFF_RANGES_SECONDS = ((20, 35), (60, 90), (180, 300))
RECAPTCHA_BACKOFF_SECONDS = tuple(high for _low, high in RECAPTCHA_BACKOFF_RANGES_SECONDS)
RECAPTCHA_WINDOW_SECONDS = 600
RECAPTCHA_CIRCUIT_BREAKER_THRESHOLD = 4
RECAPTCHA_CIRCUIT_BREAKER_SECONDS = 300
QUOTA_COOLDOWN_SECONDS = 900
IMAGE_PROMPT_MAX_SAFE_CHARS = 1500


def _normalize_code(code) -> str:
    return str(code or "").strip()


def _normalize_message(message) -> str:
    return str(message or "").strip().upper()


def is_content_filter_error(code="", message="") -> bool:
    code_str = _normalize_code(code)
    msg = _normalize_message(message)
    if code_str in CONTENT_FILTER_CODES:
        return True
    return any(token in msg for token in CONTENT_FILTER_TOKENS)


def is_quota_exhausted_error(code="", message="") -> bool:
    msg = _normalize_message(message)
    return _normalize_code(code) == "429" or any(token in msg for token in QUOTA_EXHAUSTED_TOKENS)

def is_recaptcha_failed_error(code="", message="") -> bool:
    msg = _normalize_message(message)
    return any(token in msg for token in RECAPTCHA_FAILED_TOKENS)

def classify_api_error(code="", message="", *, status="", error="") -> str:
    code_str = _normalize_code(code or status)
    text = " ".join(str(part or "") for part in (message, error))
    msg = _normalize_message(text)
    if is_content_filter_error(code_str, msg):
        return ERROR_KIND_CONTENT_FILTER
    if is_quota_exhausted_error(code_str, msg):
        return ERROR_KIND_QUOTA_EXHAUSTED
    if is_recaptcha_failed_error(code_str, msg):
        return ERROR_KIND_RECAPTCHA_FAILED
    if "TIMEOUT" in msg:
        return ERROR_KIND_TIMEOUT
    if code_str in RETRYABLE_ERROR_CODES or any(token in msg for token in HIGH_TRAFFIC_TOKENS):
        return ERROR_KIND_RETRYABLE
    if not code_str and msg:
        return ERROR_KIND_NETWORK
    return ERROR_KIND_UNKNOWN

def recaptcha_backoff_seconds(consecutive_count: int, *, rng=None) -> int:
    idx = max(1, int(consecutive_count or 1)) - 1
    if idx >= len(RECAPTCHA_BACKOFF_RANGES_SECONDS):
        idx = len(RECAPTCHA_BACKOFF_RANGES_SECONDS) - 1
    low, high = RECAPTCHA_BACKOFF_RANGES_SECONDS[idx]
    generator = rng if rng is not None else random
    return int(generator.randint(int(low), int(high)))

def is_image_prompt_too_long(prompt: str, limit: int = IMAGE_PROMPT_MAX_SAFE_CHARS) -> bool:
    return len(str(prompt or "")) > int(limit)


def is_retryable_api_error(code="", message="") -> bool:
    code_str = _normalize_code(code)
    msg = _normalize_message(message)
    if is_content_filter_error(code_str, msg):
        return False
    if is_quota_exhausted_error(code_str, msg):
        return False
    if code_str in RETRYABLE_ERROR_CODES:
        return True
    return any(token in msg for token in HIGH_TRAFFIC_TOKENS)


def build_error_guidance(code="", message="") -> str:
    msg = _normalize_message(message)
    if is_quota_exhausted_error(code, msg):
        return "Tai khoan/quota Flow dang het luot cho endpoint nay. Retry tu dong se khong giai quyet; hay doi quota reset hoac doi tai khoan roi chay lai."
    if is_content_filter_error(code, msg):
        if "PROMINENT_PEOPLE" in msg:
            return "Flow dang nhan prompt hoac anh tham chieu nhu nguoi noi bat/nhan vat franchise. Hay giu ref nhung doi ten nhan vat, vu khi, va danh xung sang mo ta generic hon roi chay lai."
        if "IP_INPUT_IMAGE" in msg:
            return "Prompt da cham bo loc IP cua Flow. Hay doi ten nhan vat, vu khi, thuong hieu, hoac franchise sang mo ta generic roi chay lai."
        if "AUDIO_FILTER" in msg:
            return "Prompt hoac loi thoai bi bo loc noi dung cua Flow chan. Hay lam mem loi thoai va bo cac tu khoa nhay cam roi chay lai."
        return "Prompt bi bo loc noi dung/nguy hiem cua Flow chan. Hay giam yeu to bao luc, tai nan, tre em trong canh nguy hiem, hoac mo ta nhay cam roi chay lai."
    if any(token in msg for token in HIGH_TRAFFIC_TOKENS) or _normalize_code(code) == "13":
        return "Flow dang tai cao. Nen giu retry tu dong, giam MULTI_VIDEO neu loi lap lai nhieu."
    return ""
