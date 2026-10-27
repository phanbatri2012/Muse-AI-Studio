from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QLineEdit, QSizePolicy


def _text_width(widget, text: str) -> int:
    try:
        return int(widget.fontMetrics().horizontalAdvance(str(text or "").replace("&", "").strip()))
    except Exception:
        return 0


def _combo_texts(combo: QComboBox) -> list[str]:
    items: list[str] = []
    try:
        for index in range(combo.count()):
            text = str(combo.itemText(index) or "").strip()
            if text:
                items.append(text)
    except Exception:
        pass
    current = str(combo.currentText() or "").strip()
    if current and current not in items:
        items.append(current)
    return items


def configure_combo_box(
    combo: QComboBox,
    *,
    min_width: int = 120,
    popup_extra: int = 56,
    max_popup_width: int = 520,
    fixed_height: int | None = None,
    expanding: bool = False,
    compact: bool = False,
    **_kwargs,
) -> int:
    texts = _combo_texts(combo)
    longest = max((_text_width(combo, text) for text in texts), default=0)
    control_width = max(int(min_width or 0), min(int(max_popup_width), int(longest + 48)))
    popup_width = max(control_width, min(int(max_popup_width), int(longest + popup_extra)))

    try:
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    except Exception:
        pass

    try:
        combo.setMinimumWidth(control_width)
    except Exception:
        pass

    try:
        combo.setSizePolicy(
            QSizePolicy.Policy.Expanding if expanding else QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
    except Exception:
        pass

    if fixed_height is not None:
        try:
            combo.setFixedHeight(int(fixed_height))
        except Exception:
            pass

    try:
        view = combo.view()
        if view is not None:
            view.setTextElideMode(Qt.TextElideMode.ElideNone)
            try:
                view.setWordWrap(False)
            except Exception:
                pass
            try:
                view.setUniformItemSizes(True)
            except Exception:
                pass
            try:
                view.setMinimumWidth(popup_width)
            except Exception:
                pass
    except Exception:
        pass

    try:
        combo.setToolTip("\n".join(texts))
    except Exception:
        pass

    try:
        combo.currentTextChanged.connect(lambda _=None, c=combo: c.setToolTip(c.currentText().strip()))
    except Exception:
        pass

    return control_width


def configure_path_line_edit(
    line_edit: QLineEdit,
    *,
    min_width: int = 280,
    fixed_height: int | None = None,
) -> None:
    def _sync_path_view(text: str) -> None:
        try:
            line_edit.setToolTip(str(text or "").strip())
        except Exception:
            pass
        try:
            line_edit.setCursorPosition(0)
        except Exception:
            pass

    try:
        line_edit.setMinimumWidth(int(min_width))
    except Exception:
        pass

    try:
        line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    except Exception:
        pass

    if fixed_height is not None:
        try:
            line_edit.setFixedHeight(int(fixed_height))
        except Exception:
            pass

    _sync_path_view(str(line_edit.text() or ""))
    try:
        line_edit.textChanged.connect(_sync_path_view)
    except Exception:
        pass
