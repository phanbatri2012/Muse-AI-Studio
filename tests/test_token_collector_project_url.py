from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pytest

TokenCollector = pytest.importorskip(
    "A_workflow_get_token",
    reason="legacy Flow token collector is optional",
).TokenCollector
from settings_manager import SettingsManager


class TokenCollectorProjectUrlTests(unittest.TestCase):
    def test_constructor_strips_edit_suffix_from_project_url(self) -> None:
        collector = TokenCollector(
            "https://labs.google/fx/vi/tools/flow/project/b9fdb229-4243-4e71-9e27-b66a42eda263/edit/6151cb77-00f3-48f5-8da7-d7df719b744e",
            mode="video",
        )

        self.assertEqual(
            collector.project_url,
            "https://labs.google/fx/vi/tools/flow/project/b9fdb229-4243-4e71-9e27-b66a42eda263",
        )

    def test_auth_snapshot_persists_root_project_url_instead_of_edit_url(self) -> None:
        original_load_config = SettingsManager.load_config
        SettingsManager.load_config = staticmethod(
            lambda: {
                "account1": {
                    "email": "demo@example.com",
                    "password": "secret",  # pragma: allowlist secret
                    "URL_GEN_TOKEN": "https://labs.google/fx/vi/tools/flow/project/old-project/edit/old-asset",
                }
            }
        )
        try:
            collector = TokenCollector("https://labs.google/fx/vi/tools/flow", mode="video")
            collector._auth_state["projectId"] = "b9fdb229-4243-4e71-9e27-b66a42eda263"
            collector.page = SimpleNamespace(
                url="https://labs.google/fx/vi/tools/flow/project/b9fdb229-4243-4e71-9e27-b66a42eda263/edit/6151cb77-00f3-48f5-8da7-d7df719b744e"
            )

            snapshot = collector._build_auth_snapshot()
        finally:
            SettingsManager.load_config = original_load_config

        self.assertEqual(
            snapshot["URL_GEN_TOKEN"],
            "https://labs.google/fx/vi/tools/flow/project/b9fdb229-4243-4e71-9e27-b66a42eda263",
        )

    def test_wait_for_profile_chrome_port_retries_until_port_appears(self) -> None:
        collector = TokenCollector("https://labs.google/fx/vi/tools/flow", mode="video")
        seen_calls: list[str] = []
        ports = iter([None, None, 9224])

        def fake_find(user_data_dir: str):
            seen_calls.append(user_data_dir)
            return next(ports)

        collector._find_running_cdp_port_for_user_data = fake_find
        collector._adopt_detected_profile_chrome = lambda: seen_calls.append("adopted")

        with patch("A_workflow_get_token.time.sleep", lambda *_args, **_kwargs: None):
            port = collector._wait_for_profile_chrome_port("/tmp/profile-under-test", timeout_s=1.0, poll_interval_s=0.01)

        self.assertEqual(port, 9224)
        self.assertIn("/tmp/profile-under-test", seen_calls)
        self.assertIn("adopted", seen_calls)


if __name__ == "__main__":
    unittest.main()
