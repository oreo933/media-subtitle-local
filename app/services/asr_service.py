from __future__ import annotations

from pathlib import Path

from app.core.config import AppConfig
from app.core.models import SubtitleSegment


class AsrService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._model = None

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("请先安装 faster-whisper 及其依赖") from exc

        self._model = WhisperModel(
            model_size_or_path=self.config.whisper_model_size,
            device=self.config.whisper_device,
            compute_type=self.config.whisper_compute_type,
        )
        return self._model

    def transcribe(self, audio_path: Path) -> tuple[list[SubtitleSegment], str | None]:
        model = self._ensure_model()
        segments, info = model.transcribe(str(audio_path), vad_filter=True, beam_size=1)
        result: list[SubtitleSegment] = []
        for seg in segments:
            txt = (seg.text or "").strip()
            if txt:
                result.append(SubtitleSegment(start=float(seg.start), end=float(seg.end), text=txt))
        lang = getattr(info, "language", None)
        return result, lang
