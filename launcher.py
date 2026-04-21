from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from pathlib import Path


def _show_error(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(0, message, "MediaSubtitleLocal 启动失败", 0x10)
    except Exception:
        pass


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _python_candidates(base: Path) -> list[list[str]]:
    env_python = os.getenv("MEDIA_SUBTITLE_PYTHON")
    candidates: list[list[str]] = []

    if env_python:
        candidates.append([env_python])

    bundled = base / ".runtime" / "python" / "python.exe"
    if bundled.exists():
        candidates.append([str(bundled)])

    workbuddy = Path.home() / ".workbuddy" / "binaries" / "python" / "versions" / "3.11.9" / "python.exe"
    if workbuddy.exists():
        candidates.append([str(workbuddy)])

    if sys.executable.lower().endswith("python.exe"):
        candidates.append([sys.executable])

    candidates.append(["py", "-3.11"])
    candidates.append(["python"])
    return candidates


def _prefer_pythonw(cmd: list[str]) -> list[str]:
    exe = Path(cmd[0])
    if exe.name.lower() == "python.exe":
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.exists():
            return [str(pythonw), *cmd[1:]]
    return cmd


def main() -> int:
    base = _base_dir()
    app_dir = base / "app"
    if not app_dir.exists():
        _show_error(f"未找到应用目录: {app_dir}")
        return 1

    for cmd in _python_candidates(base):
        try:
            run_cmd = _prefer_pythonw(cmd)
            proc = subprocess.Popen(
                [*run_cmd, "-m", "app.main"],
                cwd=str(base),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return 0 if proc.pid > 0 else 1
        except Exception:
            continue

    _show_error("未找到可用 Python 3.11 运行环境，请先安装并配置。")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
