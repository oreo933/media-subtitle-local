from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.core.config import AppConfig
from app.core.models import BatchSummary, VideoTask
from app.core.resource_guard import ResourceGuard
from app.services.pipeline_service import PipelineService
from app.ui.widgets.log_panel import LogPanel
from app.ui.widgets.task_table import TaskTable


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, logger: logging.Logger) -> None:
        super().__init__()
        self.config = config
        self.logger = logger
        self.guard = ResourceGuard(recommended_gb=config.recommended_resource_gb)
        self.pipeline = PipelineService(config=config, logger=logger)

        self.setWindowTitle("Media Subtitle Local · 本地字幕工坊")
        self.resize(1240, 780)
        self._apply_theme()

        self.mode_select = QComboBox()
        self.mode_select.addItem("单文件", "single")
        self.mode_select.addItem("文件夹", "folder")

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("请选择单个视频文件或视频文件夹…")
        self.select_btn = QPushButton("浏览")
        self.start_btn = QPushButton("开始处理")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)

        self.backend_select = QComboBox()
        self.backend_select.addItem("llama.cpp（推荐，本地离线）", "llamacpp")
        self.backend_select.addItem("Whisper + Marian（备用）", "whisper_marian")

        self.runtime_select = QComboBox()
        self.runtime_select.addItem("CPU（稳定）", "cpu")
        self.runtime_select.addItem("GPU / Vulkan（加速）", "gpu")
        self.runtime_select.setCurrentIndex(0 if self.config.llama_cpp_runtime_mode == "cpu" else 1)


        self.task_table = TaskTable()
        self.log_panel = LogPanel()

        self.status = QStatusBar()
        self.status_label = QLabel("就绪")
        self.resource_label = QLabel("资源：--")
        self.status.addWidget(self.status_label)
        self.status.addPermanentWidget(self.resource_label)
        self.setStatusBar(self.status)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("模式"))
        controls.addWidget(self.mode_select)
        controls.addWidget(QLabel("目标"))
        controls.addWidget(self.path_input, 1)
        controls.addWidget(self.select_btn)
        controls.addWidget(QLabel("后端"))
        controls.addWidget(self.backend_select)
        controls.addWidget(QLabel("运行"))
        controls.addWidget(self.runtime_select)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)


        splitter = QSplitter()
        splitter.addWidget(self.task_table)
        splitter.addWidget(self.log_panel)
        splitter.setSizes([800, 440])

        layout.addLayout(controls)
        layout.addWidget(splitter, 1)

        self.mode_select.currentIndexChanged.connect(self._on_mode_changed)
        self.select_btn.clicked.connect(self._select_target)
        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)

        self.pipeline.task_updated.connect(self._on_task_update)
        self.pipeline.log_emitted.connect(self._on_log)
        self.pipeline.batch_finished.connect(self._on_batch_finished)
        self.pipeline.progress_changed.connect(self._on_progress)

        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._refresh_resource)
        self.monitor_timer.start(1200)

        self._on_mode_changed()

    def _apply_theme(self) -> None:
        self.setFont(QFont("Noto Sans", 10))
        self.setStyleSheet(
            """
            QMainWindow { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0f172a, stop:1 #1e293b); }
            QLabel, QLineEdit, QComboBox, QPushButton, QTableWidget, QTextEdit { color: #E2E8F0; }
            QLineEdit, QComboBox, QTableWidget, QTextEdit {
                background-color: rgba(15, 23, 42, 0.75);
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px;
            }
            QPushButton {
                background-color: #2563EB;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #0EA5E9; }
            QPushButton:disabled { background-color: #475569; }
            QStatusBar { background: #0b1220; color: #cbd5e1; }
            """
        )

    def _is_single_mode(self) -> bool:
        return self.mode_select.currentData() == "single"

    def _on_mode_changed(self) -> None:
        if self._is_single_mode():
            self.path_input.setPlaceholderText("请选择一个视频文件…")
            self.select_btn.setText("选择文件")
        else:
            self.path_input.setPlaceholderText("请选择包含视频文件的文件夹…")
            self.select_btn.setText("选择文件夹")

    def _select_target(self) -> None:
        if self._is_single_mode():
            suffix = " ".join(f"*{e}" for e in self.config.video_extensions)
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择视频文件",
                "",
                f"视频文件 ({suffix})",
            )
            if file_path:
                self.path_input.setText(file_path)
            return

        folder = QFileDialog.getExistingDirectory(self, "选择视频目录")
        if folder:
            self.path_input.setText(folder)

    def _start(self) -> None:
        target = self.path_input.text().strip()
        if not target:
            QMessageBox.warning(self, "提示", "请先选择目标")
            return

        path = Path(target)
        is_single = self._is_single_mode()

        if is_single and (not path.exists() or not path.is_file()):
            QMessageBox.warning(self, "提示", "所选视频文件不存在")
            return
        if (not is_single) and (not path.exists() or not path.is_dir()):
            QMessageBox.warning(self, "提示", "目录不存在")
            return

        self.config.engine_backend = self.backend_select.currentData()
        self.config.llama_cpp_runtime_mode = self.runtime_select.currentData()
        self.start_btn.setEnabled(False)

        self.stop_btn.setEnabled(True)
        self.status_label.setText("处理中…")
        self.pipeline.start(target_path=path, is_single_file=is_single)

    def _stop(self) -> None:
        self.pipeline.stop()
        self._on_log("WARN", "收到停止请求，当前任务将在安全点停止。")

    def _on_task_update(self, task: VideoTask) -> None:
        self.task_table.upsert_task(task)
        if task.stage.value in {"提取音频", "语音识别", "字幕翻译"}:
            self.status_label.setText(
                f"[{task.queue_index}/{task.queue_total}] {task.name} · {task.stage.value} · {task.message}"
            )


    def _on_log(self, level: str, message: str) -> None:
        self.log_panel.append_log(level, message)
        if level == "ERROR":
            self.logger.error(message)
        elif level == "WARN":
            self.logger.warning(message)
        else:
            self.logger.info(message)

    def _on_progress(self, value: float) -> None:
        self.status_label.setText(f"总进度：{value:.0f}%")

    def _on_batch_finished(self, summary: BatchSummary) -> None:
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText(f"完成：成功 {summary.success}/{summary.total}，失败 {summary.failed}")
        self._on_log(
            "INFO",
            f"批处理结束，总计 {summary.total} 个，成功 {summary.success} 个，失败 {summary.failed} 个。",
        )

    def _refresh_resource(self) -> None:
        snap = self.guard.snapshot()
        gpu_text = (
            f"GPU {snap.gpu_memory_gb:.2f}GB = 专用 {snap.gpu_dedicated_gb:.2f}GB + 共享 {snap.gpu_shared_gb:.2f}GB [{snap.gpu_scope}] ({snap.gpu_monitor_name})"
            if snap.gpu_monitor_available
            else "GPU --（未检测到可用监控接口）"
        )

        self.resource_label.setText(
            f"资源：CPU {snap.cpu_percent:.0f}% | 内存 {snap.memory_gb:.2f}GB | {gpu_text}"
        )


