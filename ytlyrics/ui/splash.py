from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from ytlyrics import POWERED_BY

TOTAL_MS = 3400
FADE_MS = 380


class SplashWindow(QWidget):
    finished = Signal()

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(560, 340)
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )

        self._elapsed = 0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._dust = [
            (0.18, 0.30, 46.0, 0.9, 0.0),
            (0.72, 0.24, 60.0, 0.7, 1.7),
            (0.55, 0.72, 38.0, 1.1, 3.1),
            (0.30, 0.78, 52.0, 0.8, 4.4),
            (0.86, 0.60, 30.0, 1.3, 2.2),
        ]

    def start(self) -> None:
        self._elapsed = 0
        self.show()
        self._timer.start()

    def _tick(self) -> None:
        self._elapsed += self._timer.interval()
        if self._elapsed >= TOTAL_MS + FADE_MS:
            self._timer.stop()
            self.close()
            self.finished.emit()
            return
        self.update()

    def closeEvent(self, event) -> None:
        if self._timer.isActive():
            self._timer.stop()
        super().closeEvent(event)

    @staticmethod
    def _ease(x: float) -> float:
        x = max(0.0, min(1.0, x))
        return 1 - (1 - x) ** 3

    def paintEvent(self, event) -> None:
        del event
        t = self._elapsed / 1000.0
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # global fade in / out
        alpha = 1.0
        if self._elapsed < 300:
            alpha = self._elapsed / 300.0
        if self._elapsed > TOTAL_MS:
            alpha = max(0.0, 1.0 - (self._elapsed - TOTAL_MS) / FADE_MS)
        p.setOpacity(alpha)

        # ---- background card + moving glow
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 22, 22)
        p.fillPath(path, QColor("#070707"))

        grad = QLinearGradient(0, 0, w, h)
        shift = 0.5 + 0.5 * math.sin(t * 0.9)
        grad.setColorAt(max(0.0, shift - 0.35), QColor(255, 255, 255, 34))
        grad.setColorAt(min(1.0, shift + 0.2), QColor(255, 255, 255, 22))
        grad.setColorAt(1.0, QColor(255, 255, 255, 10))
        p.fillPath(path, grad)

        for bx, by, r, spd, phase in self._dust:
            cx = bx * w + math.sin(t * spd + phase) * 26
            cy = by * h + math.cos(t * spd * 0.8 + phase) * 18
            rad = QRadialGradient(QPointF(cx, cy), r)
            a = int(16 + 12 * math.sin(t * 1.6 + phase))
            rad.setColorAt(0.0, QColor(255, 255, 255, max(6, a)))
            rad.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(rad)
            p.drawEllipse(QPointF(cx, cy), r, r)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QLinearGradient(24, 0, w - 24, 0)
        pen.setColorAt(0, QColor(255, 255, 255, 0))
        pen.setColorAt(0.5, QColor(255, 255, 255, 150))
        pen.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(pen)
        p.drawRoundedRect(QRectF(24, h - 66, w - 48, 2), 1, 1)

        # ---- text: "This Project Powered By"
        sub = POWERED_BY.split("Vi3ecode", 1)[0].strip()
        sub_t = self._ease((t - 0.25) / 0.8)
        if sub_t > 0:
            font = QFont()
            font.setPointSize(12)
            font.setWeight(QFont.Weight.DemiBold)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0 + 3.0 * (1 - sub_t))
            p.setFont(font)
            p.setOpacity(alpha * sub_t)
            p.setPen(QColor("#a5a5a5"))
            slide = 14 * (1 - sub_t)
            p.drawText(
                QRectF(0, 74 + slide, w, 30),
                Qt.AlignmentFlag.AlignHCenter,
                sub,
            )

        # ---- brand: Vi3ecode.com
        brand_t = self._ease((t - 0.65) / 1.0)
        if brand_t > 0:
            p.setOpacity(alpha * brand_t)
            font = QFont()
            font.setPointSize(40)
            font.setWeight(QFont.Weight.Black)
            p.setFont(font)
            scale = 0.92 + 0.08 * brand_t
            p.save()
            p.translate(w / 2, 150)
            p.scale(scale, scale)

            metrics = p.fontMetrics()
            text = "Vi3ecode.com"
            tw = metrics.horizontalAdvance(text)
            x0 = -tw / 2
            rect = QRectF(x0, -28, tw, 60)

            # soft glow behind text
            glow = QRadialGradient(QPointF(0, 6), tw * 0.62)
            glow.setColorAt(0.0, QColor(255, 255, 255, int(64 * brand_t)))
            glow.setColorAt(0.55, QColor(255, 255, 255, int(22 * brand_t)))
            glow.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.setOpacity(alpha)
            p.drawEllipse(QPointF(0, 6), tw * 0.62, 54)

            # main text
            p.setPen(QColor("#ffffff"))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

            # shimmer sweep
            sweep = -0.35 + 1.4 * ((t * 0.55) % 1.3)
            sx = x0 + tw * sweep
            if -0.1 < sweep < 1.1:
                sh = QLinearGradient(sx, 0, sx + 70, 0)
                sh.setColorAt(0.0, QColor(255, 255, 255, 0))
                sh.setColorAt(0.5, QColor(255, 255, 255, 120))
                sh.setColorAt(1.0, QColor(255, 255, 255, 0))
                p.setCompositionMode(
                    QPainter.CompositionMode.CompositionMode_Plus
                )
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(sh)
                p.drawRect(rect)
                p.setCompositionMode(
                    QPainter.CompositionMode.CompositionMode_SourceOver
                )
            p.restore()
            p.setOpacity(alpha)

        # ---- progress line
        prog = self._ease(t / (TOTAL_MS / 1000.0 * 0.92))
        bar_w = (w - 140) * prog
        if bar_w > 2:
            bg = QLinearGradient(70, 0, 70 + bar_w, 0)
            bg.setColorAt(0, QColor("#ffffff"))
            bg.setColorAt(1, QColor("#9a9a9a"))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(70, h - 42, bar_w, 5), 3, 3)

        # hint
        p.setOpacity(alpha * 0.75)
        p.setPen(QColor("#6a6a6a"))
        font = QFont()
        font.setPointSize(10)
        p.setFont(font)
        p.drawText(
            QRectF(0, h - 34, w, 20),
            Qt.AlignmentFlag.AlignHCenter,
            "lyrics video factory",
        )
