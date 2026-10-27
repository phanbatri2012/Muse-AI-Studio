# -*- coding: utf-8 -*-
"""
Màn hình Xưởng Soạn Prompt & Tạo Video Hàng Loạt (Prompt Studio Tab).
Tối ưu không gian rộng rãi và trải nghiệm thân thiện cho người dùng Non-tech:
- Tích hợp NumberedPromptEdit chiếm 70% không gian với cột số dòng #1, #2, #3...
- Kéo thả file .txt hoặc nạp prompt mẫu 1-click.
- Tự động đếm số prompt thực tế (loại bỏ dòng trống).
- Lựa chọn xoay tua tài khoản tự động (Round-Robin) hoặc cố định.
- Nút bấm hành động lớn: 🚀 BẮT ĐẦU TẠO VIDEO HÀNG LOẠT.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

from PyQt6.QtCore import QEvent, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from runtime_paths import MUSE_DOWNLOADS_DIR
from muse_service_manager import MUSE2API_ACCOUNTS_FILE
from settings_manager import SettingsManager
from .widgets.numbered_prompt_edit import NumberedPromptEdit
from .widgets.prompt_guide_dialog import PromptGuideDialog

SAMPLE_PROMPTS = [
    (
        "[4K, 16:9, 6 giây]. Một chiếc đồng hồ thông minh (smartwatch) màu đen mờ tối giản đặt trên bệ đá phiến ướt nước. "
        "Góc máy: Quay tiến xoay chậm từ góc 45 độ. "
        "Nhịp cảnh: 2 giây đầu màn hình ở trạng thái nghỉ, đến giây thứ 3 màn hình OLED bừng sáng biểu đồ sinh trắc học hình tròn, phản chiếu sắc nét trên bề mặt đá ướt. "
        "Ánh sáng: Đèn viền xanh dương mát từ tấm LED, phông nền studio tối. "
        "Âm thanh: Tiếng ù trầm điện tử nhẹ, tiếng chuông kỹ thuật số tinh tế khi màn hình bật, tiếng giọt nước nhỏ vang vọng. "
        "Bảo toàn: Kích thước vỏ đồng hồ và viền bezel. Loại trừ: Viền răng cưa, méo chữ."
    ),
    (
        "[9:16, 5 giây]. Một nữ barista mặc tạp dề hất xẻng xúc đá vào ly thủy tinh rỗng và liếc nhìn thẳng vào ống kính với nụ cười tự tin. "
        "Góc máy: Cận cảnh trung cầm tay sống động, whip-in nhanh. "
        "Nhịp cảnh: Đá rơi chạm đáy ly ngay ở khung hình đầu tiên, các viên đá nảy lên rồi lắng xuống, nữ barista khẽ nhướng mày. "
        "Ánh sáng: Cửa sổ quán cà phê ngập tràn ánh nắng ấm áp. "
        "Âm thanh: Tiếng đá va chạm lách cách lớn, tiếng xẻng kim loại chạm leng keng, tiếng rít máy pha cà phê nền. "
        'Lời thoại: Nữ barista nói: "Xem này." Phụ đề căn giữa đáy màn hình: "Xem này."'
    ),
    (
        "[2.39:1, 6 giây]. Một nghệ nhân sửa đồng hồ lớn tuổi đeo kính gọng kim loại đang quan sát một bánh răng đồng hồ tinh xảo qua kính lúp phóng đại. "
        "Góc máy: Cận cảnh cực độ chuyển nét từ các bánh răng đồng ở tiền cảnh sang ánh mắt tập trung của nghệ nhân. "
        "Ánh sáng: Đèn sợi đốt định hướng êm dịu chiếu sáng các hạt bụi vi mô lơ lửng. "
        "Âm thanh: Tiếng tích tắc nhịp nhàng của hàng chục chiếc đồng hồ ở các tiết tấu khác nhau, tiếng thở khẽ khàn, tiếng nhíp kim loại gắp nhẹ. "
        "Bảo toàn: Nếp nhăn khuôn mặt và màu gỉ đồng cổ kính. Loại trừ: Mắt mờ, chớp mí mắt giả tạo."
    ),
    (
        "[16:9, 6 giây]. Một chú chim ruồi màu xanh lục ánh kim bay lơ lửng chuẩn xác trước một bông hoa dâm bụt đỏ thẫm đọng sương sớm. "
        "Góc máy: Tracking macro siêu nét chuyển động chậm, độ sâu trường ảnh nông với hậu cảnh xóa phông mượt mà. "
        "Nhịp cảnh: Đôi cánh đập nhịp nhàng khí động học uyển chuyển, mỏ chim khẽ hút mật ở giây thứ 2, giọt sương mai lấp lánh rung rinh. "
        "Ánh sáng: Ngược sáng bình minh giờ vàng làm nổi bật ánh kim của bộ lông. "
        "Âm thanh: Tiếng vỗ cánh siêu âm vo ve nhanh, gió vườn khẽ xào xạc lá cây, tiếng chim hót sớm vọng lại từ xa. "
        "Bảo toàn: Độ sắc nét của viền cánh, giải phẫu cấu trúc lông vũ."
    ),
    (
        "Một nữ nghệ nhân gốm 30 tuổi mặc tạp dề denim từ từ rót sữa bốc khói vào tách gốm sẫm màu. "
        "Góc máy: Cú máy góc thấp đẩy tiến êm ái. "
        "Ánh sáng: Ngược sáng ban mai ấm áp xuyên qua các hạt bụi li ti, bóng đổ mềm mại trên bàn gỗ sồi. "
        "Âm thanh: Tiếng xì xào êm dịu của quán cà phê, tiếng cốc chạm nhẹ vào đĩa, tiếng dòng sữa lỏng rót xuống nhẹ nhàng."
    ),
    (
        "Tham chiếu diện mạo nhân vật từ @Image1 và trang phục từ @Image2. "
        "Người phụ nữ bước đi qua ga tàu điện ngầm đông đúc nhộn nhịp, cú máy tracking trung cảnh bám theo, "
        "bảo toàn trọn vẹn đường nét khuôn mặt và chất liệu áo khoác. "
        "Âm thanh: Tiếng tàu hỏa ầm ầm từ xa, tiếng bước chân vang vọng."
    ),
]


class DurationSpinBox(QSpinBox):
    """QSpinBox tùy chỉnh: tự động bôi đen toàn bộ số khi click/focus để người dùng gõ đè ngay lập tức."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        line_edit = self.lineEdit()
        if line_edit:
            line_edit.installEventFilter(self)

    def eventFilter(self, obj: Any, event: QEvent) -> bool:
        if obj == self.lineEdit():
            if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.FocusIn):
                QTimer.singleShot(0, self.selectAll)
        return super().eventFilter(obj, event)


