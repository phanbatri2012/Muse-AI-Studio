from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from starlette.requests import Request

from muse2api_backend import app as app_module
from muse2api_backend.engine import MuseEngine
from muse2api_backend.store import Store, parse_token_amount, quota_state


class MediaQuotaStateTests(unittest.TestCase):
    def test_parse_additional_tokens_supports_decimal_units(self) -> None:
        self.assertEqual(parse_token_amount("2.7B tokens left"), 2_700_000_000)
        self.assertEqual(parse_token_amount("1.25M"), 1_250_000)
        self.assertEqual(parse_token_amount("0 tokens left"), 0)
        self.assertIsNone(parse_token_amount("unknown"))

    def test_weekly_exhausted_with_additional_tokens_is_eligible(self) -> None:
        now = int(time.time())
        account = {
            "quota": {
                "found": True,
                "checked_at": now,
                "weekly_used_pct": 100,
                "extra_left": "2.7B tokens left",
            }
        }

        self.assertEqual(quota_state(account, now=now), "eligible")

    def test_weekly_and_additional_exhausted_is_exhausted(self) -> None:
        now = int(time.time())
        account = {
            "quota": {
                "found": True,
                "checked_at": now,
                "weekly_used_pct": 100,
                "extra_pool_present": True,
                "extra_left_value": 0,
            }
        }

        self.assertEqual(quota_state(account, now=now), "exhausted")

    def test_stale_quota_is_unknown(self) -> None:
        now = int(time.time())
        account = {
            "quota": {
                "found": True,
                "checked_at": now - 901,
                "weekly_used_pct": 20,
                "extra_pool_present": False,
                "extra_left_value": 0,
            }
        }

        self.assertEqual(quota_state(account, now=now, ttl_seconds=900), "unknown")

    def test_settings_parser_marks_additional_pool_and_numeric_balance(self) -> None:
        quota = MuseEngine._parse_quota(
            "Free plan\nWeekly limit\n100% used\nAdditional tokens\n"
            "Never expires\n0% used (2.7B tokens left)"
        )

        self.assertTrue(quota["extra_pool_present"])
        self.assertEqual(quota["extra_left_value"], 2_700_000_000)


class MediaQuotaSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="muse_quota_")
        root = Path(self.tmp.name)
        cfg = SimpleNamespace(
            accounts_file=str(root / "accounts.json"),
            tasks_file=str(root / "tasks.json"),
        )
        self.store = Store(cfg)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def _account(account_id: str, state: str, *, last_used: int = 0) -> dict:
        now = int(time.time())
        quota = {
            "found": True,
            "checked_at": now,
            "weekly_used_pct": 20,
            "extra_pool_present": False,
            "extra_left_value": 0,
        }
        if state == "exhausted":
            quota["weekly_used_pct"] = 100
        elif state == "unknown":
            quota["checked_at"] = now - 901
        return {
            "id": account_id,
            "label": account_id,
            "cookies": {"hatch_sess": account_id},
            "enabled": True,
            "ok": True,
            "last_used": last_used,
            "use_count": 0,
            "quota": quota,
        }

    def test_eligible_is_selected_before_unknown_and_exhausted_is_skipped(self) -> None:
        self.store.accounts = [
            self._account("unknown", "unknown", last_used=0),
            self._account("exhausted", "exhausted", last_used=0),
            self._account("eligible", "eligible", last_used=100),
        ]

        selected = self.store.pick_account(quota_aware=True, record_use=False)

        self.assertEqual(selected["id"], "eligible")

    def test_unknown_is_used_only_when_no_eligible_account_remains(self) -> None:
        self.store.accounts = [
            self._account("exhausted", "exhausted"),
            self._account("unknown", "unknown"),
        ]

        selected = self.store.pick_account(quota_aware=True, record_use=False)

        self.assertEqual(selected["id"], "unknown")

    def test_all_exhausted_returns_no_account(self) -> None:
        self.store.accounts = [
            self._account("first", "exhausted"),
            self._account("second", "exhausted"),
        ]

        self.assertIsNone(self.store.pick_account(quota_aware=True, record_use=False))
        capacity = self.store.media_capacity()
        self.assertEqual(capacity["status"], "exhausted")
        self.assertEqual(capacity["exhausted"], 2)


class MediaQuotaBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="muse_quota_backend_")
        root = Path(self.tmp.name)
        cfg = SimpleNamespace(
            accounts_file=str(root / "accounts.json"),
            tasks_file=str(root / "tasks.json"),
        )
        self.store = Store(cfg)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def _account(account_id: str, *, weekly_used: int = 20, checked_at: int = 0) -> dict:
        return {
            "id": account_id,
            "label": account_id,
            "cookies": {"hatch_sess": account_id},
            "cookies_exp": {},
            "enabled": True,
            "ok": True,
            "last_used": None,
            "use_count": 0,
            "quota": {
                "found": True,
                "checked_at": checked_at,
                "weekly_used_pct": weekly_used,
                "extra_pool_present": False,
                "extra_left_value": 0,
            },
        }

    def test_stale_quota_refreshes_once_then_hits_cache(self) -> None:
        self.store.accounts = [self._account("account-1", checked_at=1)]
        quota_result = {
            "found": True,
            "weekly_used_pct": 39,
            "extra_pool_present": False,
            "extra_left_value": 0,
            "raw": "must not persist",
        }
        with (
            patch.object(app_module, "store", self.store),
            patch.object(app_module.engine, "start"),
            patch.object(app_module.engine, "quota", return_value=quota_result) as quota,
            patch.object(app_module.engine, "close_current_page"),
        ):
            first = app_module._media_capacity_preflight()
            second = app_module._media_capacity_preflight()

        self.assertEqual(first["status"], "ready")
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        quota.assert_called_once()
        self.assertNotIn("raw", self.store.get_account("account-1")["quota"])
        self.assertFalse(
            {"id", "account_id", "email", "cookies", "raw"}.intersection(first)
        )

    def test_preflight_stops_after_first_account_becomes_eligible(self) -> None:
        self.store.accounts = [
            self._account("account-1", checked_at=1),
            self._account("account-2", checked_at=1),
        ]
        quota_result = {
            "found": True,
            "weekly_used_pct": 20,
            "extra_pool_present": False,
            "extra_left_value": 0,
        }
        with (
            patch.object(app_module, "store", self.store),
            patch.object(app_module.engine, "start"),
            patch.object(app_module.engine, "quota", return_value=quota_result) as quota,
            patch.object(app_module.engine, "close_current_page"),
        ):
            capacity = app_module._media_capacity_preflight()

        self.assertEqual(capacity["status"], "ready")
        self.assertEqual(capacity["eligible"], 1)
        self.assertEqual(capacity["unknown"], 1)
        quota.assert_called_once()

    def test_readyz_adds_cached_quota_counts_without_changing_health(self) -> None:
        now = int(time.time())
        self.store.accounts = [
            self._account("eligible", checked_at=now),
            self._account("exhausted", weekly_used=100, checked_at=now),
        ]
        with patch.object(app_module, "store", self.store):
            ready = app_module.readyz()

        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["media_quota_status"], "ready")
        self.assertEqual(ready["media_quota_eligible"], 1)
        self.assertEqual(ready["media_quota_exhausted"], 1)

    def test_concurrent_preflight_does_not_duplicate_refresh(self) -> None:
        self.store.accounts = [self._account("account-1", checked_at=1)]
        quota_result = {
            "found": True,
            "weekly_used_pct": 20,
            "extra_pool_present": False,
            "extra_left_value": 0,
        }
        gate = threading.Barrier(2)

        def run_preflight(_index):
            gate.wait()
            return app_module._media_capacity_preflight()

        with (
            patch.object(app_module, "store", self.store),
            patch.object(app_module.engine, "start"),
            patch.object(app_module.engine, "quota", return_value=quota_result) as quota,
            patch.object(app_module.engine, "close_current_page"),
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(run_preflight, range(2)))

        self.assertEqual(quota.call_count, 1)
        self.assertEqual({item["status"] for item in results}, {"ready"})
        self.assertEqual(sum(not item["cache_hit"] for item in results), 1)

    def test_all_exhausted_rejects_before_task_creation(self) -> None:
        self.store.accounts = [
            self._account(
                "account-1", weekly_used=100, checked_at=int(time.time())
            )
        ]
        request = app_module.VideoRequest(
            prompt="Animate this frame",
            model="muse-video",
            reference_image=["scene.png"],
        )
        with patch.object(app_module, "store", self.store):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    app_module.create_video(
                        request, idempotency_key="new-request", _=None
                    )
                )

        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.detail["code"], "media_quota_exhausted")
        self.assertEqual(self.store.tasks, {})

    def test_quota_http_error_keeps_machine_readable_code(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/videos",
                "headers": [],
                "query_string": b"",
                "server": ("127.0.0.1", 18610),
                "client": ("127.0.0.1", 1),
                "scheme": "http",
            }
        )
        response = asyncio.run(
            app_module._http_exc(
                request,
                HTTPException(
                    429,
                    {
                        "message": "quota exhausted",
                        "code": "media_quota_exhausted",
                    },
                ),
            )
        )
        payload = json.loads(response.body)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(payload["error"]["code"], "media_quota_exhausted")

    def test_existing_idempotent_task_wins_before_exhausted_preflight(self) -> None:
        request = app_module.VideoRequest(
            prompt="Animate this frame",
            model="muse-video",
            reference_image=["scene.png"],
        )
        with (
            patch.object(app_module, "store", self.store),
            patch.object(app_module.threading, "Thread"),
        ):
            first = app_module._queue_video(
                request,
                app_module.build_video_prompt(request),
                request.reference_image,
                "stable-key",
            )
            with patch.object(
                app_module,
                "_media_capacity_preflight",
                side_effect=AssertionError("preflight must not run for a dedupe hit"),
            ):
                second = asyncio.run(
                    app_module.create_video(
                        request, idempotency_key="stable-key", _=None
                    )
                )

        self.assertEqual(second["task_id"], first["task_id"])
        self.assertEqual(len(self.store.tasks), 1)

    def test_runtime_quota_errors_rotate_through_all_untried_accounts(self) -> None:
        now = int(time.time())
        self.store.accounts = [
            self._account(f"account-{index}", checked_at=now)
            for index in range(1, 4)
        ]
        pool = app_module.AccountPoolManager(self.store)
        generated = {"filename": "done.png", "size": 1, "kind": "image"}
        generate = MagicMock(
            side_effect=[
                app_module.MuseQuotaError("账号额度不足"),
                app_module.MuseQuotaError("quota exceeded"),
                generated,
            ]
        )
        with (
            patch.object(app_module, "store", self.store),
            patch.object(app_module, "ACCOUNT_POOL", pool),
            patch.object(
                app_module,
                "_renew_and_persist",
                side_effect=lambda account_id, **_kwargs: self.store.get_account(account_id),
            ),
            patch.object(app_module, "_sync_cookies"),
            patch.object(app_module.engine, "start"),
            patch.object(app_module.engine, "generate", generate),
            patch.object(app_module.engine, "reset_thread"),
            patch.object(app_module.engine, "close_current_page"),
        ):
            result, account_id = app_module._run_generation_locked(
                "prompt", "image", 30, deadline=time.monotonic() + 30
            )

        self.assertEqual(result, generated)
        self.assertEqual(account_id, "account-3")
        self.assertEqual(generate.call_count, 3)
        self.assertEqual(quota_state(self.store.get_account("account-1")), "exhausted")
        self.assertEqual(quota_state(self.store.get_account("account-2")), "exhausted")
        self.assertTrue(self.store.get_account("account-1")["ok"])

    def test_generation_errors_keep_existing_two_attempt_limit(self) -> None:
        now = int(time.time())
        self.store.accounts = [
            self._account(f"account-{index}", checked_at=now)
            for index in range(1, 4)
        ]
        pool = app_module.AccountPoolManager(self.store)
        generate = MagicMock(
            side_effect=app_module.MuseGenerationError("temporary generation error")
        )
        with (
            patch.object(app_module, "store", self.store),
            patch.object(app_module, "ACCOUNT_POOL", pool),
            patch.object(
                app_module,
                "_renew_and_persist",
                side_effect=lambda account_id, **_kwargs: self.store.get_account(account_id),
            ),
            patch.object(app_module.engine, "start"),
            patch.object(app_module.engine, "generate", generate),
            patch.object(app_module.engine, "reset_thread"),
            patch.object(app_module.engine, "close_current_page"),
        ):
            with self.assertRaises(app_module.MuseGenerationError):
                app_module._run_generation_locked(
                    "prompt", "image", 30, deadline=time.monotonic() + 30
                )

        self.assertEqual(generate.call_count, 2)

    def test_concurrent_acquire_reserves_distinct_accounts(self) -> None:
        now = int(time.time())
        self.store.accounts = [
            self._account(f"account-{index}", checked_at=now)
            for index in range(1, 3)
        ]
        pool = app_module.AccountPoolManager(self.store)
        acquired = threading.Barrier(2)

        def reserve(_index):
            account = pool.acquire(quota_aware=True, timeout=2)
            try:
                acquired.wait(timeout=2)
                return account["id"]
            finally:
                pool.release(account["id"])

        with ThreadPoolExecutor(max_workers=2) as executor:
            account_ids = list(executor.map(reserve, range(2)))

        self.assertEqual(set(account_ids), {"account-1", "account-2"})


if __name__ == "__main__":
    unittest.main()
