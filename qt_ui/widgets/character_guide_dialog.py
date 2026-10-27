# -*- coding: utf-8 -*-
"""
Hộp thoại Cẩm Nang Hướng Dẫn Kỹ Thuật Đồng Bộ Nhân Vật (Character Consistency) trong Muse AI.
Biên soạn chuẩn xác theo tài liệu kỹ thuật Muse Video 2026:
- Trực ngôn kỹ thuật về Visual Tokens và Cross-Attention Conditioning.
- Quy chuẩn bộ ảnh Turnaround Set (@Image1, @Image2, @Image3).
- Đồng bộ khẩu hình Lip-Sync & Native Audio 3 tầng.
- Ma trận đánh đổi kỹ thuật & Quy trình sản xuất 4 bước.
- Thư viện Recipe Mẫu A (Có ảnh) và Mẫu B (Không ảnh).
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class CharacterRecipeCard(QFrame):
    """Card hiển thị kịch bản mẫu đồng bộ nhân vật có nút Nạp vào Xưởng và Sao chép."""

    load_requested = pyqtSignal(str)

    def __init__(
        self,
        title: str,
        category: str,
        badge_color: str,
        description: str,
        prompt_text: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.prompt_text = prompt_text
        self._init_ui(title, category, badge_color, description, prompt_text)

    def _init_ui(
        self,
        title: str,
        category: str,
        badge_color: str,
        description: str,
        prompt_text: str,
    ) -> None:
        self.setStyleSheet(
            """
            CharacterRecipeCard {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 8px;
                padding: 10px;
            }
            CharacterRecipeCard:hover {
                border-color: #38bdf8;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(lbl_title)

        lbl_badge = QLabel(f" {category} ")
        lbl_badge.setStyleSheet(
            f"background-color: {badge_color}22; color: {badge_color}; "
            f"border: 1px solid {badge_color}66; border-radius: 4px; "
            "font-size: 10px; font-weight: 700; padding: 2px 6px;"
        )
        header_layout.addWidget(lbl_badge)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        if description:
            lbl_desc = QLabel(description)
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
            layout.addWidget(lbl_desc)

        txt_box = QTextBrowser()
        txt_box.setPlainText(prompt_text)
        txt_box.setReadOnly(True)
        txt_box.setFixedHeight(95)
        txt_box.setStyleSheet(
            """
            QTextBrowser {
                background-color: #0b0f17;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 11px;
                padding: 6px;
            }
            """
        )
        layout.addWidget(txt_box)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_load = QPushButton("🚀 Nạp Vào Xưởng")
        self.btn_load.setFixedHeight(28)
        self.btn_load.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                color: #ffffff;
                font-weight: 700;
                font-size: 11px;
                border: 1px solid #34d399;
                border-radius: 5px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
            }
            """
        )
        self.btn_load.clicked.connect(lambda: self.load_requested.emit(self.prompt_text))
        btn_layout.addWidget(self.btn_load)

        self.btn_copy = QPushButton("📋 Sao Chép")
        self.btn_copy.setFixedHeight(28)
        self.btn_copy.setStyleSheet(
            """
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 600;
                border: 1px solid #475569;
                border-radius: 5px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
            """
        )
        self.btn_copy.clicked.connect(self._copy_prompt)
        btn_layout.addWidget(self.btn_copy)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

    def _copy_prompt(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.prompt_text)
            orig_text = self.btn_copy.text()
            self.btn_copy.setText("✅ Đã Sao Chép!")
            self.btn_copy.setStyleSheet(
                """
                QPushButton {
                    background-color: #064e3b;
                    color: #34d399;
                    font-size: 11px;
                    font-weight: 700;
                    border: 1px solid #059669;
                    border-radius: 5px;
                    padding: 0 12px;
                }
                """
            )
            QTimer.singleShot(1500, lambda: self._reset_copy_btn(orig_text))

    def _reset_copy_btn(self, orig_text: str) -> None:
        self.btn_copy.setText(orig_text)
        self.btn_copy.setStyleSheet(
            """
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 600;
                border: 1px solid #475569;
                border-radius: 5px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
            """
        )


class CharacterGuideDialog(QDialog):
    """
    Hộp thoại Modal hiển thị Cẩm Nang Hướng Dẫn Đồng Bộ Nhân Vật Muse AI.
    Phát tín hiệu:
    - prompt_selected(str): Khi người dùng bấm 'Nạp Vào Xưởng'.
    """

    prompt_selected = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📖 Cẩm Nang Đồng Bộ Nhân Vật Chuẩn Muse AI (Character Consistency)")
        self.setMinimumSize(880, 620)
        self.resize(920, 660)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Banner
        header = QFrame()
        header.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:1 #1e1b4b);
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 10px;
            }
            """
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 6, 8, 6)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)
        lbl_title = QLabel("👤 HƯỚNG DẪN ĐỒNG BỘ NHÂN VẬT — MUSE AI (MUSE VIDEO)")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #38bdf8;")
        title_layout.addWidget(lbl_title)

        lbl_sub = QLabel(
            "Khóa ma trận ID Embedding • Bộ ảnh Turnaround (@Image1, @Image2, @Image3) • Đồng bộ khẩu hình Lip-Sync • Native Audio"
        )
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_layout.addWidget(lbl_sub)
        h_layout.addLayout(title_layout)
        h_layout.addStretch()

        badge = QLabel("Chuẩn Quốc Tế 2026")
        badge.setStyleSheet(
            "background-color: #0284c7; color: #ffffff; font-size: 10px; "
            "font-weight: 800; padding: 4px 10px; border-radius: 12px;"
        )
        h_layout.addWidget(badge)
        main_layout.addWidget(header)

        # Tab Widget 4 chuyên đề
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_tab_tech_truth_and_syntax(), "🎯 1. Trực Ngôn & Cấu Trúc")
        self.tabs.addTab(self._create_tab_lip_sync_audio(), "🗣️ 2. Khẩu Hình & Âm Thanh")
        self.tabs.addTab(self._create_tab_tradeoff_matrix(), "⚖️ 3. Ma Trận Đánh Đổi")
        self.tabs.addTab(self._create_tab_pipeline_and_recipes(), "🚀 4. Quy Trình & Mẫu Thực Chiến")
        main_layout.addWidget(self.tabs)

        # Footer Action Bar
        footer = QHBoxLayout()
        lbl_note = QLabel("💡 Mẹo: Nhấp 'Nạp Vào Xưởng' tại kịch bản mẫu để đưa ngay vào trình soạn thảo phân cảnh.")
        lbl_note.setStyleSheet("color: #64748b; font-size: 11px;")
        footer.addWidget(lbl_note)
        footer.addStretch()

        btn_close = QPushButton("Đóng")
        btn_close.setFixedWidth(100)
        btn_close.setFixedHeight(32)
        btn_close.clicked.connect(self.reject)
        footer.addWidget(btn_close)

        main_layout.addLayout(footer)

    # =========================================================================
    # TAB 1: TRỰC NGÔN KỸ THUẬT & CẤU TRÚC PROMPT
    # =========================================================================
    def _create_tab_tech_truth_and_syntax(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(10)

        browser = QTextBrowser()
        browser.setStyleSheet("background-color: #0b0f17; border: 1px solid #1e293b; border-radius: 6px; padding: 12px;")

        html_content = """
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #f1f5f9; line-height: 1.5; font-size: 13px; }
            h2 { color: #38bdf8; font-size: 15px; margin-top: 4px; margin-bottom: 8px; border-bottom: 1px solid #1e293b; padding-bottom: 4px; }
            h3 { color: #34d399; font-size: 13px; margin-top: 10px; margin-bottom: 6px; }
            p { margin: 4px 0; }
            .box-verdict { background-color: #1e1b4b; border-left: 4px solid #818cf8; padding: 8px 12px; border-radius: 4px; margin: 8px 0; }
            .box-formula { background-color: #0f172a; border: 1px solid #0284c7; padding: 10px 14px; border-radius: 6px; margin: 8px 0; font-family: Consolas, monospace; color: #38bdf8; font-size: 12px; }
            .tag { color: #f59e0b; font-weight: bold; }
            ul { margin: 4px 0 8px 16px; padding: 0; }
            li { margin: 3px 0; }
        </style>

        <h2>1. Trực Ngôn Kỹ Thuật: Có bắt buộc phải đính kèm ảnh không?</h2>

        <div class="box-verdict">
            <b>Kết Luận Cốt Lõi:</b><br/>
            • <b>Shot đơn lẻ (Clip 4–8 giây):</b> <span style="color:#34d399; font-weight:bold;">KHÔNG BẮT BUỘC</span>. Có thể dùng kỹ thuật <i>Text Identity Anchoring</i> (Neo danh tính văn bản siêu chi tiết kèm lệnh khóa bất biến).<br/>
            • <b>Video nhiều phân cảnh (Multi-shot / Storytelling / Phim nhân vật / IP Brand):</b> <span style="color:#f43f5e; font-weight:bold;">BẮT BUỘC 100% PHẢI CÓ ẢNH THAM CHIẾU (@Image)</span>.
        </div>

        <p><b>Lý do kỹ thuật:</b> Text embedding (CLIP/T5) chỉ định vị vùng phân phối xác suất chung (ví dụ: "cô gái châu Á 25 tuổi tóc ngắn" có thể đại diện cho hàng triệu khuôn mặt). Để cố định ma trận vector khuôn mặt (ID embedding) không bị trôi dạt (<i>drift</i>) hoặc biến dạng (<i>morphing</i>) qua các góc quay khác nhau, mô hình Muse Video bắt buộc phải có visual tokens từ ảnh đầu vào để điều kiện hóa (<i>cross-attention conditioning</i>).</p>

        <h2>2. Cấu Trúc Khi CÓ ĐÍNH KÈM ẢNH (Khuyến nghị cho Production)</h2>
        <div class="box-formula">
            [THỜI LƯỢNG + TỈ LỆ]. Tham chiếu diện mạo nhân vật [khuôn mặt/vóc dáng] từ @Image1 [và trang phục từ @Image2].<br/>
            [CHỦ THỂ] [HÀNH ĐỘNG VẬT LÝ QUAY ĐƯỢC] tại [BỐI CẢNH].<br/>
            Góc máy: [CỠ CẢNH + 1 CHUYỂN ĐỘNG CHÍNH].<br/>
            Nhịp cảnh: [TIẾN TRÌNH THỜI GIAN & BIỂU CẢM THEO GIÂY].<br/>
            Lời thoại: [NHÂN VẬT] nói: "[CÂU THOẠI CHUẨN XÁC]" với khẩu hình đồng bộ tự nhiên.<br/>
            Âm thanh: [TIẾNG ĐỘNG VA CHẠM FOLEY + ÂM THANH MÔI TRƯỜNG].<br/>
            Bảo toàn: [Cấu trúc xương mặt, dáng mắt, màu da, rẽ ngôi tóc, màu sắc trang phục].<br/>
            Loại trừ: [Trôi dạt nhận diện, biến dạng khuôn mặt, đổi màu áo, dị tật chi].
        </div>

        <h3>Quy chuẩn bộ ảnh đính kèm lý tưởng (Turnaround Set 2–3 ảnh):</h3>
        <ul>
            <li><span class="tag">@Image1 (Chính diện – Front Shot):</span> Rõ khuôn mặt, mắt nhìn thẳng, ánh sáng trung tính, không bị tóc che.</li>
            <li><span class="tag">@Image2 (Góc nghiêng 45°/90° – Three-quarter/Profile):</span> Khóa cấu trúc xương hàm, sống mũi và dáng đầu.</li>
            <li><span class="tag">@Image3 (Toàn thân – Full Body Outfit):</span> Khóa tỷ lệ cơ thể, chiều cao và chất liệu trang phục.</li>
        </ul>

        <h2>3. Cấu Trúc Khi KHÔNG CÓ ẢNH ĐÍNH KÈM (Text-Only Continuity)</h2>
        <p>Áp dụng khi tạo nhân vật hoàn toàn mới từ số 0 trong một shot đơn lẻ:</p>
        <div class="box-formula" style="color: #cbd5e1;">
            [THỜI LƯỢNG + TỈ LỆ]. Một cú máy quay liền mạch duy nhất về [ĐẶC ĐIỂM NHÂN KHẨU HỌC + NEO NHẬN DIỆN BẤT BIẾN: Tuổi chính xác, sắc tộc, hình học khuôn mặt, kiểu tóc, vết sẹo/nốt ruồi, chi tiết trang phục].<br/>
            [CHỦ THỂ] thực hiện [HÀNH ĐỘNG VẬT LÝ] tại [BỐI CẢNH]. Góc máy: [1 CHUYỂN ĐỘNG DUY NHẤT ĐƯỢC CÂN BẰNG].<br/>
            Nhịp cảnh: [BIỂU CẢM & MỐC THỜI GIAN].<br/>
            Lời thoại: [CÂU THOẠI] với khẩu hình đồng bộ tự nhiên. Âm thanh: [TIẾNG VA CHẠM + MÔI TRƯỜNG].<br/>
            Duy trì chính xác cùng một đối tượng nhân vật, ngũ quan khuôn mặt, mái tóc và trang phục nhất quán từ đầu đến cuối xuyên suốt cú máy không ngắt cắt.<br/>
            Bảo toàn: [Đặc điểm khuôn mặt cụ thể và trang phục].<br/>
            Loại trừ: [Hoán đổi nhận diện, biến dạng khuôn mặt, phụ kiện biến mất].
        </div>
        """
        browser.setHtml(html_content)
        layout.addWidget(browser)

        btn_copy = QPushButton("📋 Sao Chép Cấu Trúc Khung Rỗng (Multi-View Template) Vào Clipboard")
        btn_copy.setFixedHeight(30)
        btn_copy.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-weight: 700; border: 1px solid #0284c7; border-radius: 6px;")
        btn_copy.clicked.connect(self._copy_multiview_template)
        layout.addWidget(btn_copy)

        return widget

    def _copy_multiview_template(self) -> None:
        tpl = (
            "[16:9, 6 giây]. Tham chiếu cấu trúc khuôn mặt và màu mắt nhân vật từ @Image1, và trang phục từ @Image2.\n"
            "[CHỦ THỂ] [HÀNH ĐỘNG VẬT LÝ CỤ THỂ] tại [BỐI CẢNH].\n"
            "Góc máy: [CỠ CẢNH + 1 CHUYỂN ĐỘNG CHÍNH].\n"
            "Nhịp cảnh: Từ giây 0-3 [HÀNH ĐỘNG 1]; giây thứ 4 [HÀNH ĐỘNG 2]; giây thứ 5 cất lời.\n"
            'Lời thoại: [NHÂN VẬT] nói dứt khoát: "[CÂU THOẠI]" với khẩu hình đồng bộ chuẩn xác.\n'
            "Âm thanh: [TIẾNG VA CHẠM + MÔI TRƯỜNG, giọng nói rõ ràng ưu tiên hơn tiếng ồn nền].\n"
            "Bảo toàn: [Cấu trúc xương mặt, dáng mắt, màu tóc, chi tiết trang phục].\n"
            "Loại trừ: [Trôi dạt nhận diện, biến dạng khuôn mặt, đổi màu quần áo, thừa ngón tay]."
        )
        clip = QApplication.clipboard()
        if clip:
            clip.setText(tpl)

    # =========================================================================
    # TAB 2: KHẨU HÌNH (LIP-SYNC) & ÂM THANH BẢN ĐỊA
    # =========================================================================
    def _create_tab_lip_sync_audio(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(10)

        browser = QTextBrowser()
        browser.setStyleSheet("background-color: #0b0f17; border: 1px solid #1e293b; border-radius: 6px; padding: 12px;")

        html_content = """
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #f1f5f9; line-height: 1.5; font-size: 13px; }
            h2 { color: #38bdf8; font-size: 15px; margin-top: 4px; margin-bottom: 8px; border-bottom: 1px solid #1e293b; padding-bottom: 4px; }
            h3 { color: #f59e0b; font-size: 13px; margin-top: 10px; margin-bottom: 4px; }
            .code { background-color: #111827; border: 1px solid #334155; padding: 8px 12px; border-radius: 6px; font-family: Consolas, monospace; color: #e2e8f0; font-size: 12px; margin: 6px 0; }
            .hl { color: #34d399; font-weight: bold; }
        </style>

        <h2>Đồng Bộ Khẩu Hình (Lip-Sync) & Native Audio Cho Nhân Vật</h2>
        <p>Muse AI tích hợp Native Audio Engine đồng bộ trực tiếp với chuyển động cơ mặt. Để đạt độ chân thực tối đa, hãy tuân thủ 4 quy chuẩn sau:</p>

        <h3>1. Cú pháp lời thoại bắt buộc đặt trong ngoặc kép:</h3>
        <p>Phải có cụm từ điều khiển khớp khẩu hình tự nhiên:</p>
        <div class="code">
            Người phụ nữ ngước nhìn lên và nói: <b>"Chúng ta không còn nhiều thời gian nữa."</b> với khẩu hình đồng bộ tự nhiên.
        </div>

        <h3>2. Định vị âm sắc giọng nói (Voice Profile):</h3>
        <p>Mô tả chất giọng và cảm xúc phát âm ngay trước câu thoại để mô hình sinh đúng ngữ điệu:</p>
        <div class="code">
            Bằng giọng nữ thì thầm gấp gáp: <b>"Hãy nhìn phía sau anh kìa."</b><br/>
            hoặc: Bằng giọng nói vui tươi, rạng rỡ: <b>"Chào mừng mọi người đã về nhà!"</b>
        </div>

        <h3>3. Tích hợp phụ đề đồng bộ chạy chữ dưới đáy (Subtitles):</h3>
        <p>Nếu video cần phụ đề chữ xuất hiện đồng bộ với giọng nói:</p>
        <div class="code">
            <b>Phụ đề xuất hiện ở giữa đáy màn hình: "Chúng ta không còn nhiều thời gian nữa."</b>, đồng bộ hoàn hảo với nhịp điệu lời thoại.
        </div>

        <h3>4. Phân tầng âm lượng: Giọng nói phải ưu tiên trên tiếng ồn:</h3>
        <p>Tránh để tiếng nhạc hoặc tiếng gió lấn át hoàn toàn khẩu hình:</p>
        <div class="code">
            Âm thanh: tiếng gió xào xạc nhẹ, tiếng sấm ầm ì từ xa, <b>giọng nói rõ ràng và được ưu tiên cao hơn tiếng ồn nền</b>.
        </div>
        """
        browser.setHtml(html_content)
        layout.addWidget(browser)
        return widget

    # =========================================================================
    # TAB 3: MA TRẬN ĐÁNH ĐỔI KỸ THUẬT (TRADE-OFF MATRIX)
    # =========================================================================
    def _create_tab_tradeoff_matrix(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(10)

        browser = QTextBrowser()
        browser.setStyleSheet("background-color: #0b0f17; border: 1px solid #1e293b; border-radius: 6px; padding: 12px;")

        html_content = """
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #f1f5f9; line-height: 1.5; font-size: 13px; }
            h2 { color: #38bdf8; font-size: 15px; margin-top: 4px; margin-bottom: 8px; border-bottom: 1px solid #1e293b; padding-bottom: 4px; }
            table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 12px; }
            th { background-color: #1e293b; color: #94a3b8; text-align: left; padding: 8px 10px; border-bottom: 2px solid #334155; }
            td { padding: 8px 10px; border-bottom: 1px solid #1e293b; color: #cbd5e1; vertical-align: top; }
            .good { color: #34d399; font-weight: bold; }
            .med { color: #fbbf24; font-weight: bold; }
            .bad { color: #f87171; font-weight: bold; }
        </style>

        <h2>So Sánh 3 Phương Pháp Đồng Bộ Nhân Vật</h2>
        <p>Bảng phân tích đánh đổi kỹ thuật giúp bạn chọn phương án tối ưu tùy theo độ phức tạp của dự án:</p>

        <table>
            <tr>
                <th width="22%">Tiêu chí</th>
                <th width="26%">Text-Only Continuity (Không kèm ảnh)</th>
                <th width="26%">Single Image Ref (1 ảnh @Image1)</th>
                <th width="26%">Multi-View Turnaround (2–3 ảnh @Image)</th>
            </tr>
            <tr>
                <td><b>Độ ổn định khuôn mặt (ID Fidelity)</b></td>
                <td><span class="bad">⚠️ Kém</span><br/>Chỉ giữ được trong 1 shot; render lại shot 2 sẽ ra người khác.</td>
                <td><span class="med">🟡 Khá</span><br/>Tốt ở góc quay tương đương ảnh mẫu; dễ méo khi quay góc nghiêng.</td>
                <td><span class="good">🟢 Xuất sắc</span><br/>Khóa chặt ID 360 độ qua nhiều góc máy và phân cảnh khác nhau.</td>
            </tr>
            <tr>
                <td><b>Độ tự nhiên của chuyển động</b></td>
                <td><span class="good">🟢 Rất cao</span><br/>Mô hình tự do nội suy vật lý theo văn bản không bị gò bó.</td>
                <td><span class="med">🟡 Khá</span><br/>Đôi khi bị kéo dãn texture nếu góc quay lệch nhiều so với ảnh gốc.</td>
                <td><span class="good">🟢 Cao</span><br/>Có đủ dữ liệu không gian 3D để nội suy chuyển động mượt mà.</td>
            </tr>
            <tr>
                <td><b>Đồng bộ khẩu hình (Lip-sync)</b></td>
                <td><span class="med">🟡 Trung bình</span><br/>Dễ bị lệch khớp cơ miệng khi nói các âm khép môi (b, p, m).</td>
                <td><span class="good">🟢 Tốt</span><br/>Cơ miệng biến dạng theo đúng tỷ lệ khuôn mặt thực tế.</td>
                <td><span class="good">🟢 Tốt nhất</span><br/>Khẩu hình tự nhiên cả khi vừa nói vừa quay đầu qua lại.</td>
            </tr>
            <tr>
                <td><b>Độ phức tạp chuẩn bị Asset</b></td>
                <td><span class="good">🟢 0 bước</span><br/>Chỉ cần gõ văn bản kịch bản.</td>
                <td><span class="med">🟡 1 bước</span><br/>Tạo hoặc chụp 1 ảnh chân dung nét.</td>
                <td><span class="bad">🔴 2–3 bước</span><br/>Cần bảng nhân vật: Chính diện + Góc nghiêng + Toàn thân.</td>
            </tr>
        </table>
        """
        browser.setHtml(html_content)
        layout.addWidget(browser)
        return widget

    # =========================================================================
    # TAB 4: QUY TRÌNH SẢN XUẤT & MẪU THỰC CHIẾN
    # =========================================================================
    def _create_tab_pipeline_and_recipes(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        cards_layout = QVBoxLayout(container)
        cards_layout.setContentsMargins(0, 0, 4, 0)
        cards_layout.setSpacing(12)

        # Pipeline header
        lbl_pipe_title = QLabel("🚀 QUY TRÌNH SẢN XUẤT PHIM / SERIES NHÂN VẬT CHUẨN 4 BƯỚC:")
        lbl_pipe_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #38bdf8;")
        cards_layout.addWidget(lbl_pipe_title)

        lbl_steps = QLabel(
            "<b>• Bước 1: Khởi tạo 'Anchor Sheet' trước:</b> Dùng công cụ tạo ảnh để tạo bảng 2 ảnh: Chân dung nhìn thẳng (@Image1) và Góc nghiêng 45° (@Image2).<br/>"
            "<b>• Bước 2: Gắn thẻ bóc tách rành mạch:</b> Ghi rõ diện mạo lấy từ @Image1, trang phục lấy từ @Image2 (không viết gộp chung chung).<br/>"
            "<b>• Bước 3: Luôn cài đặt khối mệnh lệnh bảo vệ:</b> Thêm rõ ràng <code>Bảo toàn: [Dáng mặt, mắt, áo măng tô]</code> và <code>Loại trừ: [Trôi dạt nhận diện, biến dạng]</code>.<br/>"
            "<b>• Bước 4: Kiểm soát độ dài shot:</b> Chia kịch bản thành các shot ngắn 4–6 giây và ghép lại (splice) để đảm bảo 100% độ sắc nét."
        )
        lbl_steps.setWordWrap(True)
        lbl_steps.setStyleSheet(
            "background-color: #0b1329; border: 1px solid #1e293b; border-radius: 6px; padding: 10px; color: #cbd5e1; font-size: 11px; line-height: 1.5;"
        )
        cards_layout.addWidget(lbl_steps)

        # Mẫu thực chiến A
        card_a = CharacterRecipeCard(
            title="Mẫu A: Có Ảnh Tham Chiếu (@Image1 - Mặt, @Image2 - Trang Phục)",
            category="PRODUCTION MULTI-SHOT",
            badge_color="#34d399",
            description="Phân cảnh kể chuyện nữ thám tử 28 tuổi đi trong mưa, quay người lại đối chất kèm thoại có khẩu hình đồng bộ.",
            prompt_text=(
                "[16:9, 6 giây]. Tham chiếu cấu trúc khuôn mặt và màu mắt nhân vật từ @Image1, và áo măng tô cổ điển từ @Image2. "
                "Một nữ thám tử 28 tuổi bước đi thoăn thoắt qua con hẻm ướt đẫm mưa lúc chạng vạng, dừng lại dưới ngọn đèn đường chập chờn, rồi quay lại nhìn thẳng vào máy quay với biểu cảm dò xét, căng thẳng. "
                "Góc máy: Quay trung cảnh bám theo mượt mà lùi dần về phía trước mặt cô, rồi dừng lại ở cỡ cận trung. "
                "Nhịp cảnh: Từ giây 0-3 cô vừa đi vừa nhìn quanh; giây thứ 4 cô dừng bước, những giọt mưa rơi nhỏ tong tòng từ cổ áo; giây thứ 5 cô cất lời. "
                'Lời thoại: Cô nói dứt khoát: "Ai đã cho anh địa chỉ này?" với khẩu hình đồng bộ chuẩn xác và chuyển động quai hàm tự nhiên. '
                "Âm thanh: Tiếng bước chân ủng ướt vang vọng, tiếng mưa rào xối xả đập xuống mặt đường nhựa, tiếng ma sát sột soạt của áo khoác, giọng thoại phát ra rõ ràng. "
                "Bảo toàn: Cấu trúc xương mặt, tàn nhang trên sống mũi, chất tóc màu nâu đỏ, ve áo măng tô màu xanh rêu đậm. "
                "Loại trừ: Trôi dạt nhận diện, biến đổi kiểu áo, khẩu hình nhòe mờ, thừa ngón tay."
            ),
        )
        card_a.load_requested.connect(self._on_recipe_load)
        cards_layout.addWidget(card_a)

        # Mẫu thực chiến B
        card_b = CharacterRecipeCard(
            title="Mẫu B: Không Có Ảnh (Khởi Tạo Nhân Vật Gốc Bằng Text)",
            category="TEXT-ONLY CONTINUITY",
            badge_color="#f59e0b",
            description="Shot đơn giới thiệu bác sĩ phẫu thuật Dr. Aris Thorne 45 tuổi, kéo khẩu trang và nói 'Các chỉ số sinh tồn đã ổn định.'",
            prompt_text=(
                "[16:9, 5 giây]. Một cú máy quay liền mạch duy nhất về Bác sĩ Aris Thorne, một nam bác sĩ phẫu thuật 45 tuổi người Địa Trung Hải với mái tóc cắt ngắn hoa râm, làn da màu ô-liu lộ vẻ mệt mỏi, đường viền hàm sắc cạnh và một vết sẹo mờ phía trên lông mày trái, đang mặc trang phục phẫu thuật vô trùng màu xanh ngọc lam và đeo găng tay cao su. "
                "Ông kéo khẩu trang phẫu thuật xuống, thở phào nhẹ nhõm và ngước nhìn đồng nghiệp với ánh mắt trút bỏ gánh nặng. "
                "Góc máy: Đẩy tiến chậm cận cảnh, giữ tiêu điểm sắc nét vào đôi mắt và khuôn mặt ông. "
                "Nhịp cảnh: Ở giây thứ 2 tay phải ông kéo khẩu trang xuống dưới cằm; ở giây thứ 4 ông mỉm cười nhẹ và nói. "
                'Lời thoại: Bằng giọng nói trầm ấm, kiệt sức nhưng điềm tĩnh, ông nói: "Các chỉ số sinh tồn đã ổn định." với khẩu hình phát âm chuẩn xác. '
                "Âm thanh: Tiếng bíp nhịp nhàng đều đặn của máy đo điện tim ECG, tiếng vo ve êm của hệ thống thông khí phòng mổ, tiếng tách dây chun khẩu trang, giọng nói trầm rõ ràng. "
                "Duy trì chính xác cùng một đối tượng nhân vật, cấu trúc hình học khuôn mặt, chi tiết vết sẹo và trang phục nhất quán xuyên suốt từng khung hình không ngắt cắt. "
                "Bảo toàn: Vị trí vết sẹo, dáng tai, màu sắc bộ đồ mổ. "
                "Loại trừ: Biến dạng thành người khác, thay đổi độ dài tóc, méo mó bàn tay."
            ),
        )
        card_b.load_requested.connect(self._on_recipe_load)
        cards_layout.addWidget(card_b)

        # Mẫu thực chiến C (2 Nhân vật đối thoại)
        card_c = CharacterRecipeCard(
            title="Mẫu C: 2 Nhân Vật Đối Thoại (Chống Lem Thuộc Tính)",
            category="MULTI-ACTOR DIALOGUE",
            badge_color="#a855f7",
            description="Phân cảnh 2 nhân vật đối thoại mặt-đối-mặt trong phòng họp, áp dụng định vị không gian Screen-Left / Screen-Right.",
            prompt_text=(
                "[16:9, 6 giây]. Tham chiếu nhân vật nữ từ @Image1 ở bên trái khung hình và nhân vật nam từ @Image2 ở bên phải khung hình. "
                "Cú máy trung cảnh hai người (Two-shot medium) trong phòng họp văn phòng ánh sáng vàng dịu. "
                "Người phụ nữ (@Image1) quay sang nhìn thẳng vào mắt người đàn ông (@Image2), cất lời dứt khoát. "
                'Lời thoại: Người phụ nữ nói: "Hồ sơ này không thể để lộ ra ngoài." với khẩu hình đồng bộ tự nhiên, người đàn ông nhíu mày gật đầu. '
                "Âm thanh: Tiếng lật tài liệu sột soạt, tiếng điều hòa phòng họp êm dịu, giọng nói nữ rõ ràng. "
                "Bảo toàn: Khuôn mặt và áo sơ mi của @Image1, kiểu tóc và vest sẫm màu của @Image2, khoảng cách phân định rõ ràng giữa hai người. "
                "Loại trừ: Lem màu trang phục giữa @Image1 và @Image2, trôi dạt nhận diện, méo mó bàn tay."
            ),
        )
        card_c.load_requested.connect(self._on_recipe_load)
        cards_layout.addWidget(card_c)

        # Mẫu thực chiến D (Người mẫu & Sản phẩm TVC)
        card_d = CharacterRecipeCard(
            title="Mẫu D: Diễn Viên & Sản Phẩm TVC (Commercial)",
            category="ACTOR + PRODUCT TVC",
            badge_color="#ec4899",
            description="TVC thương mại: Người mẫu nâng sản phẩm thiết bị lên trước ống kính với ánh sáng studio xoay phản chiếu sang trọng.",
            prompt_text=(
                "[16:9, 6 giây]. Tham chiếu người mẫu từ @Image1 và sản phẩm điện thoại từ @Image2. "
                "Cú máy cận trung tracking mượt mà: Người mẫu (@Image1) mỉm cười thanh lịch, tay phải nâng chiếc điện thoại (@Image2) lên ngang ngực hướng về ống kính, ánh đèn studio quét qua viền máy phản chiếu ánh kim loại sang trọng. "
                'Lời thoại: Người mẫu nói: "Thiết kế thực sự đỉnh cao." với khẩu hình tươi tắn rạng rỡ. '
                "Âm thanh: Tiếng lách cách nhẹ của vỏ kim loại cao cấp, tiếng nhạc nền thương mại tinh tế. "
                "Bảo toàn: Nét mặt và thần thái của người mẫu @Image1, màu sắc và logo quả táo sắc nét của sản phẩm @Image2. "
                "Loại trừ: Mờ logo, biến dạng thân máy, lem màu điện thoại vào tay người mẫu."
            ),
        )
        card_d.load_requested.connect(self._on_recipe_load)
        cards_layout.addWidget(card_d)

        # Mẫu thực chiến E (Shop KOL & Đa Thực Thể)
        card_e = CharacterRecipeCard(
            title="Mẫu E: KOL Giới Thiệu Cửa Hàng & Sản Phẩm (Đa Thực Thể)",
            category="SHOP KOL + MULTI-ENTITY",
            badge_color="#06b6d4",
            description="Video thương mại thực tế: KOL giới thiệu showroom và sản phẩm TVC với 3 ảnh tham chiếu độc lập (@Image1 Người mẫu, @Image2 Cửa hàng, @Image3 Sản phẩm).",
            prompt_text=(
                "[16:9, 10 giây]. Tham chiếu cấu trúc khuôn mặt và màu mắt nhân vật từ @Image1, không gian cửa hàng từ @Image2, và sản phẩm từ @Image3. "
                "Một nữ KOL thanh lịch đứng trong cửa hàng 'Điện Thoại Giá Tốt' với các kệ trưng bày điện thoại phía sau, mỉm cười thân thiện và cầm trên tay chiếc điện thoại iPhone 13 Pro Max màu xanh mint. "
                "Góc máy: Trung cận (Medium close-up) tracking mượt mà theo chuyển động tay và ánh mắt của cô gái. "
                "Nhịp cảnh: Giây 0-3 cô giơ điện thoại lên ngang ngực mỉm cười chào; giây 4-8 cô cất tiếng giới thiệu cửa hàng với khẩu hình tự nhiên; giây 9-10 nghiêng nhẹ máy khoe mặt lưng kim loại bóng bẩy. "
                'Lời thoại: Bằng giọng nữ ngọt ngào, cô nói: "Chào mừng các bạn đến với Điện Thoại Giá Tốt, iPhone 13 Pro Max bản xanh mint đã cập bến!" với chuyển động khẩu hình đồng bộ chuẩn xác. '
                "Âm thanh: Giọng nói rõ ràng trong trẻo, tiếng nhạc nền acoustic nhẹ nhàng, không gian ấm cúng. "
                "Bảo toàn: Diện mạo và ánh mắt từ @Image1, bối cảnh kệ hàng từ @Image2, màu sắc và cụm camera từ @Image3. "
                "Loại trừ: Lem màu sắc giữa các đối tượng, trôi dạt nhận diện, méo mó ngón tay."
            ),
        )
        card_e.load_requested.connect(self._on_recipe_load)
        cards_layout.addWidget(card_e)

        cards_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        return widget

    def _on_recipe_load(self, prompt: str) -> None:
        self.prompt_selected.emit(prompt)
        self.accept()
