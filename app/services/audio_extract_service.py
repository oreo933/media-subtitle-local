from __future__ import annotations

from pathlib import Path
import subprocess

from app.core.config import AppConfig


class AudioExtractService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def extract(self, video_path: Path) -> Path:
        tmp_dir = video_path.parent / ".subtitle_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        audio_path = tmp_dir / f"{video_path.stem}.wav"

        cmd = [
            self.config.ffmpeg_cmd,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            str(self.config.audio_channels),
            "-ar",
            str(self.config.audio_sample_rate),
            str(audio_path),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise RuntimeError(
                "未找到 FFmpeg。请安装 FFmpeg 并加入 PATH，"
                "或设置环境变量 FFMPEG_CMD=ffmpeg.exe 的绝对路径。"
            ) from exc

        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg 提取失败: {proc.stderr[-500:]}")

        return audio_path
