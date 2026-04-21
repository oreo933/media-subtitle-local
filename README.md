# Media Subtitle Local

<div align="center">

![Platform](https://img.shields.io/badge/platform-Windows-0078D6)
![Release](https://img.shields.io/github/v/release/oreo933/media-subtitle-local?display_name=tag)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)
![GUI](https://img.shields.io/badge/gui-PySide6-41CD52)
![Local First](https://img.shields.io/badge/workflow-local--first-111827)
![License](https://img.shields.io/badge/license-MIT-green)

**Windows 本地离线视频字幕生成与翻译工具**  
**Local-first subtitle transcription and translation for Windows**

一个面向 **本地批量处理视频** 场景的桌面应用：扫描视频、提取音频、生成原文字幕，并翻译输出中文字幕。项目强调 **离线、可控、可观察、可继续扩展**。

</div>

---

## Highlights

- **Local-first**：尽量不上传视频内容，降低隐私风险
- **Batch workflow**：支持单文件与文件夹批量处理
- **Desktop GUI**：任务队列、处理阶段、日志状态都可视化
- **Dual backend path**：支持 `llama.cpp + Gemma` 与 `Whisper + Marian`
- **Windows packaging ready**：提供 PowerShell 打包脚本
- **Developer-friendly**：模块结构清晰，便于继续二次开发

---

## 为什么做这个项目

这个项目的出发点其实很直接：**有一些影片本身只有英语或日语语音，但还没有现成字幕，或者现有字幕并不方便直接使用。**

很多时候，大家其实只是想更高效地解决一个实际问题：

> **把没有字幕、或者字幕不完整的英文 / 日文影片，在本地尽快整理成可用的中文字幕。**

Media Subtitle Local 就是围绕这个需求来设计的。项目希望把这件事做得更顺手一些：

- 可以直接批量处理视频
- 可以在本地完成音频提取、识别和翻译
- 可以看到任务状态和运行日志
- 可以继续扩展和调整后端能力

它的重点不是追求花哨，而是尽量把“没有字幕可用”这件事，变成一个更容易处理的本地工作流。

---

## 项目定位

这不是一个在线视频平台抓字幕工具，也不是一个依赖远程大模型服务的云端产品客户端。

它更适合被理解为：

> **一套本地优先、面向 Windows 的字幕处理应用骨架。**

既可以直接拿来跑，也适合作为：

- 本地字幕工具的二次开发基础
- 离线转写 / 翻译流水线样板
- GUI + 模型推理 + 批处理编排的参考项目

---

## Core Features

### 1. 本地离线处理
- 默认不依赖云端字幕 API
- 适合隐私敏感内容的本地处理场景
- 输出文件保留在视频所在目录

### 2. 批量视频处理
- 支持单文件模式
- 支持按文件夹批量扫描
- 支持任务队列式处理与状态展示

### 3. 字幕生成与翻译
- 音频提取
- 原文字幕生成
- 中文字幕翻译输出
- 默认输出：
  - `xxx.src.srt`
  - `xxx.zh.srt`

### 4. 可视化 GUI
- 主界面选择输入目标
- 任务表显示处理阶段
- 日志面板展示运行过程
- 更适合长时间批处理观察

### 5. 资源控制与可扩展性
- 加入基础资源监控能力
- 支持后端替换与后续增强
- 适合作为继续工程化的起点

---

## 处理流程

```text
Scan videos
  -> Extract audio with FFmpeg
  -> Transcribe with ASR backend
  -> Translate subtitle text
  -> Write .src.srt / .zh.srt
  -> Update GUI status and logs
```

默认输出文件位于原视频同目录：

- `xxx.src.srt`：原文字幕
- `xxx.zh.srt`：中文字幕

---

## Project Structure

```text
app/
  core/        configuration, logging, resource monitoring, models
  engines/     backend adapters (llama.cpp / whisper / translation)
  services/    audio extraction, pipeline orchestration, subtitle writing
  ui/          main window and UI widgets
  utils/       file scan, timecode, helper utilities
scripts/
  build_windows.ps1   Windows build script
assets/
  icons/       application icons
launcher.py    launcher entry
requirements.txt
```

---

## Tech Stack

- **GUI**: PySide6
- **ASR**: faster-whisper
- **Translation / inference**: transformers / ctranslate2 / local LLM route
- **Local LLM serving**: llama.cpp
- **Packaging**: PyInstaller
- **System monitoring**: psutil / pynvml

---

## Environment Requirements

### System
- Windows 10 / 11
- Python 3.11+
- FFmpeg available in PATH or configurable by environment variable

### Python Dependencies

See `requirements.txt`:

- `PySide6`
- `faster-whisper`
- `ctranslate2`
- `transformers`
- `sentencepiece`
- `torch`
- `requests`
- `psutil`
- `pynvml`
- `pyinstaller`

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

If FFmpeg is not in PATH, you can set it manually:

```powershell
$env:FFMPEG_CMD="C:\tools\ffmpeg\bin\ffmpeg.exe"
```

---

## Recommended Backend: llama.cpp

The project supports a local `llama.cpp` service path.

Recommended model path example:

```text
models/gemma-4-E2B-it-Uncensored-MAX.Q4_K_M.gguf
```

### Runtime strategy
- **Transcription stage**: `faster-whisper` + local correction flow
- **Translation stage**: `Gemma` outputs simplified Chinese subtitles

### Example manual startup

```bash
llama-server -m .\models\gemma-4-E2B-it-Uncensored-MAX.Q4_K_M.gguf --port 8080 --ctx-size 4096 --threads 6 --n-gpu-layers 20
```

### Supported environment overrides

- `LLAMA_CPP_BASE_URL`
- `LLAMA_CPP_MODEL`
- `LLAMA_CPP_MODEL_PATH`
- `LLAMA_CPP_SERVER_CMD`
- `LLAMA_CPP_AUTOSTART`

If `llama-server` is available in PATH, the app can try to start it automatically.  
If not, you can also place the executable in the project root or inside `llama/`.

---

## Quick Start

### 1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 2. Run the application

```bash
python -m app.main
```

### 3. Basic usage

1. Launch the application
2. Choose `single file` or `folder` mode
3. Select a target video or directory
4. Choose a backend (recommended: `llama.cpp`)
5. Start processing
6. Watch progress in the task table and log panel

---

## Build for Windows

### Launcher mode (recommended)

```powershell
./scripts/build_windows.ps1 -Mode launcher
```

This generates:

```text
MediaSubtitleLocal.exe
```

Launcher mode is the recommended distribution entry for daily use.

### Specify Python interpreter

```powershell
./scripts/build_windows.ps1 -Mode launcher -PythonExe "D:\tools\python311\python.exe"
```

### Skip dependency installation

```powershell
./scripts/build_windows.ps1 -Mode launcher -PythonExe "D:\tools\python311\python.exe" -SkipInstall
```

### Full distribution mode

```powershell
./scripts/build_windows.ps1 -Mode full
```

---

## Screenshots

> Screenshot area can be added later.

Suggested sections:
- Main window
- Task queue
- Processing log panel
- Packaging result

Example markdown after adding images:

```md
![Main Window](./docs/screenshots/main-window.png)
![Task Queue](./docs/screenshots/task-queue.png)
```

---

## FAQ

### Q1: Does it upload my videos to a cloud service?
默认设计目标是 **本地优先**。项目尽量不依赖在线字幕 API，媒体内容默认在本机处理。

### Q2: What files does it generate?
It typically writes:
- `xxx.src.srt`
- `xxx.zh.srt`

### Q3: What if `llama.cpp` is not available?
Depending on current configuration, the app may fall back, degrade gracefully, or keep the pipeline partially available.

### Q4: Is this production-ready?
更准确的说法是：它已经具备较完整的工程骨架和可运行链路，但仍然适合持续迭代，而不是宣称“最终版”。

### Q5: Can I use this as a base project?
可以。这个仓库本身就适合作为本地字幕工具、离线工作流或桌面 AI 工具的二次开发基础。

---

## Logging and Troubleshooting

The app writes local logs for easier diagnosis:

- `logs/run_<timestamp>.log`
- `logs/latest.log`

When something fails, start with:

```text
logs/latest.log
```

---

## Design Goals

- **Run end-to-end locally**
- **Show observable processing states**
- **Keep the workflow practical for Windows users**
- **Remain easy to extend and refactor**
- **Provide a real project base instead of a one-off demo**

---

## Use Cases

- Local English / Japanese subtitle generation
- Chinese subtitle draft generation for videos
- Offline subtitle workflows on Windows
- A reference project for GUI + model inference + batch processing

---

## Roadmap

- [ ] Improve batch translation strategy
- [ ] Better terminology consistency
- [ ] Stronger punctuation and segmentation post-processing
- [ ] Better backend compatibility and device adaptation
- [ ] Add screenshots and demo materials
- [ ] Add sample input / output examples

---

## Contributing

Issues, suggestions, and improvement ideas are welcome.

If you want to contribute, a simple path is:

1. Fork the repository
2. Create a feature branch
3. Make changes with clear commits
4. Open a pull request

Recommended contribution directions:
- Better subtitle quality
- More robust backend management
- UI/UX improvements
- Windows packaging improvements
- Better documentation and examples

---

## Privacy Notes

- This repository is intended to stay **local-first**
- Build artifacts, models, logs, and local binaries should not be committed by default
- Public examples should avoid personal machine paths and private environment details

---

## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for release history and notable updates.

---

## License

MIT License

---

## English Summary

Media Subtitle Local is a Windows desktop application for local-first subtitle transcription and translation. It is designed for batch video processing, GUI visibility, offline-friendly workflows, and an architecture that can continue evolving.

This repository is suitable both as a usable local subtitle tool and as a development base for building more complete desktop AI media workflows.
