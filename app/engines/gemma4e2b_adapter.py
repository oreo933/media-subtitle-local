from __future__ import annotations

import atexit
import subprocess
import time
from pathlib import Path
import os
import re


from urllib.parse import urlparse

import requests

from app.core.config import AppConfig
from app.core.models import SubtitleSegment
from app.engines.base_adapter import EngineAdapter
from app.services.asr_service import AsrService


class Gemma4E2BAdapter(EngineAdapter):
    """通过 llama.cpp(OpenAI-compatible) 调用本地 Gemma4-e2b Q4_K_M。"""

    def __init__(self, config: AppConfig, logger=None) -> None:
        self.config = config
        self.asr = AsrService(config)
        self._llama_proc: subprocess.Popen | None = None
        self._logger = logger
        self._token_total_prompt = 0
        self._token_total_completion = 0
        self._token_total_all = 0
        self._chat_calls = 0
        self._session_started_at = 0.0
        self._last_chat_started_at = 0.0
        atexit.register(self._cleanup)




    def transcribe(self, audio_path: Path) -> tuple[list[SubtitleSegment], str | None]:
        """
        识别阶段：faster-whisper 先转写，再由 Gemma 做轻量纠错（本地离线）。
        说明：当前 GGUF 文本模型不直接做音频识别，因此使用 ASR+LLM 联合流程。
        """
        segments, language = self.asr.transcribe(audio_path)
        self._ensure_runtime()

        # 纠错改为分批执行，减少请求次数并保持上下文一致性。
        refined = self._refine_segments_batch(segments, language or "auto")
        return refined, language


    def translate_segments(self, segments: list[SubtitleSegment], source_lang: str) -> list[SubtitleSegment]:
        self._ensure_runtime()
        total = len(segments)
        if total == 0:
            return []

        batch_size = 10
        out: list[SubtitleSegment] = []
        done = 0
        for i in range(0, total, batch_size):
            batch = segments[i : i + batch_size]
            translated = self._translate_segments_batch(batch, source_lang)
            out.extend(translated)
            done += len(batch)
            if self._logger and (done == len(batch) or done % 20 == 0 or done == total):
                self._logger("INFO", f"字幕翻译进度：{done}/{total}")
        return out



    def _refine_text(self, text: str, source_lang: str) -> str:
        prompt = (
            "你是字幕纠错助手。请对 ASR 识别文本做最小改动纠错，"
            "仅输出纠错后的原语言文本，不翻译、不解释。\n"
            f"原语言: {source_lang}\n"
            f"文本: {text}"
        )
        return self._chat(prompt, fallback=text, temperature=0.1, max_tokens=192)

    def _translate_text(self, text: str, source_lang: str) -> str:
        prompt = (
            "你是影视字幕翻译助手。请将下面文本翻译成简体中文，"
            "保持简洁、口语化、符合字幕阅读，不要解释。\n"
            f"原语言: {source_lang}\n"
            f"文本: {text}"
        )
        return self._chat(prompt, fallback=text, temperature=0.1, max_tokens=192)

    def _refine_segments_batch(self, segments: list[SubtitleSegment], source_lang: str) -> list[SubtitleSegment]:
        if not segments:
            return []

        batch_size = 10
        out: list[SubtitleSegment] = []
        for i in range(0, len(segments), batch_size):
            batch = segments[i : i + batch_size]
            numbered = "\n".join(f"{idx+1}. {seg.text}" for idx, seg in enumerate(batch))
            prompt = (
                "你是字幕纠错助手。对以下每一行做最小改动纠错，仅修正明显识别错误，不改写语气。\n"
                "严格要求：\n"
                "1) 必须按相同序号逐行输出；\n"
                "2) 只输出“序号. 文本”；\n"
                "3) 不要解释，不要增删行。\n"
                f"原语言: {source_lang}\n"
                "待纠错文本:\n"
                f"{numbered}"
            )
            raw = self._chat(prompt, fallback=numbered, temperature=0.0, max_tokens=512)
            parsed = self._parse_numbered_lines(raw, len(batch))
            if len(parsed) != len(batch):
                parsed = [seg.text for seg in batch]
            for seg, txt in zip(batch, parsed):
                out.append(SubtitleSegment(start=seg.start, end=seg.end, text=txt.strip() or seg.text))
        return out

    def _translate_segments_batch(self, segments: list[SubtitleSegment], source_lang: str) -> list[SubtitleSegment]:
        numbered = "\n".join(f"{idx+1}. {seg.text}" for idx, seg in enumerate(segments))
        prompt = (
            "你是专业影视字幕翻译助手。请把以下文本翻译为简体中文。\n"
            "翻译准则：\n"
            "1) 忠实原意，不漏译，不臆译；\n"
            "2) 人名/地名/专有名词保持一致；\n"
            "3) 语气自然口语化，适合字幕阅读；\n"
            "4) 不要输出任何解释。\n"
            "输出格式要求（必须遵守）：\n"
            "- 按相同序号逐行输出；\n"
            "- 每行格式：序号. 翻译文本；\n"
            "- 行数必须与输入一致。\n"
            f"原语言: {source_lang}\n"
            "待翻译文本:\n"
            f"{numbered}"
        )
        raw = self._chat(prompt, fallback=numbered, temperature=0.0, max_tokens=1024)
        parsed = self._parse_numbered_lines(raw, len(segments))
        if len(parsed) != len(segments):
            # 回退到单句翻译，保证结果可用。
            parsed = [self._translate_text(seg.text, source_lang) for seg in segments]

        out: list[SubtitleSegment] = []
        for seg, txt in zip(segments, parsed):
            out.append(SubtitleSegment(start=seg.start, end=seg.end, text=(txt.strip() or seg.text)))
        return out

    def _parse_numbered_lines(self, text: str, expected: int) -> list[str]:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        result: list[str] = []
        for ln in lines:
            m = re.match(r"^(\d+)\s*[\.)、]\s*(.*)$", ln)
            if not m:
                continue
            idx = int(m.group(1))
            content = m.group(2).strip()
            if 1 <= idx <= expected:
                while len(result) < idx:
                    result.append("")
                result[idx - 1] = content

        while result and result[-1] == "":
            result.pop()

        if len(result) != expected or any(x == "" for x in result):
            return []
        return result


    def _chat(self, prompt: str, fallback: str, temperature: float, max_tokens: int) -> str:
        url = f"{self.config.llama_cpp_base_url.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": self.config.llama_cpp_model_name,
            "messages": [
                {"role": "system", "content": "你只输出结果正文，不输出额外内容。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            if self._session_started_at <= 0:
                self._session_started_at = time.perf_counter()
            self._last_chat_started_at = time.perf_counter()
            if self._logger:
                self._logger("INFO", f"LLM 请求中：max_tokens={max_tokens}, temperature={temperature}")
            resp = requests.post(url, json=payload, timeout=self.config.llama_cpp_timeout_sec)

            resp.raise_for_status()
            data = resp.json()

            usage = data.get("usage") or {}
            prompt_tokens = int(usage.get("prompt_tokens") or 0)
            completion_tokens = int(usage.get("completion_tokens") or 0)
            total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))

            self._chat_calls += 1
            self._token_total_prompt += prompt_tokens
            self._token_total_completion += completion_tokens
            self._token_total_all += total_tokens

            chat_elapsed = max(time.perf_counter() - self._last_chat_started_at, 1e-6)
            session_elapsed = max(time.perf_counter() - self._session_started_at, 1e-6)
            avg_speed = self._token_total_all / session_elapsed
            instant_speed = total_tokens / chat_elapsed if total_tokens > 0 else 0.0


            if self._logger:
                self._logger(
                    "INFO",
                    (
                        f"LLM 返回：本次 tokens(prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens})，"
                        f"耗时 {chat_elapsed:.1f}s，速度 {instant_speed:.1f} tok/s；"
                        f"累计 calls={self._chat_calls}, total={self._token_total_all}, 平均 {avg_speed:.1f} tok/s"
                    ),
                )


            content = data["choices"][0]["message"]["content"].strip()
            return content or fallback
        except Exception as exc:
            if self._logger:
                self._logger("WARN", f"LLM 请求失败，使用回退文本：{exc}")
            return fallback


    def _ensure_runtime(self) -> None:
        if self._ping_server():
            return
        if not self.config.llama_cpp_autostart:
            raise RuntimeError("未检测到 llama.cpp 服务，请先启动 llama-server。")
        self._start_server()

    def _start_server(self) -> None:
        model_path = self.config.llama_cpp_model_path.resolve()
        if not model_path.exists():
            raise RuntimeError(f"未找到 Gemma 模型文件：{model_path}")

        # 兼容中文路径场景：部分 llama-server 版本在 Windows 下读取绝对路径会失败，
        # 这里切到模型目录并只传文件名，避免 GGUF 打开失败。
        model_cwd = model_path.parent
        model_arg = model_path.name

        parsed = urlparse(self.config.llama_cpp_base_url)
        host = parsed.hostname or "127.0.0.1"
        port = str(parsed.port or 8080)

        use_gpu = self.config.llama_cpp_runtime_mode == "gpu"
        server_cmd = self.config.llama_cpp_server_cmd_gpu if use_gpu else self.config.llama_cpp_server_cmd
        if use_gpu:
            start_layers = self.config.llama_cpp_gpu_layers if self.config.llama_cpp_gpu_layers > 0 else 999
            # 先尽量使用用户设置；失败时逐级降低层数，最后再回退到 CPU。
            tier_layers = [999, 48, 40, 32, 24, 20, 16, 12, 8, 4, 2]
            gpu_candidates = []
            for x in [start_layers, *tier_layers, 0]:
                if x not in gpu_candidates:
                    gpu_candidates.append(x)
        else:
            gpu_candidates = [0]




        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW

        detected_gpu_device = None
        if use_gpu:
            detected_gpu_device = self._detect_vulkan_device_arg(server_cmd, model_cwd, creationflags)
            if self._logger:
                if detected_gpu_device:
                    self._logger("INFO", f"检测到 Vulkan 设备参数：{detected_gpu_device}")
                else:
                    self._logger("WARN", "未检测到可用的 Vulkan 设备参数，启动时将省略 --device 以兼容当前 llama-server 版本。")

        last_error = ""
        for gpu_layers in gpu_candidates:

            current_server_cmd = server_cmd if (use_gpu and gpu_layers > 0) else self.config.llama_cpp_server_cmd
            cmd = [
                current_server_cmd,

                "-m",
                model_arg,
                "--host",
                host,
                "--port",
                port,
                "--ctx-size",
                str(self.config.llama_cpp_ctx_size),
                "--threads",
                str(self.config.llama_cpp_threads),
                "--n-gpu-layers",
                str(gpu_layers),
                "--fit",
                "off",
            ]
            if use_gpu and gpu_layers > 0:
                if detected_gpu_device:
                    cmd.extend(["--device", detected_gpu_device])
            else:
                cmd.extend(["--device", "none", "--no-kv-offload"])


            if self._logger:
                self._logger(
                    "INFO",
                    f"启动 llama-server：mode={'GPU/Vulkan' if use_gpu and gpu_layers > 0 else 'CPU'}，gpu_layers={gpu_layers}，cmd={current_server_cmd}",
                )





            boot_log_dir = Path("logs")
            boot_log_dir.mkdir(parents=True, exist_ok=True)
            mode_tag = "gpu" if (use_gpu and gpu_layers > 0) else "cpu"
            boot_log_file = boot_log_dir / f"llama_boot_{mode_tag}_{gpu_layers}.log"

            try:
                with open(boot_log_file, "w", encoding="utf-8") as boot_fh:
                    boot_fh.write("CMD: " + " ".join(cmd) + os.linesep)
                    boot_fh.flush()

                    self._llama_proc = subprocess.Popen(
                        cmd,
                        stdout=boot_fh,
                        stderr=subprocess.STDOUT,
                        creationflags=creationflags,
                        text=True,
                        encoding="utf-8",
                        errors="ignore",
                        cwd=str(model_cwd),
                    )

                    deadline = time.time() + self.config.llama_cpp_boot_timeout_sec
                    attempt_timed_out = True
                    while time.time() < deadline:
                        if self._ping_server():
                            return
                        if self._llama_proc.poll() is not None:
                            attempt_timed_out = False
                            break
                        time.sleep(0.5)

                    if self._llama_proc and self._llama_proc.poll() is None:
                        try:
                            self._llama_proc.terminate()
                            self._llama_proc.wait(timeout=3)
                        except Exception:
                            pass
                        finally:
                            self._llama_proc = None

                        reason = boot_log_file.read_text(encoding="utf-8", errors="ignore").strip()
                        if attempt_timed_out:
                            last_error = f"GPU层={gpu_layers}，启动超时，详情见 {boot_log_file.as_posix()}：{reason[-1200:]}"
                        else:
                            last_error = last_error or f"GPU层={gpu_layers}，启动失败。"
                        if use_gpu and gpu_layers > 0 and self._logger:
                            self._logger("WARN", f"GPU 启动失败，准备降级重试：{last_error}")
                        continue

                    reason = boot_log_file.read_text(encoding="utf-8", errors="ignore").strip()
                    if reason:
                        last_error = f"GPU层={gpu_layers}，进程退出，详情见 {boot_log_file.as_posix()}：{reason[-1200:]}"
                    else:
                        last_error = f"GPU层={gpu_layers}，进程已退出但未输出错误日志（{boot_log_file.as_posix()}）。"

                    if use_gpu and gpu_layers > 0 and self._logger:
                        self._logger("WARN", f"GPU 启动失败，准备降级重试：{last_error}")
                    self._llama_proc = None

            except FileNotFoundError as exc:
                if use_gpu:
                    raise RuntimeError(
                        "未找到 Vulkan 版 llama-server。请确认 llama-vulkan/ 目录中存在 llama-server.exe，"
                        "或设置 LLAMA_CPP_SERVER_CMD_GPU 为其绝对路径。"
                    ) from exc
                raise RuntimeError(
                    "未找到 llama-server。当前会自动在根目录和 llama/ 子目录搜索。"
                    "请确认下载包里包含 llama-server.exe（不仅是 hipblaslt/rocblas 依赖目录），"
                    "或设置 LLAMA_CPP_SERVER_CMD 为 llama-server.exe 的绝对路径。"
                ) from exc



        normalized_error = (last_error or "").lower()
        if "unknown model architecture" in normalized_error and "gemma4" in normalized_error:
            raise RuntimeError(
                "当前 llama-server 版本不支持 Gemma4（架构标识 gemma4）。"
                "请更新 llama.cpp 到支持 Gemma4 的新版（替换 llama 目录下可执行文件），"
                "或改用 Gemma2/Llama3 等当前版本支持的 GGUF 模型。"
            )

        if len(gpu_candidates) > 1:
            raise RuntimeError(
                "llama-server 启动失败（已尝试 GPU 与 CPU 模式）。"
                f"最后错误：{last_error or '未知错误'}"
            )
        raise RuntimeError(f"llama-server 启动失败：{last_error or '未知错误'}")





    def _detect_vulkan_device_arg(self, server_cmd: str, model_cwd: Path, creationflags: int) -> str | None:
        """探测当前 llama-server 可接受的 Vulkan 设备参数值。"""
        candidates = [
            [server_cmd, "--list-devices"],
            [server_cmd, "-ld"],
        ]
        out = ""
        for cmd in candidates:
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    timeout=6,
                    creationflags=creationflags,
                    cwd=str(model_cwd),
                )
                merged = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
                if merged:
                    out = merged
                    break
            except Exception:
                continue

        if not out:
            return None

        low = out.lower()
        if "vulkan" not in low:
            return None

        # 优先提取类似 "Vulkan0" / "vulkan0" 的显式设备名
        for token in out.replace(",", " ").split():
            t = token.strip("[](){}:;")
            tl = t.lower()
            if tl.startswith("vulkan") and len(t) > len("vulkan"):
                return t

        # 兜底：给出常见命名，后续启动尝试会验证可用性
        return "Vulkan0"

    def _ping_server(self) -> bool:
        try:
            base = self.config.llama_cpp_base_url.rstrip("/")
            resp = requests.get(f"{base}/health", timeout=2)
            if resp.ok:
                return True
        except Exception:
            pass

        try:
            base = self.config.llama_cpp_base_url.rstrip("/")
            resp = requests.get(f"{base}/v1/models", timeout=2)
            return resp.ok
        except Exception:
            return False


    def _cleanup(self) -> None:
        if self._llama_proc and self._llama_proc.poll() is None:
            self._llama_proc.terminate()

