from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DISPLAY_NAME = os.getenv("TOOL_VEO_APP_NAME", "Muse AI Studio").strip() or "Muse AI Studio"
PROJECT_DATA_FILE = "test.json"


def _resolve_install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _resolve_bundle_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        try:
            return Path(str(meipass)).resolve()
        except Exception:
            pass
    return _resolve_install_dir()


def _resolve_user_data_dir() -> Path:
    override = str(os.getenv("TOOL_VEO_USER_DATA_DIR", "") or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    if getattr(sys, "frozen", False) and os.name == "nt":
        local_appdata = str(os.getenv("LOCALAPPDATA", "") or "").strip()
        if local_appdata:
            return (Path(local_appdata) / APP_DISPLAY_NAME).resolve()
        appdata = str(os.getenv("APPDATA", "") or "").strip()
        if appdata:
            return (Path(appdata) / APP_DISPLAY_NAME).resolve()

    return _resolve_install_dir()


INSTALL_DIR = _resolve_install_dir()
BASE_DIR = INSTALL_DIR
BUNDLE_DIR = _resolve_bundle_dir()
USER_DATA_DIR = _resolve_user_data_dir()

DATA_GENERAL_DIR = USER_DATA_DIR / "data_general"
WORKFLOWS_DIR = USER_DATA_DIR / "Workflows"
DOWNLOADS_DIR = USER_DATA_DIR / "downloads"
CHROME_USER_DATA_ROOT = USER_DATA_DIR / "chrome_user_data"
RUNTIME_DIR = USER_DATA_DIR / "runtime"
RUNTIME_BIN_DIR = RUNTIME_DIR / "bin"
MANAGED_CHROME_ROOT = RUNTIME_DIR / "chrome"

SETTINGS_FILE = DATA_GENERAL_DIR / "settings.json"
CONFIG_FILE = DATA_GENERAL_DIR / "config.json"
BRANDING_STATE_FILE = DATA_GENERAL_DIR / "branding_state.json"
LICENSE_STATE_FILE = DATA_GENERAL_DIR / "license_state.json"
LICENSE_DISPLAY_FILE = DATA_GENERAL_DIR / "license_display.json"  # unencrypted, UI-readable
USER_LICENSE_FILE = DATA_GENERAL_DIR / "user_data.txt"
LICENSE_LOCK_FILE = DATA_GENERAL_DIR / "license_checker.lock"

# Muse AI specific paths
MUSE_CHROME_USER_DATA_ROOT = CHROME_USER_DATA_ROOT / "muse_profiles"
MUSE_DOWNLOADS_DIR = DOWNLOADS_DIR / "muse"
MUSE_SETTINGS_FILE = DATA_GENERAL_DIR / "muse_settings.json"
MUSE_SESSION_FILE = DATA_GENERAL_DIR / "muse_session.json"
MUSE2API_DATA_DIR = USER_DATA_DIR / "muse2api_data"


def ensure_runtime_dirs() -> None:
    for path in (
        DATA_GENERAL_DIR,
        WORKFLOWS_DIR,
        DOWNLOADS_DIR,
        CHROME_USER_DATA_ROOT,
        RUNTIME_DIR,
        RUNTIME_BIN_DIR,
        MANAGED_CHROME_ROOT,
        MUSE_CHROME_USER_DATA_ROOT,
        MUSE_DOWNLOADS_DIR,
        MUSE2API_DATA_DIR,
    ):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass


def get_icon_path(name: str) -> str:
    filename = str(name or "").strip()
    if not filename:
        return ""
    candidates = [
        INSTALL_DIR / filename,
        BUNDLE_DIR / filename,
        INSTALL_DIR / "icons" / filename,
        BUNDLE_DIR / "icons" / filename,
        INSTALL_DIR / "logo" / filename,
        BUNDLE_DIR / "logo" / filename,
    ]
    for path in candidates:
        try:
            if path.is_file():
                return str(path)
        except Exception:
            continue
    return ""


def resolve_packaged_file(*relative_parts: str) -> Path | None:
    cleaned = [str(part or "").strip("/\\") for part in relative_parts if str(part or "").strip("/\\")]
    if not cleaned:
        return None
    rel_path = Path(*cleaned)
    for root in (INSTALL_DIR, BUNDLE_DIR):
        candidate = root / rel_path
        try:
            if candidate.exists():
                return candidate
        except Exception:
            continue
    return None


ensure_runtime_dirs()
