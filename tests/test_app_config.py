from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import settings_manager
from settings_manager import SettingsManager


class AppConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="test_app_config_")
        self._tmp_path = Path(self._tmpdir.name)
        self._orig_config_file = settings_manager.CONFIG_FILE
        self._orig_settings_file = settings_manager.SETTINGS_FILE
        self._orig_data_dir = settings_manager.DATA_GENERAL_DIR

        settings_manager.DATA_GENERAL_DIR = self._tmp_path
        settings_manager.CONFIG_FILE = self._tmp_path / "config.json"
        settings_manager.SETTINGS_FILE = self._tmp_path / "settings.json"

    def tearDown(self) -> None:
        settings_manager.DATA_GENERAL_DIR = self._orig_data_dir
        settings_manager.CONFIG_FILE = self._orig_config_file
        settings_manager.SETTINGS_FILE = self._orig_settings_file
        self._tmpdir.cleanup()

    def _write_config(self, payload: dict) -> None:
        settings_manager.CONFIG_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def test_load_empty_when_missing(self) -> None:
        cfg = SettingsManager.load_config()
        self.assertEqual(cfg, {})

    def test_save_and_load_config(self) -> None:
        data = {
            "account1": {"email": "test@example.com"},
            "video_aspect_ratio": "16:9",
            "veo_model": "Veo 3.1 - Fast",
            "duration_seconds": 8,
            "MAX_IN_FLIGHT": 3,
        }
        SettingsManager.save_config(data)
        loaded = SettingsManager.load_config()
        self.assertEqual(loaded.get("video_aspect_ratio"), "16:9")
        self.assertEqual(loaded.get("duration_seconds"), 8)
        self.assertEqual(loaded.get("account1", {}).get("email"), "test@example.com")

    def test_save_and_load_settings(self) -> None:
        st = {"current_profile": "PROFILE_2"}
        SettingsManager.save_settings(st)
        loaded = SettingsManager.load_settings()
        self.assertEqual(loaded.get("current_profile"), "PROFILE_2")


if __name__ == "__main__":
    unittest.main()
