# -*- coding: utf-8 -*-
"""
Hộp thoại Cẩm Nang Hướng Dẫn Cấu Trúc Prompt Chuẩn Muse AI (Muse Video).
Thiết kế theo chuẩn "Production Shot Brief" (Bản ghi chú chỉ đạo sản xuất):
- 4 Chuyên đề: Cấu trúc Đạo diễn, Cú pháp Đa phương thức (@Image, @Video, Native Audio),
  Thư viện Recipe thực chiến (1-Click Nạp vào xưởng / Sao chép), và Khắc phục lỗi.
- Đầy đủ hướng dẫn Tiếng Việt chuẩn mực, chi tiết và trực quan.
"""

from __future__ import annotations

from typing import List, Optional
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class RecipeCard(QFrame):
    """Thẻ hiển thị một prompt mẫu thực chiến kèm nút 1-click nạp vào xưởng hoặc sao chép."""

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
            RecipeCard {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 8px;
                padding: 10px;
            }
            RecipeCard:hover {
                border-color: #38bdf8;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header: Title + Category Badge
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

        # Mô tả ngắn
        if description:
            lbl_desc = QLabel(description)
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
            layout.addWidget(lbl_desc)

        # Prompt Text box
        txt_box = QTextBrowser()
        txt_box.setPlainText(prompt_text)
        txt_box.setReadOnly(True)
        txt_box.setFixedHeight(85)
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

        # Nút thao tác: Nạp vào Xưởng & Sao chép
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


class PromptGuideDialog(QDialog):
    """
    Hộp thoại Modal hiển thị Cẩm Nang Cấu Trúc Prompt Chuẩn Muse Video.
    Phát tín hiệu:
    - prompt_selected(str): Khi người dùng bấm 'Nạp Vào Xưởng' cho 1 prompt.
    - prompts_batch_selected(list): Khi người dùng bấm 'Nạp Toàn Bộ Mẫu'.
    """

    prompt_selected = pyqtSignal(str)
    prompts_batch_selected = pyqtSignal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📖 Cẩm Nang Cấu Trúc Prompt Chuẩn Muse AI (Muse Video)")
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
        lbl_title = QLabel("🎬 HƯỚNG DẪN CẤU TRÚC PROMPT CHUẨN — MUSE AI (MUSE VIDEO)")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: 800; color: #38bdf8;")
        title_layout.addWidget(lbl_title)

        lbl_sub = QLabel(
            "Tư duy đạo diễn Production Shot Brief: Kiểm soát chuyển động vật lý • Âm thanh bản địa • Tham chiếu @Image, @Video"
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

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_tab_shot_anatomy(), "🎯 1. Cấu Trúc Đạo Diễn")
        self.tabs.addTab(self._create_tab_multimodal_syntax(), "🌟 2. Cú Pháp Đa Phương Thức")
        self.tabs.addTab(self._create_tab_recipe_library(), "📋 3. Thư Viện Prompt Mẫu")
        self.tabs.addTab(self._create_tab_troubleshooting(), "🛠️ 4. Khắc Phục Lỗi")
        main_layout.addWidget(self.tabs)

        # Footer Action Bar
        footer = QHBoxLayout()
        lbl_note = QLabel("💡 Mẹo: Nhấp 'Nạp Vào Xưởng' tại bất kỳ Recipe nào để đưa vào trình soạn thảo ngay lập tức.")
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
    # TAB 1: CẤU TRÚC ĐẠO DIỄN (SHOT ANATOMY)
    # =========================================================================
    def _create_tab_shot_anatomy(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(10)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setStyleSheet("background-color: #0b0f17; border: 1px solid #1e293b; border-radius: 6px; padding: 12px;")

        html_content = """
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #f1f5f9; line-height: 1.5; font-size: 13px; }
            h2 { color: #38bdf8; font-size: 15px; margin-top: 4px; margin-bottom: 8px; border-bottom: 1px solid #1e293b; padding-bottom: 4px; }
            h3 { color: #34d399; font-size: 13px; margin-top: 10px; margin-bottom: 6px; }
            p { margin: 4px 0; }
            .box-warn { background-color: #2e1065; border-left: 4px solid #a855f7; padding: 8px 12px; border-radius: 4px; margin: 8px 0; }
            .box-formula { background-color: #0f172a; border: 1px solid #0284c7; padding: 10px 14px; border-radius: 6px; margin: 8px 0; font-family: Consolas, monospace; color: #38bdf8; font-weight: bold; }
            table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 12px; }
            th { background-color: #1e293b; color: #94a3b8; text-align: left; padding: 6px 10px; border-bottom: 2px solid #334155; }
            td { padding: 6px 10px; border-bottom: 1px solid #1e293b; color: #cbd5e1; vertical-align: top; }
            .tag { font-weight: bold; color: #f59e0b; }
            .anti { color: #f87171; text-decoration: line-through; }
            .pro { color: #34d399; font-weight: 600; }
        </style>

        <h2>1. Tư Duy Cốt Lõi: "Production Shot Brief" (Bản Ghi Chú Đạo Diễn)</h2>
        <p>Muse AI (Muse Video) được huấn luyện để hiểu ngôn ngữ sản xuất phim thực tế thay vì nhồi nhét từ khóa mỹ miều.</p>

        <div class="box-warn">
            ⚠️ <b>Quy Tắc Vàng (Anti-Fluff):</b> Tuyệt đối <b>KHÔNG</b> dùng các từ ngữ sáo rỗng vô nghĩa như: <span class="anti">"photorealistic", "hyperrealistic", "8k", "masterpiece", "trending on artstation"</span>.<br/>
            Thay vào đó, hãy mô tả chính xác <b>nguồn sáng vật lý, bề mặt chất liệu, hành động có thể quay và ngôn ngữ máy quay</b>.
        </div>

        <h2>2. Hai Công Thức Chuẩn Đạo Diễn</h2>
        <h3>A. Công thức tối giản (Universal Starter Formula - Dành cho cảnh ngắn & nhanh)</h3>
        <div class="box-formula">
            [Bối cảnh / Loại cảnh] + [Chủ thể & Trạng thái] + [Hành động vật lý cụ thể] + [Góc & Chuyển động Camera] + [Ánh sáng & Thẩm mỹ] + [Âm thanh Bản địa]
        </div>

        <h3>B. Cấu trúc Đạo diễn Sản xuất Đầy đủ (Full Production Shot Template)</h3>
        <div class="box-formula" style="color: #34d399; font-size: 11px;">
            [THỜI LƯỢNG + TỈ LỆ KHUNG HÌNH]. [CHỦ THỂ] thực hiện [HÀNH ĐỘNG VẬT LÝ] tại [BỐI CẢNH].<br/>
            Góc máy: [CỠ CẢNH + 1 CHUYỂN ĐỘNG CHÍNH].<br/>
            Nhịp cảnh: [DIỄN BIẾN THEO THỜI GIAN GIÂY 1 -> GIÂY CUỐI].<br/>
            Âm thanh: [MÔI TRƯỜNG + TIẾNG ĐỘNG VA CHẠM + LỜI THOẠI/VOICEOVER].<br/>
            Bảo toàn: [ĐẶC TÍNH CẦN GIỮ NGUYÊN].<br/>
            Loại trừ: [CÁC LỖI CẦN TRÁNH].
        </div>

        <h2>3. Giải Phẫu 6 Thành Phần Cốt Lõi (Prompt Anatomy)</h2>
        <table>
            <tr>
                <th width="20%">Thành phần</th>
                <th width="40%">Ý nghĩa kỹ thuật & Quy tắc viết</th>
                <th width="40%">Ví dụ minh họa</th>
            </tr>
            <tr>
                <td><span class="tag">1. Subject (Chủ thể)</span></td>
                <td><b>Neo nhận diện (Identity Anchor)</b>: Chỉ định rõ 1-2 đối tượng chính, không mô tả mập mờ, không đổi tên giữa các câu.</td>
                <td><code>Một nữ nghệ nhân gốm 30 tuổi mặc tạp dề denim</code></td>
            </tr>
            <tr>
                <td><span class="tag">2. Action (Hành động)</span></td>
                <td><b>Chuyển động có thể quay (Filmable Action)</b>: Dùng động từ vật lý rõ ràng. Tránh các từ trạng thái tĩnh hoặc khái niệm trừu tượng.</td>
                <td><code>từ từ rót sữa bốc khói vào tách gốm sẫm màu</code></td>
            </tr>
            <tr>
                <td><span class="tag">3. Camera (Ống kính)</span></td>
                <td><b>1 Shot = 1 Chuyển động chính</b>. Tránh kết hợp xung đột (vừa zoom vừa pan vừa xoay lắc gây chóng mặt).</td>
                <td><code>Cú máy góc thấp đẩy tiến êm ái</code>, <code>Toàn cảnh từ trên cao cố định</code></td>
            </tr>
            <tr>
                <td><span class="tag">4. Lighting & Environment</span></td>
                <td><b>Ánh sáng & Phản xạ vật lý</b>: Chỉ rõ nguồn sáng thực tế (practical lights) và tương tác với bề mặt.</td>
                <td><code>Ngược sáng ban mai ấm áp xuyên qua các hạt bụi, bóng đổ mềm mại trên bàn gỗ sồi</code></td>
            </tr>
            <tr>
                <td><span class="tag">5. Beats (Tiến trình)</span></td>
                <td><b>Biến đổi theo mốc thời gian</b>: Mô tả cái gì diễn ra ở từng giây để chống tình trạng cảnh quay bị trôi lửng lơ.</td>
                <td><code>2 giây đầu khói bốc lên, đến giây thứ 3 một bàn tay đưa vào nâng tách lên</code></td>
            </tr>
            <tr>
                <td><span class="tag">6. Native Audio</span></td>
                <td><b>Âm thanh đồng bộ trực tiếp</b>: Phân tách rõ 3 tầng: Môi trường (Ambience) + Va chạm (Foley) + Lời thoại (Voice).</td>
                <td><code>Âm thanh: tiếng xì xào quán cà phê, tiếng cốc chạm đĩa, tiếng dòng sữa rót xuống nhẹ nhàng</code></td>
            </tr>
        </table>
        """
        browser.setHtml(html_content)
        layout.addWidget(browser)

        # Quick Copy Template Button
        btn_copy_template = QPushButton("📋 Sao Chép Cấu Trúc Khung Rỗng (Template) Vào Clipboard")
        btn_copy_template.setFixedHeight(30)
        btn_copy_template.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-weight: 700; border: 1px solid #0284c7; border-radius: 6px;")
        btn_copy_template.clicked.connect(self._copy_blank_template)
        layout.addWidget(btn_copy_template)

        return widget

    def _copy_blank_template(self) -> None:
        template = (
            "[16:9, 6 giây]. [CHỦ THỂ] thực hiện [HÀNH ĐỘNG CỤ THỂ] tại [BỐI CẢNH].\n"
            "Góc máy: [CỠ CẢNH + 1 CHUYỂN ĐỘNG CHÍNH].\n"
            "Nhịp cảnh: 2 giây đầu [HÀNH ĐỘNG 1], đến giây thứ 3 [HÀNH ĐỘNG 2].\n"
            "Âm thanh: [TIẾNG MÔI TRƯỜNG + TIẾNG VA CHẠM + LỜI THOẠI].\n"
            "Bảo toàn: [ĐẶC TÍNH CẦN GIỮ NGUYÊN].\n"
            "Loại trừ: [CÁC LỖI CẦN TRÁNH]."
        )
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(template)

    # =========================================================================
    # TAB 2: CÚ PHÁP ĐA PHƯƠNG THỨC & ÂM THANH (MULTIMODAL SYNTAX)
    # =========================================================================
    def _create_tab_multimodal_syntax(self) -> QWidget:
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
            h3 { color: #f59e0b; font-size: 13px; margin-top: 10px; margin-bottom: 6px; }
            .code { background-color: #111827; border: 1px solid #334155; padding: 8px 12px; border-radius: 6px; font-family: Consolas, monospace; color: #e2e8f0; font-size: 12px; margin: 6px 0; }
            .hl { color: #38bdf8; font-weight: bold; }
            .tip { background-color: #064e3b; border-left: 4px solid #10b981; padding: 8px 12px; border-radius: 4px; margin: 8px 0; color: #d1fae5; }
        </style>

        <h2>1. Tham Chiếu Hình Ảnh (@Image) — Khóa Nhân Vật & Sản Phẩm</h2>
        <p>Muse AI cho phép bạn giữ nguyên vẹn nhận diện khuôn mặt, trang phục hoặc logo thông qua thẻ <span class="hl">@Image[n]</span> (ví dụ: @Image1, @Image2, @Image3):</p>

        <h3>Khóa nhân vật qua nhiều góc nhìn (Multi-view Character Consistency):</h3>
        <div class="code">
            Tham chiếu diện mạo nhân vật từ <b>@Image1</b> và trang phục từ <b>@Image2</b>. Người phụ nữ bước đi qua ga tàu điện ngầm đông đúc nhộn nhịp, cú máy tracking trung cảnh bám theo, bảo toàn trọn vẹn đường nét khuôn mặt và chất liệu áo khoác. Âm thanh: tiếng tàu hỏa ầm ầm từ xa, tiếng bước chân vang vọng.
        </div>

        <h3>Chèn Logo thương hiệu ở cuối video:</h3>
        <div class="code">
            Góc máy từ từ lùi xa, màn hình mờ dần vào bóng tối, sau đó Logo từ <b>@Image1</b> hiện rõ nét tại chính giữa khung hình.
        </div>

        <h2>2. Kế Thừa Video (@Video) — Sao Chép Động Tác & Góc Máy</h2>
        <p>Khi bạn muốn áp dụng nhịp độ chuyển động phức tạp từ một video có sẵn sang nhân vật mới:</p>
        <div class="code">
            Tham chiếu chuyển động góc máy và cú nhảy thể thao từ <b>@Video 1</b>, áp dụng cho một ninja trên mái ngói Kyoto cổ kính lúc hoàng hôn. Bảo toàn vật lý tà áo khi nhào lộn. Âm thanh: tiếng gió rít, tiếng chạm chân êm ái trên mái ngói.
        </div>

        <h2>3. Lời Thoại Đồng Bộ (Dialogue), Phụ Đề & Bong Bóng Thoại</h2>
        <h3>A. Voiceover thuyết minh kèm phụ đề chạy chữ dưới đáy:</h3>
        <div class="code">
            Tạo video có voiceover thuyết minh. Một giọng nam trầm ấm nói: <i>"Sự đổi mới bắt đầu từ nơi kết thúc của sự chắc chắn."</i> Góc máy tracking từ từ qua bàn làm việc của kiến trúc sư với các bản vẽ phác thảo. <b>Phụ đề xuất hiện ở giữa đáy màn hình, đồng bộ với nhịp nói</b>. Âm thanh: tiếng bút chì vẽ sột soạt nhịp nhàng, tiếng vang nhẹ trong phòng.
        </div>

        <h3>B. Nhân vật nói chuyện + Bong bóng thoại hoạt hình (Speech Bubbles):</h3>
        <div class="code">
            Hai phi hành gia đứng trên sườn núi Sao Hỏa. Phi hành gia bên trái quay lại nói: <i>"Chúng ta đã đến nơi rồi."</i> Một <b>bong bóng thoại phong cách truyện tranh</b> xuất hiện phía trên mũ bảo hiểm chứa câu thoại. Âm thanh: tiếng rè tĩnh điện radio, tiếng thở nghẹn trong mũ, tiếng gió hú xa xăm.
        </div>

        <h2>4. Nối Dài Video (Extend) & Ghép Phân Cảnh (Splice Tracks)</h2>
        <div class="tip">
            💡 <b>Nối tiếp cảnh quay hiện có:</b> Dùng cú pháp <code>Tạo nội dung nối tiếp sau @Video 1: [hành động tiếp theo]</code> để tạo chuỗi cảnh mượt mà không bị ngắt quãng nhận diện.
        </div>
        """
        browser.setHtml(html_content)
        layout.addWidget(browser)
        return widget

    # =========================================================================
    # TAB 3: THƯ VIỆN RECIPE THỰC CHIẾN (PRODUCTION RECIPES)
    # =========================================================================
    def _create_tab_recipe_library(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Toolbar trên cùng
        tb = QHBoxLayout()
        lbl_info = QLabel("Chọn một recipe mẫu dưới đây để nạp vào xưởng hoặc bấm 'Nạp Tất Cả' để thử nghiệm hàng loạt:")
        lbl_info.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        tb.addWidget(lbl_info)
        tb.addStretch()

        btn_load_all = QPushButton("🚀 Nạp Toàn Bộ Recipe Vào Xưởng")
        btn_load_all.setFixedHeight(28)
        btn_load_all.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #38bdf8);
                color: #ffffff;
                font-weight: 700;
                font-size: 11px;
                border: 1px solid #60a5fa;
                border-radius: 5px;
                padding: 0 12px;
            }
            """
        )
        btn_load_all.clicked.connect(self._load_all_recipes)
        tb.addWidget(btn_load_all)
        layout.addLayout(tb)

        # Scroll Area chứa các Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        cards_layout = QVBoxLayout(container)
        cards_layout.setContentsMargins(0, 0, 4, 0)
        cards_layout.setSpacing(10)

        self.recipes_data = [
            {
                "title": "Recipe 1: TVC Ra Mắt Sản Phẩm Cao Cấp (Product Commercial)",
                "category": "QUẢNG CÁO",
                "badge_color": "#38bdf8",
                "desc": "Tập trung ánh sáng viền (rim light), bề mặt đá ướt phản chiếu sắc nét, chuyển động xoay tiến chậm và màn hình phát sáng đúng nhịp.",
                "prompt": (
                    "[4K, 16:9, 6 giây]. Một chiếc đồng hồ thông minh (smartwatch) màu đen mờ tối giản đặt trên bệ đá phiến ướt nước. "
                    "Góc máy: Quay tiến xoay chậm từ góc 45 độ. "
                    "Nhịp cảnh: 2 giây đầu màn hình ở trạng thái nghỉ, đến giây thứ 3 màn hình OLED bừng sáng biểu đồ sinh trắc học hình tròn, phản chiếu sắc nét trên bề mặt đá ướt. "
                    "Ánh sáng: Đèn viền xanh dương mát từ tấm LED, phông nền studio tối. "
                    "Âm thanh: Tiếng ù trầm điện tử nhẹ, tiếng chuông kỹ thuật số tinh tế khi màn hình bật, tiếng giọt nước nhỏ vang vọng. "
                    "Bảo toàn: Kích thước vỏ đồng hồ và viền bezel. Loại trừ: Viền răng cưa, méo chữ."
                ),
            },
            {
                "title": "Recipe 2: Social Hook / Video Ngắn Năng Động (Nữ Barista)",
                "category": "TIKTOK / REELS",
                "badge_color": "#ec4899",
                "desc": "Nhịp độ nhanh, bắt mắt người xem ngay giây đầu tiên, kết hợp tiếng va chạm đá và câu thoại ngắn 'Xem này nhé' kèm phụ đề đồng bộ.",
                "prompt": (
                    "[9:16, 5 giây]. Một nữ barista mặc tạp dề thả muỗng xúc đá vào ly rỗng và nhìn thẳng vào ống kính với nụ cười tự tin. "
                    "Góc máy: Cận trung cầm tay linh hoạt, lia nhanh vào gần. "
                    "Nhịp cảnh: Muỗng chạm đáy ly ngay khung hình đầu tiên, các viên đá nảy lên rồi lắng xuống, barista nhướng mày hào hứng. "
                    "Ánh sáng: Nắng sớm ấm áp chiếu qua cửa sổ quán cà phê. "
                    "Âm thanh: Tiếng đá lách cách vang rền, tiếng leng keng kim loại của muỗng, tiếng máy pha cà phê espresso xì hơi phía sau. "
                    'Lời thoại: Nữ barista nói: "Xem này nhé." Phụ đề xuất hiện ở giữa đáy màn hình: "Xem này nhé."'
                ),
            },
            {
                "title": "Recipe 3: Cảnh Điện Ảnh Kể Chuyện (Cinematic Artisan)",
                "category": "ĐIỆN ẢNH",
                "badge_color": "#f59e0b",
                "desc": "Kỹ thuật rack focus từ bánh răng đồng mờ ảo sang ánh mắt nghệ nhân, bụi vi hạt lơ lửng trong ánh đèn vàng, âm thanh đa tầng sống động.",
                "prompt": (
                    "[2.39:1, 6 giây]. Một nghệ nhân làm đồng hồ cao tuổi đeo kính gọng kim loại đang quan sát cụm bánh răng tinh xảo qua kính lúp chuyên dụng. "
                    "Góc máy: Cực cận chuyển tiêu điểm (rack focus) từ cụm bánh răng đồng ở tiền cảnh sang ánh mắt tập trung của nghệ nhân. "
                    "Ánh sáng: Đèn sợi đốt dịu nhẹ chiếu rọi các hạt bụi siêu vi lơ lửng trong không khí. "
                    "Âm thanh: Tiếng tích tắc nhịp nhàng từ hàng chục chiếc đồng hồ cơ với tốc độ khác nhau, tiếng thở nhẹ khàn, tiếng nhíp kim loại gắp linh kiện tách tách. "
                    "Bảo toàn: Nếp nhăn trên khuôn mặt và lớp gỉ đồng cổ kính. Loại trừ: Mắt mờ, chớp mắt giật cục phi tự nhiên."
                ),
            },
            {
                "title": "Recipe 4: Thiên Nhiên Hùng Vĩ & Cận Cảnh Động Vật (Wildlife Macro)",
                "category": "TÀI LIỆU",
                "badge_color": "#10b981",
                "desc": "Góc quay macro cận cảnh một chú chim ruồi bay lơ lửng hút mật hoa, chuyển động cánh siêu mượt, sương mai phản chiếu ánh bình minh.",
                "prompt": (
                    "[16:9, 6 giây]. Một chú chim ruồi màu xanh ngọc bích óng ánh bay lơ lửng chuẩn xác trước bông hoa dâm bụt đỏ thắm còn đọng sương sớm. "
                    "Góc máy: Cận cảnh macro quay chậm siêu nét, độ sâu trường ảnh nông với phông nền mờ ảo mịn màng (bokeh). "
                    "Nhịp cảnh: Đôi cánh vỗ chuyển động khí động học mượt mà, mỏ chim khẽ hút mật hoa ở giây thứ 2, giọt sương mai lấp lánh khẽ rung rinh. "
                    "Ánh sáng: Ngược sáng bình minh giờ vàng làm nổi bật độ óng ánh của lớp lông vũ. "
                    "Âm thanh: Tiếng vo ve siêu âm nhanh từ đôi cánh, gió nhẹ vườn cây lay động kẽ lá, tiếng chim hót ríu rít ban mai từ xa. "
                    "Bảo toàn: Độ sắc nét của rìa cánh, giải phẫu cấu trúc lông vũ."
                ),
            },
        ]

        for r in self.recipes_data:
            card = RecipeCard(
                title=r["title"],
                category=r["category"],
                badge_color=r["badge_color"],
                description=r["desc"],
                prompt_text=r["prompt"],
            )
            card.load_requested.connect(self._on_single_recipe_load)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        return widget

    def _on_single_recipe_load(self, prompt: str) -> None:
        self.prompt_selected.emit(prompt)
        self.accept()

    def _load_all_recipes(self) -> None:
        prompts = [r["prompt"] for r in self.recipes_data]
        self.prompts_batch_selected.emit(prompts)
        self.accept()

    # =========================================================================
    # TAB 4: KHẮC PHỤC LỖI THƯỜNG GẶP (TROUBLESHOOTING)
    # =========================================================================
    def _create_tab_troubleshooting(self) -> QWidget:
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
            h3 { color: #f43f5e; font-size: 13px; margin-top: 10px; margin-bottom: 4px; }
            p { margin: 4px 0; }
            .solution { background-color: #064e3b; border-left: 4px solid #10b981; padding: 6px 12px; border-radius: 4px; margin: 6px 0; color: #ecfdf5; }
        </style>

        <h2>Bảng Xử Lý Các Lỗi Tạo Video Thường Gặp Trong Muse AI</h2>

        <h3>1. ❌ Khung hình đẹp lung linh nhưng chủ thể bất động (Frozen Subject)</h3>
        <p><b>Nguyên nhân:</b> Bạn dùng các động từ tĩnh hoặc miêu tả trạng thái thụ động (ví dụ: <i>standing, waiting, looking at sky</i>).</p>
        <div class="solution">
            ✅ <b>Giải pháp:</b> Buộc mô hình phải tính toán chuyển động bằng <b>động từ ngoại động lực</b> có tương tác vật lý cụ thể (ví dụ: <i>takes three steps forward, unzips leather jacket, lifts cup to lips, presses red button</i>).
        </div>

        <h3>2. ❌ Camera bị rung lắc, lộn xộn hoặc méo hình khối (Jittery / Warping)</h3>
        <p><b>Nguyên nhân:</b> Mô tả xung đột nhiều góc máy trong một câu ngắn (ví dụ vừa <i>zoom-in</i> vừa <i>pan right</i> vừa <i>handheld shake</i>).</p>
        <div class="solution">
            ✅ <b>Giải pháp:</b> Áp dụng quy tắc <b>1 Shot = 1 Chuyển động duy nhất</b> (chọn hoặc <i>Slow push-in</i>, hoặc <i>Tracking shot</i>, hoặc <i>Static high-angle</i>). Muse AI sẽ duy trì phối cảnh cực kỳ vững vàng.
        </div>

        <h3>3. ❌ Âm thanh bị thiếu tự nhiên, lệch pha hoặc chỉ có tiếng rè</h3>
        <p><b>Nguyên nhân:</b> Chỉ viết chung chung <i>"with sound"</i> hoặc không chỉ định nguồn âm.</p>
        <div class="solution">
            ✅ <b>Giải pháp:</b> Phân tầng âm thanh theo cấu trúc 3 lớp:<br/>
            <code>Audio: [Tiếng môi trường: gió/mưa/phố xá] + [Tiếng va chạm vật lý: tiếng gõ/tiếng rót nước] + [Lời thoại nếu có]</code>.
        </div>

        <h3>4. ❌ Nhân vật hoặc trang phục bị biến đổi dị thường (Identity Drift)</h3>
        <p><b>Nguyên nhân:</b> Thiếu lệnh neo giữ thuộc tính và không loại trừ các biến dạng.</p>
        <div class="solution">
            ✅ <b>Giải pháp:</b> Thêm rõ ràng hai dòng bảo vệ ở cuối prompt:<br/>
            <code>Bảo toàn: [Khuôn mặt, màu áo, tỉ lệ hình học của vật thể].</code><br/>
            <code>Loại trừ: [Biến dạng, thừa chi, viền răng cưa, dị vật lơ lửng].</code>
        </div>
        """
        browser.setHtml(html_content)
        layout.addWidget(browser)
        return widget
