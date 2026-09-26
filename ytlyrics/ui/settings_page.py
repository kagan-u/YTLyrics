from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ytlyrics.core.config import BG_PRESETS, Config, save_config
from ytlyrics.ui.dashboard import open_output_dir


class SettingsPage(QWidget):
    auth_requested = Signal()
    saved = Signal(str)

    def __init__(self, cfg: Config, parent=None) -> None:
        super().__init__(parent)
        self.cfg = cfg

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 24)
        root.setSpacing(14)

        h1 = QLabel("Settings")
        h1.setObjectName("H1")
        root.addWidget(h1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        body = QVBoxLayout(inner)
        body.setContentsMargins(0, 0, 12, 0)
        body.setSpacing(14)

        # --- YouTube connection
        g1 = QGroupBox("YouTube Connection")
        l1 = QVBoxLayout()
        l1.setContentsMargins(14, 10, 14, 14)
        l1.setSpacing(10)
        self.client_id = QLineEdit()
        self.client_id.setPlaceholderText("Google Cloud OAuth Client ID")
        self.client_secret = QLineEdit()
        self.client_secret.setPlaceholderText("Client Secret")
        self.client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("Connect with Google")
        self.connect_btn.setObjectName("Primary")
        self.connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_btn.clicked.connect(self.auth_requested.emit)
        self.open_folder_btn = QPushButton("Output Folder")
        self.open_folder_btn.clicked.connect(open_output_dir)
        self.auth_status = QLabel("Account not connected")
        self.auth_status.setObjectName("Muted")
        btn_row.addWidget(self.connect_btn)
        btn_row.addWidget(self.open_folder_btn)
        btn_row.addStretch()
        l1.addWidget(self.client_id)
        l1.addWidget(self.client_secret)
        l1.addLayout(btn_row)
        l1.addWidget(self.auth_status)
        g1.setLayout(l1)
        body.addWidget(g1)

        # --- monitoring
        g2 = QGroupBox("Comment Monitoring")
        l2 = QVBoxLayout()
        l2.setContentsMargins(14, 10, 14, 14)
        l2.setSpacing(10)
        self.monitor_enabled = QCheckBox(
            "Automatically pick up lyrics requests from comments"
        )
        self.video_id = QLineEdit()
        self.video_id.setPlaceholderText(
            "Target video ID (empty = newest upload on the channel)"
        )
        row2 = QHBoxLayout()
        self.command = QLineEdit()
        self.command.setPlaceholderText("!lyrics")
        self.poll_interval = QSpinBox()
        self.poll_interval.setRange(10, 3600)
        self.poll_interval.setSuffix(" sec")
        self.poll_label = QLabel("Scan interval")
        self.poll_label.setObjectName("Muted")
        row2.addWidget(self.command)
        row2.addWidget(self.poll_label)
        row2.addWidget(self.poll_interval)
        row2.addStretch()
        l2.addWidget(self.monitor_enabled)
        l2.addWidget(self.video_id)
        l2.addLayout(row2)
        g2.setLayout(l2)
        body.addWidget(g2)

        # --- audio & render
        g3 = QGroupBox("Audio Render")
        l3 = QVBoxLayout()
        l3.setContentsMargins(14, 10, 14, 14)
        l3.setSpacing(10)
        r1 = QHBoxLayout()
        self.default_pitch = QDoubleSpinBox()
        self.default_pitch.setRange(-12.0, 12.0)
        self.default_pitch.setSingleStep(0.5)
        self.default_pitch.setPrefix("default pitch ")
        self.bg_preset = QComboBox()
        self.bg_preset.addItems(BG_PRESETS)
        self.resolution = QComboBox()
        self.resolution.addItems(["1920x1080", "1280x720", "1080x1920"])
        self.fps = QComboBox()
        self.fps.addItems(["24", "30", "60"])
        r1.addWidget(self.default_pitch)
        r1.addWidget(self.bg_preset)
        r1.addWidget(self.resolution)
        r1.addWidget(self.fps)
        r1.addStretch()
        r2 = QHBoxLayout()
        self.font_size = QSpinBox()
        self.font_size.setRange(24, 160)
        self.font_size.setPrefix("font ")
        self.scroll_speed = QDoubleSpinBox()
        self.scroll_speed.setRange(8.0, 140.0)
        self.scroll_speed.setPrefix("speed ")
        self.scroll_speed.setSuffix(" px/sec")
        self.font_name = QLineEdit()
        self.font_name.setPlaceholderText("Font (Arial, Helvetica...)")
        r2.addWidget(self.font_size)
        r2.addWidget(self.scroll_speed)
        r2.addWidget(self.font_name, 1)
        l3.addLayout(r1)
        l3.addLayout(r2)
        g3.setLayout(l3)
        body.addWidget(g3)

        # --- lyrics
        g4 = QGroupBox("Lyrics Timing")
        l4 = QVBoxLayout()
        l4.setContentsMargins(14, 10, 14, 14)
        r3 = QHBoxLayout()
        self.whisper_model = QComboBox()
        self.whisper_model.addItems(["tiny", "base", "small", "medium"])
        self.align_language = QLineEdit()
        self.align_language.setPlaceholderText(
            "Whisper language code (empty = auto, e.g. tr, en)"
        )
        note = QLabel(
            "Synced lyrics come from LRCLIB first; otherwise whisper aligns them"
        )
        note.setObjectName("Muted")
        r3.addWidget(self.whisper_model)
        r3.addWidget(self.align_language, 1)
        l4.addLayout(r3)
        l4.addWidget(note)
        g4.setLayout(l4)
        body.addWidget(g4)

        # --- upload
        g5 = QGroupBox("Upload")
        l5 = QVBoxLayout()
        l5.setContentsMargins(14, 10, 14, 14)
        l5.setSpacing(10)
        self.upload_enabled = QCheckBox(
            "Auto-upload finished videos to YouTube"
        )
        self.dry_run = QCheckBox("Dry-run (render only, skip upload)")
        self.privacy = QComboBox()
        self.privacy.addItems(["private", "unlisted", "public"])
        self.title_template = QLineEdit()
        self.title_template.setPlaceholderText(
            "Title template: {track} (Lyrics)"
        )
        self.desc_template = QPlainTextEdit()
        self.desc_template.setPlaceholderText(
            "Description template: {track} {artist} {title} {artist_tag}"
        )
        self.desc_template.setFixedHeight(110)
        l5.addWidget(self.upload_enabled)
        l5.addWidget(self.dry_run)
        row5 = QHBoxLayout()
        plabel = QLabel("Privacy")
        plabel.setObjectName("Muted")
        row5.addWidget(plabel)
        row5.addWidget(self.privacy)
        row5.addStretch()
        l5.addLayout(row5)
        l5.addWidget(self.title_template)
        l5.addWidget(self.desc_template)
        g5.setLayout(l5)
        body.addWidget(g5)

        # --- save
        actions = QHBoxLayout()
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("Primary")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self._save)
        actions.addWidget(self.save_btn)
        actions.addStretch()
        body.addLayout(actions)
        body.addStretch()

        scroll.setWidget(inner)
        root.addWidget(scroll, 1)
        self.load()

    # ---------------------------------------------------------------- io
    def load(self) -> None:
        c = self.cfg
        self.client_id.setText(c.client_id)
        self.client_secret.setText(c.client_secret)
        self.monitor_enabled.setChecked(c.monitor_enabled)
        self.video_id.setText(c.api_video_id)
        self.command.setText(c.request_command)
        self.poll_interval.setValue(c.poll_interval)
        self.default_pitch.setValue(c.default_pitch)
        self.bg_preset.setCurrentText(c.bg_preset)
        self.resolution.setCurrentText(c.resolution)
        self.fps.setCurrentText(str(c.fps))
        self.font_size.setValue(c.font_size)
        self.scroll_speed.setValue(c.scroll_speed)
        self.font_name.setText(c.font_name)
        self.whisper_model.setCurrentText(c.whisper_model)
        self.align_language.setText(c.align_language)
        self.upload_enabled.setChecked(c.upload_enabled)
        self.dry_run.setChecked(c.dry_run)
        self.privacy.setCurrentText(c.privacy)
        self.title_template.setText(c.title_template)
        self.desc_template.setPlainText(c.description_template)

    def apply_to(self, cfg: Config) -> None:
        cfg.client_id = self.client_id.text().strip()
        cfg.client_secret = self.client_secret.text().strip()
        cfg.monitor_enabled = self.monitor_enabled.isChecked()
        cfg.api_video_id = self.video_id.text().strip()
        cfg.request_command = self.command.text().strip() or "!lyrics"
        cfg.poll_interval = int(self.poll_interval.value())
        cfg.default_pitch = float(self.default_pitch.value())
        cfg.bg_preset = self.bg_preset.currentText()
        cfg.resolution = self.resolution.currentText()
        cfg.fps = int(self.fps.currentText())
        cfg.font_size = int(self.font_size.value())
        cfg.scroll_speed = float(self.scroll_speed.value())
        cfg.font_name = self.font_name.text().strip() or "Arial"
        cfg.whisper_model = self.whisper_model.currentText()
        cfg.align_language = self.align_language.text().strip()
        cfg.upload_enabled = self.upload_enabled.isChecked()
        cfg.dry_run = self.dry_run.isChecked()
        cfg.privacy = self.privacy.currentText()
        cfg.title_template = (
            self.title_template.text().strip() or "{track} (Lyrics)"
        )
        cfg.description_template = self.desc_template.toPlainText().strip()

    def _save(self) -> None:
        self.apply_to(self.cfg)
        save_config(self.cfg)
        self.saved.emit("Settings saved")

    def set_auth_status(self, text: str, ok: bool) -> None:
        self.auth_status.setText(text)
        self.auth_status.setStyleSheet(
            "color: #ffffff;" if ok else "color: #8f8f8f;"
        )
