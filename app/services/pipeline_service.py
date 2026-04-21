from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.core.config import AppConfig
from app.core.models import BatchSummary, Stage, VideoTask
from app.core.resource_guard import ResourceGuard
from app.engines.base_adapter import EngineAdapter, create_engine
from app.services.audio_extract_service import AudioExtractService
from app.services.subtitle_service import SubtitleService
from app.utils.file_scan import scan_video_files


class PipelineService(QObject):
    task_updated = Signal(VideoTask)
    log_emitted = Signal(str, str)
    progress_changed = Signal(float)
    batch_finished = Signal(BatchSummary)

    def __init__(self, config: AppConfig, logger: logging.Logger) -> None:
        super().__init__()
        self.config = config
        self.logger = logger
        self.extractor = AudioExtractService(config)
        self.subtitle_service = SubtitleService()
        self.guard = ResourceGuard(recommended_gb=config.recommended_resource_gb)

        self._engine: EngineAdapter | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, target_path: Path, is_single_file: bool) -> None:
        if self._thread and self._thread.is_alive():
            self.log_emitted.emit("WARN", "任务正在运行，请稍候。")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_batch,
            args=(target_path, is_single_file),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _collect_targets(self, target_path: Path, is_single_file: bool) -> list[Path]:
        if is_single_file:
            if target_path.exists() and target_path.is_file():
                if target_path.suffix.lower() in {e.lower() for e in self.config.video_extensions}:
                    return [target_path]
            return []
        return scan_video_files(target_path, self.config.video_extensions)

    def _run_batch(self, target_path: Path, is_single_file: bool) -> None:
        files = self._collect_targets(target_path, is_single_file)
        summary = BatchSummary(total=len(files))

        if not files:
            self.log_emitted.emit("WARN", "未扫描到可处理的视频文件。")
            self.batch_finished.emit(summary)
            return

        # 先入队，保证用户在 GUI 中看到完整排队情况
        queue_tasks: list[VideoTask] = []
        total = len(files)
        for i, video in enumerate(files, start=1):
            task = VideoTask(
                video_path=video,
                stage=Stage.QUEUED,
                message=f"排队中（{i}/{total}）",
                queue_index=i,
                queue_total=total,
            )
            queue_tasks.append(task)
            self.task_updated.emit(task)

        self._engine = create_engine(self.config, self.log_emitted.emit)
        if is_single_file:
            self.log_emitted.emit("INFO", f"单文件模式：开始处理 {files[0].name}")
        else:
            self.log_emitted.emit("INFO", f"文件夹模式：共 {len(files)} 个视频，按文件名顺序串行处理。")

        for idx, task in enumerate(queue_tasks, start=1):
            if self._stop_event.is_set():
                remaining = len(queue_tasks) - idx + 1
                summary.stopped += max(remaining, 0)
                for rest in queue_tasks[idx - 1 :]:
                    if rest.stage == Stage.QUEUED:
                        rest.stage = Stage.STOPPED
                        rest.message = "已停止（未执行）"
                        self.task_updated.emit(rest)
                break

            ok = self._process_with_retry(task)
            if ok:
                summary.success += 1
                if task.zh_srt:
                    summary.outputs.append(task.zh_srt)
            else:
                summary.failed += 1

            self.progress_changed.emit(idx / len(queue_tasks) * 100)

        self.batch_finished.emit(summary)

    def _process_with_retry(self, task: VideoTask) -> bool:
        assert self._engine is not None
        for attempt in range(self.config.max_retries + 1):
            try:
                if self._stop_event.is_set():
                    task.stage = Stage.STOPPED
                    task.message = "已停止"
                    self.task_updated.emit(task)
                    return False
                task.retries = attempt
                self._process_single(task)
                return True
            except Exception as exc:
                msg = str(exc)
                fatal_keywords = (
                    "不支持 Gemma4",
                    "unknown model architecture",
                    "未找到 Gemma 模型文件",
                    "未找到 llama-server",
                )
                should_retry = (attempt < self.config.max_retries) and not any(k in msg for k in fatal_keywords)

                if should_retry:
                    task.message = f"失败重试中（{attempt + 1}/{self.config.max_retries}）：{msg}"
                    self.task_updated.emit(task)
                    self.log_emitted.emit("WARN", f"[{task.queue_index}/{task.queue_total}] {task.name} 失败，准备重试：{msg}")
                    time.sleep(self.config.retry_backoff_sec)
                    continue

                task.stage = Stage.FAILED
                task.message = msg
                task.progress = 100.0
                self.task_updated.emit(task)
                self.log_emitted.emit("ERROR", f"[{task.queue_index}/{task.queue_total}] {task.name} 处理失败：{msg}")
                return False

        return False

    def _process_single(self, task: VideoTask) -> None:
        assert self._engine is not None

        self.guard.wait_for_budget()

        task.stage = Stage.EXTRACTING
        task.message = f"提取音频中（队列 {task.queue_index}/{task.queue_total}）"
        task.progress = 10
        self.task_updated.emit(task)
        self.log_emitted.emit("INFO", f"[{task.queue_index}/{task.queue_total}] {task.name}：开始提取音频")
        task.audio_path = self.extractor.extract(task.video_path)

        task.stage = Stage.TRANSCRIBING
        task.message = "识别语音中"
        task.progress = 40
        self.task_updated.emit(task)
        self.log_emitted.emit("INFO", f"[{task.queue_index}/{task.queue_total}] {task.name}：开始语音识别")
        src_segments, language = self._engine.transcribe(task.audio_path)
        task.language = language
        self.log_emitted.emit(
            "INFO",
            f"[{task.queue_index}/{task.queue_total}] {task.name}：语音识别完成，片段 {len(src_segments)}，语言 {language or 'auto'}",
        )


        src_path = task.video_path.with_suffix("")
        task.source_srt = self.subtitle_service.write_srt(
            src_path.with_name(f"{src_path.name}.src.srt"),
            src_segments,
        )

        task.stage = Stage.TRANSLATING
        task.message = f"翻译中（{language or 'auto'} -> zh）"
        task.progress = 70
        self.task_updated.emit(task)
        zh_segments = self._engine.translate_segments(src_segments, source_lang=language or "auto")

        task.zh_srt = self.subtitle_service.write_srt(
            task.video_path.with_suffix("").with_name(f"{task.video_path.stem}.zh.srt"),
            zh_segments,
        )
        task.stage = Stage.COMPLETED
        task.message = "已完成"
        task.progress = 100
        self.task_updated.emit(task)
        self.log_emitted.emit("INFO", f"[{task.queue_index}/{task.queue_total}] {task.name} 完成，输出：{task.zh_srt}")