class PromptStudioTab(QWidget):
    """Màn hình Xưởng Soạn Thảo Prompt & Khởi Chạy Video Hàng Loạt."""

    # Signal gửi sang Queue Monitor để khởi chạy batch
    start_batch_requested = pyqtSignal(list, dict)  # prompts_list, config_dict
    stop_batch_requested = pyqtSignal()

    def __init__(self, log_callback: Callable[[str], None] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_callback = log_callback
        self._current_download_dir = MUSE_DOWNLOADS_DIR
        self._is_running = False

        self._init_ui()
        self.populate_accounts()

    def _log(self, msg: str) -> None:
        if callable(self.log_callback):
            self.log_callback(msg)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 10)
        main_layout.setSpacing(10)

        # =====================================================================
        # 1. KHU VỰC SOẠN THẢO PROMPT (100% FULL-WIDTH)
        # =====================================================================
        editor_box = QGroupBox("📝 DANH SÁCH PROMPTS (MỖI DÒNG 1 PROMPT CÓ ĐÁNH SỐ THỨ TỰ)")
        editor_box_layout = QVBoxLayout(editor_box)
        editor_box_layout.setContentsMargins(12, 14, 12, 10)
        editor_box_layout.setSpacing(8)

        # Toolbar phía trên editor
        tb_layout = QHBoxLayout()
        tb_layout.setSpacing(8)

        self.lbl_count_badge = QLabel("📝 0 prompts")
        self.lbl_count_badge.setStyleSheet(
            "background: #1e293b; color: #38bdf8; font-weight: 700; font-size: 11px; "
            "padding: 3px 8px; border-radius: 6px; border: 1px solid #0284c7;"
        )
        tb_layout.addWidget(self.lbl_count_badge)

        lbl_drag_hint = QLabel("💡 Kéo thả file .txt")
        lbl_drag_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        lbl_drag_hint.setToolTip("Bạn có thể kéo và thả trực tiếp file .txt vào khung soạn thảo để nạp nhanh")
        tb_layout.addWidget(lbl_drag_hint)
        tb_layout.addStretch()

        self.btn_load_file = QPushButton("📂 Nạp TXT")
        self.btn_load_file.setFixedHeight(30)
        self.btn_load_file.setStyleSheet("font-size: 11px; padding: 0 8px;")
        self.btn_load_file.setToolTip("Nạp danh sách prompts từ file văn bản .txt")
        self.btn_load_file.clicked.connect(self._load_txt_file)
        tb_layout.addWidget(self.btn_load_file)

        self.btn_prompt_guide = QPushButton("📖 Cẩm Nang Prompt")
        self.btn_prompt_guide.setFixedHeight(30)
        self.btn_prompt_guide.setStyleSheet(
            "font-size: 11px; padding: 0 10px; font-weight: 700; "
            "color: #38bdf8; background-color: #0f172a; border: 1px solid #0284c7; border-radius: 6px;"
        )
        self.btn_prompt_guide.setToolTip("Mở cẩm nang cấu trúc prompt chuẩn Muse AI (Production Shot Brief) và thư viện mẫu")
        self.btn_prompt_guide.clicked.connect(self._open_prompt_guide_dialog)
        tb_layout.addWidget(self.btn_prompt_guide)
        self.btn_sample = self.btn_prompt_guide  # Giữ alias để tương thích ngược

        self.btn_clear = QPushButton("🧹 Xóa Trắng")
        self.btn_clear.setFixedHeight(30)
        self.btn_clear.setStyleSheet("font-size: 11px; padding: 0 8px;")
        self.btn_clear.clicked.connect(self._clear_editor)
        tb_layout.addWidget(self.btn_clear)

        editor_box_layout.addLayout(tb_layout)

        # Component NumberedPromptEdit
        self.editor = NumberedPromptEdit()
        self.editor.setPlaceholderText(
            "Nhập hoặc dán các prompt tại đây (mỗi dòng là 1 prompt riêng biệt)...\n\n"
            "Ví dụ theo chuẩn Production Shot Brief (Muse AI):\n"
            "[4K, 16:9, 6 giây]. Chiếc đồng hồ thông minh trên bệ đá phiến ướt. Góc máy: Xoay tiến chậm. Nhịp cảnh: Màn hình OLED phát sáng ở giây thứ 3. Âm thanh: Tiếng ù điện tử, chuông báo tinh tế.\n"
            "[9:16, 5 giây]. Nữ barista thả xẻng đá vào ly, nhìn thẳng ống kính. Góc máy: Whip-in nhanh. Lời thoại: Nữ barista nói: 'Xem này.' Âm thanh: Tiếng đá lách cách, tiếng rít máy pha cà phê.\n"
            "Nữ nghệ nhân gốm 30 tuổi từ từ rót sữa bốc khói vào tách gốm. Góc máy: Đẩy tiến góc thấp. Âm thanh: Tiếng xì xào quán cà phê, cốc chạm đĩa."
        )
        self.editor.prompts_changed.connect(self._on_prompts_count_changed)
        editor_box_layout.addWidget(self.editor)

        # Thanh Hướng Dẫn Tiếng Việt Thu Gọn / Ẩn Dưới Editor
        self.guide_bar = QFrame()
        self.guide_bar.setStyleSheet(
            "QFrame { background-color: #0d1527; border: 1px solid #1e293b; border-radius: 6px; }"
        )
        guide_bar_layout = QVBoxLayout(self.guide_bar)
        guide_bar_layout.setContentsMargins(10, 6, 10, 6)
        guide_bar_layout.setSpacing(6)

        top_guide = QHBoxLayout()
        top_guide.setSpacing(8)

        lbl_guide_summary = QLabel(
            "💡 <b>Cấu trúc chuẩn:</b> [Chủ thể] + [Hành động] + [Góc máy] + [Ánh sáng] + [Âm thanh]"
        )
        lbl_guide_summary.setStyleSheet("color: #38bdf8; font-size: 11px;")
        top_guide.addWidget(lbl_guide_summary)
        top_guide.addStretch()

        self.btn_toggle_guide = QPushButton("🔽 Xem Tóm Tắt")
        self.btn_toggle_guide.setFixedHeight(24)
        self.btn_toggle_guide.setStyleSheet(
            "font-size: 10px; padding: 0 8px; color: #94a3b8; background-color: #1e293b; border: 1px solid #334155; border-radius: 4px;"
        )
        self.btn_toggle_guide.clicked.connect(self._toggle_guide_detail)
        top_guide.addWidget(self.btn_toggle_guide)

        self.btn_quick_popup = QPushButton("📖 Cẩm Nang Chi Tiết")
        self.btn_quick_popup.setFixedHeight(24)
        self.btn_quick_popup.setStyleSheet(
            "font-size: 10px; padding: 0 8px; font-weight: 700; color: #34d399; background-color: #064e3b; border: 1px solid #059669; border-radius: 4px;"
        )
        self.btn_quick_popup.clicked.connect(self._open_prompt_guide_dialog)
        top_guide.addWidget(self.btn_quick_popup)

        guide_bar_layout.addLayout(top_guide)

        self.guide_detail_widget = QWidget()
        self.guide_detail_widget.setVisible(False)
        detail_layout = QVBoxLayout(self.guide_detail_widget)
        detail_layout.setContentsMargins(2, 4, 2, 4)
        detail_layout.setSpacing(4)

        lbl_tips = QLabel(
            "• <b>Tư duy Đạo diễn (Shot Brief):</b> Tránh từ sáo rỗng (<i>photorealistic, 8k, masterpiece</i>) — hãy tập trung nguồn sáng vật lý và hành động cụ thể.<br/>"
            "• <b>6 Thành phần:</b> Chủ thể (Identity Anchor) • Hành động (Filmable action) • Camera (1 shot = 1 chuyển động chính) • Ánh sáng thực tế • Nhịp thời gian (Beats) • Âm thanh bản địa (Ambience + Foley + Dialogue).<br/>"
            "• <b>Cú pháp nâng cao:</b> Dùng <code>@Image1</code> để khóa nhân vật/logo, <code>@Video 1</code> để kế thừa động tác/góc quay, <code>Preserve: [...]</code> chống biến dạng.<br/>"
            "• <b>Mẫu thực chiến:</b> Nhấp '📖 Cẩm Nang Prompt' để xem TVC sản phẩm, Social Hook, Phim điện ảnh và nạp 1-click vào ô soạn thảo."
        )
        lbl_tips.setWordWrap(True)
        lbl_tips.setStyleSheet("color: #cbd5e1; font-size: 11px; line-height: 1.4;")
        detail_layout.addWidget(lbl_tips)

        guide_bar_layout.addWidget(self.guide_detail_widget)
        editor_box_layout.addWidget(self.guide_bar)

        main_layout.addWidget(editor_box, 1)

        # =====================================================================
        # 2. THANH ĐIỀU KHIỂN ĐÁY SIÊU TINH GỌN (SLIM ACTION DOCK - CAO 34PX)
        # =====================================================================
        self.action_strip = QFrame()
        self.action_strip.setFixedHeight(34)
        self.action_strip.setStyleSheet(
            """
            QFrame {
                background-color: #0b1329;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
            """
        )
        strip_layout = QHBoxLayout(self.action_strip)
        strip_layout.setContentsMargins(8, 2, 8, 2)
        strip_layout.setSpacing(8)

        # --- A. Nút Pill Chọn Tài Khoản Xoay Tua ---
        self.btn_account_pill = QPushButton("🔄 Xoay tua: 🟢 ... ▾")
        self.btn_account_pill.setFixedHeight(28)
        self.btn_account_pill.setStyleSheet(
            """
            QPushButton {
                background-color: #0f172a;
                color: #34d399;
                border: 1px solid #059669;
                border-radius: 5px;
                padding: 0 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #1e293b;
            }
            """
        )
        self.btn_account_pill.setToolTip("Nhấp để chuyển đổi giữa Xoay tua tự động hoặc chọn tài khoản cố định")
        self.btn_account_pill.clicked.connect(self._show_account_popup_menu)
        strip_layout.addWidget(self.btn_account_pill)

        # Đối tượng ngầm hỗ trợ tương thích ngược (Unit tests & internal state)
        self.radio_rotation = QRadioButton()
        self.radio_rotation.setChecked(True)
        self.radio_single = QRadioButton()
        self.combo_specific_account = QComboBox()
        self.combo_specific_account.setEnabled(False)
        self.lbl_pool_status = QLabel("🟢 Khởi tạo Account Pool...")
        self.combo_ratio = QComboBox()
        self.combo_ratio.addItem("auto", "auto")
        self.spin_duration = DurationSpinBox()
        self.spin_duration.setRange(1, 10)
        self.spin_duration.setValue(6)
        self.spin_duration.setToolTip("Thời lượng: Khuyên dùng 4–6 giây (tối đa trần mô hình Muse AI: 10 giây/shot)")

        # Phân cách dọc
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet("color: #1e293b;")
        strip_layout.addWidget(sep1)

        # --- B. Làm mượt 60fps ---
        self.chk_smooth_60fps = QCheckBox("⚡ 60fps")
        self.chk_smooth_60fps.setChecked(True)
        self.chk_smooth_60fps.setStyleSheet("color: #a78bfa; font-weight: 700; font-size: 11px;")
        self.chk_smooth_60fps.setToolTip("Làm mượt quang học 60fps (MCI FFmpeg) sau khi tải video")
        strip_layout.addWidget(self.chk_smooth_60fps)

        strip_layout.addStretch()

        # --- C. Nút Hành Động Hero (Bắt Đầu Tạo Video Hàng Loạt) ---
        self.btn_start = QPushButton("🚀 BẮT ĐẦU TẠO VIDEO (0 PROMPTS)")
        self.btn_start.setFixedHeight(28)
        self.btn_start.setStyleSheet(
            "font-size: 11px; font-weight: 700; background: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 5px; padding: 0 14px;"
        )
        self.btn_start.setToolTip("Vui lòng nhập ít nhất 1 prompt hoặc bấm 'Cẩm Nang' để nạp mẫu")
        self.btn_start.clicked.connect(self._on_start_clicked)
        strip_layout.addWidget(self.btn_start)

        main_layout.addWidget(self.action_strip, 0)

    # =========================================================================
    # XỬ LÝ SỰ KIỆN & CẬP NHẬT DỮ LIỆU
    # =========================================================================

    def _show_account_popup_menu(self) -> None:
        """Mở menu popup chọn chế độ xoay tua hoặc chỉ định tài khoản cố định."""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #0f172a; color: #f8fafc; border: 1px solid #334155; padding: 4px; border-radius: 6px; } "
            "QMenu::item { padding: 6px 14px; border-radius: 4px; } "
            "QMenu::item:selected { background-color: #0284c7; } "
            "QMenu::separator { height: 1px; background: #334155; margin: 4px 0; }"
        )

        # 1. Action Xoay tua tự động
        act_rotate = menu.addAction("🔄 Xoay tua tự động tất cả tài khoản (Khuyên dùng)")
        act_rotate.setCheckable(True)
        act_rotate.setChecked(self.radio_rotation.isChecked())

        menu.addSeparator()

        # 2. Danh sách các tài khoản cố định
        account_actions = []
        for i in range(self.combo_specific_account.count()):
            text = self.combo_specific_account.itemText(i)
            aid = self.combo_specific_account.itemData(i)
            act = menu.addAction(f"👤 {text}")
            act.setCheckable(True)
            if self.radio_single.isChecked() and self.combo_specific_account.currentData() == aid:
                act.setChecked(True)
            account_actions.append((act, aid, text))

        chosen = menu.exec(self.btn_account_pill.mapToGlobal(self.btn_account_pill.rect().bottomLeft()))
        if chosen == act_rotate:
            self.radio_rotation.setChecked(True)
            self.radio_single.setChecked(False)
            self._update_account_pill_label()
        else:
            for act, aid, text in account_actions:
                if chosen == act:
                    self.radio_rotation.setChecked(False)
                    self.radio_single.setChecked(True)
                    idx = self.combo_specific_account.findData(aid)
                    if idx >= 0:
                        self.combo_specific_account.setCurrentIndex(idx)
                    self._update_account_pill_label(custom_name=text)
                    break

    def _update_account_pill_label(self, custom_name: str | None = None) -> None:
        """Cập nhật nhãn của nút Pill tài khoản."""
        if self.radio_rotation.isChecked():
            valid_count = 0
            for i in range(self.combo_specific_account.count()):
                if "🟢" in self.combo_specific_account.itemText(i):
                    valid_count += 1
            if valid_count > 0:
                self.btn_account_pill.setText(f"🔄 Xoay tua: 🟢 {valid_count} tài khoản ▾")
                self.btn_account_pill.setStyleSheet(
                    "QPushButton { background-color: #0f172a; color: #34d399; border: 1px solid #059669; border-radius: 5px; padding: 0 10px; font-size: 11px; font-weight: 700; } "
                    "QPushButton:hover { background-color: #1e293b; }"
                )
            else:
                self.btn_account_pill.setText("🔄 Xoay tua: ⚠️ 0 tài khoản ▾")
                self.btn_account_pill.setStyleSheet(
                    "QPushButton { background-color: #2a1b06; color: #f59e0b; border: 1px solid #d97706; border-radius: 5px; padding: 0 10px; font-size: 11px; font-weight: 700; } "
                    "QPushButton:hover { background-color: #3d2708; }"
                )
        else:
            name = custom_name or self.combo_specific_account.currentText()
            clean_name = name.replace("🟢 ", "").replace("🔴 ", "")
            self.btn_account_pill.setText(f"👤 Cố định: {clean_name[:18]} ▾")
            self.btn_account_pill.setStyleSheet(
                "QPushButton { background-color: #1e1b4b; color: #a5b4fc; border: 1px solid #6366f1; border-radius: 5px; padding: 0 10px; font-size: 11px; font-weight: 700; } "
                "QPushButton:hover { background-color: #312e81; }"
            )

    def _on_prompts_count_changed(self, count: int) -> None:
        """Cập nhật badge số lượng prompt và trạng thái thị giác của nút Bắt đầu."""
        self.lbl_count_badge.setText(f"📝 {count} prompts")
        if not self._is_running:
            if count > 0:
                self.btn_start.setText(f"🚀 BẮT ĐẦU TẠO VIDEO ({count} CẢNH)")
                self.btn_start.setStyleSheet(
                    "font-size: 11px; font-weight: 800; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981); color: #ffffff; border-radius: 5px; padding: 0 14px;"
                )
                self.btn_start.setToolTip(f"Bấm để bắt đầu khởi chạy render hàng loạt cho {count} prompts")
            else:
                self.btn_start.setText("🚀 BẮT ĐẦU TẠO VIDEO (0 PROMPTS)")
                self.btn_start.setStyleSheet(
                    "font-size: 11px; font-weight: 700; background: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 5px; padding: 0 12px;"
                )
                self.btn_start.setToolTip("Vui lòng nhập ít nhất 1 prompt (mỗi dòng 1 prompt) hoặc bấm 'Cẩm Nang'")

    def _on_account_mode_toggled(self, checked: bool) -> None:
        """Bật/tắt dropdown tài khoản khi chọn dùng tài khoản cố định."""
        self.combo_specific_account.setEnabled(self.radio_single.isChecked())
        self._update_account_pill_label()

    def populate_accounts(self) -> None:
        """Đọc danh sách accounts từ accounts.json và nạp vào ComboBox."""
        self.combo_specific_account.clear()
        accounts = []
        if MUSE2API_ACCOUNTS_FILE.exists():
            try:
                accounts = json.loads(MUSE2API_ACCOUNTS_FILE.read_text(encoding="utf-8"))
                if not isinstance(accounts, list):
                    accounts = []
            except Exception:
                accounts = []

        valid_count = 0
        now_ts = int(time.time())

        for acc in accounts:
            aid = str(acc.get("id", ""))
            label = str(acc.get("label", aid))
            is_enabled = acc.get("enabled", True)
            is_ok = acc.get("ok", True)
            exp_at = acc.get("expires_at", 0)

            if is_enabled and is_ok and (exp_at == 0 or exp_at > now_ts):
                valid_count += 1
                self.combo_specific_account.addItem(f"🟢 {label}", aid)
            else:
                self.combo_specific_account.addItem(f"🔴 {label} (Hết hạn)", aid)

        if valid_count > 0:
            self.lbl_pool_status.setText(f"🟢 Đang có {valid_count} tài khoản sẵn sàng xoay tua")
            self.lbl_pool_status.setStyleSheet("color: #34d399; font-size: 11px; font-weight: 600;")
        else:
            self.lbl_pool_status.setText("⚠️ Chưa có tài khoản hợp lệ. Hãy thêm tài khoản ở Tab Tài Khoản!")
            self.lbl_pool_status.setStyleSheet("color: #f87171; font-size: 11px; font-weight: 600;")

        self._update_account_pill_label()

    def _load_txt_file(self) -> None:
        """Nạp danh sách prompts từ file TXT."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn File Prompts (.txt)", "", "Text Files (*.txt *.prompts);;All Files (*.*)"
        )
        if not file_path:
            return
        try:
            content = Path(file_path).read_text(encoding="utf-8")
            self.editor.setPlainText(content)
            self._log(f"📂 Đã nạp danh sách prompts từ: {Path(file_path).name}")
        except Exception:
            try:
                content = Path(file_path).read_text(encoding="cp1252")
                self.editor.setPlainText(content)
            except Exception as e:
                QMessageBox.warning(self, "Lỗi đọc file", f"Không thể đọc file: {e}")

    def _toggle_guide_detail(self) -> None:
        """Thu gọn hoặc mở rộng khung hướng dẫn chi tiết ẩn dưới editor."""
        is_hidden = self.guide_detail_widget.isHidden()
        self.guide_detail_widget.setHidden(not is_hidden)
        if is_hidden:
            self.btn_toggle_guide.setText("🔼 Thu Gọn")
        else:
            self.btn_toggle_guide.setText("🔽 Xem Tóm Tắt")

    def _open_prompt_guide_dialog(self) -> None:
        """Mở hộp thoại cẩm nang hướng dẫn cấu trúc prompt chuẩn Muse Video."""
        dialog = PromptGuideDialog(self)
        dialog.prompt_selected.connect(self._on_guide_single_prompt_selected)
        dialog.prompts_batch_selected.connect(self._on_guide_batch_selected)
        dialog.exec()

    def _on_guide_single_prompt_selected(self, prompt: str) -> None:
        """Tiếp nhận 1 prompt từ cẩm nang và nạp vào xưởng."""
        current_prompts = self.editor.get_clean_prompts()
        if not current_prompts:
            self.editor.set_prompts_list([prompt])
        else:
            current_prompts.append(prompt)
            self.editor.set_prompts_list(current_prompts)
        self._log("💡 Đã nạp prompt chuẩn từ Cẩm nang vào xưởng.")

    def _on_guide_batch_selected(self, prompts: List[str]) -> None:
        """Tiếp nhận danh sách prompt mẫu từ cẩm nang và nạp vào xưởng."""
        self.editor.set_prompts_list(prompts)
        self._log(f"💡 Đã nạp {len(prompts)} prompt chuẩn từ Cẩm nang vào xưởng.")

    def _load_sample_prompts(self) -> None:
        """Nạp danh sách prompts mẫu chuẩn Muse AI (Production Shot Brief)."""
        self.editor.set_prompts_list(SAMPLE_PROMPTS)
        self._log(f"💡 Đã nạp {len(SAMPLE_PROMPTS)} prompt mẫu chuẩn Muse AI vào xưởng.")

    def _clear_editor(self) -> None:
        """Xóa trắng nội dung trình soạn thảo."""
        if self.editor.prompt_count() > 0:
            reply = QMessageBox.question(
                self,
                "Xác nhận xóa",
                "Bạn có chắc muốn xóa trắng toàn bộ danh sách prompt hiện có?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.editor.clear_prompts()
        else:
            self.editor.clear_prompts()

    # =========================================================================
    # KHỞI CHẠY TẠO VIDEO HÀNG LOẠT
    # =========================================================================

    def _on_start_clicked(self) -> None:
        prompts = self.editor.get_clean_prompts()
        if not prompts:
            QMessageBox.warning(
                self,
                "Chưa có prompt",
                "Vui lòng nhập ít nhất 1 prompt (mỗi dòng 1 prompt) hoặc bấm 'Nạp Prompt Mẫu' trước khi bắt đầu!",
            )
            return

        # Kiểm tra chế độ tài khoản
        account_mode = "rotation" if self.radio_rotation.isChecked() else "single"
        chosen_account_id = None
        if account_mode == "single":
            chosen_account_id = self.combo_specific_account.currentData()
            if not chosen_account_id:
                QMessageBox.warning(self, "Chưa chọn tài khoản", "Vui lòng chọn một tài khoản cố định!")
                return
        else:
            valid_count = sum(1 for i in range(self.combo_specific_account.count()) if "🟢" in self.combo_specific_account.itemText(i))
            if valid_count == 0:
                reply = QMessageBox.question(
                    self,
                    "Chưa có tài khoản sẵn sàng",
                    "Hiện tại chưa có tài khoản nào hợp lệ trong hệ thống xoay tua.\n\n"
                    "Bạn có muốn chuyển sang màn hình 'Quản Lý Tài Khoản' để đăng nhập thêm tài khoản không?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    parent_main = self.window()
                    if hasattr(parent_main, "tabs") and hasattr(parent_main, "tab_accounts"):
                        parent_main.tabs.setCurrentWidget(parent_main.tab_accounts)
                return

        # Lấy cấu hình hệ thống mặc định từ SettingsManager (Single Source of Truth)
        st = SettingsManager.load_muse_settings()
        timeout_sec = int(st.get("task_timeout_seconds", 360))
        max_retries = int(st.get("max_retries", 2))
        dl_dir = st.get("download_dir", str(MUSE_DOWNLOADS_DIR))

        config: Dict[str, Any] = {
            "account_mode": account_mode,
            "account_id": chosen_account_id,
            "aspect_ratio": self.combo_ratio.currentData(),
            "duration": self.spin_duration.value(),
            "timeout_seconds": timeout_sec,
            "max_retries": max_retries,
            "smooth_60fps": self.chk_smooth_60fps.isChecked(),
            "motion_boost": False,
            "download_dir": dl_dir,
        }

        self.set_running_state(True)
        self._log(f"🚀 Bắt đầu tiến trình tạo hàng loạt {len(prompts)} video (Chế độ: {account_mode})...")
        self.start_batch_requested.emit(prompts, config)

    def set_running_state(self, running: bool) -> None:
        """Cập nhật trạng thái nút bấm khi đang chạy hoặc rảnh."""
        self._is_running = running
        self.btn_start.setEnabled(not running)
        if running:
            self.btn_start.setText("⚡ Đang Xử Lý Hàng Đợi (Xem tab Tiến Độ)...")
            self.btn_start.setStyleSheet(
                "font-size: 13px; font-weight: 700; background: #334155; color: #94a3b8; border-radius: 8px;"
            )
        else:
            self._on_prompts_count_changed(self.editor.prompt_count())
        self.editor.setReadOnly(running)
        self.btn_load_file.setEnabled(not running)
        self.btn_sample.setEnabled(not running)
        self.btn_clear.setEnabled(not running)
