from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_LEVEL_COLORS = {
    "info": "#c9c9c9",
    "ok": "#ffffff",
    "warn": "#a8a8a8",
    "error": "#e8e8e8",
    "debug": "#6f6f6f",
}


class LogPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 24)
        root.setSpacing(12)

        head = QHBoxLayout()
        h1 = QLabel("Logs")
        h1.setObjectName("H1")
        self.autoscroll = QCheckBox("Auto-scroll")
        self.autoscroll.setChecked(True)
        clear = QPushButton("Clear")
        clear.setObjectName("Tiny")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(self.clear)
        head.addWidget(h1)
        head.addStretch()
        head.addWidget(self.autoscroll)
        head.addWidget(clear)
        root.addLayout(head)

        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.view.setAcceptRichText(True)
        self.view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        font = QFont("Menlo")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self.view.setFont(font)
        self.view.setStyleSheet(
            "QTextEdit { background: rgba(8,8,8,0.55);"
            " border: 1px solid rgba(255,255,255,0.09);"
            " border-radius: 16px; padding: 12px; }"
        )
        root.addWidget(self.view, 1)

    def append(self, message: str, level: str = "info") -> None:
        color = _LEVEL_COLORS.get(level, _LEVEL_COLORS["info"])
        stamp = time.strftime("%H:%M:%S")
        safe = (
            message.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        html = (
            f'<span style="color:#5f5f5f">{stamp}</span> '
            f'<span style="color:{color}">{safe}</span>'
        )
        self.view.append(html)
        if self.autoscroll.isChecked():
            sb = self.view.verticalScrollBar()
            sb.setValue(sb.maximum())

    def clear(self) -> None:
        self.view.clear()
