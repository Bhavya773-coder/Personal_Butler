"""
JARVIS Core — System Info Tools

Get CPU, RAM, disk, and general system information.
"""

import psutil
import platform
from datetime import datetime


def get_cpu_usage() -> dict:
    """Get current CPU usage percentage."""
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "cpu_count": psutil.cpu_count(),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_freq": {
            "current": psutil.cpu_freq().current if psutil.cpu_freq() else None,
            "max": psutil.cpu_freq().max if psutil.cpu_freq() else None,
        },
    }


def get_ram_usage() -> dict:
    """Get current RAM usage."""
    mem = psutil.virtual_memory()
    return {
        "total_gb": round(mem.total / (1024**3), 2),
        "used_gb": round(mem.used / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2),
        "percent": mem.percent,
    }


def get_disk_usage() -> dict:
    """Get disk usage for all partitions."""
    partitions = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            partitions.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent": usage.percent,
            })
        except PermissionError:
            continue
    return {"partitions": partitions}


def get_system_info() -> dict:
    """Get comprehensive system information."""
    cpu = get_cpu_usage()
    ram = get_ram_usage()
    disk = get_disk_usage()

    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time

    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "hostname": platform.node(),
        "uptime_hours": round(uptime.total_seconds() / 3600, 2),
        "cpu": cpu,
        "ram": ram,
        "disk": disk,
    }


def get_summary() -> str:
    """Get a human-readable system summary."""
    cpu = get_cpu_usage()
    ram = get_ram_usage()

    return (
        f"CPU: {cpu['cpu_percent']}% usage ({cpu['cpu_count_logical']} cores). "
        f"RAM: {ram['used_gb']}GB / {ram['total_gb']}GB ({ram['percent']}% used). "
        f"Available: {ram['available_gb']}GB."
    )
