# -*- coding: utf-8 -*-
"""
Modern Dark Theme for TOOL VEO PROMAX Desktop App (PyQt6).
Designed with Tailwind-inspired Slate/Zinc dark palette, glassmorphism accents,
crisp borders, and high-readability typography.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication

DARK_STYLESHEET = """
/* ==========================================================================
   GLOBAL APP STYLES
   ========================================================================== */
QMainWindow, QDialog {
    background-color: #0b0f17;
}

QWidget {
    color: #f1f5f9;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 13px;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
}

/* ==========================================================================
   HEADER & TOOLBAR WIDGETS
   ========================================================================== */
QWidget#AppHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:1 #1e1b4b);
    border-bottom: 1px solid #1e293b;
}

QLabel#HeaderTitle {
    font-size: 16px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 0.5px;
}

QLabel#HeaderSubtitle {
    font-size: 11px;
    color: #94a3b8;
}

QLabel#BadgeVersion {
    background-color: #1e293b;
    color: #38bdf8;
    border: 1px solid #0284c7;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 700;
}

QLabel#BadgeLicense {
    background-color: #064e3b;
    color: #34d399;
    border: 1px solid #059669;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 700;
}

/* ==========================================================================
   TAB WIDGET (NAVIGATION)
   ========================================================================== */
QTabWidget::pane {
    border: 1px solid #1e293b;
    background-color: #0f172a;
    border-radius: 8px;
    top: -1px;
}

QTabBar::tab {
    background-color: #1e293b;
    color: #94a3b8;
    border: 1px solid #334155;
    border-bottom: none;
    padding: 9px 18px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 600;
    font-size: 12px;
}

QTabBar::tab:hover {
    background-color: #273549;
    color: #f8fafc;
}

QTabBar::tab:selected {
    background-color: #0f172a;
    color: #38bdf8;
    border: 1px solid #1e293b;
    border-bottom: 2px solid #38bdf8;
    font-weight: 700;
}

/* ==========================================================================
   BUTTONS
   ========================================================================== */
QPushButton {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}

QPushButton:pressed {
    background-color: #0f172a;
}

QPushButton:disabled {
    background-color: #111827;
    color: #475569;
    border-color: #1f2937;
}

/* Primary Action Button (Blue) */
QPushButton#BtnPrimary, QPushButton[primary="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #3b82f6);
    color: #ffffff;
    border: 1px solid #60a5fa;
    font-weight: 700;
}

QPushButton#BtnPrimary:hover, QPushButton[primary="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #2563eb);
    border-color: #93c5fd;
}

/* Success Action Button (Green) */
QPushButton#BtnSuccess, QPushButton[success="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
    color: #ffffff;
    border: 1px solid #34d399;
    font-weight: 700;
}

QPushButton#BtnSuccess:hover, QPushButton[success="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
}

/* Danger / Stop Button (Red) */
QPushButton#BtnDanger, QPushButton[danger="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #ef4444);
    color: #ffffff;
    border: 1px solid #f87171;
    font-weight: 700;
}

QPushButton#BtnDanger:hover, QPushButton[danger="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b91c1c, stop:1 #dc2626);
}

/* Secondary Button (Dark Slate) */
QPushButton#BtnSecondary {
    background-color: #1e293b;
    border: 1px solid #334155;
    color: #cbd5e1;
}

/* ==========================================================================
   INPUTS (TEXT, COMBO, SPIN)
   ========================================================================== */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
    background-color: #111827;
    color: #f8fafc;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 6px 10px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {
    border: 1px solid #38bdf8;
    background-color: #0b1120;
}

QComboBox {
    background-color: #111827;
    color: #f8fafc;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 20px;
}

QComboBox:focus, QComboBox:hover {
    border-color: #38bdf8;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid #374151;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #475569;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    padding: 4px;
    outline: none;
}

/* ==========================================================================
   TABLE & LIST WIDGETS
   ========================================================================== */
QTableWidget, QTreeWidget, QListWidget {
    background-color: #0b1120;
    color: #f8fafc;
    gridline-color: #1e293b;
    border: 1px solid #1e293b;
    border-radius: 6px;
    selection-background-color: #1e3a5f;
    selection-color: #38bdf8;
    outline: none;
}

QTableWidget::item, QListWidget::item {
    padding: 6px;
    border-bottom: 1px solid #131c2e;
}

QTableWidget::item:hover, QListWidget::item:hover {
    background-color: #162032;
}

QTableWidget::item:selected, QListWidget::item:selected {
    background-color: #1e3a8a;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #94a3b8;
    padding: 7px 10px;
    border: none;
    border-right: 1px solid #334155;
    border-bottom: 1px solid #334155;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
}

/* ==========================================================================
   GROUP BOX & CARDS
   ========================================================================== */
QGroupBox {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 8px;
    margin-top: 18px;
    padding: 14px;
    font-weight: 700;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #38bdf8;
    font-size: 12px;
    font-weight: 700;
}

/* ==========================================================================
   PROGRESS BAR
   ========================================================================== */
QProgressBar {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    text-align: center;
    color: #ffffff;
    font-weight: 700;
    height: 18px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #38bdf8);
    border-radius: 5px;
}

/* ==========================================================================
   SCROLL BARS
   ========================================================================== */
QScrollBar:vertical {
    border: none;
    background: #0b0f17;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #0b0f17;
    height: 8px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #334155;
    min-width: 24px;
    border-radius: 4px;
}

/* ==========================================================================
   SCROLL AREA & CHECKBOXES
   ========================================================================== */
QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QScrollArea QWidget#qt_scrollarea_viewport {
    background-color: transparent;
    border: none;
}

QScrollArea QWidget#qt_scrollarea_hcontainer,
QScrollArea QWidget#qt_scrollarea_vcontainer {
    background-color: transparent;
}

QCheckBox {
    spacing: 7px;
    color: #cbd5e1;
    font-size: 12px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #475569;
    border-radius: 4px;
    background-color: #1e293b;
}

QCheckBox::indicator:hover {
    border-color: #38bdf8;
}

QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #60a5fa;
}

/* ==========================================================================
   LOG CONSOLE
   ========================================================================== */
QPlainTextEdit#LogConsole {
    background-color: #06090e;
    color: #38bdf8;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 8px;
}

/* ==========================================================================
   STATUS BAR
   ========================================================================== */
QStatusBar {
    background-color: #0b0f17;
    color: #64748b;
    border-top: 1px solid #1e293b;
    font-size: 11px;
}

/* ==========================================================================
   MESSAGE BOXES & DIALOGS
   ========================================================================== */
QMessageBox, QDialog {
    background-color: #0f172a;
    color: #f8fafc;
}

QMessageBox QLabel {
    color: #f8fafc;
    font-size: 13px;
}

QMessageBox QPushButton {
    min-width: 80px;
}
"""


def apply_dark_theme(app: QApplication) -> None:
    """Áp dụng toàn bộ Dark Theme bảng màu Slate/Zinc hiện đại cho ứng dụng."""
    app.setStyle("Fusion")

    # Thiết lập Palette màu tối cho Qt
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0b0f17"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1e293b"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1e293b"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#1e293b"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#38bdf8"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#38bdf8"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2563eb"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))

    app.setPalette(palette)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(DARK_STYLESHEET)
