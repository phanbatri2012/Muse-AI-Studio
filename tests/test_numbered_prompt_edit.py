# -*- coding: utf-8 -*-
"""
Unit tests cho NumberedPromptEdit widget.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from PyQt6.QtWidgets import QApplication

from qt_ui.widgets.numbered_prompt_edit import NumberedPromptEdit


@pytest.fixture(scope="session")
def qapp():
    """Đảm bảo có instance QApplication cho headless test."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


def test_numbered_prompt_edit_basic(qapp):
    editor = NumberedPromptEdit()
    assert editor.prompt_count() == 0
    assert editor.get_clean_prompts() == []

    # Điền các dòng prompt xen kẽ dòng trống và ghi chú
    raw_text = (
        "Prompt 1: Golden retriever puppy running on grass\n"
        "\n"
        "   \n"
        "# Đây là ghi chú không phải prompt\n"
        "Prompt 2: Cyberpunk flying car in neon rain\n"
        "Prompt 3: Misty pine mountain drone shot\n"
    )
    editor.setPlainText(raw_text)

    clean_prompts = editor.get_clean_prompts()
    assert len(clean_prompts) == 3
    assert clean_prompts[0] == "Prompt 1: Golden retriever puppy running on grass"
    assert clean_prompts[1] == "Prompt 2: Cyberpunk flying car in neon rain"
    assert clean_prompts[2] == "Prompt 3: Misty pine mountain drone shot"
    assert editor.prompt_count() == 3


def test_set_prompts_list(qapp):
    editor = NumberedPromptEdit()
    prompts = [
        "A beautiful sunset over ocean",
        "A cute kitten jumping in room",
        "Astronaut floating in deep space",
    ]
    editor.set_prompts_list(prompts)
    assert editor.prompt_count() == 3
    assert editor.get_clean_prompts() == prompts

    # Test append
    editor.append_prompt("Volcano eruption with lightning")
    assert editor.prompt_count() == 4
    assert editor.get_clean_prompts()[-1] == "Volcano eruption with lightning"

    # Test clear
    editor.clear_prompts()
    assert editor.prompt_count() == 0
    assert editor.get_clean_prompts() == []


def test_prompts_changed_signal(qapp):
    editor = NumberedPromptEdit()
    counts = []

    editor.prompts_changed.connect(lambda c: counts.append(c))

    editor.setPlainText("Prompt 1\nPrompt 2")
    assert len(counts) > 0
    assert counts[-1] == 2
