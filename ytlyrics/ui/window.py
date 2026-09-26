from __future__ import annotations

import logging
import math

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ytlyrics import APP_NAME
from ytlyrics.core.config import (
    APP_DIR,
    TOKEN_PATH,
    Config,
    load_config,
    save_config,
)
from ytlyrics.core.db import Database
from ytlyrics.core.worker import Worker
from ytlyrics.core.youtube import channel_title, load_credentials, run_auth_flow

from .dashboard import DashboardPage
from .log_panel import LogPanel
from .settings_page import SettingsPage
from .theme import STYLE
from .widgets import NavButton, TitleBar

log = logging.getLogger(__name__)

DB_PATH = APP_DIR / "ytlyrics.db"


class AuthThread(QThread):
    done = Signal(str)
    failed = Signal(str)
    url = Signal(str)

    def __init__(self, cfg: Config, parent=None) -> None:
        super().__init__(parent)
        self.cfg = cfg

    def run(self) -> None:
        try:
            creds = run_auth_flow(
                self.cfg.client_id,
                self.cfg.client_secret,
                TOKEN_PATH,
                on_url=self.url.emit,
            )
            title = ""
            try:
                title = channel_title(creds)
            except Exception as exc:  # noqa: BLE001
                log.debug("channel title unavailable: %s", exc)
            self.done.emit(title or "Connected")
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, start_worker: bool = True) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(QSize(1020, 660))
        self.resize(1240, 820)
        self.setStyleSheet(STYLE)

        self.cfg = load_config()
        self.db = Database(DB_PATH)

        # animated monochrome background state
        self._bg_phase = 0.0
        self._bg_timer = QTimer(self)
        self._bg_timer.setInterval(50)
        self._bg_timer.timeout.connect(self._animate_bg)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)

        self.title_bar = TitleBar("YTLYRICS · LYRICS VIDEO FACTORY")
        root.addWidget(self.title_bar)

        body = QHBoxLayout()
        body.setSpacing(0)

        # ---- sidebar (glass)
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(224)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 18, 0, 14)
        sb.setSpacing(2)

        brand = QLabel("YTLYRICS")
        brand.setObjectName("Brand")
        brandsub = QLabel("AUTOMATION SUITE")
        brandsub.setObjectName("BrandSub")
        sb.addWidget(brand)
        sb.addWidget(brandsub)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[NavButton] = []
        for i, label in enumerate(("Queue", "Settings", "Logs")):
            btn = NavButton(label)
            self.nav_group.addButton(btn, i)
            self.nav_buttons.append(btn)
            sb.addWidget(btn)
        sb.addStretch()

        self.worker_status = QLabel("Worker: idle")
        self.worker_status.setObjectName("Muted")
        self.worker_status.setWordWrap(True)
        self.worker_status.setStyleSheet(
            "QLabel#Muted { padding: 6px 14px; color: #6f6f6f;"
            " font-size: 11px; }"
        )
        sb.addWidget(self.worker_status)

        powered = QLabel("Powered by Vi3ecode.com")
        powered.setStyleSheet(
            "color: #5a5a5a; font-size: 10px; padding: 2px 14px 0 14px;"
        )
        sb.addWidget(powered)

        body.addWidget(sidebar)

        # ---- content stack
        self.stack = QStackedWidget()
        self.dashboard = DashboardPage(self.db, lambda: self.cfg)
        self.settings = SettingsPage(self.cfg)
        self.logs = LogPanel()
        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.settings)
        self.stack.addWidget(self.logs)
        body.addWidget(self.stack, 1)
        root.addLayout(body)

        self.setCentralWidget(central)

        # ---- wiring
        self.nav_group.idToggled.connect(
            lambda idx, on: self._switch(idx) if on else None
        )
        self.nav_buttons[0].setChecked(True)

        self.dashboard.cancel_requested.connect(self._on_cancel)
        self.dashboard.retry_requested.connect(self._on_retry)
        self.dashboard.request_added.connect(self._on_manual_add)
        self.settings.auth_requested.connect(self._start_auth)
        self.settings.saved.connect(self._on_saved)

        self.title_bar.close_clicked.connect(self.close)
        self.title_bar.min_clicked.connect(self.showMinimized)
        self.title_bar.max_clicked.connect(self._toggle_max)

        # ---- worker thread
        self.thread: QThread | None = None
        self.worker: Worker | None = None
        if start_worker:
            self.thread = QThread()
            self.worker = Worker(lambda: self.cfg, self.db)
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.log_message.connect(self.logs.append)
            self.worker.queue_changed.connect(self.dashboard.refresh)
            self.worker.monitor_ticked.connect(self._on_tick)
            self.worker.auth_needed.connect(self._on_auth_needed)
            self.thread.start()
        else:
            self.worker_status.setText("Worker: off")

        self._auth_thread: AuthThread | None = None
        self._page_anim: QPropertyAnimation | None = None
        self._refresh_auth_status()

    # ------------------------------------------------------------- animated bg
    def _animate_bg(self) -> None:
        if self.isMinimized():
            return
        self._bg_phase += 0.055
        self.update()

    def paintEvent(self, event) -> None:
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        p.fillRect(rect, QColor("#060606"))

        t = self._bg_phase
        w, h = rect.width(), rect.height()

        # slow diagonal sheen
        sheen = QLinearGradient(0, 0, w, h)
        pos = 0.5 + 0.5 * math.sin(t * 0.45)
        sheen.setColorAt(max(0.0, pos - 0.4), QColor(255, 255, 255, 0))
        sheen.setColorAt(min(1.0, pos), QColor(255, 255, 255, 12))
        sheen.setColorAt(min(1.0, pos + 0.4), QColor(255, 255, 255, 0))
        p.fillRect(rect, sheen)

        # three drifting white glows
        glows = (
            (0.22, 0.28, 0.30, 0.7, 16),
            (0.78, 0.35, 0.36, 0.5, 13),
            (0.50, 0.85, 0.42, 0.6, 11),
        )
        for i, (bx, by, br, spd, alpha) in enumerate(glows):
            cx = w * (bx + 0.10 * math.sin(t * spd * 0.5 + i * 2.1))
            cy = h * (by + 0.08 * math.cos(t * spd * 0.4 + i * 1.4))
            rad = QRadialGradient(cx, cy, max(w, h) * br)
            rad.setColorAt(0.0, QColor(255, 255, 255, alpha))
            rad.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillRect(rect, rad)

        # vignette
        vig = QRadialGradient(w / 2, h / 2, max(w, h) * 0.75)
        vig.setColorAt(0.0, QColor(0, 0, 0, 0))
        vig.setColorAt(1.0, QColor(0, 0, 0, 120))
        p.fillRect(rect, vig)

        # glass border
        p.setPen(QColor(255, 255, 255, 24))
        p.setBrush(Qt.BrushStyle.NoBrush)
        radius = 0 if self.isMaximized() else 14
        p.drawRoundedRect(rect.adjusted(0, 0, -1, -1), radius, radius)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._bg_timer.isActive():
            self._bg_timer.start()

    # --------------------------------------------------------------- nav
    def _switch(self, idx: int) -> None:
        if idx == self.stack.currentIndex():
            return
        # fade transition
        eff = QGraphicsOpacityEffect(self.stack)
        self.stack.setGraphicsEffect(eff)
        out = QPropertyAnimation(eff, b"opacity", self.stack)
        out.setDuration(140)
        out.setStartValue(1.0)
        out.setEndValue(0.0)
        out.setEasingCurve(QEasingCurve.Type.InCubic)

        def finish() -> None:
            self.stack.setCurrentIndex(idx)
            inn = QPropertyAnimation(eff, b"opacity", self.stack)
            inn.setDuration(180)
            inn.setStartValue(0.0)
            inn.setEndValue(1.0)
            inn.setEasingCurve(QEasingCurve.Type.OutCubic)

            def cleanup() -> None:
                self.stack.setGraphicsEffect(None)

            inn.finished.connect(cleanup)
            inn.start()
            self._page_anim = inn

        out.finished.connect(finish)
        out.start()
        self._page_anim = out

    def _toggle_max(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ------------------------------------------------------------- events
    def _on_cancel(self, req_id: int) -> None:
        if self.worker:
            self.worker.request_cancel(req_id)
        elif self.db.cancel(req_id):
            self.logs.append(f"Request #{req_id} cancelled", "info")
            self.dashboard.refresh()

    def _on_retry(self, req_id: int) -> None:
        if self.db.retry(req_id):
            self.logs.append(f"Request #{req_id} requeued", "info")
            self.dashboard.refresh()

    def _on_manual_add(
        self, artist: str, title: str, pitch: float, preset: str
    ) -> None:
        req_id = self.db.add_request(
            artist, title,
            commenter="manual",
            pitch=pitch or self.cfg.default_pitch,
            bg_preset=preset,
        )
        if req_id:
            self.logs.append(
                f"Manual request #{req_id}: "
                f"{artist + ' - ' if artist else ''}{title}",
                "ok",
            )
        else:
            self.logs.append("This track is already queued", "warn")
        self.dashboard.refresh()

    def _on_saved(self, msg: str) -> None:
        self.logs.append(msg, "ok")

    def _on_tick(self, hhmmss: str) -> None:
        state = (
            "scanning comments" if self.cfg.monitor_enabled
            else "monitoring off"
        )
        self.worker_status.setText(
            f"Worker: running\nlast scan {hhmmss} · {state}"
        )

    def _on_auth_needed(self) -> None:
        if self.settings.auth_status.text() != "Google account required":
            self.settings.set_auth_status("Google account required", False)

    # -------------------------------------------------------------- auth
    def _start_auth(self) -> None:
        self.settings.apply_to(self.cfg)
        save_config(self.cfg)
        if not self.cfg.client_id or not self.cfg.client_secret:
            self.logs.append(
                "Enter Client ID and Client Secret first", "error"
            )
            return
        self.settings.connect_btn.setEnabled(False)
        self.settings.set_auth_status(
            "Waiting for browser authorization...", False
        )
        self.logs.append("Google authorization started", "info")
        self._auth_thread = AuthThread(self.cfg, self)
        self._auth_thread.done.connect(self._on_auth_done)
        self._auth_thread.failed.connect(self._on_auth_failed)
        self._auth_thread.url.connect(
            lambda u: self.logs.append(f"Authorize: {u}", "info")
        )
        self._auth_thread.start()

    def _on_auth_done(self, title: str) -> None:
        self.settings.connect_btn.setEnabled(True)
        self.settings.set_auth_status(f"Connected: {title}", True)
        self.logs.append(f"Google account connected: {title}", "ok")
        if self.worker:
            self.worker._creds = None
            self.worker._creds_checked_at = 0.0

    def _on_auth_failed(self, err: str) -> None:
        self.settings.connect_btn.setEnabled(True)
        self.settings.set_auth_status("Connection failed", False)
        self.logs.append(f"Auth error: {err}", "error")
        if "invalid_client" in err:
            self.logs.append(
                "Google rejected the credentials. Check Settings — "
                "Client ID must end with .apps.googleusercontent.com, "
                "Client Secret must match it, and the OAuth client type "
                "must be 'Desktop app' (not Web application).",
                "error",
            )

    def _refresh_auth_status(self) -> None:
        creds = load_credentials(TOKEN_PATH)
        if creds:
            self.settings.set_auth_status("Google account connected", True)
        else:
            self.settings.set_auth_status("Account not connected", False)

    # ------------------------------------------------------------- close
    def closeEvent(self, event) -> None:
        self.logs.append("Shutting down...", "warn")
        self._bg_timer.stop()
        if self.thread:
            if self.worker:
                self.worker.stop()
            self.thread.quit()
            if not self.thread.wait(8000):
                self.thread.terminate()
                self.thread.wait(2000)
        save_config(self.cfg)
        event.accept()
