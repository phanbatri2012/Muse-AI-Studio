# -*- coding: utf-8 -*-
"""
Automated Cold-Start and Zero-State Tests.
Kiểm thử khởi động lần đầu khi hệ thống chưa có tài khoản nào.
"""
from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qt_ui.ui_main import MainWindow
from muse_service_manager import MUSE2API_ACCOUNTS_FILE, MuseServiceManager
from runtime_paths import ensure_runtime_dirs, DATA_GENERAL_DIR, MUSE_DOWNLOADS_DIR, MUSE_CHROME_USER_DATA_ROOT


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_runtime_paths_creation():
    """Kiểm tra khởi tạo tự động các thư mục runtime."""
    ensure_runtime_dirs()
    assert DATA_GENERAL_DIR.exists()
    assert MUSE_DOWNLOADS_DIR.exists()
    assert MUSE_CHROME_USER_DATA_ROOT.exists()


def test_service_manager_healthcheck():
    """Kiểm tra healthcheck của dịch vụ Backend."""
    assert MuseServiceManager.is_service_ready() is True
    assert "18610" in MuseServiceManager.get_api_base_url()


def test_cold_start_zero_accounts_redirection(qapp, monkeypatch):
    """Kiểm tra luồng khởi động trắng: khi chưa có tài khoản, tool tự động hướng dẫn chuyển Tab."""
    backup_path = MUSE2API_ACCOUNTS_FILE.with_suffix(".json.bak_zero_test")
    had_accounts = False
    if MUSE2API_ACCOUNTS_FILE.exists():
        shutil.copy2(MUSE2API_ACCOUNTS_FILE, backup_path)
        had_accounts = True
        MUSE2API_ACCOUNTS_FILE.write_text("[]", encoding="utf-8")

    try:
        # Mock QMessageBox.question để trả về Yes
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)

        win = MainWindow(start_backend=False)

        # Tab Prompt Studio hiển thị 0 tài khoản
        p_tab = win.tab_studio
        assert "0 tài khoản" in p_tab.btn_account_pill.text()

        # Tab Character Studio hiển thị 0 tài khoản
        c_tab = win.tab_character
        assert "0 tài khoản" in c_tab.btn_account_pill.text()

        # Tab Accounts hiển thị 0 dòng
        assert win.tab_accounts.table_accounts.rowCount() == 0

        # Khi bấm tạo video ở Prompt Studio -> Chuyển hướng sang Tab Accounts
        win.tabs.setCurrentWidget(p_tab)
        p_tab.editor.setPlainText("Test prompt cold start")
        p_tab._on_start_clicked()
        assert win.tabs.currentWidget() == win.tab_accounts

        # Khi bấm tạo video ở Character Studio -> Chuyển hướng sang Tab Accounts
        win.tabs.setCurrentWidget(c_tab)
        c_tab.editor.setPlainText("Test prompt character cold start")
        c_tab._on_start_clicked()
        assert win.tabs.currentWidget() == win.tab_accounts

        win.close()
    finally:
        if had_accounts and backup_path.exists():
            shutil.move(backup_path, MUSE2API_ACCOUNTS_FILE)
