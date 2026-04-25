"""主题 / QSS 样式。深色为主，浅色备选。"""
from __future__ import annotations

from typing import Literal

ThemeName = Literal["dark", "light"]

# 设计 token
TOKENS_DARK = {
    "bg":            "#1a1a2e",
    "bg_alt":        "#16162a",
    "surface":       "#2a2a3e",
    "surface_hover": "#3a3a4e",
    "border":        "#3a3a4e",
    "text":          "#e0e0e0",
    "text_muted":    "#888888",
    "text_dim":      "#666666",
    "primary":       "#00d4aa",
    "primary_hover": "#1ee5be",
    "danger":        "#ff6b6b",
    "warn":          "#ffd93d",
    "ok":            "#00d4aa",
}

TOKENS_LIGHT = {
    "bg":            "#fafbfc",
    "bg_alt":        "#ffffff",
    "surface":       "#f0f1f4",
    "surface_hover": "#e3e5ea",
    "border":        "#dcdee3",
    "text":          "#1a1a2e",
    "text_muted":    "#666666",
    "text_dim":      "#999999",
    "primary":       "#00b894",
    "primary_hover": "#00a884",
    "danger":        "#d63031",
    "warn":          "#fdcb6e",
    "ok":            "#00b894",
}


def _qss(t: dict[str, str]) -> str:
    return f"""
* {{
    font-family: "Microsoft YaHei UI", "Segoe UI", "Helvetica Neue", sans-serif;
}}

QMainWindow, QDialog, QWidget#central {{
    background-color: {t['bg']};
    color: {t['text']};
}}

QMenuBar {{
    background-color: {t['bg']};
    color: {t['text']};
    border: none;
    padding: 2px 4px;
}}
QMenuBar::item {{
    padding: 6px 12px;
    background-color: transparent;
}}
QMenuBar::item:selected {{
    background-color: {t['surface']};
    border-radius: 4px;
}}
QMenu {{
    background-color: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border']};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {t['primary']};
    color: {t['bg']};
}}
QMenu::separator {{
    height: 1px;
    background-color: {t['border']};
    margin: 4px 8px;
}}

QToolBar {{
    background-color: {t['bg']};
    border: none;
    spacing: 6px;
    padding: 8px 12px;
}}
QToolBar::separator {{
    background-color: {t['border']};
    width: 1px;
    margin: 4px 6px;
}}

QPushButton {{
    background-color: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 500;
    min-height: 22px;
}}
QPushButton:hover:enabled {{
    background-color: {t['surface_hover']};
    border-color: {t['primary']};
}}
QPushButton:pressed:enabled {{
    background-color: {t['border']};
}}
QPushButton:disabled {{
    color: {t['text_dim']};
    background-color: {t['bg_alt']};
    border-color: {t['bg_alt']};
}}
QPushButton#primary {{
    background-color: {t['primary']};
    color: {t['bg']};
    border: none;
    font-weight: bold;
}}
QPushButton#primary:hover:enabled {{
    background-color: {t['primary_hover']};
}}
QPushButton#danger {{
    background-color: {t['danger']};
    color: white;
    border: none;
    font-weight: bold;
}}

QComboBox {{
    background-color: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 22px;
    min-width: 180px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border']};
    selection-background-color: {t['primary']};
    selection-color: {t['bg']};
    padding: 4px;
}}

QLineEdit {{
    background-color: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 8px 12px;
    selection-background-color: {t['primary']};
    selection-color: {t['bg']};
}}
QLineEdit:focus {{
    border-color: {t['primary']};
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 4px;
    padding: 4px 8px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 14px;
}}

QLabel {{
    color: {t['text']};
}}
QLabel#muted {{
    color: {t['text_muted']};
    font-size: 12px;
}}
QLabel#title {{
    font-size: 18px;
    font-weight: bold;
    color: {t['text']};
}}
QLabel#h2 {{
    font-size: 14px;
    font-weight: 600;
    color: {t['text']};
}}

QLabel#statusBadge {{
    background-color: {t['surface']};
    border-radius: 12px;
    padding: 4px 14px;
    color: {t['text_muted']};
    font-weight: 600;
    font-size: 12px;
}}
QLabel#statusBadge[state="running"] {{
    background-color: {t['primary']};
    color: {t['bg']};
}}
QLabel#statusBadge[state="busy"] {{
    background-color: {t['warn']};
    color: {t['bg']};
}}
QLabel#statusBadge[state="error"] {{
    background-color: {t['danger']};
    color: white;
}}

QGroupBox {{
    border: 1px solid {t['border']};
    border-radius: 10px;
    margin-top: 16px;
    padding-top: 12px;
    color: {t['text_muted']};
    font-weight: 500;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: {t['text_muted']};
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

QTextEdit {{
    background-color: {t['bg_alt']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 12px;
    font-size: 14px;
    selection-background-color: {t['primary']};
    selection-color: {t['bg']};
}}

QStatusBar {{
    background-color: {t['bg_alt']};
    color: {t['text_muted']};
    border-top: 1px solid {t['border']};
    padding: 4px 12px;
}}

QTabWidget::pane {{
    border: 1px solid {t['border']};
    border-radius: 8px;
    background-color: {t['bg_alt']};
    top: -1px;
}}
QTabBar::tab {{
    background-color: {t['surface']};
    color: {t['text']};
    padding: 8px 22px;
    border: 1px solid {t['border']};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {t['bg_alt']};
    border-color: {t['primary']};
    color: {t['primary']};
    font-weight: bold;
}}

QSplitter::handle {{
    background-color: {t['border']};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

QCheckBox {{
    color: {t['text']};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {t['border']};
    border-radius: 3px;
    background-color: {t['surface']};
}}
QCheckBox::indicator:checked {{
    background-color: {t['primary']};
    border-color: {t['primary']};
    image: none;
}}

QScrollBar:vertical {{
    background-color: {t['bg_alt']};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {t['border']};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {t['surface_hover']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


def stylesheet(theme: ThemeName) -> str:
    tokens = TOKENS_DARK if theme == "dark" else TOKENS_LIGHT
    return _qss(tokens)


def tokens(theme: ThemeName) -> dict[str, str]:
    return TOKENS_DARK if theme == "dark" else TOKENS_LIGHT
