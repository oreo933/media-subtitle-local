from __future__ import annotations

from pathlib import Path

from app.core.models import SubtitleSegment
from app.utils.timecode import to_srt_time


class SubtitleService:
    def write_srt(self, output_path: Path, segments: list[SubtitleSegment]) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for idx, seg in enumerate(segments, start=1):
            lines.append(str(idx))
            lines.append(f"{to_srt_time(seg.start)} --> {to_srt_time(seg.end)}")
            lines.append(seg.text.strip())
            lines.append("")
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path
