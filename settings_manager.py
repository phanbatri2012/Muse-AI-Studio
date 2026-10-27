from __future__ import annotations

import json
import os

from runtime_paths import (
    BASE_DIR,  # noqa: F401  (re-exported for other modules)
    CHROME_USER_DATA_ROOT,
    CONFIG_FILE,
    DATA_GENERAL_DIR,
    DOWNLOADS_DIR,  # noqa: F401  (re-exported for other modules)
    MUSE_CHROME_USER_DATA_ROOT,
    MUSE_DOWNLOADS_DIR,
    MUSE_SESSION_FILE,
    MUSE_SETTINGS_FILE,
    PROJECT_DATA_FILE,  # noqa: F401  (re-exported for other modules)
    SETTINGS_FILE,
    WORKFLOWS_DIR,  # noqa: F401  (re-exported for other modules)
    ensure_runtime_dirs,
    get_icon_path,  # noqa: F401  (re-exported for other modules)
)

ensure_runtime_dirs()


class SettingsManager:
    @staticmethod
    def load_config() -> dict:
        try:
            if CONFIG_FILE.exists():
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    @staticmethod
    def save_config(config: dict) -> None:
        DATA_GENERAL_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config or {}, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load_settings() -> dict:
        try:
            if SETTINGS_FILE.exists():
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {"current_profile": os.getenv("PROFILE_NAME", "PROFILE_1")}

    @staticmethod
    def save_settings(settings: dict) -> None:
        DATA_GENERAL_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings or {}, f, ensure_ascii=False, indent=2)

    @staticmethod
    def create_chrome_userdata_folder(profile_name: str | None = None) -> str:
        profile = str(profile_name or os.getenv("PROFILE_NAME", "PROFILE_1")).strip() or "PROFILE_1"
        path = CHROME_USER_DATA_ROOT / profile
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    # ------------------------------------------------------------------------
    # Muse AI Configuration & Session Management
    # ------------------------------------------------------------------------
    @staticmethod
    def load_muse_settings() -> dict:
        defaults = {
            "target_url": "https://muse.ai/",
            "current_profile": os.getenv("MUSE_PROFILE_NAME", "MUSE_PROFILE_1"),
            "max_concurrent_tasks": 2,
            "task_timeout_seconds": 300,
            "download_dir": str(MUSE_DOWNLOADS_DIR),
        }
        try:
            if MUSE_SETTINGS_FILE.exists():
                data = json.loads(MUSE_SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    defaults.update(data)
        except Exception:
            pass
        return defaults

    @staticmethod
    def save_muse_settings(settings: dict) -> None:
        DATA_GENERAL_DIR.mkdir(parents=True, exist_ok=True)
        with open(MUSE_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings or {}, f, ensure_ascii=False, indent=2)

    @staticmethod
    def create_muse_userdata_folder(profile_name: str | None = None) -> str:
        profile = str(profile_name or os.getenv("MUSE_PROFILE_NAME", "MUSE_PROFILE_1")).strip() or "MUSE_PROFILE_1"
        path = MUSE_CHROME_USER_DATA_ROOT / profile
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @staticmethod
    def load_muse_session() -> dict:
        try:
            if MUSE_SESSION_FILE.exists():
                data = json.loads(MUSE_SESSION_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    @staticmethod
    def save_muse_session(session_data: dict) -> None:
        DATA_GENERAL_DIR.mkdir(parents=True, exist_ok=True)
        with open(MUSE_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session_data or {}, f, ensure_ascii=False, indent=2)
