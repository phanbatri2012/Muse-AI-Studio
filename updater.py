"""
updater.py — Auto-update checker cho VEO Tool.

Chạy trong background thread ngay sau khi MainWindow hiển thị.
Nếu server có version mới hơn version hiện tại → show dialog PyQt6
sau 12 giây (đủ thời gian fetch xong và user đã thấy app).

Không crash app nếu server không trả về / mạng chậm / lỗi parse.
"""
from __future__ import annotations

import re
import threading

VERSION_URL = "https://veo-license-dashboard.vercel.app/api/version"
FETCH_TIMEOUT = 10        # seconds
SHOW_DELAY_MS = 12_000    # ms sau khi start_update_check() mới show dialog


# ── version parsing ──────────────────────────────────────────────────────────

def _parse_ver(v: str) -> tuple[int, ...]:
    """'V2.3.0' → (2, 3, 0). Trả () nếu không parse được."""
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums) if nums else ()


def _is_newer(remote: str, current: str) -> bool:
    r, c = _parse_ver(remote), _parse_ver(current)
    return bool(r and c and r > c)


# ── shared state (set by worker thread, read by main thread via QTimer) ──────

_pending: dict | None = None   # {"version": ..., "download_url": ..., "release_notes": ...}
_lock = threading.Lock()


def _worker(current_version: str) -> None:
    global _pending
    try:
        import requests
        r = requests.get(VERSION_URL, timeout=FETCH_TIMEOUT)
        if r.status_code != 200:
            return
        data: dict = r.json()
        remote  = str(data.get("version", "") or "")
        url     = str(data.get("download_url", "") or "")
        notes   = str(data.get("release_notes", "") or "")
        if _is_newer(remote, current_version) and url:
            with _lock:
                _pending = {"version": remote, "download_url": url, "release_notes": notes}
    except Exception:
        pass  # silent — update check should never crash the app


def _show_dialog(parent) -> None:
    global _pending
    with _lock:
        info = _pending
        _pending = None

    if not info:
        return

    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
    from PyQt6.QtCore import Qt, QUrl
    from PyQt6.QtGui import QDesktopServices

    dlg = QDialog(parent)
    dlg.setWindowTitle("Có bản cập nhật mới!")
    dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    dlg.setFixedWidth(400)

    lay = QVBoxLayout(dlg)
    lay.setSpacing(12)
    lay.setContentsMargins(20, 20, 20, 20)

    # Icon + title
    title = QLabel(f"🚀  Bản cập nhật <b>{info['version']}</b> đã sẵn sàng!")
    title.setWordWrap(True)
    title.setStyleSheet("font-size:14px; color:#1e3a5f;")
    lay.addWidget(title)

    # Release notes
    if info["release_notes"]:
        notes_lbl = QLabel(info["release_notes"])
        notes_lbl.setWordWrap(True)
        notes_lbl.setStyleSheet(
            "font-size:12px; color:#374151; background:#f0f7ff; "
            "border:1px solid #bfdbfe; border-radius:8px; padding:8px;"
        )
        lay.addWidget(notes_lbl)

    hint = QLabel("Tải về và cài đè lên phiên bản cũ — license không bị ảnh hưởng.")
    hint.setWordWrap(True)
    hint.setStyleSheet("font-size:11px; color:#6b7280;")
    lay.addWidget(hint)

    # Buttons
    btn_row = QHBoxLayout()
    btn_later = QPushButton("Để sau")
    btn_later.setStyleSheet(
        "QPushButton { background:#e5e7eb; color:#374151; border:none; "
        "border-radius:8px; padding:8px 18px; font-size:12px; font-weight:600; }"
        "QPushButton:hover { background:#d1d5db; }"
    )
    btn_later.clicked.connect(dlg.reject)

    btn_download = QPushButton("⬇  Tải về ngay")
    btn_download.setStyleSheet(
        "QPushButton { background:#2563eb; color:white; border:none; "
        "border-radius:8px; padding:8px 18px; font-size:12px; font-weight:700; }"
        "QPushButton:hover { background:#1d4ed8; }"
    )
    btn_download.clicked.connect(lambda: (
        QDesktopServices.openUrl(QUrl(info["download_url"])),
        dlg.accept(),
    ))

    btn_row.addWidget(btn_later)
    btn_row.addWidget(btn_download)
    lay.addLayout(btn_row)

    dlg.exec()


# ── public API ────────────────────────────────────────────────────────────────

def start_update_check(current_version: str, parent_widget) -> None:
    """
    Gọi sau khi MainWindow đã show().
    - Fetch version info trong background thread.
    - Nếu có bản mới → show dialog sau SHOW_DELAY_MS.
    """
    threading.Thread(
        target=_worker,
        args=(current_version,),
        daemon=True,
        name="veo-update-check",
    ).start()

    from PyQt6.QtCore import QTimer
    QTimer.singleShot(SHOW_DELAY_MS, lambda: _show_dialog(parent_widget))
