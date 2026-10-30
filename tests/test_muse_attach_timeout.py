from __future__ import annotations

import json
import time
import unittest
from unittest.mock import MagicMock

from muse2api_backend.engine import MuseEngine, MuseGenerationError


class MuseAttachTimeoutTests(unittest.TestCase):
    def setUp(self) -> None:
        cfg = MagicMock()
        cfg.profile_dir = "/tmp/test_profile"
        self.engine = MuseEngine(cfg)
        self.mock_page = MagicMock()
        self.engine.page = self.mock_page

    def test_attach_image_fast_path(self) -> None:
        """Nếu DOM có sẵn input file thì hoàn tất ngay trong lượt đầu."""
        self.mock_page.js.side_effect = [
            json.dumps({"cleared": 0}),  # _clear_attachments
            json.dumps({"ok": True, "count": 1}),  # _INJECT_JS
            json.dumps({"removeCount": 1, "mediaCount": 1}),  # confirmation
        ]
        dummy_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        t_start = time.time()
        self.engine._attach_image(dummy_base64)
        elapsed = time.time() - t_start
        self.assertLess(elapsed, 2.0)

    def test_attach_image_delayed_hydration(self) -> None:
        """Nếu DOM trễ 2 nhịp (400ms) mới có input file thì retry thành công mà không bị crash."""
        self.mock_page.js.side_effect = [
            json.dumps({"cleared": 0}),                         # _clear_attachments
            json.dumps({"ok": False, "err": "no-file-input"}),  # Attempt 1
            json.dumps({"ok": False, "err": "no-file-input"}),  # Attempt 2
            json.dumps({"ok": True, "count": 1}),               # Attempt 3 (Thành công)
            json.dumps({"removeCount": 1, "mediaCount": 1}),    # confirmation
        ]
        dummy_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        t_start = time.time()
        self.engine._attach_image(dummy_base64)
        elapsed = time.time() - t_start
        self.assertGreaterEqual(elapsed, 0.4)
        self.assertLess(elapsed, 4.0)

    def test_attach_image_timeout_prevents_infinite_loop(self) -> None:
        """Nếu DOM vĩnh viễn không có input file thì phải dừng lại dứt khoát sau deadline (<= 6.5s), không lặp vô tận."""
        # _clear_attachments xong thì luôn trả về no-file-input
        self.mock_page.js.side_effect = [json.dumps({"cleared": 0})] + [
            json.dumps({"ok": False, "err": "no-file-input"})
        ] * 100

        dummy_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        t_start = time.time()
        with self.assertRaises(MuseGenerationError) as ctx:
            self.engine._attach_image(dummy_base64)
        elapsed = time.time() - t_start

        # Đảm bảo dừng lại trong khoảng 4.8s - 6.5s, không bị loop vô tận
        self.assertGreaterEqual(elapsed, 4.8)
        self.assertLess(elapsed, 6.5)
        self.assertIn("no-file-input", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
