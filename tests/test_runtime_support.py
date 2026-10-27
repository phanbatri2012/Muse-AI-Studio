from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class RuntimePathsTests(unittest.TestCase):
    def test_user_data_dir_honors_environment_override(self) -> None:
        import runtime_paths

        with tempfile.TemporaryDirectory(prefix="codex_runtime_paths_") as tmpdir:
            with mock.patch.dict(os.environ, {"TOOL_VEO_USER_DATA_DIR": tmpdir}, clear=False):
                importlib.reload(runtime_paths)
                self.assertEqual(runtime_paths.USER_DATA_DIR, Path(tmpdir).resolve())
                self.assertEqual(runtime_paths.DATA_GENERAL_DIR, Path(tmpdir).resolve() / "data_general")
        importlib.reload(runtime_paths)


class RuntimeMediaTests(unittest.TestCase):
    def test_ffmpeg_env_override_is_preferred(self) -> None:
        import runtime_media

        with tempfile.TemporaryDirectory(prefix="codex_runtime_media_") as tmpdir:
            ffmpeg_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
            ffmpeg_path = Path(tmpdir) / ffmpeg_name
            ffmpeg_path.write_text("stub", encoding="utf-8")

            with mock.patch.dict(os.environ, {"IMAGEIO_FFMPEG_EXE": str(ffmpeg_path)}, clear=False):
                importlib.reload(runtime_media)
                self.assertEqual(runtime_media.resolve_ffmpeg_executable(), str(ffmpeg_path.resolve()))
        importlib.reload(runtime_media)


class RuntimeBootstrapTests(unittest.TestCase):
    def test_browser_executable_prefers_env_override(self) -> None:
        import runtime_bootstrap

        with tempfile.TemporaryDirectory(prefix="codex_runtime_bootstrap_") as tmpdir:
            chrome_name = "chrome.exe" if os.name == "nt" else "chrome"
            chrome_path = Path(tmpdir) / chrome_name
            chrome_path.write_text("stub", encoding="utf-8")

            with mock.patch.dict(os.environ, {"CHROME_EXE_PATH": str(chrome_path)}, clear=False):
                importlib.reload(runtime_bootstrap)
                self.assertEqual(runtime_bootstrap.resolve_browser_executable(), str(chrome_path.resolve()))
        importlib.reload(runtime_bootstrap)


if __name__ == "__main__":
    unittest.main()
