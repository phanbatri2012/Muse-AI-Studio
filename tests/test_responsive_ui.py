# -*- coding: utf-8 -*-
"""
Automated responsive and adaptive UI tests across different resolutions.
Kiểm thử tính linh hoạt của giao diện khi co giãn kích thước cửa sổ.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QApplication, QScrollArea, QSplitter

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qt_ui.ui_main import MainWindow
from qt_ui.tab_prompt_studio import PromptStudioTab
from qt_ui.tab_accounts_manager import AccountsManagerTab
from qt_ui.tab_queue_monitor import QueueMonitorTab


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_main_window_minimum_size_adaptive(qapp):
    win = MainWindow(start_backend=False)
    min_size = win.minimumSize()
    # Phải hỗ trợ tối thiểu kích thước 960x580 (phù hợp laptop và chia đôi màn hình)
    assert min_size.width() <= 960
    assert min_size.height() <= 580


def test_prompt_studio_compact_action_strip(qapp):
    tab = PromptStudioTab()
    # Kiểm tra giao diện Full-Width với Action Strip siêu tinh gọn
    assert tab.action_strip is not None
    assert tab.btn_account_pill is not None
    assert tab.combo_ratio.currentData() == "auto"
    assert tab.spin_duration.value() == 6
    assert tab.chk_smooth_60fps.isChecked()
    assert tab.btn_start is not None


def test_accounts_manager_info_cards_no_clipping(qapp):
    tab = AccountsManagerTab()
    # Thẻ thống kê không được fixed chiều cao quá nhỏ (>= 64px để tránh cắt số trên Windows DPI scale)
    assert tab.card_total.minimumHeight() >= 64
    assert tab.card_active.minimumHeight() >= 64
    assert tab.card_expired.minimumHeight() >= 64


def test_queue_monitor_info_cards_no_clipping(qapp):
    tab = QueueMonitorTab()
    assert tab.card_total.minimumHeight() >= 64
    assert tab.card_processing.minimumHeight() >= 64
    assert tab.card_success.minimumHeight() >= 64
    assert tab.card_failed.minimumHeight() >= 64


def test_responsive_resize_stress(qapp):
    """Stress test co dãn MainWindow ở nhiều kích thước màn hình phổ biến."""
    win = MainWindow(start_backend=False)
    win.show()

    resolutions = [
        (960, 580),   # Windows Snap 50% trên màn 1080p
        (1024, 768),  # XGA chuẩn
        (1366, 768),  # Laptop 14-inch phổ thông
        (1440, 900),  # MacBook / WXGA+
        (1920, 1080), # Full HD
    ]

    for w, h in resolutions:
        win.resize(w, h)
        assert win.width() >= 960
        assert win.height() >= 580
    win.close()
