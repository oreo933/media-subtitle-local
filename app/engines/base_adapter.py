from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

from app.core.config import AppConfig
from app.core.models import SubtitleSegment


class EngineAdapter(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path) -> tuple[list[SubtitleSegment], str | None]:
        raise NotImplementedError

    @abstractmethod
    def translate_segments(self, segments: list[SubtitleSegment], source_lang: str) -> list[SubtitleSegment]:
        raise NotImplementedError


def create_engine(config: AppConfig, logger: Callable[[str, str], None]) -> EngineAdapter:
    if config.engine_backend == "llamacpp":
        from app.engines.gemma4e2b_adapter import Gemma4E2BAdapter

        logger(
            "INFO",
            f"后端：Whisper + Gemma4-e2b(llama.cpp)，运行模式：{config.llama_cpp_runtime_mode.upper()}，模型：{config.llama_cpp_model_path}",
        )
        return Gemma4E2BAdapter(config, logger=logger)




    from app.engines.whisper_marian_adapter import WhisperMarianAdapter

    logger("INFO", "后端：Whisper + Marian 本地离线")
    return WhisperMarianAdapter(config)
