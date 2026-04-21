from __future__ import annotations

from pathlib import Path
from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from app.core.models import Stage, VideoTask


class TaskTable(QTableWidget):
    HEADERS = ["队列", "文件", "阶段", "进度", "状态", "输出字幕"]

    def __init__(self) -> None:
        super().__init__(0, len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self._row_by_video: Dict[Path, int] = {}
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(self.SelectionBehavior.SelectRows)
        self.setEditTriggers(self.EditTrigger.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(True)

    def upsert_task(self, task: VideoTask) -> None:
        row = self._row_by_video.get(task.video_path)
        if row is None:
            row = self.rowCount()
            self.insertRow(row)
            self._row_by_video[task.video_path] = row

        queue_text = f"{task.queue_index}/{task.queue_total}" if task.queue_total else "-"
        stage_text = task.stage.value
        progress_text = f"{task.progress:.0f}%"
        status_text = task.message
        output_text = str(task.zh_srt) if task.zh_srt else "-"

        values = [queue_text, task.name, stage_text, progress_text, status_text, output_text]
        for col, value in enumerate(values):
            item = self.item(row, col)
            if item is None:
                item = QTableWidgetItem(value)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter if col in (0, 2, 3) else Qt.AlignmentFlag.AlignLeft
                )
                self.setItem(row, col, item)
            else:
                item.setText(value)

        self._paint_stage(row, task.stage)

    def _paint_stage(self, row: int, stage: Stage) -> None:
        item = self.item(row, 2)
        if not item:
            return
        if stage == Stage.COMPLETED:
            item.setForeground(Qt.GlobalColor.darkGreen)
        elif stage == Stage.FAILED:
            item.setForeground(Qt.GlobalColor.red)
        elif stage in (Stage.EXTRACTING, Stage.TRANSCRIBING, Stage.TRANSLATING):
            item.setForeground(Qt.GlobalColor.darkBlue)
        else:
            item.setForeground(Qt.GlobalColor.black)
