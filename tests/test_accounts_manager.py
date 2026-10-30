# -*- coding: utf-8 -*-
"""
Unit tests cho AccountsManagerTab và BatchLoginWorker logic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qt_ui.tab_accounts_manager import (
    AccountsManagerTab,
    BatchLoginWorker,
    parse_account_login_line,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_accounts_tab_initialization(qapp):
    tab = AccountsManagerTab()
    assert tab.table_accounts is not None
    assert tab.btn_start_login is not None
    assert tab.txt_accounts_input is not None


def test_batch_login_parsing():
    raw_lines = [
        "user1@test.com|pass1|2FA_KEY_1",
        "  user2@test.com | pass2 | 2FA_KEY_2  ",
        "user3@test.com,pass3,2FA_KEY_3",
        "# Dòng ghi chú bỏ qua",
        "",
        "invalid_line_no_pass",
    ]

    worker = BatchLoginWorker(raw_lines)
    assert len(worker.account_lines) == 6


def test_parse_account_login_line_supports_password_and_mailbox_url():
    assert parse_account_login_line("user@example.com|pass|ABC123") == (
        "user@example.com",
        "pass",
        "ABC123",
        "",
    )
    assert parse_account_login_line(
        "user@tuan89.site|https://tuan89.site/mail/?email=user%40tuan89.site"
    ) == (
        "user@tuan89.site",
        "",
        "",
        "https://tuan89.site/mail/?email=user%40tuan89.site",
    )


def test_parse_account_login_line_unwraps_markdown_mailbox_url():
    line = (
        "user@tuan89.site|"
        "[Mở hộp thư](https://tuan89.site/mail/?email=user%40tuan89.site)"
    )
    assert parse_account_login_line(line)[3] == (
        "https://tuan89.site/mail/?email=user%40tuan89.site"
    )


def test_batch_login_persists_verified_session_metadata(tmp_path):
    accounts_path = tmp_path / "accounts.json"
    accounts_path.write_text(
        json.dumps(
            [
                {
                    "id": "account-1",
                    "label": "user@example.com",
                    "cookies": {"old": "session"},
                    "ok": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    worker = BatchLoginWorker([])

    with patch("qt_ui.tab_accounts_manager.MUSE2API_ACCOUNTS_FILE", accounts_path):
        worker._save_account_to_backend(
            "user@example.com",
            {
                "cookies": {"hatch_sess": "session", "hatch_vml": "vml"},
                "cookies_exp": {"hatch_vml": 2_000_000_000},
                "expires_at": 2_000_000_000,
                "session_verified_at": 1_900_000_000,
                "verification_state": "verified",
                "expires_estimated": False,
            },
        )

    account = json.loads(accounts_path.read_text(encoding="utf-8"))[0]
    assert account["ok"] is True
    assert account["session_verified_at"] == 1_900_000_000
    assert account["verification_state"] == "verified"
    assert account["expires_estimated"] is False
