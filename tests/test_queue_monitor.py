# -*- coding: utf-8 -*-
"""
Unit tests cho QueueMonitorTab.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qt_ui.tab_queue_monitor import QueueMonitorTab


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_queue_monitor_init_and_update(qapp):
    tab = QueueMonitorTab()
    prompts = [
        "Prompt A: puppy running on grass",
        "Prompt B: cat flying in sky",
    ]
    tab.initialize_queue(prompts)
    assert tab.table.rowCount() == 2
    assert tab.card_total.value_label.text() == "2"

    # Giả lập task 1 đang render 50%
    tab.on_video_updated({
        "prompt_idx": 0,
        "status": "PROCESSING",
        "progress": 50,
        "account": "account1@example.com",
    })
    item_status_0 = tab.table.item(0, 4)
    assert "Render" in item_status_0.text()
    assert "account1@example.com" in tab.table.item(0, 2).text()

    # Giả lập task 1 thành công 100%
    tab.on_video_updated({
        "prompt_idx": 0,
        "status": "SUCCESS",
        "progress": 100,
        "elapsed": 120,
    })
    assert "Hoàn thành" in tab.table.item(0, 4).text()
    assert tab.card_success.value_label.text() == "1"

    # Giả lập task 2 thất bại
    tab.on_video_updated({
        "prompt_idx": 1,
        "status": "FAILED",
        "error": "Timeout",
    })
    assert "Thất bại" in tab.table.item(1, 4).text()
    assert tab.card_failed.value_label.text() == "1"
    assert tab.overall_progress_bar.value() == 100
