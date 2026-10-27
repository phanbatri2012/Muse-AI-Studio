# -*- coding: utf-8 -*-
"""
Native PyQt6 Muse AI Studio Tab for TOOL VEO PROMAX.
Features:
- Dedicated Chrome CDP control & real-time connection status.
- Session harvesting & authentication status detection.
- Batch multi-prompt editor with TXT import and sample library.
- Direct QThread execution with live task table progress.
- Video playback & folder opening shortcuts.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSlot
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from A_workflow_muse_text_to_video import MuseTextToVideoWorkflow
from prompt_motion_enhancer import MotionLevel
from muse_auth import MuseAuthManager
from muse_service_manager import MuseServiceManager, MUSE2API_PORT
from muse_chrome import (
    MUSE_CDP_PORT,
    is_muse_chrome_running,
    kill_muse_chrome_by_profile,
    open_muse_chrome,
    resolve_muse_profile_dir,
)
from runtime_paths import MUSE_CHROME_USER_DATA_ROOT, MUSE_DOWNLOADS_DIR
from settings_manager import SettingsManager

SAMPLE_MUSE_PROMPTS = [
    "A majestic cinematic drone flyover of misty pine forest mountains at sunrise, 4k ultra-realistic.",
    "Futuristic neon-lit cyberpunk city street in Tokyo during heavy rain with flying cars, photorealistic.",
    "A cute fluffy golden retriever puppy playing with autumn leaves in a sunlit park, slow motion.",
    "Cosmic voyage through a swirling colorful galaxy nebula with sparkling star clusters, hyper-detailed.",
]


class MuseAITab(QWidget):
    def __init__(self, log_callback=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_callback = log_callback
        self._workflow: MuseTextToVideoWorkflow | None = None
        self._table_rows_map: dict[str, int] = {}
        self._is_ui_busy: bool = False
        self._is_checking_chrome: bool = False

        self._init_ui()
        self._load_saved_credentials()
        self._setup_timer()
        self._refresh_auth_status()

    def _log(self, msg: str) -> None:
        if callable(self.log_callback):
            self.log_callback(msg)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # ---------------------------------------------------------------------
        # 1. CDP Chrome & Session Control Bar (2-Card Responsive Grid)
        # ---------------------------------------------------------------------
        cdp_group = QGroupBox("🌐 ĐIỀU KHIỂN CHROME CDP & ĐĂNG NHẬP (MUSE AI)")
        cdp_layout = QHBoxLayout(cdp_group)
        cdp_layout.setContentsMargins(12, 12, 12, 10)
        cdp_layout.setSpacing(14)

        # --- Sub-Card 1: Chrome CDP & Profile ---
        cdp_card = QWidget()
        cdp_card_layout = QVBoxLayout(cdp_card)
        cdp_card_layout.setContentsMargins(0, 0, 0, 0)
        cdp_card_layout.setSpacing(6)

        c_row1 = QHBoxLayout()
        c_row1.setSpacing(8)
        self.lbl_cdp_status = QLabel(f"🟢 Muse2API Server: Đang kiểm tra...")
        self.lbl_cdp_status.setStyleSheet("font-weight: 700; color: #38bdf8; font-size: 12px;")
        c_row1.addWidget(self.lbl_cdp_status)
        c_row1.addStretch()

        self.btn_open_admin = QPushButton("🌐 Mở Web Admin")
        self.btn_open_admin.setStyleSheet("font-size: 11px; padding: 3px 8px; font-weight: 600;")
        self.btn_open_admin.setToolTip("Mở giao diện Web Admin của muse2api trên trình duyệt")
        self.btn_open_admin.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"http://127.0.0.1:{MUSE2API_PORT}/")))
        c_row1.addWidget(self.btn_open_admin)
        cdp_card_layout.addLayout(c_row1)

        c_row2 = QHBoxLayout()
        c_row2.setSpacing(8)
        c_row2.addWidget(QLabel("Hồ sơ:"))
        self.combo_profile = QComboBox()
        self.combo_profile.setMinimumWidth(150)
        self._populate_profiles()
        c_row2.addWidget(self.combo_profile, 1)

        self.btn_restart_service = QPushButton("🔄 Khởi Động Server")
        self.btn_restart_service.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        self.btn_restart_service.clicked.connect(self._restart_service)
        c_row2.addWidget(self.btn_restart_service)

        self.btn_open_chrome = QPushButton("🌐 Mở Chrome")
        self.btn_open_chrome.clicked.connect(self._open_chrome)
        c_row2.addWidget(self.btn_open_chrome)
        cdp_card_layout.addLayout(c_row2)

        cdp_layout.addWidget(cdp_card, 4)

        # Vertical Divider
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("color: #334155;")
        cdp_layout.addWidget(sep)

        # --- Sub-Card 2: Account & Auto Login ---
        auth_card = QWidget()
        auth_card_layout = QVBoxLayout(auth_card)
        auth_card_layout.setContentsMargins(0, 0, 0, 0)
        auth_card_layout.setSpacing(6)

        a_row1 = QHBoxLayout()
        a_row1.setSpacing(8)
        a_row1.addWidget(QLabel("Email:"))
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("email tài khoản...")
        self.txt_email.setMinimumWidth(140)
        a_row1.addWidget(self.txt_email, 2)

        a_row1.addWidget(QLabel("Pass:"))
        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setPlaceholderText("mật khẩu...")
        self.txt_password.setMinimumWidth(100)
        a_row1.addWidget(self.txt_password, 2)

        self.btn_toggle_pwd = QPushButton("👁️")
        self.btn_toggle_pwd.setFixedWidth(28)
        self.btn_toggle_pwd.setToolTip("Xem/Ẩn mật khẩu")
        self.btn_toggle_pwd.clicked.connect(self._toggle_pwd_visibility)
        a_row1.addWidget(self.btn_toggle_pwd)

        a_row1.addWidget(QLabel("2FA:"))
        self.txt_2fa = QLineEdit()
        self.txt_2fa.setPlaceholderText("2FA TOTP secret...")
        self.txt_2fa.setMinimumWidth(110)
        a_row1.addWidget(self.txt_2fa, 2)

        self.btn_save_creds = QPushButton("💾 Lưu")
        self.btn_save_creds.setFixedWidth(56)
        self.btn_save_creds.setStyleSheet("font-size: 11px; padding: 3px 6px;")
        self.btn_save_creds.setToolTip("Lưu tài khoản để không cần gõ lại")
        self.btn_save_creds.clicked.connect(self._save_credentials)
        a_row1.addWidget(self.btn_save_creds)
        auth_card_layout.addLayout(a_row1)

        a_row2 = QHBoxLayout()
        a_row2.setSpacing(8)
        self.lbl_auth_status = QLabel("⚠️ Chưa đăng nhập")
        self.lbl_auth_status.setStyleSheet("color: #f59e0b; font-weight: 600; font-size: 11px;")
        a_row2.addWidget(self.lbl_auth_status)
        a_row2.addStretch()

        self.btn_auto_login = QPushButton("🚀 Đăng Nhập Tự Động")
        self.btn_auto_login.setProperty("primary", True)
        self.btn_auto_login.setStyleSheet("font-weight: 700; padding: 4px 12px;")
        self.btn_auto_login.clicked.connect(self._do_auto_login)
        a_row2.addWidget(self.btn_auto_login)

        self.btn_renew_session = QPushButton("⚡ Gia Hạn & Wake VM")
        self.btn_renew_session.setStyleSheet("font-size: 11px; padding: 4px 10px; font-weight: 700; color: #38bdf8;")
        self.btn_renew_session.setToolTip("Gia hạn hatch_vml (+48h), hatch_sess (+30d) và đánh thức Cloud VM trực tiếp qua API")
        self.btn_renew_session.clicked.connect(self._do_renew_session)
        a_row2.addWidget(self.btn_renew_session)

        self.btn_capture_auth = QPushButton("🔑 Bắt Phiên Mới")
        self.btn_capture_auth.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        self.btn_capture_auth.clicked.connect(self._capture_session)
        a_row2.addWidget(self.btn_capture_auth)
        auth_card_layout.addLayout(a_row2)

        cdp_layout.addWidget(auth_card, 6)

        main_layout.addWidget(cdp_group)

        # ---------------------------------------------------------------------
        # 2. Main Content Splitter (Left: Prompts & Params | Right: Progress Table)
        # ---------------------------------------------------------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- LEFT PANEL: Prompt Input & Parameters ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # Prompt input box
        prompt_group = QGroupBox("📝 DANH SÁCH PROMPTS (MỖI DÒNG 1 PROMPT)")
        prompt_layout = QVBoxLayout(prompt_group)
        prompt_layout.setContentsMargins(10, 14, 10, 10)
        prompt_layout.setSpacing(8)

        # Toolbar above editor
        tb_layout = QHBoxLayout()
        self.lbl_prompt_count = QLabel("Tổng số: 0 prompts")
        self.lbl_prompt_count.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11px;")
        tb_layout.addWidget(self.lbl_prompt_count)
        tb_layout.addStretch()

        self.btn_load_file = QPushButton("📂 Nạp File .txt")
        self.btn_load_file.setFixedHeight(26)
        self.btn_load_file.setStyleSheet("font-size: 11px;")
        self.btn_load_file.clicked.connect(self._load_txt_file)
        tb_layout.addWidget(self.btn_load_file)

        self.btn_sample = QPushButton("💡 Prompt Mẫu")
        self.btn_sample.setFixedHeight(26)
        self.btn_sample.setStyleSheet("font-size: 11px;")
        self.btn_sample.clicked.connect(self._load_sample_prompts)
        tb_layout.addWidget(self.btn_sample)

        self.btn_clear = QPushButton("🧹 Xóa Trắng")
        self.btn_clear.setFixedHeight(26)
        self.btn_clear.setStyleSheet("font-size: 11px;")
        self.btn_clear.clicked.connect(self._clear_prompts)
        tb_layout.addWidget(self.btn_clear)
        prompt_layout.addLayout(tb_layout)

        # Text Editor
        self.txt_prompts = QPlainTextEdit()
        self.txt_prompts.setPlaceholderText("Nhập từng prompt trên một dòng...\nVí dụ:\nCinematic sunset at tropical beach, 4k.\nFuturistic cyber city at night, rain.")
        self.txt_prompts.textChanged.connect(self._on_prompt_text_changed)
        prompt_layout.addWidget(self.txt_prompts)
        left_layout.addWidget(prompt_group)

        # Parameters Box
        params_group = QGroupBox("⚙️ CẤU HÌNH ĐỊNH DẠNG & CHUYỂN ĐỘNG")
        params_layout = QVBoxLayout(params_group)
        params_layout.setContentsMargins(10, 12, 10, 10)
        params_layout.setSpacing(8)

        row_p1 = QHBoxLayout()
        row_p1.addWidget(QLabel("📐 Tỉ lệ:"))
        self.combo_aspect_ratio = QComboBox()
        self.combo_aspect_ratio.addItem("9:16 (Dọc TikTok/Shorts)", "9:16")
        self.combo_aspect_ratio.addItem("16:9 (Ngang YouTube)", "16:9")
        self.combo_aspect_ratio.setToolTip("Tỉ lệ khung hình định dạng theo chuẩn prompt muse2api")
        row_p1.addWidget(self.combo_aspect_ratio)

        row_p1.addWidget(QLabel("⏱️ Thời lượng:"))
        self.combo_duration = QComboBox()
        self.combo_duration.addItem("5s", 5)
        self.combo_duration.addItem("6s (Chuẩn)", 6)
        self.combo_duration.addItem("8s", 8)
        self.combo_duration.addItem("10s", 10)
        self.combo_duration.setCurrentIndex(1)
        self.combo_duration.setToolTip("Thời lượng video mục tiêu yêu cầu AI sinh")
        row_p1.addWidget(self.combo_duration)

        row_p1.addWidget(QLabel("Timeout:"))
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(30, 900)
        self.spin_timeout.setValue(360)
        self.spin_timeout.setSuffix("s")
        row_p1.addWidget(self.spin_timeout)

        row_p1.addWidget(QLabel("Thử lại:"))
        self.spin_retries = QSpinBox()
        self.spin_retries.setRange(0, 5)
        self.spin_retries.setValue(2)
        row_p1.addWidget(self.spin_retries)
        row_p1.addStretch()
        params_layout.addLayout(row_p1)

        row_p2 = QHBoxLayout()
        self.chk_context_isolation = QCheckBox("🛡️ Cô lập ngữ cảnh")
        self.chk_context_isolation.setChecked(True)
        self.chk_context_isolation.setStyleSheet("font-weight: 700; color: #34d399;")
        self.chk_context_isolation.setToolTip("Thêm tiền tố 全新文生视频创作... để cô lập ngữ cảnh, triệt tiêu lỗi AI chat hội thoại rác")
        row_p2.addWidget(self.chk_context_isolation)

        self.chk_motion_boost = QCheckBox("⚡ Ép chuyển động")
        self.chk_motion_boost.setChecked(True)
        self.chk_motion_boost.setStyleSheet("font-weight: 700; color: #38bdf8;")
        self.chk_motion_boost.setToolTip("Tự động bổ sung chỉ thị động học để ngăn video bị đóng băng chủ thể")
        row_p2.addWidget(self.chk_motion_boost)

        self.combo_motion_level = QComboBox()
        self.combo_motion_level.addItem("🌊 Siêu Mượt / Smooth Glide", MotionLevel.SMOOTH)
        self.combo_motion_level.addItem("🏃 Hành động / Action", MotionLevel.ACTION)
        self.combo_motion_level.addItem("🎥 Camera Tracking", MotionLevel.TRACKING)
        self.combo_motion_level.addItem("🚁 Flycam FPV Drone", MotionLevel.DRONE)
        self.chk_motion_boost.toggled.connect(self.combo_motion_level.setEnabled)
        row_p2.addWidget(self.combo_motion_level)

        self.chk_smooth_60fps = QCheckBox("⚡ Làm mượt 60fps (MCI)")
        self.chk_smooth_60fps.setChecked(False)
        self.chk_smooth_60fps.setStyleSheet("font-weight: 700; color: #a78bfa;")
        self.chk_smooth_60fps.setToolTip("Tự động nội suy bù trừ quang học qua FFmpeg để khử sạch hiện tượng giật cục / ghép ảnh")
        row_p2.addWidget(self.chk_smooth_60fps)
        row_p2.addStretch()
        params_layout.addLayout(row_p2)

        left_layout.addWidget(params_group)

        # Output directory row
        dir_box = QHBoxLayout()
        dir_box.setSpacing(6)
        dir_box.addWidget(QLabel("📁 Lưu tại:"))
        self.lbl_current_download_dir = QLabel(str(MUSE_DOWNLOADS_DIR))
        self.lbl_current_download_dir.setStyleSheet("color: #94a3b8; font-size: 11px;")
        dir_box.addWidget(self.lbl_current_download_dir, 1)

        self.btn_open_dest_folder = QPushButton("📂 Mở")
        self.btn_open_dest_folder.setFixedHeight(24)
        self.btn_open_dest_folder.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        self.btn_open_dest_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(MUSE_DOWNLOADS_DIR.resolve()))))
        dir_box.addWidget(self.btn_open_dest_folder)
        left_layout.addLayout(dir_box)

        # Run Action Buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        self.btn_start = QPushButton("🚀 BẮT ĐẦU TẠO VIDEO (START)")
        self.btn_start.setFixedHeight(40)
        self.btn_start.setProperty("success", True)
        self.btn_start.setStyleSheet("font-size: 13px; font-weight: 800;")
        self.btn_start.clicked.connect(self._start_workflow)
        actions_layout.addWidget(self.btn_start, 3)

        self.btn_stop = QPushButton("🛑 DỪNG KHẨN CẤP")
        self.btn_stop.setFixedHeight(40)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setProperty("danger", True)
        self.btn_stop.setStyleSheet("font-size: 13px; font-weight: 800;")
        self.btn_stop.clicked.connect(self._stop_workflow)
        actions_layout.addWidget(self.btn_stop, 1)

        left_layout.addLayout(actions_layout)
        splitter.addWidget(left_widget)

        # --- RIGHT PANEL: Live Task Table ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        table_group = QGroupBox("📊 BẢNG TIẾN ĐỘ TÁC VỤ THỜI GIAN THỰC")
        table_layout = QVBoxLayout(table_group)
        table_layout.setContentsMargins(8, 14, 8, 8)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "Prompt", "Trạng Thái", "File Video", "Thao Tác"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.verticalScrollBar().setSingleStep(16)
        table_layout.addWidget(self.table)

        right_layout.addWidget(table_group)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        main_layout.addWidget(splitter)

    # -------------------------------------------------------------------------
    # Profile & Status Helpers
    # -------------------------------------------------------------------------
    def _populate_profiles(self) -> None:
        prev = self.combo_profile.currentText()
        st = SettingsManager.load_muse_settings()
        default_prof = st.get("current_profile", "MUSE_PROFILE_1")

        self.combo_profile.blockSignals(True)
        self.combo_profile.clear()
        profiles = ["MUSE_PROFILE_1", "MUSE_PROFILE_2", "MUSE_PROFILE_3"]
        if MUSE_CHROME_USER_DATA_ROOT.exists():
            for p in sorted(MUSE_CHROME_USER_DATA_ROOT.iterdir()):
                if p.is_dir() and p.name not in profiles:
                    profiles.append(p.name)
        for prof in profiles:
            self.combo_profile.addItem(prof)

        target = prev or default_prof
        idx = self.combo_profile.findText(target)
        if idx >= 0:
            self.combo_profile.setCurrentIndex(idx)
        self.combo_profile.blockSignals(False)

    def _setup_timer(self) -> None:
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._trigger_background_chrome_check)
        self.timer.start(2500)
        self._trigger_background_chrome_check()

    def _trigger_background_chrome_check(self) -> None:
        if getattr(self, "_is_checking_chrome", False):
            return
        self._is_checking_chrome = True

        def _worker():
            try:
                running = MuseServiceManager.is_service_ready()
            except Exception:
                running = False
            finally:
                self._is_checking_chrome = False
                QTimer.singleShot(0, lambda: self._apply_chrome_status(running))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_chrome_status(self, is_running: bool) -> None:
        if is_running:
            self.lbl_cdp_status.setText(f"🟢 Muse2API Server: Sẵn sàng (Port {MUSE2API_PORT})")
            self.lbl_cdp_status.setStyleSheet("font-weight: 700; color: #10b981; font-size: 12px;")
            self.btn_restart_service.setText("🔄 Khởi Động Lại")
        else:
            self.lbl_cdp_status.setText(f"🟡 Muse2API Server: Đang tắt (Port {MUSE2API_PORT})")
            self.lbl_cdp_status.setStyleSheet("font-weight: 700; color: #f59e0b; font-size: 12px;")
            self.btn_restart_service.setText("🚀 Khởi Động Server")

    def _restart_service(self) -> None:
        self._log("🔄 Đang cấu hình và khởi động lại dịch vụ Muse2API...")
        self.btn_restart_service.setEnabled(False)

        def _worker():
            try:
                MuseServiceManager.stop_service(self._log)
                time.sleep(1)
                MuseServiceManager.start_service(timeout=15, log_callback=self._log)
            finally:
                QTimer.singleShot(0, lambda: self.btn_restart_service.setEnabled(True))
                QTimer.singleShot(0, self._check_chrome_status)

        threading.Thread(target=_worker, daemon=True).start()

    def _check_chrome_status(self) -> None:
        self._trigger_background_chrome_check()

    def _refresh_auth_status(self) -> None:
        is_valid = MuseAuthManager.is_saved_session_valid()
        if is_valid:
            session_data = SettingsManager.load_muse_session()
            vm_state = session_data.get("vm_status") or ("RUNNING" if session_data.get("cookies") else "")
            if vm_state:
                self.lbl_auth_status.setText(f"✅ Phiên sẵn sàng (VM: {vm_state})")
            else:
                self.lbl_auth_status.setText("✅ Đã có phiên đăng nhập")
            self.lbl_auth_status.setStyleSheet("color: #10b981; font-weight: 700; font-size: 11px;")
        else:
            self.lbl_auth_status.setText("⚠️ Chưa thu hoạch phiên")
            self.lbl_auth_status.setStyleSheet("color: #f59e0b; font-weight: 600; font-size: 11px;")

    def _do_renew_session(self) -> None:
        self.btn_renew_session.setEnabled(False)
        self._log("⚡ Đang gọi Muse API để kiểm tra & gia hạn Cloud VM session...")

        def _task():
            import asyncio
            try:
                res = asyncio.run(MuseAuthManager.renew_session_http(log_callback=self._log))
                if res.get("success"):
                    vm_st = res.get("vm_state", "RUNNING")
                    self._log(f"🎉 Gia hạn thành công! Trạng thái Cloud VM: {vm_st}")
                else:
                    self._log(f"⚠️ Không thể gia hạn phiên: {res.get('error')}")
            except Exception as e:
                self._log(f"❌ Lỗi gia hạn session: {e}")
            finally:
                QTimer.singleShot(0, self._on_renew_session_finished)

        threading.Thread(target=_task, daemon=True).start()

    def _on_renew_session_finished(self) -> None:
        self.btn_renew_session.setEnabled(True)
        self._refresh_auth_status()

    def _load_saved_credentials(self) -> None:
        st = SettingsManager.load_muse_settings()
        if st.get("email"):
            self.txt_email.setText(st["email"])
        if st.get("password"):
            self.txt_password.setText(st["password"])
        if st.get("two_factor_secret"):
            self.txt_2fa.setText(st["two_factor_secret"])
        dl_dir = st.get("download_dir", str(MUSE_DOWNLOADS_DIR))
        if hasattr(self, "lbl_current_download_dir"):
            self.lbl_current_download_dir.setText(dl_dir)

    def _toggle_pwd_visibility(self) -> None:
        if self.txt_password.echoMode() == QLineEdit.EchoMode.Password:
            self.txt_password.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)

    def _save_credentials(self) -> None:
        email = self.txt_email.text().strip()
        pwd = self.txt_password.text()
        two_fa = self.txt_2fa.text().strip()
        current = SettingsManager.load_muse_settings()
        current["email"] = email
        current["password"] = pwd
        current["two_factor_secret"] = two_fa
        SettingsManager.save_muse_settings(current)
        self._log("💾 Đã lưu thông tin tài khoản, mật khẩu & 2FA secret.")
        QMessageBox.information(self, "Đã Lưu", "Thông tin tài khoản đã được lưu an toàn!")

    def _do_auto_login(self) -> None:
        email = self.txt_email.text().strip()
        pwd = self.txt_password.text()
        two_fa = self.txt_2fa.text().strip()
        if not email or not pwd:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập Email và Mật khẩu!")
            return

        # Tự động lưu thông tin
        current = SettingsManager.load_muse_settings()
        current["email"] = email
        current["password"] = pwd
        current["two_factor_secret"] = two_fa
        SettingsManager.save_muse_settings(current)

        profile_name = self.combo_profile.currentText()
        self.btn_auto_login.setEnabled(False)
        self._log(f"🔑 Bắt đầu tự động đăng nhập tài khoản '{email}' trên profile '{profile_name}'...")

        def _task():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                res = loop.run_until_complete(
                    MuseAuthManager.auto_login(
                        email=email,
                        password=pwd,
                        two_factor_secret=two_fa or None,
                        profile_name=profile_name,
                        port=MUSE_CDP_PORT,
                        timeout_seconds=120,
                        log_callback=self._log,
                    )
                )
                if res.get("success"):
                    self._log("🎉 Tự động đăng nhập thành công!")
                else:
                    self._log(f"⚠️ Đăng nhập chưa hoàn tất: {res.get('error')}")
            except Exception as e:
                self._log(f"❌ Lỗi tự động đăng nhập: {e}")
            finally:
                loop.close()
                QTimer.singleShot(0, self._on_auto_login_finished)

        threading.Thread(target=_task, daemon=True).start()

    def _on_auto_login_finished(self) -> None:
        self.btn_auto_login.setEnabled(True)
        self._refresh_auth_status()

    # -------------------------------------------------------------------------
    # Chrome CDP Actions
    # -------------------------------------------------------------------------
    def _open_chrome(self) -> None:
        profile_name = self.combo_profile.currentText()
        self._log(f"🚀 Đang khởi động Google Chrome cho Muse AI (Profile: {profile_name})...")
        threading.Thread(
            target=lambda: open_muse_chrome(profile_name=profile_name, port=MUSE_CDP_PORT),
            daemon=True,
        ).start()
        QTimer.singleShot(1500, self._check_chrome_status)

    def _close_chrome(self) -> None:
        profile_name = self.combo_profile.currentText()
        profile_dir = resolve_muse_profile_dir(profile_name)
        self._log("⏹️ Đang đóng trình duyệt Chrome...")
        kill_muse_chrome_by_profile(profile_dir)
        self._check_chrome_status()

    def _capture_session(self) -> None:
        profile_name = self.combo_profile.currentText()
        self.btn_capture_auth.setEnabled(False)
        self._log("🔑 Bắt đầu thu hoạch phiên đăng nhập Muse AI...")

        def _task():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                res = loop.run_until_complete(
                    MuseAuthManager.auto_capture_login(
                        profile_name=profile_name,
                        port=MUSE_CDP_PORT,
                        timeout_seconds=90,
                        log_callback=self._log,
                    )
                )
                if res.get("success"):
                    self._log(f"🎉 Thu hoạch phiên thành công! Lưu {res.get('cookie_count')} cookies.")
                else:
                    self._log(f"⚠️ Chưa bắt được phiên: {res.get('error')}")
            except Exception as e:
                self._log(f"❌ Lỗi thu hoạch phiên: {e}")
            finally:
                loop.close()
                QTimer.singleShot(0, self._on_capture_finished)

        threading.Thread(target=_task, daemon=True).start()

    def _on_capture_finished(self) -> None:
        self.btn_capture_auth.setEnabled(True)
        self._refresh_auth_status()

    # -------------------------------------------------------------------------
    # Prompt Editing Actions
    # -------------------------------------------------------------------------
    def _on_prompt_text_changed(self) -> None:
        lines = [line.strip() for line in self.txt_prompts.toPlainText().splitlines() if line.strip()]
        self.lbl_prompt_count.setText(f"Tổng số: {len(lines)} prompts")

    def _load_txt_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file prompt văn bản", "", "Text Files (*.txt);;All Files (*)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.txt_prompts.setPlainText(content)
                self._log(f"📂 Đã nạp prompt từ: {Path(path).name}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi đọc file", f"Không thể đọc file: {e}")

    def _load_sample_prompts(self) -> None:
        current = self.txt_prompts.toPlainText().strip()
        samples = "\n".join(SAMPLE_MUSE_PROMPTS)
        new_text = f"{current}\n{samples}" if current else samples
        self.txt_prompts.setPlainText(new_text.strip())
        self._log("💡 Đã nạp 4 prompt mẫu vào danh sách.")

    def _clear_prompts(self) -> None:
        self.txt_prompts.clear()

    # -------------------------------------------------------------------------
    # Workflow Execution
    # -------------------------------------------------------------------------
    def _set_ui_busy(self, busy: bool) -> None:
        """Khóa/mở các trường nhập liệu khi quy trình tự động đang chạy."""
        self._is_ui_busy = busy
        self.txt_prompts.setReadOnly(busy)
        self.btn_load_file.setEnabled(not busy)
        self.btn_sample.setEnabled(not busy)
        self.btn_clear.setEnabled(not busy)
        self.combo_profile.setEnabled(not busy)
        self.combo_aspect_ratio.setEnabled(not busy)
        self.combo_duration.setEnabled(not busy)
        self.chk_context_isolation.setEnabled(not busy)
        self.spin_timeout.setEnabled(not busy)
        self.spin_retries.setEnabled(not busy)
        self.btn_auto_login.setEnabled(not busy)
        self.btn_renew_session.setEnabled(not busy)
        self.btn_capture_auth.setEnabled(not busy)
        self.chk_motion_boost.setEnabled(not busy)
        self.combo_motion_level.setEnabled(not busy and self.chk_motion_boost.isChecked())
        if busy:
            self.btn_open_chrome.setEnabled(False)
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
        else:
            self._trigger_background_chrome_check()
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def _start_workflow(self) -> None:
        lines = [line.strip() for line in self.txt_prompts.toPlainText().splitlines() if line.strip()]
        if not lines:
            QMessageBox.warning(self, "Chưa nhập Prompt", "Vui lòng nhập ít nhất 1 prompt vào khung trước khi bắt đầu!")
            return

        # Prepare table
        self.table.setRowCount(0)
        self._table_rows_map.clear()

        for idx, prompt in enumerate(lines, start=1):
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            self._table_rows_map[str(idx)] = row_idx

            self.table.setItem(row_idx, 0, QTableWidgetItem(str(idx)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(prompt))

            status_item = QTableWidgetItem("⏳ Chờ xử lý")
            status_item.setForeground(QColor("#94a3b8"))
            status_item.setToolTip("Đang trong hàng đợi thực thi...")
            self.table.setItem(row_idx, 2, status_item)

            self.table.setItem(row_idx, 3, QTableWidgetItem("-"))
            self.table.setItem(row_idx, 4, QTableWidgetItem("-"))

        # Launch workflow thread
        profile_name = self.combo_profile.currentText()
        prompts_data = [{"id": i, "prompt": text} for i, text in enumerate(lines, start=1)]

        motion_boost = self.chk_motion_boost.isChecked()
        motion_level = self.combo_motion_level.currentData() or MotionLevel.ACTION
        aspect_ratio = str(self.combo_aspect_ratio.currentData() or "9:16")
        duration = int(self.combo_duration.currentData() or 6)
        context_isolation = self.chk_context_isolation.isChecked()

        self._workflow = MuseTextToVideoWorkflow(
            project_name="muse_desktop_batch",
            project_data={
                "prompts": prompts_data,
                "profile_name": profile_name,
                "timeout_seconds": self.spin_timeout.value(),
                "max_retries": self.spin_retries.value(),
                "aspect_ratio": aspect_ratio,
                "duration": duration,
                "context_isolation": context_isolation,
                "motion_boost": motion_boost,
                "motion_level": motion_level,
                "auto_smooth_60fps": self.chk_smooth_60fps.isChecked(),
            },
            parent=self,
        )

        self._workflow.log_message.connect(self._log)
        self._workflow.video_updated.connect(self._on_video_updated)
        self._workflow.automation_complete.connect(self._on_automation_complete)

        self._set_ui_busy(True)
        self._log(f"🎬 Bắt đầu quy trình Muse AI Text to Video ({len(lines)} tác vụ)...")
        self._workflow.start()

    def _stop_workflow(self) -> None:
        if self._workflow:
            self._workflow.stop()
            self._log("🛑 Đã gửi lệnh dừng tới quy trình.")
            self.btn_stop.setEnabled(False)

    @pyqtSlot(dict)
    def _on_video_updated(self, data: dict[str, Any]) -> None:
        prompt_id = str(data.get("id") or data.get("prompt_idx") or "")
        row = self._table_rows_map.get(prompt_id)
        if row is None or row >= self.table.rowCount():
            return

        status = str(data.get("status") or "").upper()
        status_item = self.table.item(row, 2)
        if not status_item:
            status_item = QTableWidgetItem()
            self.table.setItem(row, 2, status_item)

        if status == "PROCESSING":
            status_item.setText("🔄 Đang tạo...")
            status_item.setForeground(QColor("#38bdf8"))
            status_item.setToolTip("Đang gửi prompt và đợi Muse AI hoàn tất sinh video...")
        elif status == "SUCCESS":
            status_item.setText("✅ Hoàn thành")
            status_item.setForeground(QColor("#34d399"))
            status_item.setToolTip("Video đã tạo và tải về máy thành công!")

            video_file = data.get("video_file")
            if video_file:
                v_path = Path(video_file)
                self.table.setItem(row, 3, QTableWidgetItem(v_path.name))

                # Actions button widget
                action_widget = QWidget()
                act_layout = QHBoxLayout(action_widget)
                act_layout.setContentsMargins(4, 2, 4, 2)
                act_layout.setSpacing(6)

                btn_play = QPushButton("▶️ Xem")
                btn_play.setFixedHeight(24)
                btn_play.setStyleSheet("font-size: 11px; padding: 2px 8px;")
                btn_play.clicked.connect(lambda _, p=str(v_path): QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
                act_layout.addWidget(btn_play)

                btn_folder = QPushButton("📂 Thư mục")
                btn_folder.setFixedHeight(24)
                btn_folder.setStyleSheet("font-size: 11px; padding: 2px 8px;")
                btn_folder.clicked.connect(lambda _, p=str(v_path.parent): QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
                act_layout.addWidget(btn_folder)

                self.table.setCellWidget(row, 4, action_widget)
        elif status == "FAILED":
            err_msg = str(data.get("error") or data.get("reply_preview") or "Không tạo được video")
            status_item.setText("❌ Thất bại")
            status_item.setForeground(QColor("#f87171"))
            status_item.setToolTip(f"Nguyên nhân lỗi: {err_msg}")

    @pyqtSlot()
    def _on_automation_complete(self) -> None:
        self._set_ui_busy(False)
        self._log("🎉 Quy trình xử lý danh sách video Muse AI đã kết thúc!")

        # Rà soát kết quả các tác vụ
        failed_count = 0
        success_count = 0
        pending_count = 0
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 2)
            txt = it.text() if it else ""
            if "Chờ xử lý" in txt:
                it.setText("❌ Chưa xử lý")
                it.setForeground(QColor("#f87171"))
                it.setToolTip("Quy trình dừng hoặc gặp sự cố trước khi kịp xử lý tác vụ này.")
                pending_count += 1
            elif "Hoàn thành" in txt:
                success_count += 1
            elif "Thất bại" in txt:
                failed_count += 1

        if success_count > 0:
            QMessageBox.information(
                self,
                "Hoàn Tất",
                f"Đã xử lý xong danh sách video!\n\n• ✅ Thành công: {success_count}\n• ❌ Thất bại: {failed_count + pending_count}"
            )
        else:
            QMessageBox.warning(
                self,
                "Chưa Có Video Nào Được Tạo",
                "Quy trình đã kết thúc mà chưa tạo được video nào.\n\nVui lòng kiểm tra lại trạng thái Chrome CDP, phiên đăng nhập, hoặc log chi tiết ở bên dưới!"
            )
