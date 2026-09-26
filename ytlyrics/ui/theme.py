from __future__ import annotations

# Monochrome glass palette (alpha values are literal for qlineargradient)
COLORS = {
    "bg": "#060606",
    "surface": "rgba(255, 255, 255, 0.045)",
    "surface2": "rgba(255, 255, 255, 0.075)",
    "border": "rgba(255, 255, 255, 0.10)",
    "text": "#f2f2f2",
    "muted": "#8f8f8f",
    "accent": "#ffffff",
    "success": "#ffffff",
    "danger": "#d8d8d8",
    "warn": "#b5b5b5",
}

# status -> (background, foreground, border)
STATUS_COLORS: dict[str, tuple[str, str, str]] = {
    "queued": ("rgba(255,255,255,0.06)", "#9a9a9a", "rgba(255,255,255,0.14)"),
    "downloading": ("rgba(255,255,255,0.10)", "#ffffff", "rgba(255,255,255,0.35)"),
    "aligning": ("rgba(255,255,255,0.10)", "#ffffff", "rgba(255,255,255,0.35)"),
    "rendering": ("rgba(255,255,255,0.10)", "#ffffff", "rgba(255,255,255,0.35)"),
    "uploading": ("rgba(255,255,255,0.10)", "#ffffff", "rgba(255,255,255,0.35)"),
    "done": ("#f2f2f2", "#0a0a0a", "#f2f2f2"),
    "cancelled": ("transparent", "#6f6f6f", "rgba(255,255,255,0.18)"),
    "failed": ("#0a0a0a", "#e8e8e8", "rgba(255,255,255,0.55)"),
}

ACTIVE_STATUSES = frozenset(
    {"downloading", "aligning", "rendering", "uploading"}
)

