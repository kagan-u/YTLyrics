"""Capture glass UI screenshots offscreen (queue/settings/logs/splash)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

SHOTS = Path(__file__).resolve().parents[1] / ".shots"


def main() -> None:
    SHOTS.mkdir(exist_ok=True)
    _app = QApplication(sys.argv)

    from ytlyrics.ui.window import MainWindow

    w = MainWindow(start_worker=False)
    w.resize(1280, 800)
    w.show()
    QTest.qWait(400)
    w.dashboard.refresh()
    QTest.qWait(700)  # stat count-up + table layout
    w.grab().save(str(SHOTS / "glass_queue.png"))

    w.nav_buttons[1].click()
    QTest.qWait(700)
    w.grab().save(str(SHOTS / "glass_settings.png"))

    w.nav_buttons[2].click()
    QTest.qWait(700)
    w.grab().save(str(SHOTS / "glass_logs.png"))

    w.nav_buttons[0].click()
    QTest.qWait(700)
    w.grab().save(str(SHOTS / "glass_queue2.png"))

    w.close()

    from ytlyrics.ui.splash import SplashWindow

    splash = SplashWindow()
    splash.start()
    QTest.qWait(900)
    splash.grab().save(str(SHOTS / "glass_splash.png"))
    splash.close()

    print("ok")


if __name__ == "__main__":
    main()
