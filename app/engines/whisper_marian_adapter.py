from __future__ import annotations

from pathlib import Path

from app.core.config import AppConfig
from app.core.models import SubtitleSegment
from app.engines.base_adapter import EngineAdapter
from app.services.asr_service import AsrService
from app.services.translate_service import TranslateService


class WhisperMarianAdapter(EngineAdapter):
    def __init__(self, config: AppConfig) -> None:
        self.asr = AsrService(config)
        self.translator = TranslateService(config)

    def transcribe(self, audio_path: Path) -> tuple[list[SubtitleSegment], str | None]:
        return self.asr.transcribe(audio_path)

    def translate_segments(self, segments: list[SubtitleSegment], source_lang: str) -> list[SubtitleSegment]:
        texts = [x.text for x in segments]
        translated = self.translator.translate_batch(texts, source_lang=source_lang)
        out: list[SubtitleSegment] = []
        for i, seg in enumerate(segments):
            text = translated[i] if i < len(translated) else seg.text
            out.append(SubtitleSegment(start=seg.start, end=seg.end, text=text))
        return out
