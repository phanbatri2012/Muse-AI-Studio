# -*- coding: utf-8 -*-
"""
Integration tests cho MainWindow và liên kết 5 màn hình.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qt_ui.ui_main import MainWindow
from qt_ui.tab_accounts_manager import AccountsManagerTab
from qt_ui.tab_prompt_studio import PromptStudioTab
from qt_ui.tab_character_studio import CharacterStudioTab
from qt_ui.tab_queue_monitor import QueueMonitorTab
from qt_ui.tab_media_gallery import MediaGalleryTab
from qt_ui.tab_settings_muse import MuseSettingsTab


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_main_window_tabs_and_structure(qapp):
    win = MainWindow()
    assert win.tabs.count() == 6

    tab_0 = win.tabs.widget(0)
    tab_1 = win.tabs.widget(1)
    tab_2 = win.tabs.widget(2)
    tab_3 = win.tabs.widget(3)
    tab_4 = win.tabs.widget(4)
    tab_5 = win.tabs.widget(5)

    assert isinstance(tab_0, AccountsManagerTab)
    assert isinstance(tab_1, PromptStudioTab)
    assert isinstance(tab_2, CharacterStudioTab)
    assert isinstance(tab_3, QueueMonitorTab)
    assert isinstance(tab_4, MediaGalleryTab)
    assert isinstance(tab_5, MuseSettingsTab)


def test_start_batch_transitions_to_queue_tab(qapp):
    win = MainWindow()
    prompts = [
        "Prompt test 1: cat playing ball",
        "Prompt test 2: dog jumping high",
    ]
    cfg = {
        "account_mode": "rotation",
        "aspect_ratio": "16:9",
        "duration": 6,
        "smooth_60fps": True,
        "motion_boost": True,
        "motion_level": "smooth",
        "download_dir": "",
    }

    # Bắn request tạo batch
    win._on_start_batch_requested(prompts, cfg)

    # Đảm bảo tab hiện tại tự động chuyển sang Queue Monitor
    assert win.tabs.currentWidget() == win.tab_queue
    assert win.tab_queue.table.rowCount() == 2

    # Dừng workflow test
    win._on_stop_batch_requested()
    win.close()
    QApplication.processEvents()


def test_gallery_directory_sync_with_settings(qapp):
    win = MainWindow()
    gallery_dir = win.tab_gallery._get_target_dir()
    assert gallery_dir is not None
    assert str(gallery_dir).strip() != ""
    win.close()
    QApplication.processEvents()


def test_workflow_account_id_propagation(qapp):
    win = MainWindow()
    prompts = ["Single account task test"]
    cfg = {
        "account_mode": "single",
        "account_id": "acc_custom_001",
        "aspect_ratio": "16:9",
        "duration": 6,
        "smooth_60fps": False,
        "motion_boost": False,
        "download_dir": "",
    }
    win._on_start_batch_requested(prompts, cfg)
    assert win._workflow is not None
    assert win._workflow.account_id == "acc_custom_001"
    assert win._workflow.account_mode == "single"

    win._on_stop_batch_requested()
    win.close()
    QApplication.processEvents()
