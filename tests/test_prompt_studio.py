# -*- coding: utf-8 -*-
"""
Unit tests cho PromptStudioTab.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qt_ui.tab_prompt_studio import PromptStudioTab
from qt_ui.widgets.prompt_guide_dialog import PromptGuideDialog, RecipeCard


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_prompt_studio_init(qapp):
    tab = PromptStudioTab()
    assert tab.editor is not None
    assert tab.btn_start is not None
    assert tab.radio_rotation.isChecked()


def test_prompt_studio_sample_and_signal(qapp):
    tab = PromptStudioTab()
    tab._load_sample_prompts()
    assert tab.editor.prompt_count() > 0

    emitted_data = []
    tab.start_batch_requested.connect(lambda prompts, cfg: emitted_data.append((prompts, cfg)))

    tab._on_start_clicked()
    assert len(emitted_data) == 1
    prompts, cfg = emitted_data[0]
    assert len(prompts) > 0
    assert cfg["account_mode"] == "rotation"
    assert "aspect_ratio" in cfg
    assert "smooth_60fps" in cfg
    assert cfg["smooth_60fps"] is True
    assert cfg["duration"] == 6


def test_duration_spinbox_behavior(qapp):
    tab = PromptStudioTab()
    # Chữ "giây" không nằm trong ô input mà là nhãn riêng bên ngoài
    assert tab.spin_duration.suffix() == ""
    assert tab.spin_duration.value() == 6
    assert tab.spin_duration.maximum() == 10

    # Đổi giá trị thời lượng tự do trong giới hạn 1-10s
    tab.spin_duration.setValue(8)
    assert tab.spin_duration.value() == 8
    tab.spin_duration.setValue(30)
    assert tab.spin_duration.value() == 10  # Bị clamp bởi maximum 10s


def test_prompt_studio_button_visual_state(qapp):
    tab = PromptStudioTab()
    # Khi 0 prompt: nút ở style chờ nhập liệu
    assert "1e293b" in tab.btn_start.styleSheet()

    # Khi nạp prompt: nút bừng sáng gradient xanh
    tab._load_sample_prompts()
    assert "059669" in tab.btn_start.styleSheet()

    # Khi xóa trắng: nút trở về style chờ
    tab.editor.clear_prompts()
    assert "1e293b" in tab.btn_start.styleSheet()


def test_prompt_studio_collapsible_guide_bar(qapp):
    tab = PromptStudioTab()
    # Ban đầu khung chi tiết ẩn
    assert tab.guide_detail_widget.isHidden()
    assert tab.btn_toggle_guide.text() == "🔽 Xem Tóm Tắt"

    # Nhấp để mở rộng
    tab._toggle_guide_detail()
    assert not tab.guide_detail_widget.isHidden()
    assert tab.btn_toggle_guide.text() == "🔼 Thu Gọn"

    # Nhấp lại để thu gọn
    tab._toggle_guide_detail()
    assert tab.guide_detail_widget.isHidden()
    assert tab.btn_toggle_guide.text() == "🔽 Xem Tóm Tắt"


def test_prompt_guide_dialog_and_load(qapp):
    tab = PromptStudioTab()
    dialog = PromptGuideDialog(tab)
    assert dialog is not None
    assert len(dialog.recipes_data) >= 3

    # Kiểm tra nạp 1 recipe từ dialog vào xưởng
    first_recipe = dialog.recipes_data[0]["prompt"]
    tab._on_guide_single_prompt_selected(first_recipe)
    assert tab.editor.prompt_count() == 1
    assert "smartwatch" in tab.editor.get_clean_prompts()[0].lower()

    # Kiểm tra nạp hàng loạt recipe
    all_prompts = [r["prompt"] for r in dialog.recipes_data]
    tab._on_guide_batch_selected(all_prompts)
    assert tab.editor.prompt_count() == len(dialog.recipes_data)


def test_recipe_card_copy(qapp):
    card = RecipeCard(
        title="Test Recipe",
        category="TEST",
        badge_color="#38bdf8",
        description="Test desc",
        prompt_text="A test prompt line for copy",
    )
    card._copy_prompt()
    clip = QApplication.clipboard()
    if clip:
        assert clip.text() == "A test prompt line for copy"


def test_parse_prompt_directives_auto_detection():
    from A_workflow_muse_text_to_video import parse_prompt_directives

    # Test nhận diện 16:9 và 6 giây
    ar, dur = parse_prompt_directives("[4K, 16:9, 6 giây]. Chiếc đồng hồ thông minh...")
    assert ar == "16:9"
    assert dur == 6

    # Test nhận diện 9:16 và 5s
    ar, dur = parse_prompt_directives("[9:16, 5s]. Nữ barista nhìn ống kính...")
    assert ar == "9:16"
    assert dur == 5

    # Test fallback khi prompt không ghi
    ar, dur = parse_prompt_directives("Một chú chim bay lượn trên đồng cỏ xanh", default_ar="16:9", default_dur=8)
    assert ar == "16:9"
    assert dur == 8

    # Test tự động clamp thời lượng vượt trần (ví dụ 30 giây -> 10s)
    ar, dur = parse_prompt_directives("[16:9, 30 giây]. Một cảnh quay dài...", default_ar="16:9", default_dur=6)
    assert ar == "16:9"
    assert dur == 10

    # Test tự động clamp thời lượng fallback >10s
    ar, dur = parse_prompt_directives("Không có chỉ thị thời lượng", default_ar="16:9", default_dur=15)
    assert dur == 10
