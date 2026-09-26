from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ytlyrics.core.models import STATUS_LABELS

from .theme import ACTIVE_STATUSES, STATUS_COLORS


class StatusPill(QLabel):
    """Monochrome status pill with a soft pulse for active states."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status = "queued"
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._tick)
        self.set_status("queued")

    def set_status(self, status: str) -> None:
        self._status = status
        self.setText(STATUS_LABELS.get(status, status))
        if status in ACTIVE_STATUSES:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
            self._phase = 0.0
        self._apply()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.14) % 1.0
        self._apply()

    def _apply(self) -> None:
        bg, fg, border = STATUS_COLORS.get(
            self._status, STATUS_COLORS["queued"]
        )
        if self._status in ACTIVE_STATUSES:
            glow = 0.35 + 0.45 * abs(self._phase * 2 - 1)
            border = f"rgba(255,255,255,{glow:.2f})"
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; border-radius: 10px;"
            f" padding: 3px 10px; font-size: 11px; font-weight: 700;"
            f" border: 1px solid {border};"
        )

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)


class StatCard(QFrame):
    """Glass stat card with animated count-up numbers."""

    def __init__(self, title: str, accent: str = "#ffffff",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._value = 0
        self._number = QLabel("0")
        self._number.setObjectName("StatNumber")
        self._number.setStyleSheet(f"color: {accent};")
        label = QLabel(title.upper())
        label.setObjectName("StatTitle")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(2)
        lay.addWidget(self._number)
        lay.addWidget(label)
        self._anim: QVariantAnimation | None = None

    def set_value(self, value: int) -> None:
        if value == self._value:
            return
        start = self._value
        self._value = value
        anim = QVariantAnimation(self)
        anim.setDuration(380)
        anim.setStartValue(start)
        anim.setEndValue(value)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(
            lambda v: self._number.setText(str(int(v)))
        )
        if self._anim is not None:
            self._anim.stop()
        self._anim = anim
        anim.start()


class TitleBar(QFrame):
    close_clicked = Signal()
    min_clicked = Signal()
    max_clicked = Signal()

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(46)
        self.setStyleSheet(
            "TitleBar { background: transparent;"
            " border-bottom: 1px solid rgba(255,255,255,0.07); }"
        )
        self._drag_pos: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 8, 0)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "color: #8f8f8f; font-size: 11px; font-weight: 700;"
            " letter-spacing: 3px; background: transparent; border: none;"
        )
        layout.addWidget(title_lbl)
        layout.addStretch()

        for text, slot in (
            ("\u2013", self.min_clicked.emit),
            ("\u25a1", self.max_clicked.emit),
            ("\u2715", self.close_clicked.emit),
        ):
            btn = QPushButton(text)
            btn.setFixedSize(42, 30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: none;"
                " color: #9a9a9a; font-size: 14px; font-weight: 700;"
                " border-radius: 8px; }"
                "QPushButton:hover { background: rgba(255,255,255,0.12);"
                " color: #ffffff; }"
                "QPushButton:pressed { background: rgba(255,255,255,0.06); }"
            )
            btn.clicked.connect(slot)
            layout.addWidget(btn)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            win = self.window()
            win.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        del event
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event) -> None:
        del event
        self.max_clicked.emit()


class NavButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("Nav")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)


class Spinner(QWidget):
    """Small indeterminate activity indicator."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self._angle = 0
        self._timer_id = 0

    def start(self) -> None:
        if not self._timer_id:
            self._timer_id = self.startTimer(30)

    def stop(self) -> None:
        if self._timer_id:
            self.killTimer(self._timer_id)
            self._timer_id = 0

    def timerEvent(self, event) -> None:
        del event
        self._angle = (self._angle + 12) % 360
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#ffffff"), 2.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(2, 2, 14, 14, -self._angle * 16, 110 * 16)


def fade_in(widget: QWidget, duration: int = 260) -> None:
    anim = QPropertyAnimation(widget, b"windowOpacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    widget._fade_anim = anim
    anim.start()


class ClickableCard(QFrame):
    """Glass card container with a vertical layout."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(18, 16, 18, 16)
        self._lay.setSpacing(10)

    @property
    def layout_(self) -> QVBoxLayout:
        return self._lay


def big_font(size: int = 26, weight: int = QFont.Weight.Bold) -> QFont:
    f = QFont()
    f.setPointSize(size)
    f.setWeight(weight)
    return f
