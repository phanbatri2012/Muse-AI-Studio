# -*- coding: utf-8 -*-
"""
Native PyQt6 Settings Tab dedicated to Muse AI.
Provides clean configuration for Chrome profiles, output paths, timeouts, and retries.
"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from muse_service_manager import MUSE2API_PORT, MuseServiceManager
from runtime_paths import MUSE_DOWNLOADS_DIR
from settings_manager import SettingsManager


class MuseSettingsTab(QWidget):
    profile_changed = Signal()
    switch_to_accounts_requested = Signal()
    settings_saved = Signal()

    def __init__(self, log_callback=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_callback = log_callback
        self._init_ui()
        self._load_settings()

    def _log(self, msg: str) -> None:
        if callable(self.log_callback):
            self.log_callback(msg)

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Scroll Area to prevent clipping on small screens
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.verticalScrollBar().setSingleStep(24)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 20)
        layout.setSpacing(14)

        # ---------------------------------------------------------------------
        # 1. Output Paths Configuration (NƠI DUY NHẤT CẤU HÌNH THƯ MỤC LƯU)
        # ---------------------------------------------------------------------
        path_group = QGroupBox("📁 THƯ MỤC LƯU TRỮ VIDEO MẶC ĐỊNH")
        path_layout = QVBoxLayout(path_group)
        path_layout.setContentsMargins(14, 16, 14, 14)
        path_layout.setSpacing(10)

        row_path = QHBoxLayout()
        row_path.addWidget(QLabel("Thư mục lưu video:"))
        self.txt_download_dir = QLineEdit(str(MUSE_DOWNLOADS_DIR))
        self.txt_download_dir.setMinimumHeight(32)
        row_path.addWidget(self.txt_download_dir, 1)

        btn_browse = QPushButton("📂 Chọn Thư Mục")
        btn_browse.setFixedHeight(32)
        btn_browse.clicked.connect(self._browse_download_dir)
        row_path.addWidget(btn_browse)
        path_layout.addLayout(row_path)

        lbl_path_hint = QLabel("💡 Tất cả video sinh ra từ Xưởng Tạo Video sẽ tự động được lưu vào thư mục này.")
        lbl_path_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        path_layout.addWidget(lbl_path_hint)

        layout.addWidget(path_group)

        # ---------------------------------------------------------------------
        # 2. REST API Backend Status & Service
        # ---------------------------------------------------------------------
        api_group = QGroupBox("🔌 DỊCH VỤ REST API ENGINE (MUSE2API)")
        api_layout = QVBoxLayout(api_group)
        api_layout.setContentsMargins(14, 16, 14, 14)
        api_layout.setSpacing(10)

        api_row = QHBoxLayout()
        self.lbl_api_status = QLabel(f"🟢 Máy chủ REST API: http://127.0.0.1:{MUSE2API_PORT} (Đang hoạt động)")
        self.lbl_api_status.setStyleSheet("color: #34d399; font-weight: 700; font-size: 12px;")
        api_row.addWidget(self.lbl_api_status)
        api_row.addStretch()

        self.btn_restart_service = QPushButton("🔄 Khởi Động Lại Service")
        self.btn_restart_service.setFixedHeight(30)
        self.btn_restart_service.setStyleSheet("font-weight: 600; padding: 0 12px;")
        self.btn_restart_service.clicked.connect(self._restart_service)
        api_row.addWidget(self.btn_restart_service)
        api_layout.addLayout(api_row)

        lbl_api_desc = QLabel(
            "ℹ️ Muse2API xử lý toàn bộ các yêu cầu sinh video độc lập, hỗ trợ xoay tua đa tài khoản và tái sử dụng session tối ưu."
        )
        lbl_api_desc.setStyleSheet("color: #64748b; font-size: 11px;")
        api_layout.addWidget(lbl_api_desc)

        layout.addWidget(api_group)

        # ---------------------------------------------------------------------
        # 3. Account Pool Navigation Card (Loại bỏ form login đơn lẻ trùng lặp)
        # ---------------------------------------------------------------------
        acc_banner = QFrame()
        acc_banner.setStyleSheet(
            "QFrame { background: #0f172a; border: 1px solid #1e293b; border-left: 4px solid #38bdf8; border-radius: 8px; padding: 12px 14px; }"
        )
        acc_layout = QHBoxLayout(acc_banner)
        acc_layout.setContentsMargins(6, 6, 6, 6)
        acc_layout.setSpacing(12)

        info_box = QVBoxLayout()
        info_box.setSpacing(2)
        lbl_acc_title = QLabel("👥 QUẢN LÝ TÀI KHOẢN & XOAY TUA (ACCOUNT POOL)")
        lbl_acc_title.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 12px;")
        lbl_acc_sub = QLabel("Hệ thống hoạt động theo cơ chế Account Pool đa tài khoản (email | pass | 2fa) hoàn toàn tự động.")
        lbl_acc_sub.setStyleSheet("color: #94a3b8; font-size: 11px;")
        info_box.addWidget(lbl_acc_title)
        info_box.addWidget(lbl_acc_sub)
        acc_layout.addLayout(info_box, 1)

        btn_goto_accounts = QPushButton("👉 Quản Lý Tài Khoản")
        btn_goto_accounts.setFixedHeight(34)
        btn_goto_accounts.setStyleSheet("font-weight: 700; color: #38bdf8; padding: 0 14px; border: 1px solid #0284c7;")
        btn_goto_accounts.clicked.connect(self.switch_to_accounts_requested.emit)
        acc_layout.addWidget(btn_goto_accounts)

        layout.addWidget(acc_banner)

        # ---------------------------------------------------------------------
        # 4. Automation Parameters Configuration
        # ---------------------------------------------------------------------
        param_group = QGroupBox("⚙️ THAM SỐ TỰ ĐỘNG HÓA MẶC ĐỊNH")
        param_form = QFormLayout(param_group)
        param_form.setContentsMargins(14, 16, 14, 14)
        param_form.setSpacing(10)

        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(30, 900)
        self.spin_timeout.setValue(360)
        self.spin_timeout.setSuffix(" giây")
        self.spin_timeout.setMinimumHeight(30)
        param_form.addRow("Thời gian chờ tối đa mặc định (Timeout):", self.spin_timeout)

        self.spin_retries = QSpinBox()
        self.spin_retries.setRange(0, 5)
        self.spin_retries.setValue(2)
        self.spin_retries.setMinimumHeight(30)
        param_form.addRow("Số lần thử lại khi lỗi (Max Retries):", self.spin_retries)

        self.spin_concurrent = QSpinBox()
        self.spin_concurrent.setRange(1, 5)
        self.spin_concurrent.setValue(2)
        self.spin_concurrent.setMinimumHeight(30)
        param_form.addRow("Số tác vụ xử lý đồng thời (Concurrent):", self.spin_concurrent)

        self.spin_keepalive_hours = QSpinBox()
        self.spin_keepalive_hours.setRange(1, 48)
        self.spin_keepalive_hours.setValue(6)
        self.spin_keepalive_hours.setSuffix(" giờ")
        self.spin_keepalive_hours.setMinimumHeight(30)
        self.spin_keepalive_hours.setToolTip("Chu kỳ tự động gọi gia hạn và đánh thức Cloud VM")
        param_form.addRow("Chu kỳ tự động gia hạn VM (Keep-Alive):", self.spin_keepalive_hours)

        layout.addWidget(param_group)

        # Save Button Bar
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()

        self.btn_save = QPushButton("💾 LƯU CẤU HÌNH (SAVE SETTINGS)")
        self.btn_save.setFixedHeight(40)
        self.btn_save.setProperty("primary", True)
        self.btn_save.setStyleSheet("font-weight: 700; padding: 6px 28px; font-size: 13px;")
        self.btn_save.clicked.connect(self._save_settings)
        btn_bar.addWidget(self.btn_save)

        layout.addLayout(btn_bar)
        layout.addSpacing(20)

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

    def _restart_service(self) -> None:
        self.lbl_api_status.setText("⏳ Đang khởi động lại dịch vụ Muse2API...")
        self.lbl_api_status.setStyleSheet("color: #facc15; font-weight: 700; font-size: 12px;")
        try:
            ok = MuseServiceManager.restart_service(timeout=15)
            if ok:
                self.lbl_api_status.setText(f"🟢 Máy chủ REST API: http://127.0.0.1:{MUSE2API_PORT} (Đang hoạt động)")
                self.lbl_api_status.setStyleSheet("color: #34d399; font-weight: 700; font-size: 12px;")
                self._log("🎉 Khởi động lại Muse2API Server thành công.")
                QMessageBox.information(self, "Dịch Vụ API", "Máy chủ Muse2API đã được khởi động lại thành công!")
            else:
                self.lbl_api_status.setText(f"🔴 Máy chủ REST API: Không phản hồi trên cổng {MUSE2API_PORT}")
                self.lbl_api_status.setStyleSheet("color: #f87171; font-weight: 700; font-size: 12px;")
                self._log("❌ Không thể khởi động lại Muse2API Server.")
        except Exception as exc:
            self._log(f"⚠️ Lỗi khởi động lại service: {exc}")

    def _load_settings(self) -> None:
        st = SettingsManager.load_muse_settings()
        dl_dir = st.get("download_dir", str(MUSE_DOWNLOADS_DIR))
        self.txt_download_dir.setText(dl_dir)

        self.spin_timeout.setValue(int(st.get("task_timeout_seconds", 360)))
        self.spin_retries.setValue(int(st.get("max_retries", 2)))
        self.spin_concurrent.setValue(int(st.get("max_concurrent_tasks", 2)))
        self.spin_keepalive_hours.setValue(int(st.get("keepalive_interval_hours", 6)))

    def _save_settings(self) -> None:
        current = SettingsManager.load_muse_settings()
        current.update({
            "download_dir": self.txt_download_dir.text().strip(),
            "task_timeout_seconds": self.spin_timeout.value(),
            "max_retries": self.spin_retries.value(),
            "max_concurrent_tasks": self.spin_concurrent.value(),
            "keepalive_interval_hours": self.spin_keepalive_hours.value(),
        })
        SettingsManager.save_muse_settings(current)
        self._log("💾 Đã lưu cấu hình Muse AI thành công.")
        self.settings_saved.emit()
        QMessageBox.information(self, "Đã Lưu", "Cấu hình Muse AI đã được lưu thành công!")

    def _browse_download_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu video Muse AI", self.txt_download_dir.text())
        if path:
            self.txt_download_dir.setText(path)
