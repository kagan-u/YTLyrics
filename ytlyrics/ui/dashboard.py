from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ytlyrics.core.config import BG_PRESETS, OUTPUT_DIR
from ytlyrics.core.db import Database
from ytlyrics.core.models import TERMINAL, Status

from .widgets import ClickableCard, StatCard, StatusPill


class DashboardPage(QWidget):
    cancel_requested = Signal(int)
    retry_requested = Signal(int)
    request_added = Signal(str, str, float, str)   # artist, title, pitch, preset

    def __init__(self, db: Database, cfg_provider, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._cfg_provider = cfg_provider
        self._struct_sig: tuple = ()
        self._row_by_id: dict[int, int] = {}
        try:
            self._preset_default = cfg_provider().bg_preset
        except Exception:  # noqa: BLE001
            self._preset_default = "violet"

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 24)
        root.setSpacing(16)

        # header
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        h1 = QLabel("Queue")
        h1.setObjectName("H1")
        sub = QLabel("Lyrics requests picked up from comments — or add one manually")
        sub.setObjectName("Muted")
        titles.addWidget(h1)
        titles.addWidget(sub)
        head.addLayout(titles)
        head.addStretch()
        root.addLayout(head)

        # stats
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self.stat_queued = StatCard("Queued")
        self.stat_active = StatCard("Active")
        self.stat_done = StatCard("Done")
        self.stat_failed = StatCard("Failed")
        for c in (self.stat_queued, self.stat_active, self.stat_done,
                  self.stat_failed):
            stats_row.addWidget(c)
        root.addLayout(stats_row)

        # manual add card
        add_card = ClickableCard()
        row = QHBoxLayout()
        row.setSpacing(10)
        self.inp_artist = QLineEdit()
        self.inp_artist.setPlaceholderText("Artist (optional)")
        self.inp_artist.setFixedWidth(220)
        self.inp_title = QLineEdit()
        self.inp_title.setPlaceholderText("Song title *")
        self.inp_pitch = QDoubleSpinBox()
        self.inp_pitch.setRange(-12.0, 12.0)
        self.inp_pitch.setSingleStep(0.5)
        self.inp_pitch.setPrefix("pitch ")
        self.inp_pitch.setFixedWidth(130)
        self.inp_preset = QComboBox()
        self.inp_preset.addItems(BG_PRESETS)
        self.inp_preset.setCurrentText(self._preset_default)
        self.inp_preset.setFixedWidth(150)
        add_btn = QPushButton("Add to Queue")
        add_btn.setObjectName("Primary")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add)
        self.inp_title.returnPressed.connect(self._on_add)
        row.addWidget(self.inp_artist)
        row.addWidget(self.inp_title, 1)
        row.addWidget(self.inp_pitch)
        row.addWidget(self.inp_preset)
        row.addWidget(add_btn)
        add_card.layout_.addLayout(row)
        root.addWidget(add_card)

        # table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["#", "TRACK", "REQUESTED BY", "STATUS", "PROGRESS", "ACTION"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 52)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 190)
        self.table.setColumnWidth(5, 160)
        self.table.setMinimumHeight(300)
        root.addWidget(self.table, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(1200)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    # ------------------------------------------------------------- actions
    def _on_add(self) -> None:
        title = self.inp_title.text().strip()
        if not title:
            self.inp_title.setStyleSheet("border-color: rgba(255,255,255,0.7);")
            return
        self.inp_title.setStyleSheet("")
        self.request_added.emit(
            self.inp_artist.text().strip(),
            title,
            float(self.inp_pitch.value()),
            self.inp_preset.currentText(),
        )
        self.inp_title.clear()
        self.inp_artist.clear()

    # ------------------------------------------------------------- refresh
    def refresh(self) -> None:
        rows = self.db.list_requests()
        struct = tuple((r["id"], r["status"]) for r in rows)
        if struct != self._struct_sig:
            self._struct_sig = struct
            self._rebuild(rows)
        else:
            self._update_progress(rows)
        self._update_stats(rows)

    def _update_stats(self, rows: list[dict]) -> None:
        counts = {s: 0 for s in Status}
        for r in rows:
            try:
                counts[Status(r["status"])] += 1
            except ValueError:
                pass
        active = sum(
            counts[s] for s in (
                Status.DOWNLOADING, Status.ALIGNING,
                Status.RENDERING, Status.UPLOADING,
            )
        )
        self.stat_queued.set_value(counts[Status.QUEUED])
        self.stat_active.set_value(active)
        self.stat_done.set_value(counts[Status.DONE])
        self.stat_failed.set_value(
            counts[Status.FAILED] + counts[Status.CANCELLED]
        )

    def _rebuild(self, rows: list[dict]) -> None:
        self.table.setRowCount(len(rows))
        self._row_by_id.clear()
        bold = QFont()
        bold.setWeight(QFont.Weight.Bold)
        for i, r in enumerate(rows):
            self._row_by_id[r["id"]] = i
            req_id = r["id"]
            status = r["status"]

            item_id = QTableWidgetItem(str(req_id))
            item_id.setForeground(QColor("#7a7a7a"))
            self.table.setItem(i, 0, item_id)

            name = r["artist"] + " - " + r["title"] if r["artist"] else r["title"]
            item_name = QTableWidgetItem(name)
            item_name.setFont(bold)
            tip = f"Command: !lyrics {name}"
            if r["commenter"]:
                tip = f"@{r['commenter']} · {tip}"
            item_name.setToolTip(tip)
            self.table.setItem(i, 1, item_name)

            item_who = QTableWidgetItem(r["commenter"] or "manual")
            item_who.setForeground(QColor("#8f8f8f"))
            self.table.setItem(i, 2, item_who)

            pill = StatusPill()
            pill.set_status(status)
            self.table.setCellWidget(i, 3, pill)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(float(r["progress"]) * 100))
            bar.setFormat("%p%")
            bar.setFixedHeight(16)
            self.table.setCellWidget(i, 4, bar)

            action = self._make_action(req_id, status, r)
            self.table.setCellWidget(i, 5, action)
            self.table.setRowHeight(i, 46)

    def _make_action(self, req_id: int, status: str, row: dict) -> QWidget:
        wrap = QFrame()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(6)
        if status not in TERMINAL:
            btn = QPushButton("Cancel")
            btn.setObjectName("Danger")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda _=False, i=req_id: self.cancel_requested.emit(i)
            )
            lay.addWidget(btn)
        elif status in ("failed", "cancelled"):
            btn = QPushButton("Retry")
            btn.setObjectName("Tiny")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda _=False, i=req_id: self.retry_requested.emit(i)
            )
            lay.addWidget(btn)
        else:
            out = row.get("output_path") or ""
            if out and Path(out).exists():
                btn = QPushButton("Folder")
                btn.setObjectName("Tiny")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(
                    lambda _=False, p=out: QDesktopServices.openUrl(
                        QUrl.fromLocalFile(str(Path(p).parent))
                    )
                )
                lay.addWidget(btn)
            yt = row.get("yt_video_id") or ""
            if yt:
                btn2 = QPushButton("Video")
                btn2.setObjectName("Tiny")
                btn2.setCursor(Qt.CursorShape.PointingHandCursor)
                btn2.clicked.connect(
                    lambda _=False, v=yt: QDesktopServices.openUrl(
                        QUrl(f"https://youtu.be/{v}")
                    )
                )
                lay.addWidget(btn2)
        lay.addStretch()
        return wrap

    def _update_progress(self, rows: list[dict]) -> None:
        for r in rows:
            i = self._row_by_id.get(r["id"])
            if i is None:
                continue
            bar = self.table.cellWidget(i, 4)
            if isinstance(bar, QProgressBar):
                bar.setValue(int(float(r["progress"]) * 100))


def open_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(OUTPUT_DIR)))
