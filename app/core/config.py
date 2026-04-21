from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os


def _detect_llama_server(default_cmd: str, base_dir: str = "llama") -> str:
    if default_cmd != "llama-server":
        return default_cmd

    base = Path(base_dir)
    candidates = [
        Path("llama-server.exe"),
        base / "llama-server.exe",
        base / "bin" / "llama-server.exe",
    ]

    for path in candidates:
        if path.exists():
            return str(path.resolve())

    for path in base.rglob("llama-server*.exe") if base.exists() else []:
        if path.is_file():
            return str(path.resolve())

    return default_cmd




@dataclass(slots=True)
class AppConfig:
    app_name: str = "Media Subtitle Local"
    output_same_dir: bool = True
    log_dir: Path = field(default_factory=lambda: Path("logs"))

    # 资源策略：5GB 为推荐目标，不是硬限制
    recommended_resource_gb: float = 5.0
    max_concurrent_jobs: int = 1
    max_retries: int = 1
    retry_backoff_sec: float = 1.5

    # 媒体与输出
    video_extensions: tuple[str, ...] = (".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv")
    audio_sample_rate: int = 16000
    audio_channels: int = 1
    ffmpeg_cmd: str = "ffmpeg"


    # 模型后端
    engine_backend: str = "llamacpp"  # llamacpp | whisper_marian
    whisper_model_size: str = "small"
    whisper_compute_type: str = "int8"
    whisper_device: str = "auto"

    # llama.cpp OpenAI-compatible server
    llama_cpp_base_url: str = "http://127.0.0.1:8080"
    llama_cpp_model_name: str = "gemma4-e2b-q4km"
    llama_cpp_timeout_sec: int = 120
    llama_cpp_server_cmd: str = "llama-server"
    llama_cpp_server_cmd_gpu: str = "llama-server"
    llama_cpp_runtime_mode: str = "cpu"  # cpu | gpu
    llama_cpp_autostart: bool = True
    llama_cpp_boot_timeout_sec: int = 300


    llama_cpp_ctx_size: int = 4096
    llama_cpp_threads: int = 6
    llama_cpp_gpu_layers: int = 0

    llama_cpp_model_path: Path = field(
        default_factory=lambda: Path("models") / "gemma-4-E2B-it-Uncensored-MAX.Q4_K_M.gguf"
    )

    # 翻译模型（备用）
    marian_en_zh: str = "Helsinki-NLP/opus-mt-en-zh"
    marian_ja_zh: str = "Helsinki-NLP/opus-mt-ja-zh"


def _to_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config() -> AppConfig:
    cfg = AppConfig()
    cfg.engine_backend = os.getenv("SUBTITLE_ENGINE", cfg.engine_backend)
    cfg.whisper_model_size = os.getenv("WHISPER_MODEL_SIZE", cfg.whisper_model_size)
    cfg.llama_cpp_base_url = os.getenv("LLAMA_CPP_BASE_URL", cfg.llama_cpp_base_url)
    cfg.llama_cpp_model_name = os.getenv("LLAMA_CPP_MODEL", cfg.llama_cpp_model_name)
    cfg.llama_cpp_server_cmd = os.getenv("LLAMA_CPP_SERVER_CMD", cfg.llama_cpp_server_cmd)
    cfg.llama_cpp_server_cmd_gpu = os.getenv("LLAMA_CPP_SERVER_CMD_GPU", cfg.llama_cpp_server_cmd_gpu)
    cfg.llama_cpp_runtime_mode = os.getenv("LLAMA_CPP_RUNTIME_MODE", cfg.llama_cpp_runtime_mode).strip().lower()
    if cfg.llama_cpp_runtime_mode not in {"cpu", "gpu"}:
        cfg.llama_cpp_runtime_mode = "cpu"

    cfg.llama_cpp_autostart = _to_bool(os.getenv("LLAMA_CPP_AUTOSTART"), cfg.llama_cpp_autostart)
    cfg.llama_cpp_model_path = Path(os.getenv("LLAMA_CPP_MODEL_PATH", str(cfg.llama_cpp_model_path)))
    cfg.llama_cpp_boot_timeout_sec = int(os.getenv("LLAMA_CPP_BOOT_TIMEOUT_SEC", str(cfg.llama_cpp_boot_timeout_sec)))
    cfg.llama_cpp_ctx_size = int(os.getenv("LLAMA_CPP_CTX_SIZE", str(cfg.llama_cpp_ctx_size)))
    cfg.llama_cpp_threads = int(os.getenv("LLAMA_CPP_THREADS", str(cfg.llama_cpp_threads)))
    cfg.llama_cpp_gpu_layers = int(os.getenv("LLAMA_CPP_GPU_LAYERS", str(cfg.llama_cpp_gpu_layers)))
    cfg.ffmpeg_cmd = os.getenv("FFMPEG_CMD", cfg.ffmpeg_cmd)


    cfg.llama_cpp_server_cmd = _detect_llama_server(cfg.llama_cpp_server_cmd, base_dir="llama")
    cfg.llama_cpp_server_cmd_gpu = _detect_llama_server(cfg.llama_cpp_server_cmd_gpu, base_dir="llama-vulkan")



    local_ffmpeg = Path("ffmpeg.exe")
    if cfg.ffmpeg_cmd == "ffmpeg" and local_ffmpeg.exists():
        cfg.ffmpeg_cmd = str(local_ffmpeg.resolve())


    cfg.log_dir.mkdir(parents=True, exist_ok=True)

    return cfg

