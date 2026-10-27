# -*- coding: utf-8 -*-
"""
Main Application Window for MUSE AI STUDIO Desktop Application (PyQt6).
Kiến trúc 5 Màn Hình Chuyên Biệt (Zero Clutter):
1. 👥 Quản Lý Tài Khoản (AccountsManagerTab) - Xoay tua đa tài khoản tự động
2. 🎬 Xưởng Tạo Video (PromptStudioTab) - Khung soạn Prompt rộng rãi đánh số thứ tự
3. 📊 Tiến Độ & Hàng Đợi (QueueMonitorTab) - Bảng theo dõi tiến độ thời gian thực
4. 📁 Thư Viện Video (MediaGalleryTab) - Xem và phát lại các video thành phẩm
5. ⚙️ Cài Đặt Hệ Thống (MuseSettingsTab) - Cấu hình hệ thống, timeout và thư mục lưu
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from branding_config import (
    APP_VERSION,
    DEFAULT_BOT_USERNAME,
    OWNER_PHONE,
    OWNER_PHONE_LABEL,
    TELEGRAM_ADMIN_URL,
    TELEGRAM_BOT_URL,
)
from muse_chrome import cleanup_all_muse_processes
from muse_service_manager import MUSE2API_PORT, MuseServiceManager
from runtime_paths import get_icon_path
from A_workflow_muse_text_to_video import MuseTextToVideoWorkflow

from .tab_accounts_manager import AccountsManagerTab
from .tab_prompt_studio import PromptStudioTab
from .tab_character_studio import CharacterStudioTab
from .tab_queue_monitor import QueueMonitorTab
from .tab_media_gallery import MediaGalleryTab
from .tab_settings_muse import MuseSettingsTab
from .widgets.log_panel import LogPanelWidget


def _get_app_icon() -> QIcon:
    for name in ("app_icon.ico", "logo.ico", "app_icon.png", "logo.png"):
        candidate = get_icon_path(name)
        if candidate and os.path.isfile(candidate):
            ic = QIcon(candidate)
            if not ic.isNull():
                return ic
    return QIcon()


class MainWindow(QMainWindow):
    """Cửa sổ chính của ứng dụng MUSE AI STUDIO."""

    def __init__(self, parent: QWidget | None = None, start_backend: bool = True) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"MUSE AI STUDIO - Automated Video Generator ({OWNER_PHONE_LABEL})")
        self.setWindowIcon(_get_app_icon())
        self.resize(1366, 850)
        self.setMinimumSize(960, 580)

        self._workflow: MuseTextToVideoWorkflow | None = None

        self._init_ui()

        # Khởi động dịch vụ Muse2API ngầm nếu bật
        if start_backend:
            threading.Thread(target=lambda: MuseServiceManager.start_service(timeout=15), daemon=True).start()

    def _init_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---------------------------------------------------------------------
        # 1. Header Bar
        # ---------------------------------------------------------------------
        header = QWidget()
        header.setObjectName("AppHeader")
        header.setFixedHeight(54)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)
        header_layout.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        logo_path = get_icon_path("logo.png") or get_icon_path("app_icon.ico")
        if logo_path and os.path.isfile(logo_path):
            lbl_logo = QLabel()
            lbl_logo.setFixedSize(28, 28)
            pix = QPixmap(logo_path).scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_logo.setPixmap(pix)
            title_row.addWidget(lbl_logo)

        lbl_title = QLabel("MUSE AI STUDIO")
        lbl_title.setObjectName("HeaderTitle")
        title_row.addWidget(lbl_title)

        lbl_ver = QLabel(APP_VERSION)
        lbl_ver.setObjectName("BadgeVersion")
        title_row.addWidget(lbl_ver)

        lbl_badge = QLabel("PROMAX ĐA TÀI KHOẢN")
        lbl_badge.setObjectName("BadgeLicense")
        title_row.addWidget(lbl_badge)
        title_row.addStretch()

        title_box.addLayout(title_row)

        lbl_sub = QLabel("Hệ Thống Tự Động Hóa Video Đa Tài Khoản Xoay Tua & REST API Engine")
        lbl_sub.setObjectName("HeaderSubtitle")
        title_box.addWidget(lbl_sub)

        header_layout.addLayout(title_box)
        header_layout.addStretch()

        def _open_url(target_url: str):
            try:
                import webbrowser
                if not QDesktopServices.openUrl(QUrl(target_url)):
                    webbrowser.open(target_url)
            except Exception:
                import webbrowser
                webbrowser.open(target_url)

        # Contact & Store Buttons Container
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        # Nút 1: Liên hệ hỗ trợ qua Telegram
        btn_tele = QPushButton(f"✈️ Tele: {OWNER_PHONE}")
        btn_tele.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_tele.setFixedHeight(30)
        btn_tele.setStyleSheet(
            "QPushButton { background: #0c4a6e; color: #38bdf8; border: 1px solid #0284c7; "
            "border-radius: 14px; padding: 0 12px; font-size: 11px; font-weight: 700; } "
            "QPushButton:hover { background: #0284c7; color: #ffffff; border-color: #38bdf8; }"
        )
        btn_tele.setToolTip(f"Bấm để mở chat Telegram hỗ trợ với Admin {OWNER_PHONE}")
        btn_tele.clicked.connect(lambda: _open_url(TELEGRAM_ADMIN_URL))
        btn_box.addWidget(btn_tele)

        # Nút 2: Trang hỗ trợ tài khoản
        btn_bot = QPushButton(f"🛒 Mua Muse AI ({DEFAULT_BOT_USERNAME})")
        btn_bot.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_bot.setFixedHeight(30)
        btn_bot.setStyleSheet(
            "QPushButton { background: #581c87; color: #e9d5ff; border: 1px solid #9333ea; "
            "border-radius: 14px; padding: 0 12px; font-size: 11px; font-weight: 800; } "
            "QPushButton:hover { background: #7e22ce; color: #ffffff; border-color: #c084fc; }"
        )
        btn_bot.setToolTip(f"Bấm để mở Bot Telegram mua tài khoản Muse AI tự động 24/7 ({DEFAULT_BOT_USERNAME})")
        btn_bot.clicked.connect(lambda: _open_url(TELEGRAM_BOT_URL))
        btn_box.addWidget(btn_bot)

        header_layout.addLayout(btn_box)
        root_layout.addWidget(header)

        # ---------------------------------------------------------------------
        # 2. Main Content & Console Splitter
        # ---------------------------------------------------------------------
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setContentsMargins(8, 8, 8, 4)
        splitter.setChildrenCollapsible(False)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        # Tabs Container
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMinimumHeight(340)

        # Log Panel
        self.log_panel = LogPanelWidget()
        self.log_panel.setMinimumHeight(100)

        # Màn hình 1: 👥 Quản Lý Tài Khoản (Accounts Manager)
        self.tab_accounts = AccountsManagerTab(log_callback=self.log_panel.append_log)
        self.tabs.addTab(self.tab_accounts, "👥 Quản Lý Tài Khoản")

        # Màn hình 2: 🎬 Xưởng Tạo Video (Prompt Studio)
        self.tab_studio = PromptStudioTab(log_callback=self.log_panel.append_log)
        self.tabs.addTab(self.tab_studio, "🎬 Xưởng Tạo Video")

        # Màn hình 3: 👤 Đồng Bộ Nhân Vật (Character Studio)
        self.tab_character = CharacterStudioTab(log_callback=self.log_panel.append_log)
        self.tabs.addTab(self.tab_character, "👤 Đồng Bộ Nhân Vật")

        # Màn hình 4: 📊 Tiến Độ & Hàng Đợi (Queue Monitor)
        self.tab_queue = QueueMonitorTab(log_callback=self.log_panel.append_log)
        self.tabs.addTab(self.tab_queue, "📊 Tiến Độ & Hàng Đợi")

        # Màn hình 5: 📁 Thư Viện Video (Media Gallery)
        self.tab_gallery = MediaGalleryTab(log_callback=self.log_panel.append_log)
        self.tabs.addTab(self.tab_gallery, "📁 Thư Viện Video")

        # Màn hình 6: ⚙️ Cài Đặt Hệ Thống (Settings)
        self.tab_settings = MuseSettingsTab(log_callback=self.log_panel.append_log)
        self.tabs.addTab(self.tab_settings, "⚙️ Cài Đặt Hệ Thống")

        # ---------------------------------------------------------------------
        # KẾT NỐI TÍN HIỆU GIỮA CÁC MÀN HÌNH (SIGNALS / SLOTS)
        # ---------------------------------------------------------------------
        # Khi tài khoản thay đổi -> cập nhật dropdown trong Studio và Character Studio
        self.tab_accounts.accounts_changed.connect(self.tab_studio.populate_accounts)
        self.tab_accounts.accounts_changed.connect(self.tab_character.populate_accounts)

        # Khi bấm Bắt đầu tạo video từ Studio hoặc Character Studio
        self.tab_studio.start_batch_requested.connect(self._on_start_batch_requested)
        self.tab_studio.stop_batch_requested.connect(self._on_stop_batch_requested)
        self.tab_character.start_batch_requested.connect(self._on_start_batch_requested)
        self.tab_character.stop_batch_requested.connect(self._on_stop_batch_requested)

        # Khi bấm Dừng từ Queue Monitor
        self.tab_queue.stop_requested.connect(self._on_stop_batch_requested)

        # Chuyển hướng nhanh từ Cài Đặt sang Quản Lý Tài Khoản
        self.tab_settings.switch_to_accounts_requested.connect(lambda: self.tabs.setCurrentWidget(self.tab_accounts))
        # Khi lưu Cài Đặt -> Tự động làm mới Thư Viện Video theo thư mục mới
        self.tab_settings.settings_saved.connect(lambda: self.tab_gallery.refresh_gallery(force=True))

        # Khi chuyển đổi Tab
        self.tabs.currentChanged.connect(self._on_tab_changed)

        splitter.addWidget(self.tabs)
        splitter.addWidget(self.log_panel)

        # 75% workspace tabs, 25% console log
        splitter.setSizes([680, 180])
        root_layout.addWidget(splitter, 1)

        # ---------------------------------------------------------------------
        # 3. Status Bar
        # ---------------------------------------------------------------------
        self.status_bar = QStatusBar()
        self.status_bar.showMessage(f"🟢 Hệ Thống Sẵn Sàng • Muse2API Port {MUSE2API_PORT}")
        self.setStatusBar(self.status_bar)

    # =========================================================================
    # ĐIỀU PHỐI TIẾN TRÌNH TẠO VIDEO HÀNG LOẠT
    # =========================================================================

    def _on_start_batch_requested(self, prompts: list, config: dict) -> None:
        """Nhận yêu cầu tạo video từ Studio và khởi động pipeline chạy ngầm."""
        # 1. Khởi tạo hàng đợi và tự động chuyển người dùng sang tab Tiến Độ
        download_dir = config.get("download_dir", "")
        self.tab_queue.initialize_queue(prompts, download_dir=download_dir)
        self.tabs.setCurrentWidget(self.tab_queue)

        # 2. Chuẩn bị cấu hình dự án
        project_data = dict(config)
        project_data["prompts"] = prompts
        project_data["project_name"] = "batch_studio"

        # 3. Khởi tạo Workflow QThread
        if self._workflow and self._workflow.isRunning():
            self._workflow.stop()
            self._workflow.wait(1500)

        self._workflow = MuseTextToVideoWorkflow(
            project_name="batch_studio",
            project_data=project_data,
            parent=self,
        )

        # 4. Kết nối tín hiệu của Workflow vào Queue Monitor và Log Panel
        self._workflow.video_updated.connect(self.tab_queue.on_video_updated)
        self._workflow.log_message.connect(self.log_panel.append_log)
        self._workflow.automation_complete.connect(self._on_workflow_finished)
        self._workflow.video_folder_updated.connect(lambda _: self.tab_gallery.refresh_gallery())

        # 5. Kích hoạt chạy nền
        self._workflow.start()
        self.status_bar.showMessage(f"⚡ Đang chạy tiến trình tạo {len(prompts)} video...")

    def _on_stop_batch_requested(self) -> None:
        """Dừng tác vụ tạo video hiện tại."""
        if self._workflow and self._workflow.isRunning():
            self._workflow.stop()
            self._workflow.wait(1000)
        self.tab_studio.set_running_state(False)
        self.tab_character.set_running_state(False)
        self.tab_queue.btn_stop_queue.setEnabled(False)
        self.status_bar.showMessage("🛑 Đã dừng tiến trình tạo video.")

    def _on_workflow_finished(self) -> None:
        """Xử lý khi toàn bộ danh sách prompt hoàn tất."""
        self.tab_studio.set_running_state(False)
        self.tab_character.set_running_state(False)
        self.tab_queue.on_workflow_finished()
        self.tab_gallery.refresh_gallery()
        self.status_bar.showMessage("🎉 Đã hoàn tất toàn bộ danh sách video!")

    def _on_tab_changed(self, index: int) -> None:
        """Xử lý cập nhật dữ liệu tự động khi người dùng chuyển tab."""
        current_widget = self.tabs.widget(index)
        if isinstance(current_widget, MediaGalleryTab):
            current_widget.refresh_gallery(force=True)
        elif isinstance(current_widget, (PromptStudioTab, CharacterStudioTab)):
            current_widget.populate_accounts()
        elif isinstance(current_widget, AccountsManagerTab):
            current_widget.refresh_accounts_table()

    def closeEvent(self, event) -> None:
        """Dọn dẹp triệt để tài nguyên khi người dùng đóng cửa sổ ứng dụng."""
        try:
            if self._workflow and self._workflow.isRunning():
                self._workflow.stop()
                self._workflow.wait(1000)
            MuseServiceManager.stop_service()
            cleanup_all_muse_processes()
        except Exception:
            pass

        event.accept()
