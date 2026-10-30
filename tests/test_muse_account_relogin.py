from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from muse_auth import has_complete_muse_session, has_muse_session_bootstrap
from muse2api_backend import app as muse_app


class MuseAccountReloginTests(unittest.IsolatedAsyncioTestCase):
    def _request(self, method: str) -> muse_app.AccountReloginRequest:
        if method == "mailbox":
            return muse_app.AccountReloginRequest(
                email="user@tuan89.site",
                method="mailbox",
                mailbox_url="https://mail.tuan89.site/inbox/user",
            )
        return muse_app.AccountReloginRequest(
            email="user@example.com",
            method="password",
            password="secret-password",
            two_factor_secret="BASE32SECRET",
        )

    async def _successful_relogin(self, method: str) -> tuple[dict, MagicMock]:
        now = int(time.time())
        store = MagicMock()
        store.get_account.return_value = {
            "id": "account-1",
            "label": "Account 1",
            "enabled": True,
        }
        store.update_account.return_value = {
            "id": "account-1",
            "label": "Account 1",
            "expires_at": now + 3600,
        }
        account_pool = MagicMock()
        gen_lock = MagicMock()
        gen_lock.limit = 2
        gen_lock.acquire.return_value = True
        engine = MagicMock()
        login_result = {
            "success": True,
            "cookies": {"hatch_sess": "session", "hatch_vml": "vml"},
            "cookies_exp": {"hatch_vml": now + 3600},
        }

        with (
            patch.object(muse_app, "store", store),
            patch.object(muse_app, "ACCOUNT_POOL", account_pool),
            patch.object(muse_app, "GEN_LOCK", gen_lock),
            patch.object(muse_app, "engine", engine),
            patch.object(muse_app, "_active_media_task_count", return_value=0),
            patch.object(
                muse_app.MuseAuthManager,
                "login_standalone",
                new=AsyncMock(return_value=login_result),
            ) as login,
        ):
            response = await muse_app.relogin_account(
                "account-1", self._request(method), None
            )

        payload = json.loads(response.body)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["account"]["id"], "account-1")
        self.assertNotIn("cookies", payload["account"])
        self.assertNotIn("password", response.body.decode("utf-8").lower())
        account_pool.acquire.assert_called_once_with(
            account_id="account-1", timeout=0.1, record_use=False
        )
        account_pool.release.assert_called_once_with("account-1")
        self.assertEqual(gen_lock.release.call_count, 2)
        engine.refresh.assert_called_once()
        return login.await_args.kwargs, store

    async def test_password_relogin_verifies_then_replaces_session(self) -> None:
        kwargs, store = await self._successful_relogin("password")
        self.assertEqual(kwargs["email"], "user@example.com")
        self.assertEqual(kwargs["password"], "secret-password")
        self.assertEqual(kwargs["two_factor_secret"], "BASE32SECRET")
        self.assertIsNone(kwargs["mailbox_url"])
        store.update_account.assert_called_once()
        persisted = store.update_account.call_args.kwargs
        self.assertTrue(persisted["ok"])
        self.assertEqual(persisted["login_email"], "user@example.com")
        self.assertGreater(persisted["session_verified_at"], 0)
        self.assertEqual(persisted["verification_state"], "verified")

    async def test_mailbox_relogin_uses_no_password_or_totp(self) -> None:
        kwargs, store = await self._successful_relogin("mailbox")
        self.assertEqual(kwargs["password"], "")
        self.assertIsNone(kwargs["two_factor_secret"])
        self.assertEqual(
            kwargs["mailbox_url"], "https://mail.tuan89.site/inbox/user"
        )
        store.update_account.assert_called_once()

    async def test_failed_relogin_does_not_replace_existing_session(self) -> None:
        store = MagicMock()
        store.get_account.return_value = {"id": "account-1", "enabled": True}
        account_pool = MagicMock()
        gen_lock = MagicMock()
        gen_lock.limit = 2
        gen_lock.acquire.return_value = True
        with (
            patch.object(muse_app, "store", store),
            patch.object(muse_app, "ACCOUNT_POOL", account_pool),
            patch.object(muse_app, "GEN_LOCK", gen_lock),
            patch.object(muse_app, "_active_media_task_count", return_value=0),
            patch.object(
                muse_app.MuseAuthManager,
                "login_standalone",
                new=AsyncMock(return_value={"success": False, "error": "bad password"}),
            ),
        ):
            with self.assertRaises(muse_app.HTTPException) as raised:
                await muse_app.relogin_account(
                    "account-1", self._request("password"), None
                )

        self.assertEqual(raised.exception.status_code, 401)
        self.assertEqual(raised.exception.headers["Cache-Control"], "no-store")
        store.update_account.assert_not_called()

    async def test_partial_session_is_rejected_before_persistence(self) -> None:
        store = MagicMock()
        store.get_account.return_value = {"id": "account-1", "enabled": True}
        account_pool = MagicMock()
        gen_lock = MagicMock(limit=1)
        gen_lock.acquire.return_value = True
        with (
            patch.object(muse_app, "store", store),
            patch.object(muse_app, "ACCOUNT_POOL", account_pool),
            patch.object(muse_app, "GEN_LOCK", gen_lock),
            patch.object(muse_app, "_active_media_task_count", return_value=0),
            patch.object(
                muse_app.MuseAuthManager,
                "login_standalone",
                new=AsyncMock(
                    return_value={
                        "success": False,
                        "error_code": "session_cookie_incomplete",
                    }
                ),
            ),
        ):
            with self.assertRaises(muse_app.HTTPException) as raised:
                await muse_app.relogin_account(
                    "account-1", self._request("mailbox"), None
                )

        self.assertEqual(raised.exception.status_code, 401)
        self.assertIn("session hoàn chỉnh", raised.exception.detail)
        store.update_account.assert_not_called()

    async def test_verification_retries_before_persisting(self) -> None:
        now = int(time.time())
        store = MagicMock()
        store.get_account.return_value = {"id": "account-1", "enabled": True}
        store.update_account.return_value = {
            "id": "account-1",
            "label": "Account 1",
            "expires_at": now + 3600,
            "session_verified_at": now,
        }
        account_pool = MagicMock()
        gen_lock = MagicMock(limit=1)
        gen_lock.acquire.return_value = True
        engine = MagicMock()
        engine.refresh.side_effect = [
            muse_app.MuseAuthError("not ready"),
            None,
        ]
        with (
            patch.object(muse_app, "store", store),
            patch.object(muse_app, "ACCOUNT_POOL", account_pool),
            patch.object(muse_app, "GEN_LOCK", gen_lock),
            patch.object(muse_app, "engine", engine),
            patch.object(muse_app, "_active_media_task_count", return_value=0),
            patch.object(muse_app.time, "sleep"),
            patch.object(
                muse_app.MuseAuthManager,
                "login_standalone",
                new=AsyncMock(
                    return_value={
                        "success": True,
                        "cookies": {"hatch_sess": "session", "hatch_vml": "vml"},
                        "cookies_exp": {"hatch_vml": now + 3600},
                    }
                ),
            ),
        ):
            response = await muse_app.relogin_account(
                "account-1", self._request("mailbox"), None
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(engine.refresh.call_count, 2)
        engine.close_current_page.assert_called_once()
        store.update_account.assert_called_once()

    async def test_verified_bootstrap_session_does_not_require_hatch_vml(self) -> None:
        now = int(time.time())
        store = MagicMock()
        store.get_account.return_value = {"id": "account-1", "enabled": True}
        store.update_account.return_value = {
            "id": "account-1",
            "expires_at": now + 2 * 86400,
            "session_verified_at": now,
        }
        account_pool = MagicMock()
        gen_lock = MagicMock(limit=1)
        gen_lock.acquire.return_value = True
        engine = MagicMock()
        with (
            patch.object(muse_app, "store", store),
            patch.object(muse_app, "ACCOUNT_POOL", account_pool),
            patch.object(muse_app, "GEN_LOCK", gen_lock),
            patch.object(muse_app, "engine", engine),
            patch.object(muse_app, "_active_media_task_count", return_value=0),
            patch.object(
                muse_app.MuseAuthManager,
                "login_standalone",
                new=AsyncMock(
                    return_value={
                        "success": True,
                        "cookies": {"hatch_sess": "session"},
                        "cookies_exp": {},
                        "expires_at": now + 2 * 86400,
                        "expires_estimated": True,
                    }
                ),
            ),
        ):
            response = await muse_app.relogin_account(
                "account-1", self._request("mailbox"), None
            )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body)
        self.assertTrue(payload["account"]["expires_estimated"])
        engine.refresh.assert_called_once()
        persisted = store.update_account.call_args.kwargs
        self.assertEqual(persisted["cookies"], {"hatch_sess": "session"})
        self.assertGreaterEqual(persisted["expiry_anchor"], now)
        self.assertGreater(persisted["session_verified_at"], 0)

    async def test_relogin_requires_all_browser_slots_without_waiting(self) -> None:
        store = MagicMock()
        store.get_account.return_value = {"id": "account-1", "enabled": True}
        account_pool = MagicMock()
        gen_lock = MagicMock()
        gen_lock.limit = 2
        gen_lock.acquire.side_effect = [True, False]
        with (
            patch.object(muse_app, "store", store),
            patch.object(muse_app, "ACCOUNT_POOL", account_pool),
            patch.object(muse_app, "GEN_LOCK", gen_lock),
            patch.object(muse_app, "_active_media_task_count", return_value=0),
            patch.object(
                muse_app.MuseAuthManager,
                "login_standalone",
                new=AsyncMock(),
            ) as login,
        ):
            with self.assertRaises(muse_app.HTTPException) as raised:
                await muse_app.relogin_account(
                    "account-1", self._request("password"), None
                )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(gen_lock.release.call_count, 1)
        account_pool.release.assert_called_once_with("account-1")
        login.assert_not_awaited()

    async def test_relogin_rejects_active_media_without_opening_browser(self) -> None:
        store = MagicMock()
        store.get_account.return_value = {"id": "account-1", "enabled": True}
        with (
            patch.object(muse_app, "store", store),
            patch.object(muse_app, "_active_media_task_count", return_value=1),
            patch.object(
                muse_app.MuseAuthManager,
                "login_standalone",
                new=AsyncMock(),
            ) as login,
        ):
            with self.assertRaises(muse_app.HTTPException) as raised:
                await muse_app.relogin_account(
                    "account-1", self._request("password"), None
                )

        self.assertEqual(raised.exception.status_code, 409)
        login.assert_not_awaited()

    async def test_validation_error_does_not_echo_secret_input(self) -> None:
        request = muse_app.Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/admin/accounts/account-1/relogin",
                "raw_path": b"/admin/accounts/account-1/relogin",
                "query_string": b"",
                "headers": [],
                "client": ("test", 123),
                "server": ("test", 80),
                "root_path": "",
            }
        )
        error = muse_app.RequestValidationError(
            [
                {
                    "type": "literal_error",
                    "loc": ("body", "method"),
                    "msg": "invalid method",
                    "input": "SECRET-PASSWORD-TOTP",
                }
            ]
        )

        response = await muse_app._validation_exc(request, error)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("SECRET-PASSWORD-TOTP", response.body.decode("utf-8"))

    def test_relogin_capability_and_totp_logs_are_safe(self) -> None:
        models = muse_app.models(None)
        self.assertEqual(models["capabilities"]["account_relogin"], 2)
        auth_source = Path(muse_app.__file__).resolve().parents[1] / "muse_auth.py"
        text = auth_source.read_text(encoding="utf-8")
        self.assertNotIn('f"🔢 Nhập mã 2FA TOTP tự động: {totp}', text)

    def test_complete_session_requires_both_canonical_cookies(self) -> None:
        self.assertFalse(has_muse_session_bootstrap({}))
        self.assertTrue(has_muse_session_bootstrap({"hatch_sess": "session"}))
        self.assertFalse(has_complete_muse_session({"hatch_sess": "session"}))
        self.assertFalse(has_complete_muse_session({"hatch_vml": "vml"}))
        self.assertTrue(
            has_complete_muse_session(
                {"hatch_sess": "session", "hatch_vml": "vml"}
            )
        )


if __name__ == "__main__":
    unittest.main()
