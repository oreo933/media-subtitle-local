## Media Subtitle Local（Windows 本地离线字幕工具）

这是一个本地离线运行的桌面软件：批量扫描视频、提取音频、识别英文/日文语音并翻译为中文字幕，默认输出 `.zh.srt` 到视频同目录。

### 功能特性
- **本地离线**：默认不走网络 API，不上传视频内容。
- **批处理目录**：选择一个文件夹即可批量处理。
- **可视化 GUI**：查看提取、识别、翻译阶段状态与日志。
- **资源控制**：内存/显存以约 `5GB` 为推荐目标，自动节流与重试。
- **后端可选**：
  - `llama.cpp`（推荐，Gemma Q4）
  - `Whisper + Marian`（备用）

### 目录结构
- `app/main.py`：程序入口
- `app/ui/`：主界面与组件
- `app/services/`：提取、流水线、字幕写出
- `app/engines/`：模型适配层
- `app/core/`：配置、日志、资源监控

### 环境准备（Windows）
1. 安装 Python 3.11+
2. 安装 FFmpeg，并确保 `ffmpeg` 在 PATH 中
   - 如果不想改 PATH，可设置环境变量：`FFMPEG_CMD=C:\\path\\to\\ffmpeg.exe`
3. 安装依赖：


```bash
python -m pip install -r requirements.txt
```

### llama.cpp 调用方式（推荐）
程序会优先使用项目目录 `models/` 下的模型文件：
- `models/gemma-4-E2B-it-Uncensored-MAX.Q4_K_M.gguf`

运行时策略：
- **识别阶段**：`faster-whisper` 转写 + `Gemma` 本地纠错
- **翻译阶段**：`Gemma` 翻译为简体中文字幕

如果本机已装 `llama-server` 并在 PATH 中，程序会自动尝试拉起服务（默认 `127.0.0.1:8080`）。
也可手动启动：

```bash
llama-server -m .\models\gemma-4-E2B-it-Uncensored-MAX.Q4_K_M.gguf --port 8080 --ctx-size 4096 --threads 6 --n-gpu-layers 20
```

可通过环境变量覆盖：

- `LLAMA_CPP_BASE_URL`
- `LLAMA_CPP_MODEL`
- `LLAMA_CPP_MODEL_PATH`
- `LLAMA_CPP_SERVER_CMD`
- `LLAMA_CPP_AUTOSTART`

提示：若你不想配置 PATH，可把 `llama-server.exe` 放到项目根目录或 `llama/` 目录，程序会自动搜索并优先使用。
如果 `llama/` 下只有 `hipblaslt`、`rocblas` 这类依赖库目录，但没有 `llama-server.exe`，仍然无法启动服务。




### 运行程序

```bash
python -m app.main
```

### 打包为 EXE

默认推荐 **launcher 模式**（稳定入口 exe，放在项目根目录）：

```powershell
./scripts/build_windows.ps1 -Mode launcher
```

执行后会生成：`./MediaSubtitleLocal.exe`（就在根目录）。

该模式下，`exe` 只是启动器，后续你更新 `app/` 代码通常**不需要反复重打包**；保持根目录 `MediaSubtitleLocal.exe` 不变即可。

如果系统默认 `python` 指向 Windows 商店桩程序，可显式指定解释器：

```powershell
./scripts/build_windows.ps1 -Mode launcher -PythonExe "D:\\tools\\python311\\python.exe"
```

如果依赖已提前安装，可加 `-SkipInstall` 提速：

```powershell
./scripts/build_windows.ps1 -Mode launcher -PythonExe "C:\\Users\\你的用户名\\.workbuddy\\binaries\\python\\versions\\3.11.9\\python.exe" -SkipInstall
```

如需传统全量分发包（`dist/MediaSubtitleLocal/`），可使用：

```powershell
./scripts/build_windows.ps1 -Mode full
```




### 使用说明
1. 启动程序
2. 选择模式：`单文件` 或 `文件夹`
3. 选择目标文件/目录
4. 选择后端（推荐 `llama.cpp`）
5. 点击“开始处理”
6. 在右侧日志和任务表中查看进度（含队列序号）

### 外置日志（无需手动复制报错）
- 每次运行都会生成：`logs/run_时间戳.log`
- 同时维护固定入口：`logs/latest.log`（始终是最近一次运行日志）
- 当你遇到错误时，可直接查看 `logs/latest.log`


输出：
- 原文字幕：`xxx.src.srt`
- 中文字幕：`xxx.zh.srt`

### 注意事项
- 影视内容可能包含敏感场景，本工具仍在本地离线处理，不上传素材。
- 若 `llama.cpp` 服务未启动，翻译会回退为原文（任务不中断）。
- 首次加载模型可能较慢，属于正常现象。

### 开源发布建议
- 当前仓库已使用 **MIT License**。
- 默认 `.gitignore` 已忽略模型、日志、打包产物与本地二进制，避免仓库体积过大。
- 建议发布 `v0.x` 版本，先收集真实使用反馈再持续迭代。

### Roadmap（可选）
- 批量翻译策略继续优化（按语言/长度动态 batch）。
- 术语表与专有名词一致性增强。
- 更多字幕后处理能力（断句、标点、口语化风格模板）。
- 更多平台/显卡后端兼容性优化。

