from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.config import load_config
from app.core.logger import setup_logger
from app.ui.main_window import MainWindow


def main() -> int:
    config = load_config()
    logger = setup_logger(config.log_dir)

    app = QApplication(sys.argv)
    app.setApplicationName(config.app_name)

    icon_candidates = [
        Path("assets/icons/app.ico"),
        Path("assets/icons/app.png"),
        Path("assets/icons/app.svg"),
    ]
    for icon_path in icon_candidates:
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            break

    window = MainWindow(config=config, logger=logger)

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