STYLE = f"""
* {{
    font-family: "Segoe UI", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: {COLORS['text']};
}}
QMainWindow {{
    background: transparent;
}}
QWidget {{
    background: transparent;
}}
QWidget#Sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(14,14,14,0.72), stop:1 rgba(8,8,8,0.58));
    border-right: 1px solid rgba(255,255,255,0.08);
}}
QLabel#Brand {{
    font-size: 17px;
    font-weight: 800;
    letter-spacing: 2px;
    color: #ffffff;
    padding: 4px 6px;
}}
QLabel#BrandSub {{
    font-size: 10px;
    color: #8f8f8f;
    letter-spacing: 3px;
    padding: 0 6px 14px 6px;
}}
QPushButton#Nav {{
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 11px 14px;
    text-align: left;
    font-size: 13px;
    font-weight: 600;
    color: #8f8f8f;
    margin: 2px 8px;
}}
QPushButton#Nav:hover {{
    background: rgba(255,255,255,0.06);
    color: #ffffff;
}}
QPushButton#Nav:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(255,255,255,0.16), stop:1 rgba(255,255,255,0.04));
    color: #ffffff;
    border-left: 3px solid #ffffff;
}}
QLabel#H1 {{
    font-size: 22px;
    font-weight: 800;
    color: #ffffff;
}}
QLabel#H2 {{
    font-size: 15px;
    font-weight: 700;
}}
QLabel#Muted {{
    color: #8f8f8f;
    font-size: 12px;
}}
QFrame#Card {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255,255,255,0.075), stop:1 rgba(255,255,255,0.030));
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 16px;
}}
QLabel#StatNumber {{
    font-size: 26px;
    font-weight: 800;
    color: #ffffff;
}}
QLabel#StatTitle {{
    font-size: 10px;
    color: #8f8f8f;
    letter-spacing: 2px;
}}
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255,255,255,0.10), stop:1 rgba(255,255,255,0.05));
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 600;
    color: #f2f2f2;
}}
QPushButton:hover {{
    border-color: rgba(255,255,255,0.45);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255,255,255,0.16), stop:1 rgba(255,255,255,0.08));
}}
QPushButton:pressed {{
    background: rgba(255,255,255,0.06);
}}
QPushButton:disabled {{
    color: #5a5a5a;
    border-color: rgba(255,255,255,0.06);
    background: rgba(255,255,255,0.03);
}}
QPushButton#Primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ffffff, stop:1 #cfcfcf);
    border: none;
    color: #0a0a0a;
    font-weight: 700;
}}
QPushButton#Primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ffffff, stop:1 #e8e8e8);
}}
QPushButton#Danger {{
    background: transparent;
    border: 1px solid rgba(255,255,255,0.35);
    color: #e8e8e8;
    padding: 5px 12px;
    font-size: 12px;
}}
QPushButton#Danger:hover {{
    background: rgba(255,255,255,0.12);
    border-color: #ffffff;
    color: #ffffff;
}}
QPushButton#Tiny {{
    padding: 4px 10px;
    font-size: 12px;
    border-radius: 8px;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: rgba(255,255,255,0.055);
    border: 1px solid rgba(255,255,255,0.11);
    border-radius: 10px;
    padding: 7px 10px;
    selection-background-color: #ffffff;
    selection-color: #0a0a0a;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: rgba(255,255,255,0.55);
    background: rgba(255,255,255,0.075);
}}
QLineEdit:hover, QComboBox:hover {{ border-color: rgba(255,255,255,0.25); }}
QComboBox::drop-down {{
    border: none;
    width: 26px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #9a9a9a;
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background: rgba(12,12,12,0.96);
    border: 1px solid rgba(255,255,255,0.14);
    selection-background-color: rgba(255,255,255,0.14);
    selection-color: #ffffff;
    outline: none;
    border-radius: 10px;
}}
QCheckBox {{
    spacing: 9px;
    padding: 4px 0;
}}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.28);
    background: rgba(255,255,255,0.05);
}}
QCheckBox::indicator:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ffffff, stop:1 #c9c9c9);
    border-color: #ffffff;
}}
QTableWidget {{
    background: rgba(8,8,8,0.55);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 16px;
    gridline-color: transparent;
    selection-background-color: rgba(255,255,255,0.10);
    selection-color: #ffffff;
    alternate-background-color: rgba(255,255,255,0.022);
}}
QTableWidget::item {{
    padding: 6px;
    border: none;
}}
QHeaderView::section {{
    background-color: rgba(255,255,255,0.04);
    color: #8f8f8f;
    border: none;
    border-bottom: 1px solid rgba(255,255,255,0.10);
    padding: 9px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QHeaderView::section:horizontal:hover {{ color: #ffffff; }}
QTableCornerButton::section {{
    background-color: rgba(255,255,255,0.04);
    border: none;
    border-bottom: 1px solid rgba(255,255,255,0.10);
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.18);
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.45); }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: rgba(255,255,255,0.18);
    border-radius: 5px;
    min-width: 30px;
}}
QProgressBar {{
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 8px;
    height: 14px;
    text-align: center;
    font-size: 10px;
    color: #9a9a9a;
}}
QProgressBar::chunk {{
    border-radius: 7px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ffffff, stop:1 #a8a8a8);
}}
QGroupBox {{
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 16px;
    margin-top: 16px;
    padding-top: 8px;
    font-weight: 700;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255,255,255,0.055), stop:1 rgba(255,255,255,0.025));
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #ffffff;
}}
QToolTip {{
    background: rgba(10,10,10,0.96);
    color: #f2f2f2;
    border: 1px solid rgba(255,255,255,0.16);
    padding: 6px 8px;
    border-radius: 8px;
}}
QSplitter::handle {{ background: rgba(255,255,255,0.10); }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QMenu {{
    background: rgba(12,12,12,0.97);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 24px 7px 14px;
    border-radius: 7px;
}}
QMenu::item:selected {{ background: rgba(255,255,255,0.12); }}
"""


def status_style(status: str) -> tuple[str, str]:
    """Returns (background, foreground) for a status pill."""
    bg, fg, _border = STATUS_COLORS.get(status, STATUS_COLORS["queued"])
    return bg, fg
