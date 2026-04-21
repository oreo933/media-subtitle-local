from __future__ import annotations

from typing import Iterable

from app.core.config import AppConfig


class TranslateService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._cache: dict[str, tuple[object, object]] = {}

    def _model_name(self, source_lang: str) -> str:
        if source_lang.startswith("ja"):
            return self.config.marian_ja_zh
        return self.config.marian_en_zh

    def _ensure_model(self, source_lang: str):
        model_name = self._model_name(source_lang)
        if model_name in self._cache:
            return self._cache[model_name]

        try:
            from transformers import MarianMTModel, MarianTokenizer
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("请先安装 transformers 与 sentencepiece") from exc

        tok = MarianTokenizer.from_pretrained(model_name)
        model = MarianMTModel.from_pretrained(model_name)
        self._cache[model_name] = (tok, model)
        return tok, model

    def translate_batch(self, texts: Iterable[str], source_lang: str) -> list[str]:
        data = [t.strip() for t in texts if t.strip()]
        if not data:
            return []
        tok, model = self._ensure_model(source_lang)
        encoded = tok(data, return_tensors="pt", padding=True, truncation=True)
        generated = model.generate(**encoded, max_new_tokens=192)
        return tok.batch_decode(generated, skip_special_tokens=True)
