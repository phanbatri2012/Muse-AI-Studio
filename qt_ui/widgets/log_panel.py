# -*- coding: utf-8 -*-
"""
Modern Log Console & Task Monitor Dock Widget for PyQt6 Desktop App.
Provides real-time auto-scrolling log monitoring, clipboard copying, and directory access.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSlot
from PyQt6.QtGui import QDesktopServices, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from runtime_paths import DOWNLOADS_DIR, MUSE_DOWNLOADS_DIR


class LogPanelWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        title_lbl = QLabel("🖥️ NHẬT KÝ HOẠT ĐỘNG THỜI GIAN THỰC")
        title_lbl.setStyleSheet("font-weight: 700; color: #38bdf8; font-size: 11px;")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch()

        self.auto_scroll_chk = QCheckBox("Tự động cuộn")
        self.auto_scroll_chk.setChecked(True)
        self.auto_scroll_chk.setStyleSheet("color: #94a3b8; font-size: 11px;")
        header_layout.addWidget(self.auto_scroll_chk)

        self.btn_copy = QPushButton("📋 Sao Chép")
        self.btn_copy.setFixedHeight(24)
        self.btn_copy.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        self.btn_copy.clicked.connect(self._copy_log)
        header_layout.addWidget(self.btn_copy)

        self.btn_clear = QPushButton("🗑️ Xóa")
        self.btn_clear.setFixedHeight(24)
        self.btn_clear.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        self.btn_clear.clicked.connect(self._clear_log)
        header_layout.addWidget(self.btn_clear)

        self.btn_downloads = QPushButton("📂 Mở Thư Mục Video")
        self.btn_downloads.setFixedHeight(24)
        self.btn_downloads.setStyleSheet("font-size: 11px; padding: 2px 8px; color: #34d399;")
        self.btn_downloads.clicked.connect(self._open_downloads_folder)
        header_layout.addWidget(self.btn_downloads)

        self.btn_toggle_collapse = QPushButton("🔽 Thu Gọn")
        self.btn_toggle_collapse.setFixedHeight(24)
        self.btn_toggle_collapse.setStyleSheet("font-size: 11px; padding: 2px 8px; color: #94a3b8;")
        self.btn_toggle_collapse.clicked.connect(self._toggle_collapse)
        header_layout.addWidget(self.btn_toggle_collapse)

        layout.addLayout(header_layout)

        # Log Console Editor
        self.console = QPlainTextEdit()
        self.console.setObjectName("LogConsole")
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(1500)
        layout.addWidget(self.console)

        # Welcome message
        self.append_log("✨ Hệ thống MUSE AI STUDIO Desktop đã sẵn sàng hoạt động.")

    @pyqtSlot(str)
    def append_log(self, message: str) -> None:
        """Ghi log an toàn luồng (hỗ trợ gọi từ QThread)."""
        if not message:
            return

        now_str = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{now_str}] {message}"

        self.console.appendPlainText(formatted)

        if self.auto_scroll_chk.isChecked():
            self.console.moveCursor(QTextCursor.MoveOperation.End)

    def _copy_log(self) -> None:
        text = self.console.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)

    def _clear_log(self) -> None:
        self.console.clear()
        self.append_log("Đã xóa toàn bộ nhật ký.")

    def _open_downloads_folder(self) -> None:
        target_dir = MUSE_DOWNLOADS_DIR if MUSE_DOWNLOADS_DIR.exists() else DOWNLOADS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_dir.resolve())))

    def _toggle_collapse(self) -> None:
        if self.console.isVisible():
            self.console.setVisible(False)
            self.setMaximumHeight(36)
            self.setMinimumHeight(36)
            self.btn_toggle_collapse.setText("🔼 Mở Rộng")
        else:
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(100)
            self.console.setVisible(True)
            self.btn_toggle_collapse.setText("🔽 Thu Gọn")
