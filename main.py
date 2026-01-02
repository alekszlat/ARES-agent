import datetime as _dt
import shutil
import subprocess
import psutil

CPU_HINTS = ("package", "tctl", "tdie", "cpu", "core")
GPU_QUERY = "name,utilization.gpu,temperature.gpu,memory.total,memory.used,memory.free"

def get_cpu_temp_c() -> float | None:
    """Best-effort CPU temperature in °C, or None if unavailable."""
    temps = psutil.sensors_temperatures(fahrenheit=False)
    if not temps:
        return None

    fallback: float | None = None

    for sensor_name, entries in temps.items():
        sname = (sensor_name or "").lower()
        for e in entries:
            cur = getattr(e, "current", None)
            if cur is None:
                continue

            label = (getattr(e, "label", "") or "").lower()
            cpuish = any(h in label for h in CPU_HINTS) or any(h in sname for h in CPU_HINTS)

            # Prefer CPU-ish readings immediately
            if cpuish and 0 < cur < 130:
                return float(cur)

            # Keep a reasonable fallback (in case nothing matches CPU hints)
            if fallback is None and 0 < cur < 130:
                fallback = float(cur)

    return fallback


def get_nvidia_gpus(timeout_s: int = 2) -> tuple[list[dict], str | None]:
    """
    Returns (gpus, error). gpus is a list of dicts; empty list if unavailable.
    """
    if shutil.which("nvidia-smi") is None:
        return [], "nvidia-smi not found"

    cmd = [
        "nvidia-smi",
        f"--query-gpu={GPU_QUERY}",
        "--format=csv,noheader,nounits",
    ]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except Exception as e:
        return [], f"nvidia-smi failed to run: {e}"

    if r.returncode != 0:
        err = (r.stderr or "").strip() or "unknown nvidia-smi error"
        return [], f"nvidia-smi returned {r.returncode}: {err}"

    gpus: list[dict] = []
    for line in (r.stdout or "").strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 6:
            continue

        name, util, temp, mem_total, mem_used, mem_free = parts

        def to_float(x: str) -> float | None:
            try:
                return float(x)
            except Exception:
                return None

        gpus.append(
            {
                "name": name,
                "utilization_percent": to_float(util),
                "temperature_c": to_float(temp),
                "memory_total_mb": to_float(mem_total),
                "memory_used_mb": to_float(mem_used),
                "memory_free_mb": to_float(mem_free),
            }
        )

    return gpus, None

def get_system_info(timeout: int = 2) -> dict:
    """
    Return a structured snapshot of CPU/memory/disk + best-effort NVIDIA GPU stats.
    Never crashes just because a metric is missing.
    """
    errors: list[str] = []

    # CPU
    cpu_usage = psutil.cpu_percent(interval=0.2)  # small delay for a meaningful reading
    cpu_temp = get_cpu_temp_c()
    if cpu_temp is None:
        errors.append("cpu_temp_unavailable")

    # Memory
    mem = psutil.virtual_memory()

    # Disk (root partition as a simple default)
    disk = psutil.disk_usage("/")

    # GPU (NVIDIA only, behind detection)
    gpus, gpu_err = get_nvidia_gpus(timeout_s=timeout)
    if gpu_err:
        errors.append(f"gpu_unavailable: {gpu_err}")

    return {
        "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
        "cpu": {
            "usage_percent": cpu_usage,
            "temperature_c": cpu_temp,
        },
        "memory": {
            "total_gb": mem.total / (1024**3),
            "used_gb": mem.used / (1024**3),
            "available_gb": mem.available / (1024**3),
            "used_percent": mem.percent,
        },
        "disk": {
            "mount": "/",
            "total_gb": disk.total / (1024**3),
            "used_gb": disk.used / (1024**3),
            "free_gb": disk.free / (1024**3),
            "used_percent": disk.percent,
        },
        "gpu": {
            "backend": "nvidia-smi",
            "gpus": gpus,  # 0/1/many
        },
        "errors": errors,  # optional, but super useful for debugging + “best effort”
    }

if __name__ == "__main__":
    info = get_system_info()
    import pprint

    pprint.pprint(info)