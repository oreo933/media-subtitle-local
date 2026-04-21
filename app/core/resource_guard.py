from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field


import psutil

try:
    import pynvml  # type: ignore
except Exception:  # pragma: no cover
    pynvml = None



@dataclass(slots=True)
class ResourceSnapshot:
    cpu_percent: float
    memory_gb: float
    gpu_memory_gb: float
    gpu_dedicated_gb: float = 0.0
    gpu_shared_gb: float = 0.0
    gpu_monitor_name: str = "未检测到"
    gpu_monitor_available: bool = False
    gpu_scope: str = "整机"
    captured_at: float = field(default_factory=time.time)






class ResourceGuard:
    def __init__(self, recommended_gb: float = 5.0) -> None:
        self.recommended_gb = recommended_gb
        self.proc = psutil.Process()
        self._nvml_ready = False
        self._windows_gpu_counter_ready = False
        self._gpu_cache_ttl_sec = 3.0
        self._last_gpu_snapshot: ResourceSnapshot | None = None
        if pynvml is not None:

            try:
                pynvml.nvmlInit()
                self._nvml_ready = True
            except Exception:
                self._nvml_ready = False

        if not self._nvml_ready:
            self._windows_gpu_counter_ready = self._probe_windows_gpu_counter()

    def snapshot(self) -> ResourceSnapshot:
        mem_gb = self.proc.memory_info().rss / (1024 ** 3)
        cpu_percent = psutil.cpu_percent(interval=0.05)
        now = time.time()

        if self._last_gpu_snapshot and (now - self._last_gpu_snapshot.captured_at) < self._gpu_cache_ttl_sec:
            return ResourceSnapshot(
                cpu_percent=cpu_percent,
                memory_gb=mem_gb,
                gpu_memory_gb=self._last_gpu_snapshot.gpu_memory_gb,
                gpu_dedicated_gb=self._last_gpu_snapshot.gpu_dedicated_gb,
                gpu_shared_gb=self._last_gpu_snapshot.gpu_shared_gb,
                gpu_monitor_name=self._last_gpu_snapshot.gpu_monitor_name,
                gpu_monitor_available=self._last_gpu_snapshot.gpu_monitor_available,
                gpu_scope=self._last_gpu_snapshot.gpu_scope,
                captured_at=self._last_gpu_snapshot.captured_at,
            )

        dedicated_gb, shared_gb, monitor_name, available, scope = self._gpu_memory_info()
        snap = ResourceSnapshot(
            cpu_percent=cpu_percent,
            memory_gb=mem_gb,
            gpu_memory_gb=dedicated_gb + shared_gb,
            gpu_dedicated_gb=dedicated_gb,
            gpu_shared_gb=shared_gb,
            gpu_monitor_name=monitor_name,
            gpu_monitor_available=available,
            gpu_scope=scope,
            captured_at=now,
        )
        self._last_gpu_snapshot = snap
        return snap





    def should_throttle(self) -> bool:
        snap = self.snapshot()
        return (snap.memory_gb + snap.gpu_memory_gb) > self.recommended_gb

    def wait_for_budget(self, check_interval: float = 0.8, max_wait: float = 30.0) -> None:
        waited = 0.0
        while self.should_throttle() and waited < max_wait:
            time.sleep(check_interval)
            waited += check_interval

    def _gpu_memory_info(self) -> tuple[float, float, str, bool, str]:
        if self._windows_gpu_counter_ready:
            try:
                dedicated, shared = self._gpu_memory_gb_windows_process_tree()
                return dedicated, shared, "Windows GPUProcessMemory", True, "当前程序"
            except Exception:
                pass

            try:
                dedicated, shared = self._gpu_memory_gb_windows()
                return dedicated, shared, "Windows GPUAdapterMemory", True, "整机"
            except Exception:
                pass

        if self._nvml_ready:
            try:
                dedicated = 0.0
                device_count = pynvml.nvmlDeviceGetCount()
                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    dedicated += info.used / (1024 ** 3)
                return dedicated, 0.0, "NVML", True, "整机"
            except Exception:
                pass

        return 0.0, 0.0, "未检测到", False, "未知"


    def _probe_windows_gpu_counter(self) -> bool:
        try:
            dedicated, shared = self._gpu_memory_gb_windows()
            return dedicated >= 0.0 and shared >= 0.0
        except Exception:
            return False

    def _gpu_memory_gb_windows(self) -> tuple[float, float]:
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance -ClassName Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory | Select-Object Name,DedicatedUsage,SharedUsage | ConvertTo-Json -Compress",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        raw = (proc.stdout or "").strip()

        if proc.returncode != 0 or not raw:
            raise RuntimeError("Windows GPU 计数器不可用")

        data = json.loads(raw)
        rows = data if isinstance(data, list) else [data]
        dedicated = 0.0
        shared = 0.0
        for row in rows:
            if not isinstance(row, dict):
                continue
            dedicated += float(row.get("DedicatedUsage") or 0.0)
            shared += float(row.get("SharedUsage") or 0.0)
        return dedicated / (1024 ** 3), shared / (1024 ** 3)

    def _gpu_memory_gb_windows_process_tree(self) -> tuple[float, float]:
        pid_set = {self.proc.pid}
        try:
            for child in self.proc.children(recursive=True):
                pid_set.add(child.pid)
        except Exception:
            pass

        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance -ClassName Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory | Select-Object Name,IDProcess,DedicatedUsage,SharedUsage | ConvertTo-Json -Compress",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=2,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        raw = (proc.stdout or "").strip()
        if proc.returncode != 0 or not raw:
            raise RuntimeError("Windows GPU 进程计数器不可用")


        data = json.loads(raw)
        rows = data if isinstance(data, list) else [data]
        dedicated = 0.0
        shared = 0.0
        matched = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                pid = int(row.get("IDProcess") or 0)
            except Exception:
                pid = 0
            if pid not in pid_set:
                continue
            matched = True
            dedicated += float(row.get("DedicatedUsage") or 0.0)
            shared += float(row.get("SharedUsage") or 0.0)

        if not matched:
            raise RuntimeError("未找到当前程序的 GPU 进程计数器")
        return dedicated / (1024 ** 3), shared / (1024 ** 3)


