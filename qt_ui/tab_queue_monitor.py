# -*- coding: utf-8 -*-
"""
Màn hình Giám Sát Tiến Độ & Hàng Đợi (Queue & Progress Monitor Tab).
Thiết kế tối ưu cho người dùng Non-tech:
- Thanh tiến độ tổng quan lớn (Overall Progress Bar).
- Bảng tiến độ full-screen theo dõi từng video thời gian thực.
- Hiển thị rõ tài khoản nào trong pool đang thực hiện task nào.
- 1-Click xem video ngay sau khi hoàn thành.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from runtime_paths import MUSE_DOWNLOADS_DIR


class QueueMonitorTab(QWidget):
    """Màn hình giám sát tiến độ render video thời gian thực."""

    stop_requested = pyqtSignal()
    open_gallery_requested = pyqtSignal()

    def __init__(self, log_callback: Callable[[str], None] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_callback = log_callback
        self._task_rows: Dict[str, int] = {}  # id/idx -> row index
        self._total_tasks = 0
        self._completed_tasks = 0
        self._failed_tasks = 0
        self._current_download_dir = MUSE_DOWNLOADS_DIR

        self._init_ui()

    def _log(self, msg: str) -> None:
        if callable(self.log_callback):
            self.log_callback(msg)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        # ---------------------------------------------------------------------
        # 1. Header Cards & Progress Bar Tổng Thể
        # ---------------------------------------------------------------------
        top_group = QGroupBox("📊 TỔNG QUAN TIẾN ĐỘ HÀNG ĐỢI")
        top_layout = QVBoxLayout(top_group)
        top_layout.setContentsMargins(12, 12, 12, 12)
        top_layout.setSpacing(10)

        # Hàng thẻ thống kê
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        self.card_total = self._create_card("📋 Tổng Tác Vụ", "0", "#38bdf8")
        self.card_processing = self._create_card("🔄 Đang Xử Lý", "0", "#facc15")
        self.card_success = self._create_card("✅ Hoàn Thành", "0", "#34d399")
        self.card_failed = self._create_card("❌ Thất Bại", "0", "#f87171")

        cards_row.addWidget(self.card_total)
        cards_row.addWidget(self.card_processing)
        cards_row.addWidget(self.card_success)
        cards_row.addWidget(self.card_failed)
        cards_row.addStretch()

        # Nút điều khiển nhanh
        self.btn_stop_queue = QPushButton("🛑 Dừng Khẩn Cấp")
        self.btn_stop_queue.setFixedHeight(38)
        self.btn_stop_queue.setEnabled(False)
        self.btn_stop_queue.setProperty("danger", True)
        self.btn_stop_queue.setStyleSheet("font-weight: 700; background: #dc2626; color: #ffffff; padding: 0 14px;")
        self.btn_stop_queue.clicked.connect(self._on_stop_clicked)
        cards_row.addWidget(self.btn_stop_queue)

        self.btn_open_folder = QPushButton("📂 Mở Thư Mục")
        self.btn_open_folder.setFixedHeight(38)
        self.btn_open_folder.setStyleSheet("font-weight: 600; padding: 0 14px;")
        self.btn_open_folder.clicked.connect(self._open_downloads_folder)
        cards_row.addWidget(self.btn_open_folder)

        self.btn_clear_table = QPushButton("🧹 Dọn Bảng")
        self.btn_clear_table.setFixedHeight(38)
        self.btn_clear_table.setStyleSheet("font-size: 11px; padding: 0 12px;")
        self.btn_clear_table.clicked.connect(self.clear_queue)
        cards_row.addWidget(self.btn_clear_table)

        top_layout.addLayout(cards_row)

        # Progress bar tổng thể
        pb_row = QHBoxLayout()
        self.lbl_overall_status = QLabel("Trạng thái: Sẵn sàng nhận tác vụ mới...")
        self.lbl_overall_status.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        pb_row.addWidget(self.lbl_overall_status)
        pb_row.addStretch()

        self.lbl_overall_percent = QLabel("0%")
        self.lbl_overall_percent.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 800;")
        pb_row.addWidget(self.lbl_overall_percent)
        top_layout.addLayout(pb_row)

        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setFixedHeight(12)
        self.overall_progress_bar.setRange(0, 100)
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setTextVisible(False)
        self.overall_progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #334155; border-radius: 4px; background: #0f172a; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #34d399); border-radius: 3px; }"
        )
        top_layout.addWidget(self.overall_progress_bar)

        main_layout.addWidget(top_group)

        # ---------------------------------------------------------------------
        # 2. Bảng Tiến Độ Hàng Đợi Thời Gian Thực (Full Width)
        # ---------------------------------------------------------------------
        table_group = QGroupBox("📋 CHI TIẾT TỪNG TÁC VỤ (HÀNG ĐỢI THỜI GIAN THỰC)")
        table_layout = QVBoxLayout(table_group)
        table_layout.setContentsMargins(10, 14, 10, 10)
        table_layout.setSpacing(8)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "#", "Nội Dung Prompt", "Tài Khoản Phụ Trách", "Tiến Độ", "Trạng Thái", "File Video Kết Quả", "Thao Tác"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        table_layout.addWidget(self.table)

        main_layout.addWidget(table_group, 1)

    def _create_card(self, title: str, val: str, color_hex: str) -> QFrame:
        """Tạo thẻ thống kê thông số hàng đợi trực quan, chống clipping số."""
        card = QFrame()
        card.setMinimumHeight(66)
        card.setMinimumWidth(130)
        card.setStyleSheet(
            "QFrame { background: #131b2e; border: 1px solid #1e293b; border-radius: 8px; padding: 4px 10px; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        lbl_v = QLabel(val)
        lbl_v.setStyleSheet(f"color: {color_hex}; font-size: 20px; font-weight: 800; line-height: 1;")
        layout.addWidget(lbl_t)
        layout.addWidget(lbl_v)
        card.value_label = lbl_v  # type: ignore
        return card

    # =========================================================================
    # QUẢN LÝ TIẾN ĐỘ & DỮ LIỆU BẢNG
    # =========================================================================

    def initialize_queue(self, prompts: List[str], download_dir: str = "") -> None:
        """Khởi tạo bảng hàng đợi với danh sách prompts mới."""
        if download_dir:
            self._current_download_dir = Path(download_dir)

        self._task_rows.clear()
        self._total_tasks = len(prompts)
        self._completed_tasks = 0
        self._failed_tasks = 0

        self.table.setRowCount(self._total_tasks)
        self.card_total.value_label.setText(str(self._total_tasks))  # type: ignore
        self.card_processing.value_label.setText("0")  # type: ignore
        self.card_success.value_label.setText("0")  # type: ignore
        self.card_failed.value_label.setText("0")  # type: ignore

        self.overall_progress_bar.setValue(0)
        self.lbl_overall_percent.setText("0%")
        self.lbl_overall_status.setText(f"Đang chuẩn bị tạo hàng loạt {self._total_tasks} video...")
        self.btn_stop_queue.setEnabled(True)

        for idx, prompt_text in enumerate(prompts):
            prompt_id_str = str(idx + 1)
            self._task_rows[prompt_id_str] = idx
            self._task_rows[f"prompt_{prompt_id_str}"] = idx
            self._task_rows[f"#{prompt_id_str}"] = idx

            # 0. STT
            it_idx = QTableWidgetItem(f"#{idx + 1}")
            it_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_idx.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.table.setItem(idx, 0, it_idx)

            # 1. Prompt
            it_prompt = QTableWidgetItem(prompt_text)
            it_prompt.setToolTip(prompt_text)
            self.table.setItem(idx, 1, it_prompt)

            # 2. Account
            it_acc = QTableWidgetItem("🔄 Đang xoay tua...")
            it_acc.setForeground(QColor("#94a3b8"))
            it_acc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(idx, 2, it_acc)

            # 3. Tiến độ (Widget)
            pb_widget = QWidget()
            pb_layout = QVBoxLayout(pb_widget)
            pb_layout.setContentsMargins(6, 6, 6, 6)
            pb = QProgressBar()
            pb.setFixedHeight(14)
            pb.setRange(0, 100)
            pb.setValue(0)
            pb.setTextVisible(True)
            pb.setFormat("%p%")
            pb.setStyleSheet(
                "QProgressBar { border: 1px solid #334155; border-radius: 3px; text-align: center; font-size: 9px; }"
                "QProgressBar::chunk { background: #0284c7; }"
            )
            pb_layout.addWidget(pb)
            self.table.setCellWidget(idx, 3, pb_widget)

            # 4. Trạng thái
            it_status = QTableWidgetItem("⏳ Chờ xử lý")
            it_status.setForeground(QColor("#94a3b8"))
            it_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_status.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.table.setItem(idx, 4, it_status)

            # 5. File video
            it_file = QTableWidgetItem("---")
            it_file.setForeground(QColor("#64748b"))
            it_file.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(idx, 5, it_file)

            # 6. Thao tác (Widget)
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(6)
            action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            btn_play = QPushButton("▶️ Xem")
            btn_play.setFixedHeight(24)
            btn_play.setEnabled(False)
            btn_play.setStyleSheet("font-size: 11px; padding: 0 8px;")
            action_layout.addWidget(btn_play)

            self.table.setCellWidget(idx, 6, action_widget)

    def on_video_updated(self, data: Dict[str, Any]) -> None:
        """Cập nhật tiến độ hoặc kết quả của 1 task từ Workflow."""
        prompt_idx = data.get("prompt_idx")
        row = None
        if prompt_idx is not None:
            try:
                zero_based = int(prompt_idx)
                if 0 <= zero_based < self.table.rowCount():
                    row = zero_based
            except (TypeError, ValueError):
                pass
        raw_id = str(data.get("id", "") if prompt_idx is None else prompt_idx)
        if row is None and prompt_idx is None:
            row = self._task_rows.get(raw_id)
        if row is None or row < 0 or row >= self.table.rowCount():
            try:
                p_num = int(raw_id)
                if 1 <= p_num <= self.table.rowCount():
                    row = p_num - 1
                elif 0 <= p_num < self.table.rowCount():
                    row = p_num
                else:
                    return
            except Exception:
                return

        status = str(data.get("status", "")).upper()
        progress = int(data.get("progress", 0))
        account_name = str(data.get("account", data.get("account_id", "")))
        video_file = str(data.get("video_file", ""))
        elapsed = data.get("elapsed", "")

        # Cập nhật Account nếu có
        if account_name:
            it_acc = self.table.item(row, 2)
            if it_acc:
                it_acc.setText(f"👤 {account_name}")
                it_acc.setForeground(QColor("#38bdf8"))

        # Cập nhật ProgressBar của task
        pb_widget = self.table.cellWidget(row, 3)
        if pb_widget:
            pb = pb_widget.findChild(QProgressBar)
            if pb:
                pb.setValue(progress)
                if status == "SUCCESS":
                    pb.setStyleSheet("QProgressBar::chunk { background: #059669; }")
                elif status == "FAILED":
                    pb.setStyleSheet("QProgressBar::chunk { background: #dc2626; }")

        # Cập nhật Trạng thái
        it_status = self.table.item(row, 4)
        if it_status:
            if status in ("PROCESSING", "RENDER"):
                it_status.setText(f"🔄 Render ({progress}%)")
                it_status.setForeground(QColor("#facc15"))
            elif status == "SMOOTHING":
                it_status.setText("⚡ Làm mượt 60fps...")
                it_status.setForeground(QColor("#a78bfa"))
            elif status == "SUCCESS":
                info_parts = []
                dur_val = data.get("duration")
                if dur_val:
                    info_parts.append(f"{dur_val}s")
                if elapsed:
                    info_parts.append(f"{elapsed}s render")
                suffix = f" ({' • '.join(info_parts)})" if info_parts else ""
                it_status.setText(f"✅ Hoàn thành{suffix}")
                it_status.setForeground(QColor("#34d399"))
            elif status == "FAILED":
                err = str(data.get("error", "Lỗi sinh video"))
                it_status.setText("❌ Thất bại")
                it_status.setForeground(QColor("#f87171"))
                it_status.setToolTip(err)

        # Cập nhật File Video
        if video_file and Path(video_file).is_file():
            f_path = Path(video_file)
            size_mb = f_path.stat().st_size / (1024 * 1024)
            it_file = self.table.item(row, 5)
            if it_file:
                it_file.setText(f"{f_path.name} ({size_mb:.1f}MB)")
                it_file.setForeground(QColor("#38bdf8"))
                it_file.setToolTip(str(f_path.resolve()))

            # Kích hoạt nút Xem video
            action_widget = self.table.cellWidget(row, 6)
            if action_widget:
                btn_play = action_widget.findChild(QPushButton)
                if btn_play:
                    btn_play.setEnabled(True)
                    btn_play.clicked.disconnect() if btn_play.receivers(btn_play.clicked) > 0 else None
                    btn_play.clicked.connect(lambda _, p=str(f_path.resolve()): self._play_video(p))

        # Cập nhật thống kê tổng
        self._recalculate_overall_progress()

    def _recalculate_overall_progress(self) -> None:
        """Tính lại tổng số hoàn thành/lỗi và thanh tiến độ tổng thể."""
        success_cnt = 0
        failed_cnt = 0
        processing_cnt = 0

        for r in range(self.table.rowCount()):
            it = self.table.item(r, 4)
            if it:
                txt = it.text()
                if "Hoàn thành" in txt:
                    success_cnt += 1
                elif "Thất bại" in txt:
                    failed_cnt += 1
                elif "Render" in txt or "Làm mượt" in txt:
                    processing_cnt += 1

        self._completed_tasks = success_cnt
        self._failed_tasks = failed_cnt

        self.card_processing.value_label.setText(str(processing_cnt))  # type: ignore
        self.card_success.value_label.setText(str(success_cnt))  # type: ignore
        self.card_failed.value_label.setText(str(failed_cnt))  # type: ignore

        if self._total_tasks > 0:
            done_total = success_cnt + failed_cnt
            pct = int((done_total / self._total_tasks) * 100)
            self.overall_progress_bar.setValue(pct)
            self.lbl_overall_percent.setText(f"{pct}%")
            self.lbl_overall_status.setText(
                f"Tiến độ: Hoàn thành {success_cnt}/{self._total_tasks} video "
                + (f"({failed_cnt} lỗi)" if failed_cnt > 0 else "")
            )
            if done_total == self._total_tasks:
                self.btn_stop_queue.setEnabled(False)
                self.lbl_overall_status.setText("🎉 ĐÃ HOÀN TẤT TOÀN BỘ DANH SÁCH TÁC VỤ!")

    def on_workflow_finished(self) -> None:
        """Gọi khi toàn bộ workflow chạy xong."""
        self.btn_stop_queue.setEnabled(False)
        self._recalculate_overall_progress()
        self._log("🎉 Tất cả các tác vụ trong hàng đợi đã hoàn tất!")

    def _play_video(self, file_path: str) -> None:
        """Mở video bằng trình phát mặc định của máy."""
        if os.path.isfile(file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        else:
            QMessageBox.warning(self, "Không tìm thấy file", f"File video không tồn tại: {file_path}")

    def _open_downloads_folder(self) -> None:
        folder = Path(self._current_download_dir).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _on_stop_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            "Xác nhận dừng",
            "Bạn có chắc muốn dừng khẩn cấp toàn bộ các tác vụ đang render?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.btn_stop_queue.setEnabled(False)
            self.stop_requested.emit()

    def clear_queue(self) -> None:
        """Xóa trắng bảng hàng đợi nếu không có tác vụ nào đang chạy."""
        self.table.setRowCount(0)
        self._task_rows.clear()
        self._total_tasks = 0
        self.card_total.value_label.setText("0")  # type: ignore
        self.card_processing.value_label.setText("0")  # type: ignore
        self.card_success.value_label.setText("0")  # type: ignore
        self.card_failed.value_label.setText("0")  # type: ignore
        self.overall_progress_bar.setValue(0)
        self.lbl_overall_percent.setText("0%")
        self.lbl_overall_status.setText("Hàng đợi đã được dọn sạch.")
        self.btn_stop_queue.setEnabled(False)
