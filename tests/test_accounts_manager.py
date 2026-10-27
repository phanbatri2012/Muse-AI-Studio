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

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qt_ui.tab_accounts_manager import AccountsManagerTab, BatchLoginWorker


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
