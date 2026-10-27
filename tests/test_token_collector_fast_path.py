from __future__ import annotations

import time
import unittest

import pytest

TokenCollector = pytest.importorskip(
    "A_workflow_get_token",
    reason="legacy Flow token collector is optional",
).TokenCollector


class _FastPathPage:
    url = "https://labs.google/fx/tools/flow/project/project-1"

    def is_closed(self) -> bool:
        return False


class TokenCollectorFastPathTests(unittest.IsolatedAsyncioTestCase):
    def _collector(self):
        collector = TokenCollector.__new__(TokenCollector)
        collector.mode = "generate_image"
        collector._image_mode_ready = True
        collector._image_fast_path_ready_ts = time.time()
        collector._cached_prompt_input_selector = "div[contenteditable='true']"
        collector._cached_prompt_input_type = "contenteditable"
        collector._cached_create_button_selector = "button[aria-label*='Send']"
        collector._cached_create_button_excludes = []
        collector.page = _FastPathPage()
        return collector

    def test_image_fast_path_requires_fresh_cached_selectors(self) -> None:
        collector = self._collector()

        self.assertTrue(collector._is_image_fast_path_ready())

        collector._image_fast_path_ready_ts = time.time() - 31
        self.assertFalse(collector._is_image_fast_path_ready())

    async def test_trigger_token_fast_path_uses_cached_fill_and_click(self) -> None:
        collector = self._collector()
        calls: list[str] = []

        async def fake_ready():
            calls.append("ready")
            return True

        async def fake_fill(text):
            calls.append(f"fill:{text}")
            return True

        async def fake_click(prefer_cached=False):
            calls.append(f"click:{prefer_cached}")
            return True

        collector._is_flow_composer_ready = fake_ready
        collector._fill_prompt_input_text = fake_fill
        collector._click_create_or_send_button = fake_click
        collector._invalidate_image_fast_path_cache = lambda: calls.append("invalidate")
        collector._log = lambda message: calls.append("log")

        self.assertTrue(await collector._trigger_token_fast_path())
        self.assertEqual(calls[:3], ["ready", "fill:a", "click:True"])
        self.assertNotIn("invalidate", calls)


if __name__ == "__main__":
    unittest.main()
