from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from ytlyrics import APP_NAME
from ytlyrics.ui.splash import SplashWindow
from ytlyrics.ui.widgets import fade_in
from ytlyrics.ui.window import MainWindow


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Vi3ecode")
    app.setStyle("Fusion")

    window = MainWindow()
    splash = SplashWindow()

    def on_splash_finished() -> None:
        window.show()
        fade_in(window, 320)

    splash.finished.connect(on_splash_finished)
    splash.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
