# -*- coding: utf-8 -*-
"""
Màn hình Quản Lý Danh Sách Tài Khoản & Xoay Tua Tự Động (Accounts Manager Tab).
Phù hợp 100% với người dùng Non-tech:
- Nhập danh sách tài khoản hàng loạt theo định dạng: email|password|2fa
- Đăng nhập ngầm tự động (Playwright giải mã 2FA TOTP), nạp session vào Account Pool.
- Bảng danh sách trực quan: trạng thái sống/chết (🟢/🔴), quota, bật/tắt xoay tua, xóa tài khoản.
- Tự động kích hoạt keepalive gia hạn session.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, List

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QDesktopServices
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from branding_config import TELEGRAM_BOT_URL
from muse_auth import MuseAuthManager
from muse_service_manager import (
    MUSE2API_ACCOUNTS_FILE,
    MUSE2API_KEY,
    MuseServiceManager,
)
from muse_api_client import MuseAPIClient


_MARKDOWN_LINK_RE = re.compile(r"^\[[^\]]*\]\((https?://[^)]+)\)$", re.IGNORECASE)


def parse_account_login_line(line: str) -> tuple[str, str, str, str]:
    """Parse legacy password credentials or an email mailbox link."""
    value = line.strip()
    if not value:
        raise ValueError("Dòng tài khoản trống.")

    if "|" in value:
        parts = [part.strip() for part in value.split("|")]
    elif "\t" in value:
        parts = [part.strip() for part in value.split("\t")]
    else:
        parts = [part.strip() for part in value.split(",")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError("Cần nhập email và mật khẩu hoặc link hộp thư.")

    email = parts[0]
    second = parts[1]
    markdown_match = _MARKDOWN_LINK_RE.fullmatch(second)
    mailbox_url = markdown_match.group(1) if markdown_match else second
    if mailbox_url.lower().startswith(("https://", "http://")):
        return email, "", "", mailbox_url

    two_factor_secret = parts[2] if len(parts) >= 3 else ""
    return email, second, two_factor_secret, ""


class BatchLoginWorker(QThread):
    """Thread chạy nền xử lý đăng nhập tuần tự cho danh sách tài khoản."""

    progress_signal = pyqtSignal(int, int, str, str)  # current, total, email, message
    finished_signal = pyqtSignal(int, int)  # success_count, fail_count
    log_signal = pyqtSignal(str)

    def __init__(self, account_lines: List[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.account_lines = account_lines
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        total = len(self.account_lines)
        success_count = 0
        fail_count = 0

        self.log_signal.emit(f"🚀 Bắt đầu đăng nhập hàng loạt cho {total} tài khoản...")

        for idx, line in enumerate(self.account_lines, start=1):
            if self._is_cancelled:
                self.log_signal.emit("🛑 Người dùng đã hủy tiến trình đăng nhập.")
                break

            s = line.strip()
            if not s or s.startswith("#"):
                continue

            try:
                email, password, two_fa, mailbox_url = parse_account_login_line(s)
            except ValueError as exc:
                self.log_signal.emit(f"⚠️ Bỏ qua dòng {idx}: {exc}")
                fail_count += 1
                continue

            self.progress_signal.emit(idx, total, email, f"Đang đăng nhập ({idx}/{total})...")
            self.log_signal.emit(f"[{idx}/{total}] 🔑 Đang đăng nhập tài khoản: {email}...")

            try:
                res = asyncio.run(
                    MuseAuthManager.login_standalone(
                        email=email,
                        password=password,
                        two_factor_secret=two_fa,
                        mailbox_url=mailbox_url or None,
                        timeout_seconds=60,
                        log_callback=self.log_signal.emit,
                    )
                )

                if res.get("success"):
                    success_count += 1
                    self.log_signal.emit(f"✅ Đăng nhập thành công: {email}!")
                    # Nạp tài khoản vào backend accounts.json
                    self._save_account_to_backend(email, res)
                else:
                    fail_count += 1
                    err = res.get("error", "Lỗi không xác định")
                    self.log_signal.emit(f"❌ Đăng nhập thất bại ({email}): {err}")

            except Exception as exc:
                fail_count += 1
                self.log_signal.emit(f"❌ Ngoại lệ khi đăng nhập ({email}): {exc}")

            time.sleep(1.0)

        self.finished_signal.emit(success_count, fail_count)

    def _save_account_to_backend(self, email: str, login_res: dict) -> None:
        """Lưu hoặc cập nhật thông tin tài khoản vào backend accounts.json."""
        try:
            MUSE2API_ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            accounts = []
            if MUSE2API_ACCOUNTS_FILE.exists():
                try:
                    accounts = json.loads(MUSE2API_ACCOUNTS_FILE.read_text(encoding="utf-8"))
                    if not isinstance(accounts, list):
                        accounts = []
                except Exception:
                    accounts = []

            cookies = login_res.get("cookies", {})
            cookies_exp = login_res.get("cookies_exp", {})
            expires_at = login_res.get("expires_at", int(time.time() + 2 * 86400))
            now_ts = int(time.time())

            # Tìm xem đã có tài khoản này chưa
            found = False
            for acc in accounts:
                if acc.get("label") == email or acc.get("id") == email:
                    acc["cookies"] = cookies
                    acc["cookies_exp"] = cookies_exp
                    acc["expires_at"] = expires_at
                    acc["enabled"] = True
                    acc["ok"] = True
                    acc["synced_at"] = now_ts
                    found = True
                    break

            if not found:
                acc_id = f"acc_{int(now_ts)}_{len(accounts) + 1}"
                new_acc = {
                    "id": acc_id,
                    "label": email,
                    "cookies": cookies,
                    "cookies_exp": cookies_exp,
                    "expires_at": expires_at,
                    "enabled": True,
                    "created_at": now_ts,
                    "last_used": None,
                    "last_keepalive": None,
                    "use_count": 0,
                    "ok": True,
                    "note": f"Added via Accounts Manager on {time.strftime('%Y-%m-%d %H:%M')}",
                    "synced_at": now_ts,
                }
                accounts.append(new_acc)

            MUSE2API_ACCOUNTS_FILE.write_text(
                json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            # Đồng bộ sang DATA_GENERAL/muse_session.json để hệ sinh thái desktop nhất quán
            try:
                from runtime_paths import DATA_GENERAL_DIR
                sess_file = DATA_GENERAL_DIR / "muse_session.json"
                raw_cookies = [
                    {"name": k, "value": v, "domain": "muse.ai", "path": "/"}
                    for k, v in cookies.items()
                ]
                sess_data = {
                    "email": email,
                    "cookies": raw_cookies,
                    "updated_at": now_ts,
                    "source": "accounts_manager_login",
                }
                sess_file.write_text(json.dumps(sess_data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        except Exception as e:
            self.log_signal.emit(f"⚠️ Lỗi lưu account vào accounts.json: {e}")



class AccountQuotaWorker(QThread):
    """Thread chạy nền kiểm tra hạn mức token (Quota) cho từng tài khoản hoặc hàng loạt."""
    account_progress = pyqtSignal(str, str)  # aid, status_message
    account_finished = pyqtSignal(str, dict, bool, str)  # aid, quota_dict, success, error_message
    batch_finished = pyqtSignal(int, int)  # success_count, fail_count
    log_signal = pyqtSignal(str)

    def __init__(self, account_ids: List[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.account_ids = account_ids
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        import urllib.request
        base_url = MuseServiceManager.get_api_base_url()
        success = 0
        failed = 0
        total = len(self.account_ids)
        self.log_signal.emit(f"🔍 Bắt đầu kiểm tra token cho {total} tài khoản...")

        for idx, aid in enumerate(self.account_ids, start=1):
            if self._is_cancelled:
                self.log_signal.emit("🛑 Người dùng đã hủy tiến trình kiểm tra token.")
                break

            self.account_progress.emit(aid, "⏳ Đang đọc...")
            self.log_signal.emit(f"[{idx}/{total}] 💎 Đang kiểm tra token tài khoản: {aid}...")

            req = urllib.request.Request(
                f"{base_url}/admin/accounts/{aid}/quota",
                data=b"{}",
                headers={
                    "Authorization": f"Bearer {MUSE2API_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": "MUSE-STUDIO-Desktop/1.1",
                },
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=35) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    success += 1
                    self.account_finished.emit(aid, data, True, "")
                    self.log_signal.emit(f"✅ Tài khoản {aid}: {data.get('extra_left') or 'N/A'} (Đã dùng {data.get('weekly_used_pct', 0)}% tuần)")
            except Exception as e:
                failed += 1
                err_msg = str(e)
                self.account_finished.emit(aid, {}, False, err_msg)
                self.log_signal.emit(f"⚠️ Kiểm tra token thất bại cho {aid}: {err_msg}")

        self.batch_finished.emit(success, failed)


class AccountsManagerTab(QWidget):

    """Màn hình chính phụ trách Quản Lý Tài Khoản và Xoay Tua Đa Tài Khoản."""

    accounts_changed = pyqtSignal()  # Phát khi pool tài khoản có thay đổi

    def __init__(self, log_callback: Callable[[str], None] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_callback = log_callback
        self._login_worker: BatchLoginWorker | None = None
        self._quota_worker: AccountQuotaWorker | None = None

        self._init_ui()
        self.refresh_accounts_table()

    def _log(self, msg: str) -> None:
        if callable(self.log_callback):
            self.log_callback(msg)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        # ---------------------------------------------------------------------
        # 1. Thống Kê Tổng Quan (Info Cards Header)
        # ---------------------------------------------------------------------
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self.card_total = self._create_info_card("👥 Tổng Tài Khoản", "0", "#38bdf8")
        self.card_active = self._create_info_card("🟢 Đang Sẵn Sàng", "0", "#34d399")
        self.card_expired = self._create_info_card("🔴 Hết Hạn / Lỗi", "0", "#f87171")
        self.card_tokens = self._create_info_card("💎 Token Khả Dụng", "--", "#c084fc")

        cards_layout.addWidget(self.card_total)
        cards_layout.addWidget(self.card_active)
        cards_layout.addWidget(self.card_expired)
        cards_layout.addWidget(self.card_tokens)
        cards_layout.addStretch()

        # Nút nạp lại, check token và gia hạn nhanh
        self.btn_refresh = QPushButton("🔄 Tải Lại")
        self.btn_refresh.setFixedHeight(38)
        self.btn_refresh.setStyleSheet("font-weight: 600; padding: 0 14px;")
        self.btn_refresh.clicked.connect(self.refresh_accounts_table)
        cards_layout.addWidget(self.btn_refresh)

        self.btn_check_all_quota = QPushButton("💎 Check Toàn Bộ Token")
        self.btn_check_all_quota.setFixedHeight(38)
        self.btn_check_all_quota.setStyleSheet("font-weight: 700; color: #c084fc; padding: 0 14px;")
        self.btn_check_all_quota.setToolTip("Quét và kiểm tra hạn mức token của tất cả tài khoản trong hệ thống")
        self.btn_check_all_quota.clicked.connect(self._do_check_all_quota)
        cards_layout.addWidget(self.btn_check_all_quota)

        self.btn_keepalive_all = QPushButton("⚡ Gia Hạn Tất Cả")
        self.btn_keepalive_all.setFixedHeight(38)
        self.btn_keepalive_all.setStyleSheet("font-weight: 700; color: #38bdf8; padding: 0 14px;")
        self.btn_keepalive_all.setToolTip("Gửi yêu cầu đánh thức Cloud VM và gia hạn cookie cho toàn bộ tài khoản")
        self.btn_keepalive_all.clicked.connect(self._do_keepalive_all)
        cards_layout.addWidget(self.btn_keepalive_all)

        main_layout.addLayout(cards_layout)

        # ---------------------------------------------------------------------
        # 2. Main Content Splitter (Trái: Nhập hàng loạt | Phải: Bảng danh sách)
        # ---------------------------------------------------------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        # --- LEFT PANEL: Nhập tài khoản hàng loạt ---
        left_box = QGroupBox("📥 NHẬP DANH SÁCH TÀI KHOẢN (BATCH IMPORT)")
        left_box.setMinimumWidth(300)
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(12, 14, 12, 12)
        left_layout.setSpacing(8)

        def _open_bot_store():
            try:
                import webbrowser
                if not QDesktopServices.openUrl(QUrl(TELEGRAM_BOT_URL)):
                    webbrowser.open(TELEGRAM_BOT_URL)
            except Exception:
                import webbrowser
                webbrowser.open(TELEGRAM_BOT_URL)

        # Nút hỗ trợ tài khoản (chỉ hoạt động khi đã cấu hình URL)
        btn_buy_fast = QPushButton("🛒 Hỗ trợ tài khoản")
        btn_buy_fast.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_buy_fast.setFixedHeight(32)
        btn_buy_fast.setStyleSheet(
            "QPushButton { background: #3b0764; color: #f3e8ff; border: 1px solid #7e22ce; "
            "border-radius: 6px; font-weight: 700; font-size: 11px; } "
            "QPushButton:hover { background: #581c87; border-color: #a855f7; color: #ffffff; }"
        )
        btn_buy_fast.setToolTip("Mở trang hỗ trợ tài khoản đã cấu hình")
        btn_buy_fast.setEnabled(bool(TELEGRAM_BOT_URL))
        btn_buy_fast.clicked.connect(_open_bot_store)
        left_layout.addWidget(btn_buy_fast)

        # Hướng dẫn nhanh cho người dùng non-tech
        lbl_hint = QLabel(
            "💡 <b>Dạng 1:</b> <code>email | mật_khẩu | mã_2fa</code><br>"
            "💡 <b>Dạng 2:</b> <code>email | link_hộp_thư</code>"
        )
        lbl_hint.setStyleSheet("color: #94a3b8; font-size: 11px;")
        left_layout.addWidget(lbl_hint)

        # Text Editor
        self.txt_accounts_input = QPlainTextEdit()
        self.txt_accounts_input.setPlaceholderText(
            "Dán danh sách tài khoản tại đây, mỗi dòng một tài khoản:\n\n"
            "user1@example.com|Password123|JBSWY3DPEHPK3PXP\n"
            "user2@tuan89.site|https://tuan89.site/mail/?email=user2%40tuan89.site\n"
        )
        self.txt_accounts_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.txt_accounts_input.setFont(font)
        left_layout.addWidget(self.txt_accounts_input)

        # Toolbar dưới ô text
        tb_layout = QHBoxLayout()
        self.btn_load_txt = QPushButton("📂 Nạp File .TXT")
        self.btn_load_txt.setFixedHeight(30)
        self.btn_load_txt.clicked.connect(self._load_accounts_from_file)
        tb_layout.addWidget(self.btn_load_txt)

        self.btn_clear_input = QPushButton("🧹 Xóa Trắng")
        self.btn_clear_input.setFixedHeight(30)
        self.btn_clear_input.clicked.connect(self.txt_accounts_input.clear)
        tb_layout.addWidget(self.btn_clear_input)
        left_layout.addLayout(tb_layout)

        # Thanh tiến độ đăng nhập
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #334155; border-radius: 4px; text-align: center; font-size: 10px; background: #0f172a; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8); border-radius: 3px; }"
        )
        left_layout.addWidget(self.progress_bar)

        self.lbl_progress_status = QLabel("")
        self.lbl_progress_status.setVisible(False)
        self.lbl_progress_status.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
        left_layout.addWidget(self.lbl_progress_status)

        # Nút bắt đầu đăng nhập
        self.btn_start_login = QPushButton("🚀 ĐĂNG NHẬP & KÍCH HOẠT HÀNG LOẠT")
        self.btn_start_login.setFixedHeight(42)
        self.btn_start_login.setProperty("primary", True)
        self.btn_start_login.setStyleSheet("font-size: 13px; font-weight: 800;")
        self.btn_start_login.clicked.connect(self._start_batch_login)
        left_layout.addWidget(self.btn_start_login)

        splitter.addWidget(left_box)

        # --- RIGHT PANEL: Bảng danh sách tài khoản hiện có ---
        right_box = QGroupBox("📋 DANH SÁCH TÀI KHOẢN TRONG HỆ THỐNG (ACCOUNT POOL)")
        right_box.setMinimumWidth(380)
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(12, 14, 12, 12)
        right_layout.setSpacing(8)

        self.table_accounts = QTableWidget(0, 7)
        self.table_accounts.setHorizontalHeaderLabels([
            "#", "Tài Khoản / Email", "Trạng Thái", "Token / Quota", "Hạn Phiên", "Đã Tạo", "Thao Tác"
        ])
        self.table_accounts.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_accounts.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_accounts.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_accounts.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_accounts.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_accounts.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table_accounts.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table_accounts.setColumnWidth(6, 185)
        self.table_accounts.verticalHeader().setVisible(False)
        self.table_accounts.verticalHeader().setDefaultSectionSize(44)
        self.table_accounts.setAlternatingRowColors(True)
        self.table_accounts.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_accounts.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table_accounts.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        right_layout.addWidget(self.table_accounts)

        # Nút thao tác nhanh dưới bảng
        table_actions = QHBoxLayout()
        self.btn_delete_expired = QPushButton("🧹 Dọn Dẹp Tài Khoản Hỏng")
        self.btn_delete_expired.setFixedHeight(30)
        self.btn_delete_expired.setStyleSheet("font-size: 11px;")
        self.btn_delete_expired.clicked.connect(self._delete_failed_accounts)
        table_actions.addWidget(self.btn_delete_expired)
        table_actions.addStretch()

        right_layout.addLayout(table_actions)
        splitter.addWidget(right_box)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        main_layout.addWidget(splitter, 1)

    def _create_info_card(self, title: str, default_val: str, color_hex: str) -> QFrame:
        """Tạo thẻ thống kê thông tin nhanh trực quan, chống clipping số."""
        card = QFrame()
        card.setMinimumHeight(66)
        card.setMinimumWidth(140)
        card.setStyleSheet(
            f"QFrame {{ background: #131b2e; border: 1px solid #1e293b; border-radius: 8px; padding: 4px 10px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        lbl_v = QLabel(default_val)
        lbl_v.setStyleSheet(f"color: {color_hex}; font-size: 20px; font-weight: 800; line-height: 1;")
        layout.addWidget(lbl_t)
        layout.addWidget(lbl_v)
        card.value_label = lbl_v  # type: ignore
        return card

    # =========================================================================
    # QUẢN LÝ DỮ LIỆU & BẢNG TÀI KHOẢN
    # =========================================================================

    def refresh_accounts_table(self) -> None:
        """Đọc danh sách accounts từ accounts.json và hiển thị lên bảng."""
        accounts = []
        if MUSE2API_ACCOUNTS_FILE.exists():
            try:
                accounts = json.loads(MUSE2API_ACCOUNTS_FILE.read_text(encoding="utf-8"))
            except Exception:
                accounts = []

        total_cnt = len(accounts)
        active_cnt = 0
        expired_cnt = 0

        self.table_accounts.setRowCount(total_cnt)
        now_ts = int(time.time())

        for idx, acc in enumerate(accounts):
            aid = str(acc.get("id", ""))
            label = str(acc.get("label", aid))
            is_enabled = acc.get("enabled", True)
            is_ok = acc.get("ok", True)
            exp_at = acc.get("expires_at", 0)
            use_count = acc.get("use_count", 0)

            # Đánh giá trạng thái
            if not is_enabled:
                status_text = "⏸️ Đã tắt"
                status_color = "#94a3b8"
            elif is_ok and (exp_at == 0 or exp_at > now_ts):
                status_text = "🟢 Sẵn sàng"
                status_color = "#34d399"
                active_cnt += 1
            else:
                status_text = "🔴 Cần đăng nhập lại"
                status_color = "#f87171"
                expired_cnt += 1

            # Hạn dùng
            if exp_at > 0:
                hours_left = max(0, int((exp_at - now_ts) / 3600))
                exp_text = f"Còn ~{hours_left}h"
            else:
                exp_text = "Không xác định"

            # 1. STT
            it_idx = QTableWidgetItem(str(idx + 1))
            it_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_accounts.setItem(idx, 0, it_idx)

            # 2. Label/Email
            it_label = QTableWidgetItem(label)
            it_label.setToolTip(f"ID: {aid}\n{acc.get('note', '')}")
            self.table_accounts.setItem(idx, 1, it_label)

            # 3. Trạng thái
            it_status = QTableWidgetItem(status_text)
            it_status.setForeground(QColor(status_color))
            it_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_status.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.table_accounts.setItem(idx, 2, it_status)

            # 4. Token / Quota
            quota = acc.get("quota")
            if isinstance(quota, dict) and quota.get("found"):
                extra_left = quota.get("extra_left") or ""
                weekly_used = quota.get("weekly_used_pct", 0)
                weekly_left = max(0, 100 - weekly_used)
                plan = quota.get("plan", "Free plan")
                reset_date = quota.get("weekly_reset", "")
                capacity_status = acc.get("media_quota_status") or "unknown"

                token_text = (
                    f"Tuần còn {weekly_left}% · "
                    f"Bổ sung còn {extra_left or '0'}"
                )

                if capacity_status == "eligible":
                    token_color = "#34d399"  # Xanh lá
                elif capacity_status == "exhausted":
                    token_color = "#f87171"  # Đỏ
                else:
                    token_color = "#94a3b8"  # Chưa xác định / stale

                chk_time = time.strftime('%H:%M %d/%m', time.localtime(quota.get('checked_at', now_ts)))
                tooltip_txt = (
                    f"Gói dịch vụ: {plan}\n"
                    f"Token bổ sung: {extra_left or 'Không có'}\n"
                    f"Hạn mức tuần: Đã dùng {weekly_used}% (Còn {weekly_left}%)\n"
                    f"Reset tuần vào: {reset_date}\n"
                    f"Kiểm tra lúc: {chk_time}"
                )
            else:
                token_text = "Chưa kiểm tra"
                token_color = "#64748b"
                tooltip_txt = "Bấm nút [Check] để truy vấn số dư token thực tế từ hệ thống"

            it_token = QTableWidgetItem(token_text)
            it_token.setForeground(QColor(token_color))
            it_token.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_token.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            it_token.setToolTip(tooltip_txt)
            self.table_accounts.setItem(idx, 3, it_token)

            # 5. Hạn phiên
            it_exp = QTableWidgetItem(exp_text)
            it_exp.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_accounts.setItem(idx, 4, it_exp)

            # 6. Đã tạo
            it_cnt = QTableWidgetItem(f"{use_count} video")
            it_cnt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_accounts.setItem(idx, 5, it_cnt)

            # 7. Thao tác (Widget)
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 4, 4, 4)
            action_layout.setSpacing(4)
            action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            btn_check = QPushButton("Check")
            btn_check.setFixedHeight(28)
            btn_check.setMinimumWidth(48)
            btn_check.setStyleSheet(
                "QPushButton { background: #1e1b4b; color: #c084fc; border: 1px solid #4338ca; border-radius: 4px; padding: 0 4px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #312e81; color: #e9d5ff; border-color: #6366f1; }"
            )
            btn_check.setToolTip("Kiểm tra token còn lại của tài khoản này ngay lập tức")
            btn_check.clicked.connect(lambda _, a=aid: self._check_single_account_quota(a))
            action_layout.addWidget(btn_check)

            btn_toggle = QPushButton("Tắt" if is_enabled else "Bật")
            btn_toggle.setFixedHeight(28)
            btn_toggle.setMinimumWidth(46)
            if is_enabled:
                btn_toggle.setStyleSheet(
                    "QPushButton { background: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 4px; padding: 0 4px; font-size: 11px; font-weight: 600; }"
                    "QPushButton:hover { background: #334155; color: #ffffff; border-color: #475569; }"
                )
            else:
                btn_toggle.setStyleSheet(
                    "QPushButton { background: #064e3b; color: #34d399; border: 1px solid #059669; border-radius: 4px; padding: 0 4px; font-size: 11px; font-weight: 700; }"
                    "QPushButton:hover { background: #047857; color: #ffffff; }"
                )
            btn_toggle.setToolTip("Tạm tắt hoặc kích hoạt lại tài khoản này trong xoay tua")
            btn_toggle.clicked.connect(lambda _, a=aid, cur=is_enabled: self._toggle_account(a, not cur))
            action_layout.addWidget(btn_toggle)

            btn_del = QPushButton("Xóa")
            btn_del.setFixedHeight(28)
            btn_del.setMinimumWidth(44)
            btn_del.setStyleSheet(
                "QPushButton { background: #450a0a; color: #fca5a5; border: 1px solid #7f1d1d; border-radius: 4px; padding: 0 4px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #7f1d1d; color: #ffffff; border-color: #dc2626; }"
            )
            btn_del.setToolTip("Xóa tài khoản này khỏi hệ thống")
            btn_del.clicked.connect(lambda _, a=aid: self._delete_account(a))
            action_layout.addWidget(btn_del)

            self.table_accounts.setCellWidget(idx, 6, action_widget)

        # Cập nhật số liệu thẻ Header
        self.card_total.value_label.setText(str(total_cnt))  # type: ignore
        self.card_active.value_label.setText(str(active_cnt))  # type: ignore
        self.card_expired.value_label.setText(str(expired_cnt))  # type: ignore

        # Thống kê tổng token / quota
        checked_cnt = sum(1 for a in accounts if isinstance(a.get("quota"), dict) and a.get("quota", {}).get("found"))
        self.card_tokens.value_label.setText(f"{checked_cnt}/{total_cnt} TK" if total_cnt > 0 else "--")  # type: ignore

        # Bắn signal thông báo tài khoản thay đổi
        self.accounts_changed.emit()

    def _toggle_account(self, aid: str, new_state: bool) -> None:
        """Bật hoặc tắt trạng thái tham gia xoay tua của 1 tài khoản."""
        try:
            if MUSE2API_ACCOUNTS_FILE.exists():
                accounts = json.loads(MUSE2API_ACCOUNTS_FILE.read_text(encoding="utf-8"))
                for acc in accounts:
                    if acc.get("id") == aid:
                        acc["enabled"] = new_state
                        break
                MUSE2API_ACCOUNTS_FILE.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8")
                self.refresh_accounts_table()
        except Exception as e:
            self._log(f"⚠️ Lỗi thay đổi trạng thái tài khoản {aid}: {e}")

    def _delete_account(self, aid: str) -> None:
        """Xóa 1 tài khoản khỏi danh sách."""
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Bạn có chắc muốn xóa tài khoản này khỏi danh sách xoay tua?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if MUSE2API_ACCOUNTS_FILE.exists():
                    accounts = json.loads(MUSE2API_ACCOUNTS_FILE.read_text(encoding="utf-8"))
                    accounts = [a for a in accounts if a.get("id") != aid]
                    MUSE2API_ACCOUNTS_FILE.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8")
                    self.refresh_accounts_table()
                    self._log(f"🗑️ Đã xóa tài khoản {aid}.")
            except Exception as e:
                self._log(f"⚠️ Lỗi xóa tài khoản {aid}: {e}")

    def _delete_failed_accounts(self) -> None:
        """Dọn dẹp nhanh tất cả các tài khoản bị hỏng hoặc hết hạn."""
        now_ts = int(time.time())
        try:
            if MUSE2API_ACCOUNTS_FILE.exists():
                accounts = json.loads(MUSE2API_ACCOUNTS_FILE.read_text(encoding="utf-8"))
                valid = [a for a in accounts if a.get("ok", True) and (a.get("expires_at", 0) > now_ts or a.get("expires_at", 0) == 0)]
                deleted_cnt = len(accounts) - len(valid)
                if deleted_cnt > 0:
                    MUSE2API_ACCOUNTS_FILE.write_text(json.dumps(valid, ensure_ascii=False, indent=2), encoding="utf-8")
                    self.refresh_accounts_table()
                    QMessageBox.information(self, "Thông báo", f"Đã dọn dẹp {deleted_cnt} tài khoản không hợp lệ!")
                else:
                    QMessageBox.information(self, "Thông báo", "Không có tài khoản lỗi nào cần dọn dẹp.")
        except Exception as e:
            self._log(f"⚠️ Lỗi dọn tài khoản hỏng: {e}")

    def _do_keepalive_all(self) -> None:
        """Gia hạn session và đánh thức VM cho toàn bộ tài khoản."""
        self._log("⚡ Đang gửi yêu cầu gia hạn và đánh thức toàn bộ tài khoản...")
        client = MuseAPIClient(
            base_url=MuseServiceManager.get_api_base_url(),
            api_key=MUSE2API_KEY,
            log_callback=self._log,
        )
        try:
            def _task():
                res = client.post("/admin/accounts/keepalive", {})
                self._log(f"🎉 Kết quả gia hạn: {res}")
                # Hẹn giờ chạy trên Main GUI Thread để refresh lại bảng tuyệt đối an toàn
                QTimer.singleShot(2000, self.refresh_accounts_table)
            threading.Thread(target=_task, daemon=True).start()
        except Exception as e:
            self._log(f"⚠️ Lỗi gọi keepalive: {e}")


    # =========================================================================
    # KIỂM TRA HẠN MỨC TOKEN (QUOTA)
    # =========================================================================

    def _check_single_account_quota(self, aid: str) -> None:
        """Kiểm tra token còn lại của 1 tài khoản cụ thể."""
        # Cập nhật ô hiển thị thành trạng thái đang kiểm tra
        for r in range(self.table_accounts.rowCount()):
            it_label = self.table_accounts.item(r, 1)
            if it_label and aid in it_label.toolTip():
                it_tok = self.table_accounts.item(r, 3)
                if it_tok:
                    it_tok.setText("⏳ Đang check...")
                    it_tok.setForeground(QColor("#38bdf8"))
                break

        self._log(f"🔍 Bắt đầu kiểm tra token tài khoản: {aid}...")
        self._quota_worker = AccountQuotaWorker([aid])
        self._quota_worker.log_signal.connect(self._log)
        self._quota_worker.account_finished.connect(self._on_single_quota_finished)
        self._quota_worker.start()

    def _on_single_quota_finished(self, aid: str, quota_data: dict, ok: bool, err_msg: str) -> None:
        if ok:
            extra = quota_data.get("extra_left") or "N/A"
            used = quota_data.get("weekly_used_pct", 0)
            self._log(f"🎉 Đã kiểm tra xong tài khoản {aid}: Token thêm = {extra}, Tuần đã dùng = {used}%.")
        else:
            self._log(f"⚠️ Kiểm tra token tài khoản {aid} thất bại: {err_msg}")
        self.refresh_accounts_table()

    def _do_check_all_quota(self) -> None:
        """Kiểm tra token hàng loạt cho toàn bộ tài khoản đang bật."""
        accounts = []
        if MUSE2API_ACCOUNTS_FILE.exists():
            try:
                accounts = json.loads(MUSE2API_ACCOUNTS_FILE.read_text(encoding="utf-8"))
            except Exception:
                accounts = []

        active_aids = [str(a.get("id")) for a in accounts if a.get("enabled", True) and a.get("id")]
        if not active_aids:
            QMessageBox.information(self, "Thông báo", "Không có tài khoản nào đang hoạt động để kiểm tra token.")
            return

        self.btn_check_all_quota.setEnabled(False)
        self.btn_check_all_quota.setText("⏳ Đang check...")

        self._quota_worker = AccountQuotaWorker(active_aids)
        self._quota_worker.log_signal.connect(self._log)
        self._quota_worker.account_progress.connect(self._on_batch_quota_progress)
        self._quota_worker.batch_finished.connect(self._on_batch_quota_finished)
        self._quota_worker.start()

    def _on_batch_quota_progress(self, aid: str, msg: str) -> None:
        for r in range(self.table_accounts.rowCount()):
            it_label = self.table_accounts.item(r, 1)
            if it_label and aid in it_label.toolTip():
                it_tok = self.table_accounts.item(r, 3)
                if it_tok:
                    it_tok.setText(msg)
                    it_tok.setForeground(QColor("#38bdf8"))
                break

    def _on_batch_quota_finished(self, success_cnt: int, fail_cnt: int) -> None:
        self.btn_check_all_quota.setEnabled(True)
        self.btn_check_all_quota.setText("💎 Check Toàn Bộ Token")
        self.refresh_accounts_table()
        QMessageBox.information(
            self,
            "Kết quả kiểm tra Token",
            f"Đã hoàn thành kiểm tra Token cho toàn bộ tài khoản!\n\n"
            f"✅ Thành công: {success_cnt} tài khoản\n"
            f"⚠️ Thất bại/lỗi: {fail_cnt} tài khoản\n\n"
            f"Dữ liệu token và hạn mức đã được cập nhật vào bảng.",
        )

    def _load_accounts_from_file(self) -> None:
        """Nạp danh sách tài khoản từ file TXT."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn File Danh Sách Tài Khoản (.txt)", "", "Text Files (*.txt);;All Files (*.*)"
        )
        if not file_path:
            return
        try:
            content = Path(file_path).read_text(encoding="utf-8")
            self.txt_accounts_input.setPlainText(content)
            self._log(f"📂 Đã nạp danh sách tài khoản từ: {Path(file_path).name}")
        except Exception as e:
            QMessageBox.warning(self, "Lỗi đọc file", f"Không thể đọc file: {e}")

    # =========================================================================
    # TIẾN TRÌNH ĐĂNG NHẬP HÀNG LOẠT
    # =========================================================================

    def _start_batch_login(self) -> None:
        """Bắt đầu tiến trình đăng nhập hàng loạt."""
        raw_text = self.txt_accounts_input.toPlainText()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip() and not line.strip().startswith("#")]

        if not lines:
            QMessageBox.warning(
                self,
                "Chưa có tài khoản",
                "Vui lòng dán danh sách tài khoản vào ô nhập hoặc bấm 'Nạp File .TXT' trước khi bắt đầu!",
            )
            return

        self.btn_start_login.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(lines))
        self.progress_bar.setValue(0)
        self.lbl_progress_status.setVisible(True)
        self.lbl_progress_status.setText("Đang khởi động tiến trình đăng nhập tự động...")

        self._login_worker = BatchLoginWorker(lines)
        self._login_worker.log_signal.connect(self._log)
        self._login_worker.progress_signal.connect(self._on_login_progress)
        self._login_worker.finished_signal.connect(self._on_login_finished)
        self._login_worker.start()

    def _on_login_progress(self, current: int, total: int, email: str, msg: str) -> None:
        self.progress_bar.setValue(current)
        self.lbl_progress_status.setText(f"[{current}/{total}] {email} - {msg}")

    def _on_login_finished(self, success_count: int, fail_count: int) -> None:
        self.btn_start_login.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_progress_status.setText(f"🎉 Hoàn tất! Thành công: {success_count} | Thất bại: {fail_count}")

        # Tải lại bảng tài khoản
        self.refresh_accounts_table()

        # Đảm bảo backend được khởi động hoặc nạp lại tài khoản
        MuseServiceManager.start_service(timeout=15, log_callback=self._log)

        QMessageBox.information(
            self,
            "Kết Quả Đăng Nhập",
            f"Đã hoàn thành đăng nhập hàng loạt!\n\n"
            f"✅ Thành công: {success_count} tài khoản\n"
            f"❌ Thất bại: {fail_count} tài khoản\n\n"
            f"Các tài khoản thành công đã được tự động nạp vào hệ thống xoay tua.",
        )
