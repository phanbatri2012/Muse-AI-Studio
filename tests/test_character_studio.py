# -*- coding: utf-8 -*-
"""
Unit tests cho CharacterStudioTab và CharacterGuideDialog.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qt_ui.tab_character_studio import CharacterStudioTab, ImageSlotWidget
from qt_ui.widgets.character_guide_dialog import CharacterGuideDialog, CharacterRecipeCard


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_character_studio_init(qapp):
    tab = CharacterStudioTab()
    assert tab.editor is not None
    assert tab.btn_start is not None
    assert tab.radio_rotation.isChecked()
    assert tab.radio_with_images.isChecked()
    assert not tab.slots_container.isHidden()
    assert tab.slot1 is not None
    assert tab.slot2 is not None
    assert tab.slot3 is not None


def test_character_studio_mode_toggle(qapp):
    tab = CharacterStudioTab()
    assert not tab.slots_container.isHidden()

    # Chuyển sang Text-Only
    tab.radio_text_only.setChecked(True)
    assert tab.slots_container.isHidden()

    # Chuyển lại Có ảnh
    tab.radio_with_images.setChecked(True)
    assert not tab.slots_container.isHidden()


def test_character_studio_image_slots(qapp):
    tab = CharacterStudioTab()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
        temp_img_path = f.name

    try:
        # Gán ảnh vào slot 1
        tab.slot1.set_image(temp_img_path)
        assert tab.slot1.image_path == temp_img_path
        assert tab.reference_images[0] == temp_img_path

        # Lấy danh sách ảnh hợp lệ
        valid_imgs = tab.get_valid_reference_images()
        assert len(valid_imgs) == 1
        assert valid_imgs[0] == temp_img_path

        # Xóa ảnh slot 1
        tab.slot1.clear_image()
        assert tab.slot1.image_path == ""
        assert len(tab.get_valid_reference_images()) == 0
    finally:
        try:
            Path(temp_img_path).unlink()
        except Exception:
            pass


def test_character_studio_sample_prompts(qapp):
    tab = CharacterStudioTab()

    # Nạp Mẫu A
    tab._load_sample_a()
    assert tab.editor.prompt_count() == 2
    assert tab.radio_with_images.isChecked()
    assert "@image" in tab.editor.get_clean_prompts()[0].lower()

    # Nạp Mẫu B
    tab._load_sample_b()
    assert tab.editor.prompt_count() == 1
    assert tab.radio_text_only.isChecked()
    assert "thorne" in tab.editor.get_clean_prompts()[0].lower()


def test_character_studio_collapsible_guide(qapp):
    tab = CharacterStudioTab()
    assert tab.guide_detail_widget.isHidden()
    assert tab.btn_toggle_guide.text() == "🔽 Xem Tóm Tắt"

    tab._toggle_guide_detail()
    assert not tab.guide_detail_widget.isHidden()
    assert tab.btn_toggle_guide.text() == "🔼 Thu Gọn"

    tab._toggle_guide_detail()
    assert tab.guide_detail_widget.isHidden()


def test_character_guide_dialog(qapp):
    tab = CharacterStudioTab()
    dialog = CharacterGuideDialog(tab)
    assert dialog is not None

    received_prompts = []
    dialog.prompt_selected.connect(lambda p: received_prompts.append(p))

    dialog._on_recipe_load("Test prompt from dialog")
    assert len(received_prompts) == 1
    assert received_prompts[0] == "Test prompt from dialog"


def test_character_studio_start_batch_signal(qapp):
    tab = CharacterStudioTab()
    tab._load_sample_b()

    emitted = []
    tab.start_batch_requested.connect(lambda p, c: emitted.append((p, c)))

    tab._on_start_clicked()
    assert len(emitted) == 1
    prompts, cfg = emitted[0]
    assert len(prompts) == 1
    assert cfg["account_mode"] == "rotation"
    assert cfg["duration"] == 6
    assert cfg["smooth_60fps"] is True
    assert "reference_images" in cfg


def test_character_studio_dynamic_slots_add_and_remove(qapp):
    tab = CharacterStudioTab()
    assert len(tab.slots) == 3
    assert len(tab.reference_images) == 3
    assert not tab.slot1.can_remove
    assert not tab.slot2.can_remove
    assert not tab.slot3.can_remove

    # Thêm slot 4
    tab._on_add_slot_clicked()
    assert len(tab.slots) == 4
    assert len(tab.reference_images) == 4
    assert tab.slots[3].slot_index == 4
    assert tab.slots[3].can_remove is True

    # Thêm slot 5 và slot 6
    tab._on_add_slot_clicked()
    tab._on_add_slot_clicked()
    assert len(tab.slots) == 6
    assert len(tab.reference_images) == 6
    assert tab.btn_add_slot.isEnabled() is False

    # Không thể thêm slot 7
    tab._on_add_slot_clicked()
    assert len(tab.slots) == 6

    # Gỡ slot 5 (chỉ số 5)
    tab._on_remove_slot_requested(5)
    assert len(tab.slots) == 5
    assert len(tab.reference_images) == 5
    assert tab.btn_add_slot.isEnabled() is True
    # Slot cuối cùng bây giờ có index là 5
    assert tab.slots[4].slot_index == 5

    # Gỡ tiếp slot 5 và slot 4 -> còn 3 slots
    tab._on_remove_slot_requested(5)
    tab._on_remove_slot_requested(4)
    assert len(tab.slots) == 3
    assert not tab.slots[0].can_remove
    assert not tab.slots[1].can_remove
    assert not tab.slots[2].can_remove

    # Không thể gỡ khi chỉ còn 3 slots
    tab._on_remove_slot_requested(3)
    assert len(tab.slots) == 3


def test_character_studio_sample_e(qapp):
    tab = CharacterStudioTab()
    tab._load_sample_e()
    assert tab.radio_with_images.isChecked()
    assert tab.combo_slot_preset.currentData() == "shop_kol"
    prompts = tab.editor.get_clean_prompts()
    assert len(prompts) == 1
    prompt = prompts[0]
    assert "Điện Thoại Giá Tốt" in prompt
    assert "iPhone 13 Pro Max" in prompt
    assert "@Image1" in prompt
    assert "@Image2" in prompt
    assert "@Image3" in prompt
