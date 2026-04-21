from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def setup_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)

    # 每次运行独立日志
    run_file = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    # 便于外部工具/助手直接读取的固定日志入口（覆盖写入）
    latest_file = log_dir / "latest.log"

    logger = logging.getLogger("media_subtitle")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    run_handler = logging.FileHandler(run_file, encoding="utf-8")
    run_handler.setFormatter(formatter)
    logger.addHandler(run_handler)

    latest_handler = logging.FileHandler(latest_file, mode="w", encoding="utf-8")
    latest_handler.setFormatter(formatter)
    logger.addHandler(latest_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.info("日志已初始化：%s", run_file)
    logger.info("最新日志入口：%s", latest_file)
    return logger
