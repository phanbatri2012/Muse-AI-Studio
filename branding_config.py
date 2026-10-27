from __future__ import annotations

EXPECTED_FOLDER_NAME = "VEO3_GROK_NEW"
import re  # noqa: E402
import json  # noqa: E402
import unicodedata  # noqa: E402

from runtime_paths import BRANDING_STATE_FILE  # noqa: E402

DEFAULT_OWNER_NAME = "Muse AI Studio"
DEFAULT_OWNER_PHONE = ""
DEFAULT_BOT_USERNAME = ""
TELEGRAM_ADMIN_URL = ""
TELEGRAM_BOT_URL = ""

#ngôn ngư chrome grok tiếng việt
APP_VERSION = "V1.0.0"
def _normalize_ascii(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.upper()


def _apply_owner_values(owner_name: str, owner_phone: str):
    global OWNER_NAME, OWNER_PHONE
    global OWNER_NAME_ASCII, OWNER_NAME_ASCII_COMPACT
    global EXPECTED_FOLDER_NAME, WINDOW_TITLE, COPYRIGHT_NOTICE, OWNER_UI_LABEL, OWNER_PHONE_LABEL
    global LICENSE_ACTIVATION_TEXT_MACHINE, LICENSE_ACTIVATION_TEXT_SHORT

    owner_name = str(owner_name or "").strip() or DEFAULT_OWNER_NAME
    owner_phone = str(owner_phone or "").strip() or DEFAULT_OWNER_PHONE

    OWNER_NAME = owner_name
    OWNER_PHONE = owner_phone

    OWNER_NAME_ASCII = _normalize_ascii(OWNER_NAME).replace("_", " ")
    OWNER_NAME_ASCII_COMPACT = _normalize_ascii(OWNER_NAME)
    OWNER_PHONE_LABEL = f"Tele: {OWNER_PHONE}"

    EXPECTED_FOLDER_NAME = f"{OWNER_NAME_ASCII_COMPACT}_{OWNER_PHONE}"
    WINDOW_TITLE = f"MUSE AI STUDIO - Tele: {OWNER_NAME} ({OWNER_PHONE})"

    COPYRIGHT_NOTICE = (
        f"Bản quyền thuộc về {OWNER_NAME_ASCII} Tele: {OWNER_PHONE}.\n"
        "Liên hệ trực tiếp để admin mua tool chính hãng và được bảo hành.\n"
        "Mua bên khác sẽ không được bảo hành. Rủi ro tự mình chịu."
    )

    OWNER_UI_LABEL = f"{OWNER_NAME} Tele: {OWNER_PHONE}"

    LICENSE_ACTIVATION_TEXT_MACHINE = (
        f"Copy Mã MACHINE_ID rồi gửi cho Admin {OWNER_NAME} Tele: {OWNER_PHONE} để kích hoạt"
    )
    LICENSE_ACTIVATION_TEXT_SHORT = (
        f"Copy Mã máy rồi gửi cho Admin {OWNER_NAME} Tele: {OWNER_PHONE} để kích hoạt"
    )


def _load_owner_from_state():
    try:
        if not BRANDING_STATE_FILE.exists():
            return None
        payload = json.loads(BRANDING_STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        owner_name = str(payload.get("name", "")).strip()
        owner_phone = str(payload.get("sdt", "")).strip()
        if owner_name and owner_phone:
            return owner_name, owner_phone
    except Exception:
        return None
    return None


def save_runtime_owner(owner_name: str, owner_phone: str) -> bool:
    owner_name = str(owner_name or "").strip()
    owner_phone = str(owner_phone or "").strip()

    if not owner_name or not owner_phone:
        return False

    _apply_owner_values(owner_name, owner_phone)

    try:
        BRANDING_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        BRANDING_STATE_FILE.write_text(
            json.dumps({"name": OWNER_NAME, "sdt": OWNER_PHONE}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


_apply_owner_values(DEFAULT_OWNER_NAME, DEFAULT_OWNER_PHONE)

_saved_owner = _load_owner_from_state()
if _saved_owner:
    _apply_owner_values(_saved_owner[0], _saved_owner[1])
