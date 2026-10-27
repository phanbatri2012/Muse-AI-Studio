# -*- coding: utf-8 -*-
"""
Màn hình Xưởng Tạo Video Đồng Bộ Nhân Vật (Character Studio Tab).
Kiến trúc chuyên biệt giải quyết bài toán chống trôi dạt ID và biến dạng khuôn mặt:
- 2 Chế độ: Có ảnh tham chiếu (@Image1, @Image2, @Image3 - Turnaround Set) vs Không kèm ảnh (Text-Only Continuity).
- Bộ quản lý 3 Slot ảnh tham chiếu trực quan (Chính diện, Góc nghiêng, Toàn thân) kèm xem trước và kéo thả.
- Trình soạn thảo phân cảnh liên tiếp (NumberedPromptEdit) với công cụ nạp Mẫu A, Mẫu B và chèn cú pháp nhanh.
- Thanh hướng dẫn thu gọn ẩn dưới editor & Box nổi Cẩm Nang Chuyên Sâu.
- Bảng cấu hình xoay tua tài khoản và khởi chạy pipeline.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
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
from .tab_prompt_studio import DurationSpinBox
from .widgets.numbered_prompt_edit import NumberedPromptEdit
from .widgets.character_guide_dialog import CharacterGuideDialog

# Mẫu A: Có ảnh đính kèm (Nữ thám tử 28 tuổi trong mưa)
SAMPLE_A_PROMPTS = [
    (
        "[16:9, 6 giây]. Tham chiếu cấu trúc khuôn mặt và màu mắt nhân vật từ @Image1, và áo măng tô cổ điển từ @Image2. "
        "Một nữ thám tử 28 tuổi bước đi thoăn thoắt qua con hẻm ướt đẫm mưa lúc chạng vạng, dừng lại dưới ngọn đèn đường chập chờn, rồi quay lại nhìn thẳng vào máy quay với biểu cảm dò xét, căng thẳng. "
        "Góc máy: Quay trung cảnh bám theo mượt mà lùi dần về phía trước mặt cô, rồi dừng lại ở cỡ cận trung. "
        "Nhịp cảnh: Từ giây 0-3 cô vừa đi vừa nhìn quanh; giây thứ 4 cô dừng bước, những giọt mưa rơi nhỏ tong tòng từ cổ áo; giây thứ 5 cô cất lời. "
        'Lời thoại: Cô nói dứt khoát: "Ai đã cho anh địa chỉ này?" với khẩu hình đồng bộ chuẩn xác và chuyển động quai hàm tự nhiên. '
        "Âm thanh: Tiếng bước chân ủng ướt vang vọng, tiếng mưa rào xối xả đập xuống mặt đường nhựa, tiếng ma sát sột soạt của áo khoác, giọng thoại phát ra rõ ràng. "
        "Bảo toàn: Cấu trúc xương mặt, tàn nhang trên sống mũi, chất tóc màu nâu đỏ, ve áo măng tô màu xanh rêu đậm. "
        "Loại trừ: Trôi dạt nhận diện, biến đổi kiểu áo, khẩu hình nhòe mờ, thừa ngón tay."
    ),
    (
        "[16:9, 6 giây]. Tham chiếu diện mạo nhân vật từ @Image1 và áo khoác từ @Image2. "
        "Nữ thám tử bước vào dưới mái hiên gạch của một nhà kho bỏ hoang, giũ nước mưa đọng trên cổ áo, rồi cúi nhìn chiếc chìa khóa đồng cũ kỹ trong lòng bàn tay. "
        "Góc máy: Trung cảnh qua vai chuyển đổi mượt mà sang cực cận đặc tả ánh mắt cô và chiếc chìa khóa. "
        "Nhịp cảnh: 2 giây đầu cô giũ áo khoác; giây thứ 3 ánh mắt hạ xuống nhìn chìa khóa; giây thứ 5 cô thì thầm khe khẽ. "
        'Lời thoại: Bằng giọng thì thầm trầm ấm, cô lẩm bẩm: "Nó thực sự vừa vặn." với chuyển động môi tinh tế. '
        "Âm thanh: Tiếng mưa rơi lộp bộp nặng hạt trên mái tôn, tiếng vải áo sột soạt, tiếng kim loại va chạm leng keng nhẹ, hơi thở nghẹn ngào. "
        "Bảo toàn: Chuẩn xác cấu trúc khuôn mặt, tàn nhang, màu mắt và chất liệu áo măng tô từ @Image1 và @Image2. "
        "Loại trừ: Lệch phom dáng mặt, đổi màu tóc, chìa khóa biến mất."
    ),
]

# Mẫu B: Không kèm ảnh (Khởi tạo nhân vật gốc bằng Text)
SAMPLE_B_PROMPTS = [
    (
        "[16:9, 5 giây]. Một cú máy quay liền mạch duy nhất về Bác sĩ Aris Thorne, một nam bác sĩ phẫu thuật 45 tuổi người Địa Trung Hải với mái tóc cắt ngắn hoa râm, làn da màu ô-liu lộ vẻ mệt mỏi, đường viền hàm sắc cạnh và một vết sẹo mờ phía trên lông mày trái, đang mặc trang phục phẫu thuật vô trùng màu xanh ngọc lam và đeo găng tay cao su. "
        "Ông kéo khẩu trang phẫu thuật xuống, thở phào nhẹ nhõm và ngước nhìn đồng nghiệp với ánh mắt trút bỏ gánh nặng. "
        "Góc máy: Đẩy tiến chậm cận cảnh, giữ tiêu điểm sắc nét vào đôi mắt và khuôn mặt ông. "
        "Nhịp cảnh: Ở giây thứ 2 tay phải ông kéo khẩu trang xuống dưới cằm; ở giây thứ 4 ông mỉm cười nhẹ và nói. "
        'Lời thoại: Bằng giọng nói trầm ấm, kiệt sức nhưng điềm tĩnh, ông nói: "Các chỉ số sinh tồn đã ổn định." với khẩu hình phát âm chuẩn xác. '
        "Âm thanh: Tiếng bíp nhịp nhàng đều đặn của máy đo điện tim ECG, tiếng vo ve êm của hệ thống thông khí phòng mổ, tiếng tách dây chun khẩu trang, giọng nói trầm rõ ràng. "
        "Duy trì chính xác cùng một đối tượng nhân vật, cấu trúc hình học khuôn mặt, chi tiết vết sẹo và trang phục nhất quán xuyên suốt từng khung hình không ngắt cắt. "
        "Bảo toàn: Vị trí vết sẹo, dáng tai, màu sắc bộ đồ mổ. "
        "Loại trừ: Biến dạng thành người khác, thay đổi độ dài tóc, méo mó bàn tay."
    )
]

# Mẫu C: 2 Nhân vật đối thoại (Two-Character Dialogue)
SAMPLE_C_PROMPTS = [
    (
        "[16:9, 6 giây]. Tham chiếu nhân vật nữ từ @Image1 ở bên trái khung hình và nhân vật nam từ @Image2 ở bên phải khung hình. "
        "Cú máy trung cảnh hai người (Two-shot medium) trong phòng họp văn phòng ánh sáng vàng dịu. "
        "Người phụ nữ (@Image1) quay sang nhìn thẳng vào mắt người đàn ông (@Image2), cất lời dứt khoát. "
        'Lời thoại: Người phụ nữ nói: "Hồ sơ này không thể để lộ ra ngoài." với khẩu hình đồng bộ tự nhiên, người đàn ông nhíu mày gật đầu. '
        "Âm thanh: Tiếng lật tài liệu sột soạt, tiếng điều hòa phòng họp êm dịu, giọng nói nữ rõ ràng. "
        "Bảo toàn: Khuôn mặt và áo sơ mi của @Image1, kiểu tóc và vest sẫm màu của @Image2, khoảng cách phân định rõ ràng giữa hai người. "
        "Loại trừ: Lem màu trang phục giữa @Image1 và @Image2, trôi dạt nhận diện, méo mó bàn tay."
    ),
    (
        "[16:9, 6 giây]. Cắt sang góc máy cận qua vai (Over-the-shoulder shot): Người đàn ông (@Image2) nhìn người phụ nữ (@Image1), hạ thấp giọng thì thầm. "
        'Lời thoại: Người đàn ông nói: "Tôi hiểu rồi, mọi thứ sẽ được bảo mật tuyệt đối." với cử động môi chuẩn xác và ánh mắt nghiêm nghị. '
        "Âm thanh: Giọng nam trầm thì thầm rõ ràng, tiếng bút đặt xuống mặt bàn. "
        "Bảo toàn: Nhận diện chuẩn xác của người đàn ông từ @Image2 và góc vai sau của @Image1. "
        "Loại trừ: Biến dạng xương hàm, lệch hướng nhìn."
    ),
]

# Mẫu D: Diễn viên & Sản phẩm TVC (Actor + Product Commercial)
SAMPLE_D_PROMPTS = [
    (
        "[16:9, 6 giây]. Tham chiếu người mẫu từ @Image1 và sản phẩm điện thoại từ @Image2. "
        "Cú máy cận trung tracking mượt mà: Người mẫu (@Image1) mỉm cười thanh lịch, tay phải nâng chiếc điện thoại (@Image2) lên ngang ngực hướng về ống kính, ánh đèn studio quét qua viền máy phản chiếu ánh kim loại sang trọng. "
        'Lời thoại: Người mẫu nói: "Thiết kế thực sự đỉnh cao." với khẩu hình tươi tắn rạng rỡ. '
        "Âm thanh: Tiếng lách cách nhẹ của vỏ kim loại cao cấp, tiếng nhạc nền thương mại tinh tế. "
        "Bảo toàn: Nét mặt và thần thái của người mẫu @Image1, màu sắc và logo quả táo sắc nét của sản phẩm @Image2. "
        "Loại trừ: Mờ logo, biến dạng thân máy, lem màu điện thoại vào tay người mẫu."
    ),
]
# Mẫu E: KOL Giới Thiệu Cửa Hàng & Sản Phẩm (Shop KOL Commercial)
SAMPLE_E_PROMPTS = [
    (
        "[16:9, 10 giây]. Tham chiếu cấu trúc khuôn mặt và màu mắt nhân vật từ @Image1, không gian cửa hàng từ @Image2, và sản phẩm từ @Image3. "
        "Một nữ KOL thanh lịch đứng trong cửa hàng 'Điện Thoại Giá Tốt' với các kệ trưng bày điện thoại phía sau, mỉm cười thân thiện và cầm trên tay chiếc điện thoại iPhone 13 Pro Max màu xanh mint. "
        "Góc máy: Trung cận (Medium close-up) tracking mượt mà theo chuyển động tay và ánh mắt của cô gái. "
        "Nhịp cảnh: Giây 0-3 cô giơ điện thoại lên ngang ngực mỉm cười chào; giây 4-8 cô cất tiếng giới thiệu cửa hàng với khẩu hình tự nhiên; giây 9-10 nghiêng nhẹ máy khoe mặt lưng kim loại bóng bẩy. "
        'Lời thoại: Bằng giọng nữ ngọt ngào, cô nói: "Chào mừng các bạn đến với Điện Thoại Giá Tốt, iPhone 13 Pro Max bản xanh mint đã cập bến!" với chuyển động khẩu hình đồng bộ chuẩn xác. '
        "Âm thanh: Giọng nói rõ ràng trong trẻo, tiếng nhạc nền acoustic nhẹ nhàng, không gian ấm cúng. "
        "Bảo toàn: Diện mạo và ánh mắt từ @Image1, bối cảnh kệ hàng từ @Image2, màu sắc và cụm camera từ @Image3. "
        "Loại trừ: Lem màu sắc giữa các đối tượng, trôi dạt nhận diện, méo mó ngón tay."
    )
]


# Cấu hình Presets phân bổ vai trò các Slot ảnh
SLOT_PRESETS = {
    "turnaround_1p": {
        "title": "🎯 1 Nhân Vật 360° (Turnaround)",
        "hint": "💡 Khóa ID nhân vật 360° bằng 3 góc chuẩn:",
        "slots": [
            ("@Image1: Chính Diện", "Mặt nhìn thẳng, sáng rõ, khóa ngũ quan"),
            ("@Image2: Nghiêng 45°", "Khóa xương hàm, sống mũi, dáng đầu"),
            ("@Image3: Toàn Thân / Áo", "Khóa tỷ lệ cơ thể, chiều cao, màu áo"),
        ],
    },
    "two_actors": {
        "title": "👥 2 Nhân Vật Đối Thoại (Phim)",
        "hint": "💡 Phân chia ranh giới 2 diễn viên, chống lem thuộc tính:",
        "slots": [
            ("@Image1: Nhân Vật A (Trái)", "Người ở bên trái khung hình (Nam/Nữ)"),
            ("@Image2: Nhân Vật B (Phải)", "Người ở bên phải khung hình đối thoại"),
            ("@Image3: Bối Cảnh / Đạo Cụ", "Đạo cụ chung, không gian bối cảnh"),
        ],
    },
    "actor_and_product": {
        "title": "🛍️ Người & Sản Phẩm (TVC)",
        "hint": "💡 Diễn viên cầm/tương tác với sản phẩm hoặc thiết bị:",
        "slots": [
            ("@Image1: Diễn Viên Chính", "Người mẫu / Diễn viên trải nghiệm"),
            ("@Image2: Sản Phẩm Cận Cảnh", "Thiết bị, điện thoại, mỹ phẩm, đồng hồ"),
            ("@Image3: Logo / Hộp Bao Bì", "Bao bì, hộp sản phẩm hoặc logo thương hiệu"),
        ],
    },
    "shop_kol": {
        "title": "🏬 KOL & Shop & Sản Phẩm (TVC 3 Thực Thể)",
        "hint": "💡 Đồng bộ 3 thực thể: KOL + Không gian cửa hàng + Sản phẩm:",
        "slots": [
            ("@Image1: Người Mẫu / KOL", "Khuôn mặt, ánh mắt, người dẫn dắt chính"),
            ("@Image2: Cửa Hàng / Bối Cảnh", "Không gian showroom, kệ hàng, bảng hiệu"),
            ("@Image3: Sản Phẩm / Thiết Bị", "Điện thoại, góc cạnh máy, màu sắc"),
        ],
    },
    "multi_products": {
        "title": "📦 Đa Sản Phẩm / Đạo Cụ",
        "hint": "💡 Quảng cáo so sánh hoặc bộ combo 2-3 thiết bị:",
        "slots": [
            ("@Image1: Sản Phẩm A", "Thiết bị chính / Phiên bản A"),
            ("@Image2: Sản Phẩm B", "Thiết bị phụ / Phiên bản B so sánh"),
            ("@Image3: Phụ Kiện / Bao Bì", "Hộp quà, phụ kiện, đế sạc đi kèm"),
        ],
    },
}


class ImageSlotWidget(QFrame):
    """Widget quản lý 1 slot ảnh tham chiếu (Dạng thẻ ngang Horizontal Card nhỏ gọn trong cột dọc)."""

    image_changed = pyqtSignal(int, str)
    remove_slot_requested = pyqtSignal(int)

    def __init__(
        self,
        slot_index: int,
        slot_label: str,
        slot_desc: str,
        can_remove: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.slot_index = slot_index
        self.slot_label = slot_label
        self.slot_desc = slot_desc
        self.image_path: str = ""
        self.can_remove = can_remove
        self.setAcceptDrops(True)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet(
            """
            ImageSlotWidget {
                background-color: #0f172a;
                border: 1px dashed #334155;
                border-radius: 8px;
            }
            ImageSlotWidget:hover {
                border-color: #38bdf8;
            }
            """
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Thumbnail Preview bên trái (68x68 px)
        self.lbl_preview = QLabel("👤\nChọn ảnh")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setFixedSize(68, 68)
        self.lbl_preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_preview.setToolTip("Nhấp để chọn file ảnh hoặc kéo thả ảnh vào đây")
        self.lbl_preview.setStyleSheet(
            "background-color: #111827; border: 1px solid #1e293b; border-radius: 6px; "
            "color: #64748b; font-size: 10px; font-weight: 600; line-height: 1.2;"
        )
        self.lbl_preview.mousePressEvent = self._on_preview_clicked
        layout.addWidget(self.lbl_preview)

        # Cột thông tin & nút bên phải
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(3)

        self.lbl_title = QLabel(self.slot_label)
        self.lbl_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #38bdf8;")
        info_layout.addWidget(self.lbl_title)

        self.lbl_hint = QLabel(self.slot_desc)
        self.lbl_hint.setWordWrap(True)
        self.lbl_hint.setStyleSheet("font-size: 10px; color: #94a3b8; line-height: 1.2;")
        info_layout.addWidget(self.lbl_hint)

        info_layout.addStretch()

        # Hàng nút thao tác
        btn_box = QHBoxLayout()
        btn_box.setSpacing(6)

        self.btn_browse = QPushButton("📂 Chọn")
        self.btn_browse.setFixedHeight(22)
        self.btn_browse.setStyleSheet(
            "QPushButton { font-size: 10px; font-weight: 600; padding: 0 8px; background-color: #1e293b; color: #38bdf8; border: 1px solid #0284c7; border-radius: 4px; } "
            "QPushButton:hover { background-color: #0284c7; color: #ffffff; }"
        )
        self.btn_browse.clicked.connect(self._browse_image)
        btn_box.addWidget(self.btn_browse)

        self.btn_clear = QPushButton("❌ Xóa")
        self.btn_clear.setFixedHeight(22)
        self.btn_clear.setStyleSheet(
            "QPushButton { font-size: 10px; padding: 0 8px; color: #f87171; background-color: #1e293b; border: 1px solid #475569; border-radius: 4px; } "
            "QPushButton:hover { background-color: #7f1d1d; color: #ffffff; border-color: #ef4444; }"
        )
        self.btn_clear.clicked.connect(self.clear_image)
        btn_box.addWidget(self.btn_clear)

        self.btn_remove_slot = QPushButton("🗑️ Gỡ")
        self.btn_remove_slot.setFixedHeight(22)
        self.btn_remove_slot.setStyleSheet(
            "QPushButton { font-size: 10px; padding: 0 6px; color: #f43f5e; background-color: #27121b; border: 1px solid #881337; border-radius: 4px; } "
            "QPushButton:hover { background-color: #e11d48; color: #ffffff; border-color: #f43f5e; }"
        )
        self.btn_remove_slot.setToolTip(f"Gỡ bỏ Slot @Image{self.slot_index}")
        self.btn_remove_slot.clicked.connect(self._on_remove_clicked)
        self.btn_remove_slot.setVisible(self.can_remove)
        btn_box.addWidget(self.btn_remove_slot)

        btn_box.addStretch()
        info_layout.addLayout(btn_box)

        layout.addLayout(info_layout, 1)

    def _on_preview_clicked(self, event) -> None:
        self._browse_image()

    def _on_remove_clicked(self) -> None:
        self.remove_slot_requested.emit(self.slot_index)

    def set_removable(self, removable: bool) -> None:
        self.can_remove = removable
        if hasattr(self, "btn_remove_slot"):
            self.btn_remove_slot.setVisible(removable)

    def set_slot_index(self, new_idx: int, default_label: str = "", default_desc: str = "") -> None:
        """Cập nhật lại slot_index khi một slot phía trước bị xóa."""
        old_idx = self.slot_index
        self.slot_index = new_idx
        if hasattr(self, "btn_remove_slot"):
            self.btn_remove_slot.setToolTip(f"Gỡ bỏ Slot @Image{self.slot_index}")
        if default_label:
            self.slot_label = default_label
            if hasattr(self, "lbl_title"):
                self.lbl_title.setText(default_label)
        elif self.slot_label.startswith(f"@Image{old_idx}:"):
            self.slot_label = self.slot_label.replace(f"@Image{old_idx}:", f"@Image{new_idx}:", 1)
            if hasattr(self, "lbl_title"):
                self.lbl_title.setText(self.slot_label)
        else:
            self.slot_label = f"@Image{new_idx}: Bổ sung / Góc khác"
            if hasattr(self, "lbl_title"):
                self.lbl_title.setText(self.slot_label)
        if default_desc:
            self.slot_desc = default_desc
            if hasattr(self, "lbl_hint"):
                self.lbl_hint.setText(default_desc)

    def _browse_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Chọn ảnh cho {self.slot_label}", "", "Images (*.png *.jpg *.jpeg *.webp);;All Files (*.*)"
        )
        if file_path:
            self.set_image(file_path)

    def set_image(self, path: str) -> None:
        if not path or not os.path.isfile(path):
            return
        self.image_path = os.path.abspath(path)
        pix = QPixmap(self.image_path)
        if not pix.isNull():
            scaled = pix.scaled(
                64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_preview.setPixmap(scaled)
            self.lbl_preview.setStyleSheet("border: 1px solid #059669; border-radius: 6px; background-color: #022c22;")
            self.setStyleSheet("ImageSlotWidget { background-color: #062b1e; border: 1px solid #10b981; border-radius: 8px; }")
            self.setToolTip(f"{self.slot_label}\nFile: {Path(path).name}\nĐường dẫn: {self.image_path}")
        self.image_changed.emit(self.slot_index, self.image_path)

    def clear_image(self) -> None:
        self.image_path = ""
        self.lbl_preview.clear()
        self.lbl_preview.setText("👤\nChọn ảnh")
        self.lbl_preview.setStyleSheet("background-color: #111827; border: 1px solid #1e293b; border-radius: 6px; color: #64748b; font-size: 10px; font-weight: 600;")
        self.setStyleSheet("ImageSlotWidget { background-color: #0f172a; border: 1px dashed #334155; border-radius: 8px; }")
        self.setToolTip("")
        self.image_changed.emit(self.slot_index, "")

    def update_slot_meta(self, new_label: str, new_desc: str) -> None:
        """Cập nhật nhãn và mô tả của slot khi chuyển đổi Preset."""
        self.slot_label = new_label
        self.slot_desc = new_desc
        if hasattr(self, 'lbl_title'):
            self.lbl_title.setText(new_label)
        if hasattr(self, 'lbl_hint'):
            self.lbl_hint.setText(new_desc)
        if self.image_path:
            self.setToolTip(f"{self.slot_label}\nFile: {Path(self.image_path).name}\nĐường dẫn: {self.image_path}")

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path and path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                self.set_image(path)


class CharacterStudioTab(QWidget):
    """
    Màn hình Xưởng Tạo Video Đồng Bộ Nhân Vật (Character Studio Tab).
    """

    start_batch_requested = pyqtSignal(list, dict)
    stop_batch_requested = pyqtSignal()

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.log_callback = log_callback
        self._is_running = False
        self.reference_images: List[str] = ["", "", ""]  # [slot1, slot2, slot3]
        self.slots: List[ImageSlotWidget] = []

        self._init_ui()
        self.populate_accounts()

    def _log(self, msg: str) -> None:
        if callable(self.log_callback):
            self.log_callback(msg)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # Box lớn bao quanh
        studio_box = QGroupBox("👤 KỊCH BẢN & BỘ ẢNH ĐỒNG BỘ NHÂN VẬT")
        studio_box_layout = QVBoxLayout(studio_box)
        studio_box_layout.setContentsMargins(10, 10, 10, 10)
        studio_box_layout.setSpacing(8)

        # ---------------------------------------------------------------------
        # 1. Chế độ làm việc (Có ảnh tham chiếu vs Không kèm ảnh)
        # ---------------------------------------------------------------------
        mode_box = QFrame()
        mode_box.setStyleSheet("background-color: #0b1329; border: 1px solid #1e293b; border-radius: 6px;")
        mode_box_layout = QHBoxLayout(mode_box)
        mode_box_layout.setContentsMargins(10, 6, 10, 6)
        mode_box_layout.setSpacing(16)

        lbl_mode_title = QLabel("🎯 Chế độ:")
        lbl_mode_title.setStyleSheet("font-weight: 700; color: #38bdf8; font-size: 11px;")
        mode_box_layout.addWidget(lbl_mode_title)

        self.radio_with_images = QRadioButton("🌟 Có ảnh tham chiếu (@Image1, @Image2, @Image3)")
        self.radio_with_images.setChecked(True)
        self.radio_with_images.setStyleSheet("font-weight: 700; color: #34d399; font-size: 11px;")
        self.radio_with_images.toggled.connect(self._on_mode_toggled)
        mode_box_layout.addWidget(self.radio_with_images)

        self.radio_text_only = QRadioButton("✍️ Không kèm ảnh (Text-Only)")
        self.radio_text_only.setStyleSheet("font-weight: 600; color: #cbd5e1; font-size: 11px;")
        mode_box_layout.addWidget(self.radio_text_only)
        mode_box_layout.addStretch()

        studio_box_layout.addWidget(mode_box, 0)

        # ---------------------------------------------------------------------
        # 2. KHU VỰC CHÍNH DÙNG QSPLITTER NGANG (TRÁI: KỊCH BẢN | PHẢI: BỘ ẢNH)
        # ---------------------------------------------------------------------
        self.center_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- A. CỘT TRÁI: Trình Soạn Thảo Kịch Bản Phân Cảnh (Bung 100% chiều cao) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        # Toolbar Soạn Thảo
        tb_layout = QHBoxLayout()
        tb_layout.setSpacing(6)

        self.lbl_count_badge = QLabel("📝 0 cảnh")
        self.lbl_count_badge.setStyleSheet(
            "background: #1e293b; color: #38bdf8; font-weight: 700; font-size: 11px; "
            "padding: 3px 8px; border-radius: 6px; border: 1px solid #0284c7;"
        )
        tb_layout.addWidget(self.lbl_count_badge)

        self.btn_load_sample_a = QPushButton("💡 Mẫu A (Có Ảnh)")
        self.btn_load_sample_a.setFixedHeight(28)
        self.btn_load_sample_a.setStyleSheet("font-size: 11px; padding: 0 6px; color: #34d399; font-weight: 600;")
        self.btn_load_sample_a.setToolTip("Nạp kịch bản mẫu nữ thám tử đi trong mưa có ảnh tham chiếu")
        self.btn_load_sample_a.clicked.connect(self._load_sample_a)
        tb_layout.addWidget(self.btn_load_sample_a)

        self.btn_load_sample_b = QPushButton("💡 Mẫu B (Text)")
        self.btn_load_sample_b.setFixedHeight(28)
        self.btn_load_sample_b.setStyleSheet("font-size: 11px; padding: 0 6px; color: #f59e0b; font-weight: 600;")
        self.btn_load_sample_b.setToolTip("Nạp kịch bản mẫu bác sĩ phẫu thuật khởi tạo bằng Text")
        self.btn_load_sample_b.clicked.connect(self._load_sample_b)
        tb_layout.addWidget(self.btn_load_sample_b)

        self.btn_load_sample_c = QPushButton("👥 Mẫu C (2 Người)")
        self.btn_load_sample_c.setFixedHeight(28)
        self.btn_load_sample_c.setStyleSheet("font-size: 11px; padding: 0 6px; color: #a855f7; font-weight: 600;")
        self.btn_load_sample_c.setToolTip("Nạp kịch bản 2 nhân vật đối thoại mặt-đối-mặt (Chống lem thuộc tính)")
        self.btn_load_sample_c.clicked.connect(self._load_sample_c)
        tb_layout.addWidget(self.btn_load_sample_c)

        self.btn_load_sample_d = QPushButton("🛍️ Mẫu D (TVC)")
        self.btn_load_sample_d.setFixedHeight(28)
        self.btn_load_sample_d.setStyleSheet("font-size: 11px; padding: 0 6px; color: #ec4899; font-weight: 600;")
        self.btn_load_sample_d.setToolTip("Nạp kịch bản Người mẫu tương tác với Sản phẩm TVC")
        self.btn_load_sample_d.clicked.connect(self._load_sample_d)
        tb_layout.addWidget(self.btn_load_sample_d)

        self.btn_load_sample_e = QPushButton("🏬 Mẫu E (Shop KOL)")
        self.btn_load_sample_e.setFixedHeight(28)
        self.btn_load_sample_e.setStyleSheet("font-size: 11px; padding: 0 6px; color: #06b6d4; font-weight: 600;")
        self.btn_load_sample_e.setToolTip("Nạp kịch bản Người mẫu KOL giới thiệu cửa hàng Điện Thoại Giá Tốt & iPhone 13 Pro Max")
        self.btn_load_sample_e.clicked.connect(self._load_sample_e)
        tb_layout.addWidget(self.btn_load_sample_e)

        # Nút Chèn Cú Pháp Nhanh
        self.btn_insert_syntax = QPushButton("📋 Cú Pháp ▾")
        self.btn_insert_syntax.setFixedHeight(28)
        self.btn_insert_syntax.setStyleSheet("font-size: 11px; padding: 0 6px; color: #cbd5e1;")
        self.btn_insert_syntax.clicked.connect(self._show_syntax_menu)
        tb_layout.addWidget(self.btn_insert_syntax)

        tb_layout.addStretch()

        self.btn_character_guide = QPushButton("📖 Cẩm Nang")
        self.btn_character_guide.setFixedHeight(28)
        self.btn_character_guide.setStyleSheet(
            "font-size: 11px; padding: 0 8px; font-weight: 700; "
            "color: #38bdf8; background-color: #0f172a; border: 1px solid #0284c7; border-radius: 6px;"
        )
        self.btn_character_guide.setToolTip("Mở cẩm nang chuyên sâu về đồng bộ nhân vật, khẩu hình và ma trận đánh đổi")
        self.btn_character_guide.clicked.connect(self._open_character_guide)
        tb_layout.addWidget(self.btn_character_guide)

        self.btn_load_file = QPushButton("📂 Nạp TXT")
        self.btn_load_file.setFixedHeight(28)
        self.btn_load_file.setStyleSheet("font-size: 11px; padding: 0 6px;")
        self.btn_load_file.clicked.connect(self._load_txt_file)
        tb_layout.addWidget(self.btn_load_file)

        self.btn_clear = QPushButton("🧹 Xóa")
        self.btn_clear.setFixedHeight(28)
        self.btn_clear.setStyleSheet("font-size: 11px; padding: 0 6px;")
        self.btn_clear.clicked.connect(self._clear_editor)
        tb_layout.addWidget(self.btn_clear)

        left_layout.addLayout(tb_layout)

        # Trình Soạn Thảo Phân Cảnh (Bung 100% chiều cao)
        self.editor = NumberedPromptEdit()
        self.editor.setPlaceholderText(
            "Nhập kịch bản phân cảnh của nhân vật tại đây (Mỗi dòng là 1 cảnh quay liên tiếp #1, #2, #3...)...\n\n"
            "Ví dụ theo chuẩn Turnaround có ảnh tham chiếu:\n"
            "[16:9, 6 giây]. Tham chiếu cấu trúc khuôn mặt từ @Image1 và trang phục từ @Image2. Nữ thám tử 28 tuổi bước đi trong mưa, quay lại nói: 'Ai đã cho anh địa chỉ này?' với khẩu hình đồng bộ tự nhiên. Bảo toàn: Cấu trúc xương mặt, áo măng tô. Loại trừ: Trôi dạt nhận diện, biến dạng.\n"
            "[16:9, 6 giây]. Tham chiếu nhân vật từ @Image1. Nữ thám tử bước dưới mái hiên, nhìn xuống chiếc chìa khóa trong lòng bàn tay, thì thầm: 'Nó thực sự vừa vặn.' với cử động môi tinh tế. Bảo toàn: Đường nét khuôn mặt chuẩn xác."
        )
        self.editor.prompts_changed.connect(self._on_prompts_count_changed)
        left_layout.addWidget(self.editor, 1)

        # Thanh Hướng Dẫn Tiếng Việt Thu Gọn Dưới Editor
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
            "💡 <b>Cú pháp đồng bộ:</b> [@Image1/@Image2] + [Chủ thể] + [Hành động] + [Thoại Khẩu hình] + [Bảo toàn/Loại trừ]"
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
        self.btn_quick_popup.clicked.connect(self._open_character_guide)
        top_guide.addWidget(self.btn_quick_popup)

        guide_bar_layout.addLayout(top_guide)

        # Khung chi tiết ẩn mặc định
        self.guide_detail_widget = QWidget()
        self.guide_detail_widget.setVisible(False)
        detail_layout = QVBoxLayout(self.guide_detail_widget)
        detail_layout.setContentsMargins(2, 4, 2, 4)
        detail_layout.setSpacing(4)

        lbl_tips = QLabel(
            "• <b>Tại sao cần ảnh:</b> Để cố định ma trận vector ID qua các góc quay khác nhau, Muse Video bắt buộc cần visual tokens từ ảnh tham chiếu (@Image1, @Image2).<br/>"
            "• <b>Đồng bộ khẩu hình (Lip-sync):</b> Bắt buộc đặt thoại trong ngoặc kép: <code>nói: \"...\" với khẩu hình đồng bộ tự nhiên.</code> kèm định vị âm sắc.<br/>"
            "• <b>Lệnh bảo vệ bất biến:</b> Luôn cài đặt <code>Bảo toàn: [Dáng mặt, mắt, tóc, trang phục]</code> và <code>Loại trừ: [Trôi dạt nhận diện, biến dạng]</code>.<br/>"
            "• <b>Thời lượng shot:</b> Nên chia kịch bản thành các shot ngắn 4–6 giây để bảo toàn 100% độ sắc nét."
        )
        lbl_tips.setWordWrap(True)
        lbl_tips.setStyleSheet("color: #cbd5e1; font-size: 11px; line-height: 1.4;")
        detail_layout.addWidget(lbl_tips)

        guide_bar_layout.addWidget(self.guide_detail_widget)
        left_layout.addWidget(self.guide_bar, 0)

        # --- B. CỘT PHẢI: Bộ Ảnh Tham Chiếu Dọc (Hệ Thống Slot Động) ---
        self.slots_container = QFrame()
        self.slots_container.setMinimumWidth(280)
        self.slots_container.setMaximumWidth(380)
        self.slots_container.setStyleSheet(
            """
            QFrame {
                background-color: #0b1329;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
            """
        )
        slots_layout = QVBoxLayout(self.slots_container)
        slots_layout.setContentsMargins(10, 10, 10, 10)
        slots_layout.setSpacing(8)

        slots_header = QVBoxLayout()
        slots_header.setSpacing(6)

        header_top = QHBoxLayout()
        header_top.setSpacing(6)
        lbl_slots_title = QLabel("🖼️ BỘ ẢNH THAM CHIẾU")
        lbl_slots_title.setStyleSheet("font-weight: 800; font-size: 11px; color: #38bdf8;")
        header_top.addWidget(lbl_slots_title)
        header_top.addStretch()

        self.btn_add_slot = QPushButton("➕ Thêm Slot")
        self.btn_add_slot.setFixedHeight(24)
        self.btn_add_slot.setStyleSheet(
            "QPushButton { font-size: 10px; font-weight: 700; color: #34d399; background-color: #064e3b; "
            "border: 1px solid #059669; border-radius: 4px; padding: 0 8px; } "
            "QPushButton:hover { background-color: #059669; color: #ffffff; } "
            "QPushButton:disabled { background-color: #1e293b; color: #64748b; border-color: #334155; }"
        )
        self.btn_add_slot.setToolTip("Thêm một slot ảnh tham chiếu mới (Tối đa 6 slot: @Image1 đến @Image6)")
        self.btn_add_slot.clicked.connect(self._on_add_slot_clicked)
        header_top.addWidget(self.btn_add_slot)
        slots_header.addLayout(header_top)

        # Bộ chọn cấu trúc Slot linh hoạt (1 Người 360° / 2 Người / Người + Sản phẩm / Đa Sản phẩm / Shop KOL)
        self.combo_slot_preset = QComboBox()
        self.combo_slot_preset.setFixedHeight(26)
        self.combo_slot_preset.setStyleSheet(
            "QComboBox { background-color: #1e293b; color: #38bdf8; font-weight: 700; font-size: 10px; "
            "border: 1px solid #0284c7; border-radius: 4px; padding: 0 6px; } "
            "QComboBox::drop-down { border: none; } "
            "QComboBox QAbstractItemView { background-color: #0f172a; color: #f8fafc; selection-background-color: #0284c7; }"
        )
        for pkey, pdata in SLOT_PRESETS.items():
            self.combo_slot_preset.addItem(pdata["title"], pkey)
        self.combo_slot_preset.currentIndexChanged.connect(self._on_slot_preset_changed)
        slots_header.addWidget(self.combo_slot_preset)

        self.lbl_slots_tip = QLabel(SLOT_PRESETS["turnaround_1p"]["hint"])
        self.lbl_slots_tip.setStyleSheet("font-size: 10px; color: #64748b;")
        slots_header.addWidget(self.lbl_slots_tip)
        slots_layout.addLayout(slots_header)

        # QScrollArea chứa danh sách các Slot ảnh động cuộn dọc mượt mà
        self.slots_scroll = QScrollArea()
        self.slots_scroll.setWidgetResizable(True)
        self.slots_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.slots_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.slots_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.slots_scroll_content = QWidget()
        self.slots_scroll_content.setStyleSheet("background: transparent;")
        self.slots_list_layout = QVBoxLayout(self.slots_scroll_content)
        self.slots_list_layout.setContentsMargins(0, 0, 4, 0)
        self.slots_list_layout.setSpacing(6)

        self._init_default_slots()

        self.slots_scroll.setWidget(self.slots_scroll_content)
        slots_layout.addWidget(self.slots_scroll, 1)

        # Thêm Cột Trái & Cột Phải vào QSplitter
        self.center_splitter.addWidget(left_panel)
        self.center_splitter.addWidget(self.slots_container)
        self.center_splitter.setCollapsible(0, False)
        self.center_splitter.setCollapsible(1, True)
        self.center_splitter.setSizes([750, 320])

        studio_box_layout.addWidget(self.center_splitter, 1)

        main_layout.addWidget(studio_box, 1)

        # =====================================================================
        # THANH ĐIỀU KHIỂN ĐÁY SIÊU TINH GỌN (SLIM ACTION DOCK - CAO 34PX)
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

        # --- C. Nút Hành Động Hero (Bắt Đầu Tạo Video Đồng Bộ) ---
        self.btn_start = QPushButton("🚀 BẮT ĐẦU TẠO VIDEO ĐỒNG BỘ")
        self.btn_start.setFixedHeight(28)
        self.btn_start.setStyleSheet(
            "font-size: 11px; font-weight: 700; background: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 5px; padding: 0 14px;"
        )
        self.btn_start.setToolTip("Vui lòng nhập ít nhất 1 phân cảnh hoặc bấm 'Mẫu A' / 'Mẫu B' để bắt đầu")
        self.btn_start.clicked.connect(self._on_start_clicked)
        strip_layout.addWidget(self.btn_start)

        main_layout.addWidget(self.action_strip, 0)

    # =========================================================================
    # SỰ KIỆN & THAO TÁC
    # =========================================================================

    def _on_mode_toggled(self, checked: bool) -> None:
        """Ẩn/hiện khung tải ảnh khi đổi chế độ."""
        is_with_images = self.radio_with_images.isChecked()
        self.slots_container.setVisible(is_with_images)
        if is_with_images:
            self._log("🌟 Đã bật chế độ Có ảnh tham chiếu (Turnaround Set).")
        else:
            self._log("✍️ Đã chuyển sang chế độ Không kèm ảnh (Text-Only Continuity).")

    @property
    def slot1(self) -> Optional[ImageSlotWidget]:
        return self.slots[0] if len(self.slots) > 0 else None

    @property
    def slot2(self) -> Optional[ImageSlotWidget]:
        return self.slots[1] if len(self.slots) > 1 else None

    @property
    def slot3(self) -> Optional[ImageSlotWidget]:
        return self.slots[2] if len(self.slots) > 2 else None

    def _init_default_slots(self) -> None:
        """Khởi tạo 3 slot mặc định (@Image1, @Image2, @Image3)."""
        preset = SLOT_PRESETS["turnaround_1p"]["slots"]
        self.slots = []
        self.reference_images = ["", "", ""]
        for idx in range(1, 4):
            label, desc = preset[idx - 1]
            slot = ImageSlotWidget(
                slot_index=idx,
                slot_label=label,
                slot_desc=desc,
                can_remove=False,
                parent=self,
            )
            slot.image_changed.connect(self._on_slot_image_changed)
            slot.remove_slot_requested.connect(self._on_remove_slot_requested)
            self.slots.append(slot)
            self.slots_list_layout.addWidget(slot)
        self.slots_list_layout.addStretch()
        self._update_slots_removable_state()

    def _on_add_slot_clicked(self) -> None:
        """Thêm một slot ảnh tham chiếu mới (Tối đa 6 slot: @Image1 đến @Image6)."""
        if len(self.slots) >= 6:
            self._log("⚠️ Đã đạt giới hạn tối đa 6 Slot ảnh tham chiếu (@Image1 đến @Image6).")
            if self.isVisible():
                QMessageBox.information(
                    self,
                    "Giới hạn Slot ảnh",
                    "Đã đạt giới hạn tối đa 6 Slot ảnh tham chiếu (@Image1 đến @Image6) để đảm bảo hiệu năng tối ưu.",
                )
            return

        new_idx = len(self.slots) + 1
        label = f"@Image{new_idx}: Bổ sung / Góc khác"
        desc = f"Ảnh tham chiếu thứ {new_idx} cho nhân vật hoặc đối tượng"

        slot = ImageSlotWidget(
            slot_index=new_idx,
            slot_label=label,
            slot_desc=desc,
            can_remove=True,
            parent=self,
        )
        slot.image_changed.connect(self._on_slot_image_changed)
        slot.remove_slot_requested.connect(self._on_remove_slot_requested)

        # Xóa stretch cuối cùng trước khi thêm widget mới
        if self.slots_list_layout.count() > 0:
            item = self.slots_list_layout.takeAt(self.slots_list_layout.count() - 1)
            if item and item.spacerItem():
                del item

        self.slots.append(slot)
        self.reference_images.append("")
        self.slots_list_layout.addWidget(slot)
        self.slots_list_layout.addStretch()

        self._update_slots_removable_state()
        self._log(f"➕ Đã thêm Slot @Image{new_idx} (Tổng số slots: {len(self.slots)}/6).")

    def _on_remove_slot_requested(self, slot_idx: int) -> None:
        """Gỡ bỏ 1 slot ảnh và tái lập chỉ số index cho các slot còn lại."""
        if len(self.slots) <= 3:
            self._log("⚠️ Cần duy trì tối thiểu 3 slot ảnh tham chiếu cơ bản.")
            if self.isVisible():
                QMessageBox.warning(self, "Không thể gỡ", "Cần duy trì tối thiểu 3 slot ảnh tham chiếu cơ bản.")
            return

        target_idx = slot_idx - 1
        if 0 <= target_idx < len(self.slots):
            slot = self.slots.pop(target_idx)
            if target_idx < len(self.reference_images):
                self.reference_images.pop(target_idx)
            self.slots_list_layout.removeWidget(slot)
            slot.deleteLater()

            # Tái lập chỉ mục (re-index) cho các slot sau
            for i, s in enumerate(self.slots):
                new_idx = i + 1
                s.set_slot_index(new_idx)

            self._update_slots_removable_state()
            valid = self.get_valid_reference_images()
            self._log(f"🗑️ Đã gỡ bỏ Slot @Image{slot_idx}. Hiện còn {len(self.slots)} slots (Tổng {len(valid)} ảnh hợp lệ).")

    def _update_slots_removable_state(self) -> None:
        can_remove = len(self.slots) > 3
        for i, s in enumerate(self.slots):
            s.set_removable(can_remove and (i >= 3))
        if hasattr(self, "btn_add_slot"):
            self.btn_add_slot.setEnabled(len(self.slots) < 6)

    def _on_slot_image_changed(self, slot_index: int, path: str) -> None:
        """Cập nhật đường dẫn ảnh tham chiếu theo slot."""
        if 1 <= slot_index <= len(self.reference_images):
            self.reference_images[slot_index - 1] = path
            valid = self.get_valid_reference_images()
            self._log(f"🖼️ Đã cập nhật Slot @Image{slot_index}: {Path(path).name if path else '(Đã xóa)'} (Tổng {len(valid)} ảnh)")

    def get_valid_reference_images(self) -> List[str]:
        """Lấy danh sách các ảnh tham chiếu hợp lệ đã tải lên."""
        if self.radio_text_only.isChecked():
            return []
        valid: List[str] = []
        for s in self.slots:
            if s.image_path and os.path.isfile(s.image_path):
                valid.append(s.image_path)
        return valid

    def _toggle_guide_detail(self) -> None:
        is_hidden = self.guide_detail_widget.isHidden()
        self.guide_detail_widget.setHidden(not is_hidden)
        if is_hidden:
            self.btn_toggle_guide.setText("🔼 Thu Gọn")
        else:
            self.btn_toggle_guide.setText("🔽 Xem Tóm Tắt")

    def _open_character_guide(self) -> None:
        dialog = CharacterGuideDialog(self)
        dialog.prompt_selected.connect(self._on_guide_prompt_selected)
        dialog.exec()

    def _on_guide_prompt_selected(self, prompt: str) -> None:
        current = self.editor.get_clean_prompts()
        if not current:
            self.editor.set_prompts_list([prompt])
        else:
            current.append(prompt)
            self.editor.set_prompts_list(current)
        self._log("💡 Đã nạp kịch bản mẫu từ cẩm nang đồng bộ vào xưởng.")

    def _show_syntax_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1e293b; color: #f8fafc; border: 1px solid #475569; } QMenu::item:selected { background-color: #2563eb; }")

        action1 = menu.addAction("Tham chiếu diện mạo từ @Image1 (Khuôn mặt/Người 1)")
        action2 = menu.addAction("và trang phục từ @Image2 (Quần áo/Người 2)")
        menu.addSeparator()
        action_spatial1 = menu.addAction("Định vị: Ở nửa bên trái khung hình, nhân vật từ @Image1...")
        action_spatial2 = menu.addAction("Định vị: Ở nửa bên phải khung hình, nhân vật từ @Image2...")
        action_interact = menu.addAction("Tương tác: @Image1 cầm trên tay phải sản phẩm từ @Image2...")
        menu.addSeparator()
        action3 = menu.addAction('Lời thoại: Cô ấy nói: "..." với khẩu hình đồng bộ tự nhiên.')
        action4 = menu.addAction('Bằng giọng nữ thì thầm gấp gáp: "..."')
        menu.addSeparator()
        action5 = menu.addAction("Bảo toàn: [Cấu trúc xương mặt, dáng mắt, màu tóc, trang phục]")
        action_antibleed = menu.addAction("Chống lem: Bảo toàn diện mạo @Image1 và @Image2, loại trừ lem màu")
        action6 = menu.addAction("Loại trừ: [Trôi dạt nhận diện, biến dạng khuôn mặt, thừa chi]")
        action7 = menu.addAction('Phụ đề xuất hiện ở giữa đáy màn hình: "..."')

        chosen = menu.exec(self.btn_insert_syntax.mapToGlobal(self.btn_insert_syntax.rect().bottomLeft()))
        if chosen == action1:
            self.editor.insertPlainText("Tham chiếu cấu trúc khuôn mặt và màu mắt nhân vật từ @Image1 ")
        elif chosen == action2:
            self.editor.insertPlainText("và trang phục cổ điển từ @Image2. ")
        elif chosen == action_spatial1:
            self.editor.insertPlainText("Ở nửa bên trái khung hình, nhân vật từ @Image1 ")
        elif chosen == action_spatial2:
            self.editor.insertPlainText("đứng đối diện với nhân vật từ @Image2 ở nửa bên phải khung hình. ")
        elif chosen == action_interact:
            self.editor.insertPlainText("Nhân vật từ @Image1 dùng tay phải nâng sản phẩm từ @Image2 lên hướng về ống kính, ánh đèn studio quét qua bề mặt sang trọng. ")
        elif chosen == action3:
            self.editor.insertPlainText('Lời thoại: Cô ấy nói: "Chúng ta phải đi ngay." với khẩu hình đồng bộ chuẩn xác. ')
        elif chosen == action4:
            self.editor.insertPlainText('Bằng giọng nữ thì thầm gấp gáp: "Coi chừng đấy." ')
        elif chosen == action5:
            self.editor.insertPlainText("Bảo toàn: Cấu trúc xương mặt, dáng mắt, màu tóc, chất liệu áo khoác. ")
        elif chosen == action_antibleed:
            self.editor.insertPlainText("Bảo toàn: Diện mạo và trang phục độc lập của @Image1 ở bên trái và @Image2 ở bên phải. Loại trừ: Lem màu sắc giữa @Image1 và @Image2, lai tạp ngũ quan. ")
        elif chosen == action6:
            self.editor.insertPlainText("Loại trừ: Trôi dạt nhận diện, biến dạng khuôn mặt, thay đổi trang phục, thừa chi. ")
        elif chosen == action7:
            self.editor.insertPlainText('Phụ đề xuất hiện ở giữa đáy màn hình: "Chúng ta phải đi ngay.", đồng bộ chuẩn xác với nhịp nói. ')

    def _on_slot_preset_changed(self, index: int) -> None:
        """Cập nhật các Slot ảnh khi người dùng chọn Preset cấu trúc đối tượng."""
        preset_key = self.combo_slot_preset.currentData()
        preset = SLOT_PRESETS.get(preset_key)
        if not preset:
            return
        if hasattr(self, 'lbl_slots_tip'):
            self.lbl_slots_tip.setText(preset["hint"])
        slots_meta = preset["slots"]
        for i, meta in enumerate(slots_meta):
            if i < len(self.slots):
                self.slots[i].update_slot_meta(meta[0], meta[1])
        self._log(f"🌟 Đã chuyển cấu trúc Slots sang: {preset['title']}")

    def _load_sample_e(self) -> None:
        """Nạp kịch bản mẫu KOL Giới Thiệu Cửa Hàng & Sản Phẩm (Mẫu E)."""
        self.radio_with_images.setChecked(True)
        idx = self.combo_slot_preset.findData("shop_kol")
        if idx >= 0:
            self.combo_slot_preset.setCurrentIndex(idx)
        self.editor.set_prompts_list(SAMPLE_E_PROMPTS)
        self._log("💡 Đã nạp Mẫu E (KOL giới thiệu Cửa Hàng & iPhone 13 Pro Max đa thực thể).")

    def _load_sample_c(self) -> None:
        """Nạp kịch bản mẫu 2 Nhân vật đối thoại (Mẫu C)."""
        self.radio_with_images.setChecked(True)
        idx = self.combo_slot_preset.findData("two_actors")
        if idx >= 0:
            self.combo_slot_preset.setCurrentIndex(idx)
        self.editor.set_prompts_list(SAMPLE_C_PROMPTS)
        self._log("💡 Đã nạp Mẫu C (2 Nhân vật đối thoại: Nữ văn phòng & Nam thám tử) gồm 2 phân cảnh.")

    def _load_sample_d(self) -> None:
        """Nạp kịch bản mẫu Diễn viên & Sản phẩm TVC (Mẫu D)."""
        self.radio_with_images.setChecked(True)
        idx = self.combo_slot_preset.findData("actor_and_product")
        if idx >= 0:
            self.combo_slot_preset.setCurrentIndex(idx)
        self.editor.set_prompts_list(SAMPLE_D_PROMPTS)
        self._log("💡 Đã nạp Mẫu D (Người mẫu trải nghiệm sản phẩm TVC thương mại).")

    def _load_sample_a(self) -> None:
        self.radio_with_images.setChecked(True)
        self.editor.set_prompts_list(SAMPLE_A_PROMPTS)
        self._log("💡 Đã nạp Mẫu A (Có ảnh tham chiếu: Nữ thám tử 28 tuổi trong mưa) gồm 2 phân cảnh.")

    def _load_sample_b(self) -> None:
        self.radio_text_only.setChecked(True)
        self.editor.set_prompts_list(SAMPLE_B_PROMPTS)
        self._log("💡 Đã nạp Mẫu B (Không kèm ảnh: Bác sĩ phẫu thuật Dr. Thorne).")

    def _load_txt_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn File Kịch Bản (.txt)", "", "Text Files (*.txt *.prompts);;All Files (*.*)"
        )
        if not file_path:
            return
        try:
            content = Path(file_path).read_text(encoding="utf-8")
            self.editor.setPlainText(content)
            self._log(f"📂 Đã nạp kịch bản phân cảnh từ: {Path(file_path).name}")
        except Exception:
            try:
                content = Path(file_path).read_text(encoding="cp1252")
                self.editor.setPlainText(content)
            except Exception as e:
                QMessageBox.warning(self, "Lỗi đọc file", f"Không thể đọc file: {e}")

    def _clear_editor(self) -> None:
        if self.editor.prompt_count() > 0:
            reply = QMessageBox.question(
                self,
                "Xác nhận xóa",
                "Bạn có chắc muốn xóa trắng toàn bộ kịch bản phân cảnh hiện có?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.editor.clear_prompts()
        else:
            self.editor.clear_prompts()

    def _show_account_popup_menu(self) -> None:
        """Mở menu popup chọn chế độ xoay tua hoặc chỉ định tài khoản cố định."""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #0f172a; color: #f8fafc; border: 1px solid #334155; padding: 4px; border-radius: 6px; } "
            "QMenu::item { padding: 6px 14px; border-radius: 4px; } "
            "QMenu::item:selected { background-color: #0284c7; } "
            "QMenu::separator { height: 1px; background: #334155; margin: 4px 0; }"
        )

        act_rotate = menu.addAction("🔄 Xoay tua tự động tất cả tài khoản (Khuyên dùng)")
        act_rotate.setCheckable(True)
        act_rotate.setChecked(self.radio_rotation.isChecked())

        menu.addSeparator()

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
        self.lbl_count_badge.setText(f"📝 {count} cảnh")
        if not self._is_running:
            if count > 0:
                self.btn_start.setText(f"🚀 BẮT ĐẦU TẠO ({count} CẢNH)")
                self.btn_start.setStyleSheet(
                    "font-size: 11px; font-weight: 800; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981); color: #ffffff; border-radius: 5px; padding: 0 14px;"
                )
                self.btn_start.setToolTip(f"Bắt đầu khởi chạy tạo {count} video phân cảnh đồng bộ")
            else:
                self.btn_start.setText("🚀 BẮT ĐẦU TẠO VIDEO ĐỒNG BỘ")
                self.btn_start.setStyleSheet(
                    "font-size: 11px; font-weight: 700; background: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 5px; padding: 0 12px;"
                )
                self.btn_start.setToolTip("Vui lòng nhập ít nhất 1 phân cảnh hoặc bấm nạp kịch bản mẫu")

    def _on_account_mode_toggled(self, checked: bool) -> None:
        self.combo_specific_account.setEnabled(self.radio_single.isChecked())
        self._update_account_pill_label()

    def populate_accounts(self) -> None:
        self.combo_specific_account.clear()
        accounts: list = []
        if os.path.exists(MUSE2API_ACCOUNTS_FILE):
            try:
                with open(MUSE2API_ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    accounts = json.load(f)
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

    def _on_start_clicked(self) -> None:
        prompts = self.editor.get_clean_prompts()
        if not prompts:
            QMessageBox.warning(
                self,
                "Chưa có kịch bản",
                "Vui lòng nhập ít nhất 1 phân cảnh hoặc bấm 'Mẫu A' / 'Mẫu B' trước khi bắt đầu!",
            )
            return

        ref_imgs = self.get_valid_reference_images()
        if self.radio_with_images.isChecked() and not ref_imgs:
            reply = QMessageBox.question(
                self,
                "Chưa tải ảnh tham chiếu",
                "Bạn đang chọn chế độ 'Có ảnh tham chiếu' nhưng chưa tải ảnh nào vào các Slot (@Image1, @Image2, @Image3).\n\n"
                "Bạn có muốn tiếp tục tạo video chỉ bằng văn bản (Text-Only) không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

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

        st = SettingsManager.load_muse_settings()
        timeout_sec = int(st.get("task_timeout_seconds", 360))
        max_retries = int(st.get("max_retries", 2))
        dl_dir = st.get("download_dir", str(MUSE_DOWNLOADS_DIR))

        # Đóng gói cấu hình dự án
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
            "reference_images": ref_imgs if ref_imgs else None,
            "reference_image": ref_imgs[0] if len(ref_imgs) == 1 else (ref_imgs if ref_imgs else None),
        }

        self.set_running_state(True)
        self.start_batch_requested.emit(prompts, config)
        self._log(
            f"🚀 [CHARACTER STUDIO] Bắt đầu tạo chuỗi {len(prompts)} video phân cảnh đồng bộ nhân vật "
            f"({len(ref_imgs)} ảnh tham chiếu)..."
        )

    def set_running_state(self, running: bool) -> None:
        self._is_running = running
        if running:
            self.btn_start.setEnabled(False)
            self.btn_start.setText("⚡ ĐANG TẠO CHUỖI VIDEO ĐỒNG BỘ...")
            self.btn_start.setStyleSheet(
                "font-size: 13px; font-weight: 800; background-color: #312e81; color: #a5b4fc; border: 1px solid #6366f1; border-radius: 8px;"
            )
        else:
            self.btn_start.setEnabled(True)
            self.btn_start.setText("🚀 BẮT ĐẦU TẠO VIDEO ĐỒNG BỘ")
            self._on_prompts_count_changed(self.editor.prompt_count())
