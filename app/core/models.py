from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Stage(str, Enum):
    QUEUED = "排队中"
    EXTRACTING = "提取音频"
    TRANSCRIBING = "语音识别"
    TRANSLATING = "字幕翻译"
    COMPLETED = "完成"
    FAILED = "失败"
    STOPPED = "已停止"


@dataclass(slots=True)
class SubtitleSegment:
    start: float
    end: float
    text: str


@dataclass(slots=True)
class VideoTask:
    video_path: Path
    stage: Stage = Stage.QUEUED
    progress: float = 0.0
    message: str = "等待处理"
    retries: int = 0
    queue_index: int = 0
    queue_total: int = 0
    audio_path: Path | None = None
    source_srt: Path | None = None
    zh_srt: Path | None = None
    language: str | None = None

    @property
    def name(self) -> str:
        return self.video_path.name


@dataclass(slots=True)
class BatchSummary:
    total: int = 0
    success: int = 0
    failed: int = 0
    stopped: int = 0
    outputs: list[Path] = field(default_factory=list)
