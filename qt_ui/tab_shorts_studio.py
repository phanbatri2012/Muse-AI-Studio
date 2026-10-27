# -*- coding: utf-8 -*-
"""
PyQt6 Tab for End-to-End Shorts Studio.
Allows users to create 100% automated YouTube Shorts / TikTok videos:
Topic -> Muse AI Scripting -> Voiceover TTS -> Muse AI Video -> 60fps MCI -> FFmpeg BGM Composer.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pipeline_shorts_generator import PipelineShortsGenerator
from runtime_paths import DOWNLOADS_DIR
from shorts_script_engine import SceneItem, ShortsScriptEngine
from shorts_tts_engine import DEFAULT_VOICE, SUPPORTED_VOICES

SAMPLE_TOPICS = [
    "Bí ẩn hố sâu Mariana và những sinh vật phát sáng kỳ lạ",
    "Sự thật kinh ngạc về kim tự tháp Ai Cập mà bạn chưa biết",
    "Nếu con người rơi vào hố đen vũ trụ thì điều gì sẽ xảy ra?",
    "Khám phá thành phố tương lai năm 2050 với xe bay và robot AI",
]


class ScriptGenWorker(QThread):
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self, topic: str, scene_count: int, log_cb=None) -> None:
        super().__init__()
        self.topic = topic
        self.scene_count = scene_count
        self.log_cb = log_cb

    def run(self) -> None:
        try:
            engine = ShortsScriptEngine(log_callback=self.log_cb)
            scenes = engine.generate_storyboard(topic=self.topic, scene_count=self.scene_count)
            self.finished_signal.emit(scenes)
        except Exception as e:
            self.error_signal.emit(str(e))


class PipelineRunWorker(QThread):
    progress_signal = pyqtSignal(float, str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        topic: str,
        scenes: list[SceneItem],
        voice: str,
        bgm_mood: str,
        smooth: bool,
        burn_sub: bool,
        aspect_ratio: str,
        log_cb=None,
    ) -> None:
        super().__init__()
        self.topic = topic
        self.scenes = scenes
        self.voice = voice
        self.bgm_mood = bgm_mood
        self.smooth = smooth
        self.burn_sub = burn_sub
        self.aspect_ratio = aspect_ratio
        self.log_cb = log_cb

    def run(self) -> None:
        try:
            pipeline = PipelineShortsGenerator(
                log_callback=self.log_cb,
                progress_callback=lambda p, m: self.progress_signal.emit(p, m),
            )
            final_path = pipeline.run(
                topic=self.topic,
                custom_scenes=self.scenes,
                scene_count=len(self.scenes),
                aspect_ratio=self.aspect_ratio,
                voice=self.voice,
                bgm_mood=self.bgm_mood,
                smooth_60fps=self.smooth,
                burn_subtitles=self.burn_sub,
            )
            self.finished_signal.emit(str(final_path))
        except Exception as e:
            self.error_signal.emit(str(e))


class AutoShortsStudioTab(QWidget):
    """Tab Tự Động Hóa Sản Xuất Shorts Studio."""

    def __init__(self, log_callback=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_callback = log_callback
        self._current_scenes: list[SceneItem] = []
        self._last_final_video: str | None = None
        self._worker: QThread | None = None

        self._init_ui()

    def _log(self, msg: str) -> None:
        if callable(self.log_callback):
            try:
                self.log_callback(msg)
                return
            except Exception:
                pass
        print(f"[SHORTS_TAB] {msg}")

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        # -------------------------------------------------------------
        # 1. Topic & Quick Controls Panel
        # -------------------------------------------------------------
        top_group = QGroupBox("💡 CHỦ ĐỀ & KỊCH BẢN TỰ ĐỘNG (MUSE AI CHAT)")
        top_layout = QVBoxLayout(top_group)
        top_layout.setSpacing(10)

        # Row 1: Topic Input
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        lbl_topic = QLabel("Chủ đề:")
        lbl_topic.setStyleSheet("font-weight: bold; color: #38bdf8;")
        row1.addWidget(lbl_topic)

        self.txt_topic = QLineEdit()
        self.txt_topic.setPlaceholderText("Nhập ý tưởng video ngắn... (VD: Bí ẩn vực thẳm Mariana, Sự thật về kim tự tháp)")
        self.txt_topic.setText(SAMPLE_TOPICS[0])
        self.txt_topic.setStyleSheet("padding: 6px 10px; font-size: 13px; background: #0f172a; border: 1px solid #334155; border-radius: 6px; color: #f8fafc;")
        row1.addWidget(self.txt_topic, stretch=4)

        self.btn_sample_topic = QPushButton("🎲 Mẫu ngẫu nhiên")
        self.btn_sample_topic.setStyleSheet("padding: 6px 12px; background: #334155; color: #e2e8f0; border-radius: 6px;")
        self.btn_sample_topic.clicked.connect(self._on_random_topic)
        row1.addWidget(self.btn_sample_topic)

        self.btn_gen_script = QPushButton("✨ 1. Viết Kịch Bản (Muse AI)")
        self.btn_gen_script.setStyleSheet("padding: 6px 16px; font-weight: bold; background: #2563eb; color: #ffffff; border-radius: 6px;")
        self.btn_gen_script.clicked.connect(self._on_generate_script)
        row1.addWidget(self.btn_gen_script)

        top_layout.addLayout(row1)

        # Row 2: Production Parameters
        row2 = QHBoxLayout()
        row2.setSpacing(16)

        # Scene Count
        row2.addWidget(QLabel("Số cảnh:"))
        self.spin_scenes = QSpinBox()
        self.spin_scenes.setRange(2, 6)
        self.spin_scenes.setValue(3)
        self.spin_scenes.setStyleSheet("padding: 4px; background: #1e293b; color: #ffffff;")
        row2.addWidget(self.spin_scenes)

        # Voice Selector
        row2.addWidget(QLabel("Giọng đọc (TTS):"))
        self.cbo_voice = QComboBox()
        for k, v in SUPPORTED_VOICES.items():
            self.cbo_voice.addItem(v, k)
        self.cbo_voice.setStyleSheet("padding: 4px; background: #1e293b; color: #ffffff;")
        row2.addWidget(self.cbo_voice)

        # BGM Mood Selector
        row2.addWidget(QLabel("Mood Nhạc:"))
        self.cbo_bgm = QComboBox()
        self.cbo_bgm.addItems(["hook", "evidence", "concrete_scene", "modern_mirror"])
        self.cbo_bgm.setStyleSheet("padding: 4px; background: #1e293b; color: #ffffff;")
        row2.addWidget(self.cbo_bgm)

        # Aspect Ratio
        row2.addWidget(QLabel("Tỉ lệ:"))
        self.cbo_aspect = QComboBox()
        self.cbo_aspect.addItem("9:16 (Dọc Shorts/TikTok)", "9:16")
        self.cbo_aspect.addItem("16:9 (Ngang Widescreen)", "16:9")
        self.cbo_aspect.setStyleSheet("padding: 4px; background: #1e293b; color: #ffffff;")
        row2.addWidget(self.cbo_aspect)

        # Checkboxes
        self.chk_smooth = QCheckBox("Làm mượt 60fps (MCI)")
        self.chk_smooth.setChecked(False)
        row2.addWidget(self.chk_smooth)

        self.chk_burn_sub = QCheckBox("Dán phụ đề TikTok")
        self.chk_burn_sub.setChecked(True)
        row2.addWidget(self.chk_burn_sub)

        row2.addStretch()
        top_layout.addLayout(row2)

        main_layout.addWidget(top_group)

        # -------------------------------------------------------------
        # 2. Storyboard Table (Editable)
        # -------------------------------------------------------------
        story_group = QGroupBox("📋 BẢNG PHÂN CẢNH CHI TIẾT (STORYBOARD)")
        story_layout = QVBoxLayout(story_group)
        story_layout.setSpacing(8)

        self.tbl_scenes = QTableWidget(0, 4)
        self.tbl_scenes.setHorizontalHeaderLabels([
            "Cảnh #",
            "Câu thoại thuyết minh (Tiếng Việt)",
            "Visual Prompt sinh video (Tiếng Anh - Meta Muse)",
            "Độ dài (s)",
        ])
        header = self.tbl_scenes.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_scenes.setStyleSheet("background: #0f172a; alternate-background-color: #1e293b; color: #f8fafc;")
        self.tbl_scenes.setAlternatingRowColors(True)
        story_layout.addWidget(self.tbl_scenes)

        # Actions on Storyboard
        act_row = QHBoxLayout()
        self.btn_add_scene = QPushButton("➕ Thêm cảnh")
        self.btn_add_scene.clicked.connect(self._on_add_scene)
        act_row.addWidget(self.btn_add_scene)

        self.btn_del_scene = QPushButton("🗑️ Xóa cảnh chọn")
        self.btn_del_scene.clicked.connect(self._on_del_scene)
        act_row.addWidget(self.btn_del_scene)

        act_row.addStretch()

        self.lbl_story_status = QLabel("Chưa có kịch bản. Hãy bấm 'Viết Kịch Bản' để bắt đầu.")
        self.lbl_story_status.setStyleSheet("color: #94a3b8; font-style: italic;")
        act_row.addWidget(self.lbl_story_status)

        story_layout.addLayout(act_row)
        main_layout.addWidget(story_group, stretch=1)

        # -------------------------------------------------------------
        # 3. Execution & Progress Bar
        # -------------------------------------------------------------
        bot_group = QGroupBox("🚀 TIẾN TRÌNH SẢN XUẤT HOÀN THIỆN")
        bot_layout = QVBoxLayout(bot_group)
        bot_layout.setSpacing(10)

        # Progress Row
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.pbar.setTextVisible(True)
        self.pbar.setStyleSheet(
            "QProgressBar { background: #1e293b; border-radius: 6px; text-align: center; color: #ffffff; height: 22px; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #10b981); border-radius: 6px; }"
        )
        bot_layout.addWidget(self.pbar)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_start = QPushButton("🚀 BẮT ĐẦU TẠO VIDEO SHORTS HOÀN CHỈNH")
        self.btn_start.setFixedHeight(44)
        self.btn_start.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);"
            " color: #ffffff; font-weight: bold; font-size: 14px; border-radius: 8px; padding: 0 20px; }"
            "QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #db2777); }"
            "QPushButton:disabled { background: #475569; color: #94a3b8; }"
        )
        self.btn_start.clicked.connect(self._on_start_pipeline)
        btn_row.addWidget(self.btn_start, stretch=3)

        self.btn_open_folder = QPushButton("📁 Mở Thư Mục")
        self.btn_open_folder.setFixedHeight(44)
        self.btn_open_folder.setStyleSheet("background: #334155; color: #ffffff; font-weight: bold; border-radius: 8px;")
        self.btn_open_folder.clicked.connect(self._on_open_folder)
        btn_row.addWidget(self.btn_open_folder, stretch=1)

        self.btn_play_video = QPushButton("▶️ Xem Video")
        self.btn_play_video.setFixedHeight(44)
        self.btn_play_video.setEnabled(False)
        self.btn_play_video.setStyleSheet(
            "QPushButton { background: #10b981; color: #ffffff; font-weight: bold; border-radius: 8px; }"
            "QPushButton:disabled { background: #334155; color: #64748b; }"
        )
        self.btn_play_video.clicked.connect(self._on_play_video)
        btn_row.addWidget(self.btn_play_video, stretch=1)

        bot_layout.addLayout(btn_row)
        main_layout.addWidget(bot_group)

    def _on_random_topic(self) -> None:
        import random
        choice = random.choice(SAMPLE_TOPICS)
        self.txt_topic.setText(choice)

    def _on_generate_script(self) -> None:
        topic = self.txt_topic.text().strip()
        if not topic:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập chủ đề trước khi tạo kịch bản!")
            return

        scene_count = self.spin_scenes.value()
        self.btn_gen_script.setEnabled(False)
        self.lbl_story_status.setText(f"Đang nhờ Muse AI Chat viết kịch bản ({scene_count} cảnh)...")

        self._worker = ScriptGenWorker(topic=topic, scene_count=scene_count, log_cb=self._log)
        self._worker.finished_signal.connect(self._on_script_success)
        self._worker.error_signal.connect(self._on_script_error)
        self._worker.start()

    @pyqtSlot(list)
    def _on_script_success(self, scenes: list[SceneItem]) -> None:
        self.btn_gen_script.setEnabled(True)
        self._current_scenes = scenes
        self._render_table()
        self.lbl_story_status.setText(f"✅ Đã tạo thành công {len(scenes)} phân cảnh! Bạn có thể chỉnh sửa nội dung bên dưới.")

    @pyqtSlot(str)
    def _on_script_error(self, err: str) -> None:
        self.btn_gen_script.setEnabled(True)
        self.lbl_story_status.setText("❌ Lỗi tạo kịch bản.")
        QMessageBox.critical(self, "Lỗi Muse AI Chat", f"Không thể tạo kịch bản: {err}")

    def _render_table(self) -> None:
        self.tbl_scenes.setRowCount(0)
        for s in self._current_scenes:
            row = self.tbl_scenes.rowCount()
            self.tbl_scenes.insertRow(row)

            item_idx = QTableWidgetItem(f"Cảnh {s.scene_index}")
            item_idx.setFlags(item_idx.flags() & ~Qt.ItemFlag.ItemIsEditable)

            item_voice = QTableWidgetItem(s.voice_text)
            item_prompt = QTableWidgetItem(s.visual_prompt)
            item_dur = QTableWidgetItem(f"{s.estimated_seconds:.1f}s")
            item_dur.setFlags(item_dur.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.tbl_scenes.setItem(row, 0, item_idx)
            self.tbl_scenes.setItem(row, 1, item_voice)
            self.tbl_scenes.setItem(row, 2, item_prompt)
            self.tbl_scenes.setItem(row, 3, item_dur)

    def _sync_scenes_from_table(self) -> list[SceneItem]:
        scenes: list[SceneItem] = []
        for row in range(self.tbl_scenes.rowCount()):
            voice = (self.tbl_scenes.item(row, 1).text() if self.tbl_scenes.item(row, 1) else "").strip()
            prompt = (self.tbl_scenes.item(row, 2).text() if self.tbl_scenes.item(row, 2) else "").strip()
            if not voice or not prompt:
                continue
            scenes.append(
                SceneItem(
                    scene_index=row + 1,
                    voice_text=voice,
                    visual_prompt=prompt,
                    estimated_seconds=max(3.0, len(voice.split()) * 0.35),
                )
            )
        return scenes

    def _on_add_scene(self) -> None:
        row = self.tbl_scenes.rowCount()
        self.tbl_scenes.insertRow(row)
        item_idx = QTableWidgetItem(f"Cảnh {row + 1}")
        item_idx.setFlags(item_idx.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.tbl_scenes.setItem(row, 0, item_idx)
        self.tbl_scenes.setItem(row, 1, QTableWidgetItem("Nhập câu thoại thuyết minh tại đây..."))
        self.tbl_scenes.setItem(row, 2, QTableWidgetItem("Cinematic vertical 9:16 prompt in English..."))
        self.tbl_scenes.setItem(row, 3, QTableWidgetItem("4.0s"))

    def _on_del_scene(self) -> None:
        cur_row = self.tbl_scenes.currentRow()
        if cur_row >= 0:
            self.tbl_scenes.removeRow(cur_row)

    def _on_start_pipeline(self) -> None:
        scenes = self._sync_scenes_from_table()
        if not scenes:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng bấm 'Viết Kịch Bản' hoặc thêm ít nhất 1 phân cảnh!")
            return

        topic = self.txt_topic.text().strip()
        voice = self.cbo_voice.currentData()
        bgm_mood = self.cbo_bgm.currentText()
        aspect_ratio = self.cbo_aspect.currentData()
        smooth = self.chk_smooth.isChecked()
        burn_sub = self.chk_burn_sub.isChecked()

        self.btn_start.setEnabled(False)
        self.btn_play_video.setEnabled(False)
        self.pbar.setValue(0)

        self._worker = PipelineRunWorker(
            topic=topic,
            scenes=scenes,
            voice=voice,
            bgm_mood=bgm_mood,
            smooth=smooth,
            burn_sub=burn_sub,
            aspect_ratio=aspect_ratio,
            log_cb=self._log,
        )
        self._worker.progress_signal.connect(self._on_pipeline_progress)
        self._worker.finished_signal.connect(self._on_pipeline_success)
        self._worker.error_signal.connect(self._on_pipeline_error)
        self._worker.start()

    @pyqtSlot(float, str)
    def _on_pipeline_progress(self, percent: float, status_msg: str) -> None:
        self.pbar.setValue(int(percent))
        self.lbl_story_status.setText(status_msg)

    @pyqtSlot(str)
    def _on_pipeline_success(self, final_video_path: str) -> None:
        self.btn_start.setEnabled(True)
        self.pbar.setValue(100)
        self._last_final_video = final_video_path
        self.btn_play_video.setEnabled(True)
        self.lbl_story_status.setText(f"🎉 Hoàn tất video Shorts: {Path(final_video_path).name}")
        QMessageBox.information(
            self,
            "Thành công rực rỡ",
            f"Đã tạo thành công video Shorts hoàn chỉnh!\n\nĐường dẫn: {final_video_path}",
        )

    @pyqtSlot(str)
    def _on_pipeline_error(self, err: str) -> None:
        self.btn_start.setEnabled(True)
        self.lbl_story_status.setText("❌ Quá trình tạo video thất bại.")
        QMessageBox.critical(self, "Lỗi tạo video Shorts", f"Đã xảy ra lỗi:\n{err}")

    def _on_open_folder(self) -> None:
        folder = Path(DOWNLOADS_DIR) / "shorts_studio"
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))

    def _on_play_video(self) -> None:
        if self._last_final_video and os.path.exists(self._last_final_video):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._last_final_video).resolve())))
