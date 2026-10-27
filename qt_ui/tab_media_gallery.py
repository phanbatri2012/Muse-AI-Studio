# -*- coding: utf-8 -*-
"""
Native PyQt6 Media Gallery Tab dedicated to Muse AI.
Scans and displays all generated videos from Muse AI with thumbnail previews,
file metadata, quick desktop playback, and folder explorer.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSlot
from PyQt6.QtGui import QColor, QDesktopServices, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from runtime_paths import MUSE_DOWNLOADS_DIR
from settings_manager import SettingsManager


class MediaGalleryTab(QWidget):
    def __init__(self, log_callback=None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_callback = log_callback
        self._all_items: list[dict] = []
        self._current_rendered_items: list[dict] = []
        self._pixmap_cache: dict[str, QPixmap] = {}
        self._dirty: bool = True

        self._init_ui()
        self.refresh_gallery(force=True)

    def _log(self, msg: str) -> None:
        if callable(self.log_callback):
            self.log_callback(msg)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header & Filter Toolbar
        tb_group = QGroupBox("🎬 THƯ VIỆN VIDEO MUSE AI")
        tb_layout = QHBoxLayout(tb_group)
        tb_layout.setContentsMargins(10, 14, 10, 10)
        tb_layout.setSpacing(10)

        tb_layout.addWidget(QLabel("🔍 Tìm kiếm:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Nhập từ khóa tìm kiếm trong prompt hoặc tên file...")
        self.search_input.textChanged.connect(self._filter_items)
        tb_layout.addWidget(self.search_input, 2)

        self.btn_refresh = QPushButton("🔄 Làm Mới")
        self.btn_refresh.clicked.connect(lambda: self.refresh_gallery(force=True))
        tb_layout.addWidget(self.btn_refresh)

        self.btn_open_muse_folder = QPushButton("📂 Mở Thư Mục Video")
        self.btn_open_muse_folder.setStyleSheet("color: #38bdf8; font-weight: 600;")
        self.btn_open_muse_folder.clicked.connect(lambda: self._open_folder(self._get_target_dir()))
        tb_layout.addWidget(self.btn_open_muse_folder)

        self.lbl_stats = QLabel("0 videos")
        self.lbl_stats.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 11px;")
        tb_layout.addWidget(self.lbl_stats)

        layout.addWidget(tb_group)

        # Table of Videos with Smooth Pixel Scrolling
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Xem Trước", "Tên File", "Kích Thước", "Thời Gian Tạo", "Thao Tác"])
        self.table.setIconSize(self.table.iconSize())
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.verticalScrollBar().setSingleStep(16)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        layout.addWidget(self.table, 1)

    def mark_dirty(self) -> None:
        self._dirty = True

    def _get_target_dir(self) -> Path:
        """Lấy thư mục lưu video được cấu hình trong SettingsManager."""
        try:
            st = SettingsManager.load_muse_settings()
            custom_dir = str(st.get("download_dir") or "").strip()
            if custom_dir:
                p = Path(custom_dir)
                p.mkdir(parents=True, exist_ok=True)
                return p
        except Exception:
            pass
        return MUSE_DOWNLOADS_DIR

    def refresh_gallery(self, force: bool = False) -> None:
        """Quét toàn bộ video từ thư mục output của Muse AI (đồng bộ với Settings)."""
        if not force and not self._dirty and self._all_items:
            self._render_items(self._all_items)
            return

        self._dirty = False
        items: list[dict] = []
        target_dir = self._get_target_dir()
        seen_paths: set[Path] = set()

        dirs_to_scan = [target_dir]
        from runtime_paths import DOWNLOADS_DIR
        if DOWNLOADS_DIR.exists() and DOWNLOADS_DIR.resolve() != target_dir.resolve():
            dirs_to_scan.append(DOWNLOADS_DIR)

        for d in dirs_to_scan:
            if not d.exists():
                continue
            for f in d.glob("**/*.mp4"):
                f_res = f.resolve()
                if f_res in seen_paths:
                    continue
                seen_paths.add(f_res)
                try:
                    stat = f.stat()
                    thumb = f.with_suffix(".jpg")
                    meta_f = f.with_name(f"{f.stem}_meta.json")
                    meta = {}
                    if meta_f.is_file():
                        try:
                            meta = json.loads(meta_f.read_text(encoding="utf-8"))
                        except Exception:
                            pass

                    items.append({
                        "path": f,
                        "filename": f.name,
                        "prompt": meta.get("prompt", ""),
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "mtime": stat.st_mtime,
                        "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "thumbnail": thumb if thumb.is_file() else None,
                    })
                except Exception:
                    pass

        # Sắp xếp mới nhất lên đầu
        items.sort(key=lambda x: x["mtime"], reverse=True)
        self._all_items = items
        self._render_items(self._all_items)

    def _render_items(self, items: list[dict]) -> None:
        self._current_rendered_items = list(items)
        self.table.setRowCount(0)
        self.lbl_stats.setText(f"Tổng số: {len(items)} videos")

        if not items:
            self.table.setRowCount(1)
            empty_item = QTableWidgetItem("🎬 Thư mục chưa có video nào. Hãy bắt đầu tạo video tại tab 'Xưởng Tạo Video' hoặc 'Đồng Bộ Nhân Vật'!")
            empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_item.setForeground(QColor("#94a3b8"))
            self.table.setItem(0, 1, empty_item)
            return

        for row, item in enumerate(items):
            self.table.insertRow(row)

            # 0. Thumbnail Preview with RAM Cache
            thumb_lbl = QLabel()
            thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if item["thumbnail"]:
                thumb_path = str(item["thumbnail"])
                if thumb_path not in self._pixmap_cache:
                    try:
                        self._pixmap_cache[thumb_path] = QPixmap(thumb_path).scaled(
                            64, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                        )
                    except Exception:
                        self._pixmap_cache[thumb_path] = QPixmap()
                thumb_lbl.setPixmap(self._pixmap_cache[thumb_path])
            else:
                thumb_lbl.setText("🎬 Video")
                thumb_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
            self.table.setCellWidget(row, 0, thumb_lbl)

            # 1. Filename & Prompt
            fn_text = item["filename"]
            if item["prompt"]:
                fn_text += f"\nPrompt: {item['prompt'][:70]}..."
            fn_item = QTableWidgetItem(fn_text)
            fn_item.setToolTip(f"Đường dẫn: {item['path']}\nPrompt: {item['prompt']}")
            self.table.setItem(row, 1, fn_item)

            # 2. Size
            self.table.setItem(row, 2, QTableWidgetItem(f"{item['size_mb']} MB"))

            # 3. Created Date
            self.table.setItem(row, 3, QTableWidgetItem(item["created_at"]))

            # 4. Actions Widget
            actions = QWidget()
            act_layout = QHBoxLayout(actions)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(6)

            btn_play = QPushButton("▶️ Phát")
            btn_play.setFixedHeight(24)
            btn_play.setStyleSheet("padding: 2px 8px; font-size: 11px;")
            v_path = item["path"]
            btn_play.clicked.connect(lambda _, p=v_path: self._play_video(p))
            act_layout.addWidget(btn_play)

            btn_folder = QPushButton("📂 Thư Mục")
            btn_folder.setFixedHeight(24)
            btn_folder.setStyleSheet("padding: 2px 8px; font-size: 11px;")
            btn_folder.clicked.connect(lambda _, p=v_path: self._open_folder(p.parent))
            act_layout.addWidget(btn_folder)

            btn_delete = QPushButton("🗑️")
            btn_delete.setFixedWidth(28)
            btn_delete.setFixedHeight(24)
            btn_delete.setToolTip("Xóa video khỏi đĩa")
            btn_delete.setStyleSheet("padding: 2px; font-size: 11px; color: #f87171;")
            btn_delete.clicked.connect(lambda _, it=item: self._delete_video(it))
            act_layout.addWidget(btn_delete)

            self.table.setCellWidget(row, 4, actions)

    def _filter_items(self, text: str) -> None:
        query = str(text or "").strip().lower()
        if not query:
            self._render_items(self._all_items)
            return

        filtered = [
            it for it in self._all_items
            if query in it["filename"].lower() or query in it.get("prompt", "").lower()
        ]
        self._render_items(filtered)

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        if hasattr(self, "_current_rendered_items") and 0 <= row < len(self._current_rendered_items):
            item = self._current_rendered_items[row]
            self._play_video(item["path"])

    def _delete_video(self, item: dict) -> None:
        v_path: Path = item["path"]
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa video",
            f"Bạn có chắc chắn muốn xóa video '{v_path.name}' khỏi máy tính?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if v_path.is_file():
                    v_path.unlink()
                thumb = v_path.with_suffix(".jpg")
                if thumb.is_file():
                    thumb.unlink()
                meta_f = v_path.with_name(f"{v_path.stem}_meta.json")
                if meta_f.is_file():
                    meta_f.unlink()
                self._pixmap_cache.pop(str(thumb), None)
                self.mark_dirty()
                self._log(f"🗑️ Đã xóa video: {v_path.name}")
                self.refresh_gallery(force=True)
            except Exception as exc:
                QMessageBox.critical(self, "Lỗi xóa video", f"Không thể xóa file: {exc}")

    def _play_video(self, path: Path) -> None:
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
        else:
            QMessageBox.warning(self, "Không tìm thấy file", f"File video không còn tồn tại tại: {path}")

    def _open_folder(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))
