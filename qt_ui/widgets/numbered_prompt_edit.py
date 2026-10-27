# -*- coding: utf-8 -*-
"""
NumberedPromptEdit - Trình soạn thảo Prompt chuyên nghiệp với cột đánh số thứ tự dòng (LineNumberArea).
Tối ưu cho Muse AI Studio:
- Hiển thị số thứ tự #1, #2, #3... thẳng hàng với từng prompt.
- Tự động highlight dòng đang soạn thảo.
- Tự động co giãn kích thước cột số theo số lượng dòng.
- Hỗ trợ kéo thả (drag & drop) file .txt để nạp prompt trực tiếp.
- Cung cấp các phương thức tiện ích: get_clean_prompts, prompt_count, set_prompts_list.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from PyQt6.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextFormat,
)
from PyQt6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget


class LineNumberArea(QWidget):
    """Widget hiển thị cột số dòng bên trái của NumberedPromptEdit."""

    def __init__(self, editor: NumberedPromptEdit) -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:
        self.editor.line_number_area_paint_event(event)


class NumberedPromptEdit(QPlainTextEdit):
    """QPlainTextEdit chuyên dụng cho việc nhập danh sách prompts (mỗi dòng 1 prompt)."""

    # Signal phát ra khi số lượng prompt thực tế thay đổi
    prompts_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)  # Tự động xuống dòng khi hết chiều rộng khung hình

        # Font chữ rõ nét, dễ đọc
        font = QFont("Consolas", 12)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        # Widget vẽ số dòng
        self.line_number_area = LineNumberArea(self)

        # Kết nối sự kiện để đồng bộ hóa
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.textChanged.connect(self._on_text_changed)

        self._update_line_number_area_width(0)
        self._highlight_current_line()

    def line_number_area_width(self) -> int:
        """Tính toán chiều rộng cột số dòng dựa trên số lượng block (tối thiểu 3 chữ số + đệm)."""
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        digits = max(digits, 2)  # Tối thiểu 2 chữ số để không bị chật

        space = 24 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def _update_line_number_area_width(self, _new_block_count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy != 0:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def _highlight_current_line(self) -> None:
        """Tô màu dòng đang có con trỏ gõ để người dùng dễ theo dõi."""
        if self.isReadOnly():
            return

        selection = QTextEdit.ExtraSelection()
        line_color = QColor("#1e293b")  # Slate-800 tô sáng nhẹ nhàng
        selection.format.setBackground(line_color)
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()

        self.setExtraSelections([selection])

    def line_number_area_paint_event(self, event: QPaintEvent) -> None:
        """Vẽ cột số dòng với màu sắc chuẩn mực dark mode."""
        painter = QPainter(self.line_number_area)
        # Nền cột số dòng
        painter.fillRect(event.rect(), QColor("#0f172a"))

        # Đường viền ngăn cách mảnh bên phải
        painter.setPen(QColor("#1e293b"))
        right_edge = event.rect().right()
        painter.drawLine(right_edge, event.rect().top(), right_edge, event.rect().bottom())

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        current_block_number = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                # Dòng đang chọn thì số có màu xanh sáng, dòng khác màu xám dịu
                if block_number == current_block_number:
                    painter.setPen(QColor("#38bdf8"))
                    f = painter.font()
                    f.setBold(True)
                    painter.setFont(f)
                else:
                    painter.setPen(QColor("#64748b"))
                    f = painter.font()
                    f.setBold(False)
                    painter.setFont(f)

                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 8,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    number,
                )

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def _on_text_changed(self) -> None:
        """Phát signal cập nhật số prompt thực tế khi văn bản thay đổi."""
        self.prompts_changed.emit(self.prompt_count())

    # =========================================================================
    # CÁC PHƯƠNG THỨC TIỆN ÍCH DÀNH CHO STUDIO
    # =========================================================================

    def get_clean_prompts(self) -> List[str]:
        """Trả về danh sách prompts sạch (đã loại bỏ dòng trống và khoảng trắng thừa)."""
        raw_text = self.toPlainText()
        prompts: List[str] = []
        for line in raw_text.splitlines():
            s = line.strip()
            if s and not s.startswith("#"):  # Bỏ qua dòng trống và dòng ghi chú
                prompts.append(s)
        return prompts

    def prompt_count(self) -> int:
        """Đếm số lượng prompt hợp lệ thực tế."""
        return len(self.get_clean_prompts())

    def set_prompts_list(self, prompts: List[str]) -> None:
        """Gán danh sách prompts vào trình soạn thảo."""
        clean = [p.strip() for p in prompts if p and p.strip()]
        self.setPlainText("\n".join(clean))

    def append_prompt(self, prompt: str) -> None:
        """Thêm 1 prompt vào cuối danh sách."""
        s = prompt.strip()
        if not s:
            return
        current = self.toPlainText().strip()
        if current:
            self.setPlainText(f"{current}\n{s}")
        else:
            self.setPlainText(s)

    def clear_prompts(self) -> None:
        """Xóa trắng toàn bộ nội dung."""
        self.clear()

    # =========================================================================
    # KÉO THẢ (DRAG & DROP) FILE .TXT
    # =========================================================================

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith((".txt", ".prompts")):
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = Path(url.toLocalFile())
                if file_path.is_file() and file_path.suffix.lower() in [".txt", ".prompts"]:
                    try:
                        content = file_path.read_text(encoding="utf-8")
                    except Exception:
                        try:
                            content = file_path.read_text(encoding="cp1252")
                        except Exception:
                            continue
                    self.setPlainText(content)
                    event.acceptProposedAction()
                    return
        super().dropEvent(event)
