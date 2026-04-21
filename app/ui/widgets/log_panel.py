from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QTextEdit


class LogPanel(QTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setPlaceholderText("运行日志将显示在这里…")

    def append_log(self, level: str, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.append(f"[{ts}] [{level}] {message}")
