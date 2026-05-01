"""System information collector for macOS.

Gathers CPU, memory, disk, battery, network, and process data
using only stdlib subprocess calls (no psutil dependency).
"""

import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from . import atomic_write_json

_CACHE_DIR = Path(__file__).parent.parent
_HW_CACHE_FILE = _CACHE_DIR / ".hw_cache.json"
_NET_SPEED_CACHE_FILE = _CACHE_DIR / ".net_speed_cache.json"
_NET_SPEED_CACHE_TTL = 30 * 60  # 30 minutes


def _run(cmd, timeout=10):
    """Run a shell command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _get_hardware_info():
    """Get model, chip, and memory from system_profiler (cached to disk)."""
    # Hardware never changes — read from disk cache if available
    try:
        if _HW_CACHE_FILE.exists():
            cached = json.loads(_HW_CACHE_FILE.read_text())
            if cached:
                return cached
    except Exception:
        pass

    raw = _run(["system_profiler", "SPHardwareDataType", "-json"])
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        hw = data["SPHardwareDataType"][0]
        result = {
            "machine_name": hw.get("machine_name", ""),
            "chip": hw.get("chip_type", ""),
            "physical_memory": hw.get("physical_memory", ""),
            "serial_last4": hw.get("serial_number", "")[-4:],
            "model_number": hw.get("model_number", ""),
        }
        atomic_write_json(_HW_CACHE_FILE, result)
        return result
    except (json.JSONDecodeError, KeyError, IndexError):
        return {}


def _get_macos_version():
    """Get macOS product name and version."""
    raw = _run(["sw_vers"])
    info = {}
    for line in raw.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            info[key.strip()] = val.strip()
    name = info.get("ProductName", "macOS")
    ver = info.get("ProductVersion", "")
    return f"{name} {ver}" if ver else name


def _get_hostname():
    """Get the user-facing computer name."""
    name = _run(["scutil", "--get", "ComputerName"])
    return name or os.uname().nodename


def _get_uptime():
    """Calculate uptime from kern.boottime."""
    raw = _run(["sysctl", "-n", "kern.boottime"])
    m = re.search(r"sec\s*=\s*(\d+)", raw)
    if not m:
        return "Unknown"
    boot = int(m.group(1))
    elapsed = int(time.time()) - boot
    days, rem = divmod(elapsed, 86400)
    hours, minutes = divmod(rem, 3600)
    minutes //= 60
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _get_cpu_info():
    """Get CPU core counts and usage."""
    physical = _run(["sysctl", "-n", "hw.physicalcpu"])
    logical = _run(["sysctl", "-n", "hw.logicalcpu"])

    # CPU usage from top (takes ~2s for 2 samples)
    raw = _run(["top", "-l", "2", "-n", "0", "-s", "1"], timeout=15)
    user_pct = sys_pct = idle_pct = 0.0
    for line in raw.splitlines():
        if "CPU usage:" in line:
            # Keep overwriting — we want the 2nd sample
            m = re.findall(r"([\d.]+)%\s+(user|sys|idle)", line)
            for val, label in m:
                if label == "user":
                    user_pct = float(val)
                elif label == "sys":
                    sys_pct = float(val)
                elif label == "idle":
                    idle_pct = float(val)

    return {
        "cores_physical": int(physical) if physical.isdigit() else 0,
        "cores_logical": int(logical) if logical.isdigit() else 0,
        "usage_user": round(user_pct, 1),
        "usage_sys": round(sys_pct, 1),
        "usage_total": round(user_pct + sys_pct, 1),
        "usage_idle": round(idle_pct, 1),
    }


def _get_memory_info():
    """Get memory stats from sysctl, vm_stat, and swap."""
    total_bytes = _run(["sysctl", "-n", "hw.memsize"])
    total_gb = int(total_bytes) / (1024**3) if total_bytes.isdigit() else 0

    # Parse vm_stat for page-level detail
    raw = _run(["vm_stat"])
    pages = {}
    page_size = 16384  # default
    for line in raw.splitlines():
        m = re.match(r".*page size of (\d+) bytes", line)
        if m:
            page_size = int(m.group(1))
        m = re.match(r'(.+?):\s+([\d.]+)', line)
        if m:
            pages[m.group(1).strip().strip('"')] = int(float(m.group(2)))

    active = pages.get("Pages active", 0) * page_size
    wired = pages.get("Pages wired down", 0) * page_size
    compressed = pages.get("Pages occupied by compressor", 0) * page_size
    used_gb = (active + wired + compressed) / (1024**3)
    available_gb = total_gb - used_gb

    # Swap
    swap_raw = _run(["sysctl", "-n", "vm.swapusage"])
    swap_used = 0.0
    m = re.search(r"used\s*=\s*([\d.]+)M", swap_raw)
    if m:
        swap_used = float(m.group(1)) / 1024  # convert to GB

    return {
        "total_gb": round(total_gb, 1),
        "used_gb": round(used_gb, 1),
        "available_gb": round(available_gb, 1),
        "used_pct": round(used_gb / total_gb * 100, 1) if total_gb else 0,
        "swap_used_gb": round(swap_used, 2),
    }


def _get_disk_info():
    """Get disk volume usage from df.

    On modern macOS the boot disk is split into a read-only system
    snapshot (/) and a data volume (/System/Volumes/Data) that share
    one APFS container.  We show the Data volume as "Macintosh HD"
    because it reflects real usage, and skip the tiny system snapshot.
    """
    raw = _run(["df", "-H"])
    volumes = []
    seen_devices = set()

    for line in raw.splitlines()[1:]:  # skip header
        parts = line.split()
        if len(parts) < 9:
            continue
        mount = parts[-1]
        device = parts[0]

        # Skip virtual/pseudo filesystems
        if device in ("devfs", "map"):
            continue
        # Skip misc system volumes (VM, Preboot, Update, xarts, etc.)
        # but keep /System/Volumes/Data — that's the real user data
        if mount.startswith("/System/Volumes") and mount != "/System/Volumes/Data":
            continue
        if mount == "/dev":
            continue

        try:
            total = _parse_size(parts[1])
            used = _parse_size(parts[2])
            avail = _parse_size(parts[3])
            pct = int(parts[4].rstrip("%"))
        except (ValueError, IndexError):
            continue

        # The Data volume and root (/) share the same APFS container.
        # Prefer the Data volume; skip root if we already have it.
        base_device = re.sub(r"s\d+s\d+$", "", device)  # /dev/disk3s5 -> /dev/disk3
        if mount == "/":
            if base_device in seen_devices:
                continue  # already added via Data volume
            name = "Macintosh HD"
        elif mount == "/System/Volumes/Data":
            name = "Macintosh HD"
            seen_devices.add(base_device)
        else:
            name = mount

        volumes.append({
            "mount": mount,
            "name": name,
            "total_gb": round(total, 1),
            "used_gb": round(used, 1),
            "free_gb": round(avail, 1),
            "percent_used": pct,
        })

    # If we added the Data volume, remove any duplicate root entry
    data_mounts = [v for v in volumes if v["mount"] == "/System/Volumes/Data"]
    if data_mounts:
        volumes = [v for v in volumes if v["mount"] != "/"]

    return volumes


def _parse_size(s):
    """Parse df -H size strings like '995G', '12G', '234M' into GB."""
    s = s.strip()
    if s.endswith("T"):
        return float(s[:-1]) * 1024
    elif s.endswith("G"):
        return float(s[:-1])
    elif s.endswith("M"):
        return float(s[:-1]) / 1024
    elif s.endswith("K"):
        return float(s[:-1]) / (1024 * 1024)
    return 0


def _get_battery_info():
    """Get battery status from pmset. Returns None for desktops."""
    raw = _run(["pmset", "-g", "batt"])
    if "InternalBattery" not in raw:
        return None

    info = {"percent": 0, "charging": False, "power_source": "", "time_remaining": ""}

    # Power source
    m = re.search(r"drawing from '(.+?)'", raw)
    if m:
        info["power_source"] = m.group(1)

    # Battery line: -InternalBattery-0 (id=...)  87%; charging; 1:23 remaining
    m = re.search(r"(\d+)%;\s*(\w+)", raw)
    if m:
        info["percent"] = int(m.group(1))
        status = m.group(2)
        info["charging"] = status in ("charging", "charged", "finishing")

    m = re.search(r"(\d+:\d+) remaining", raw)
    if m:
        info["time_remaining"] = m.group(1)

    # Cycle count + condition from system_profiler
    sp_raw = _run(["system_profiler", "SPPowerDataType", "-json"])
    if sp_raw:
        try:
            sp = json.loads(sp_raw)
            for item in sp.get("SPPowerDataType", []):
                health = item.get("sppower_battery_health_info", {})
                info["cycle_count"] = health.get("sppower_battery_cycle_count", "N/A")
                info["condition"] = health.get(
                    "sppower_battery_health", "N/A"
                ).replace("spbattery_health_", "").title()
        except (json.JSONDecodeError, KeyError):
            pass

    return info


def _get_network_info():
    """Get active network interface, IP, Wi-Fi SSID."""
    info = {"interface": "", "type": "", "wifi_ssid": "", "local_ip": "", "mac_address": ""}

    # Try Wi-Fi first
    wifi_raw = _run(["networksetup", "-getairportnetwork", "en0"])
    if "not associated" not in wifi_raw.lower() and "error" not in wifi_raw.lower():
        m = re.search(r"Current Wi-Fi Network:\s*(.+)", wifi_raw)
        if m:
            info["wifi_ssid"] = m.group(1).strip()
            info["type"] = "Wi-Fi"
            info["interface"] = "en0"

    # Parse ifconfig for IP and MAC
    iface = info["interface"] or "en0"
    raw = _run(["ifconfig", iface])
    m = re.search(r"inet\s+([\d.]+)", raw)
    if m:
        info["local_ip"] = m.group(1)
        if not info["interface"]:
            info["interface"] = iface
            info["type"] = "Ethernet"

    m = re.search(r"ether\s+([\da-f:]+)", raw)
    if m:
        info["mac_address"] = m.group(1)

    # If en0 didn't have an IP, try en1
    if not info["local_ip"]:
        raw = _run(["ifconfig", "en1"])
        m = re.search(r"inet\s+([\d.]+)", raw)
        if m:
            info["local_ip"] = m.group(1)
            info["interface"] = "en1"
            info["type"] = "Ethernet"
        m = re.search(r"ether\s+([\da-f:]+)", raw)
        if m:
            info["mac_address"] = m.group(1)

    return info


def _get_top_processes():
    """Get top processes by CPU and memory usage."""
    cpu_procs = []
    mem_procs = []

    # Top by CPU (-r flag)
    # Put comm last so it can safely contain spaces
    raw = _run(["ps", "-eo", "pid,%cpu,%mem,comm", "-r"])
    for line in raw.splitlines()[1:9]:  # skip header, top 8
        parts = line.split(None, 3)  # split into 4 parts max
        if len(parts) >= 4:
            pid, cpu, mem = parts[0], parts[1], parts[2]
            name = os.path.basename(parts[3])
            cpu_procs.append({"pid": pid, "name": name, "cpu": cpu, "mem": mem})

    # Top by memory (-m flag)
    raw = _run(["ps", "-eo", "pid,%cpu,%mem,comm", "-m"])
    for line in raw.splitlines()[1:9]:
        parts = line.split(None, 3)
        if len(parts) >= 4:
            pid, cpu, mem = parts[0], parts[1], parts[2]
            name = os.path.basename(parts[3])
            mem_procs.append({"pid": pid, "name": name, "cpu": cpu, "mem": mem})

    return cpu_procs, mem_procs


def _get_network_speed():
    """Run macOS networkQuality tool and return speed results.

    Results are cached for 30 minutes to avoid the ~15-25 second cost
    on every refresh.  Returns None if unavailable.
    """
    # Check disk cache first
    try:
        if _NET_SPEED_CACHE_FILE.exists():
            cached = json.loads(_NET_SPEED_CACHE_FILE.read_text())
            if time.time() - cached.get("ts", 0) < _NET_SPEED_CACHE_TTL:
                return cached["data"]
    except Exception:
        pass

    raw = _run(["networkQuality", "-c"], timeout=45)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        dl = data.get("dl_throughput", 0)
        ul = data.get("ul_throughput", 0)
        rtt = data.get("base_rtt", 0)

        # Convert bps to human-readable
        def _fmt_speed(bps):
            mbps = bps / 1_000_000
            if mbps >= 1000:
                return f"{mbps / 1000:.1f} Gbps"
            return f"{mbps:.0f} Mbps"

        result = {
            "download": _fmt_speed(dl),
            "upload": _fmt_speed(ul),
            "latency_ms": round(rtt, 1),
            "dl_mbps": round(dl / 1_000_000, 1),
            "ul_mbps": round(ul / 1_000_000, 1),
        }
        atomic_write_json(_NET_SPEED_CACHE_FILE, {"ts": time.time(), "data": result})
        return result
    except (json.JSONDecodeError, KeyError):
        return None


def _get_listening_ports():
    """Get TCP listening ports from lsof."""
    raw = _run(["lsof", "-iTCP", "-sTCP:LISTEN", "-nP"])
    ports = []
    seen = set()

    for line in raw.splitlines()[1:]:  # skip header
        parts = line.split()
        if len(parts) < 9:
            continue
        process = parts[0]
        pid = parts[1]
        name_col = parts[8]  # e.g. *:8080 or 127.0.0.1:49655

        m = re.search(r":(\d+)$", name_col)
        if not m:
            continue
        port = m.group(1)

        key = f"{port}:{process}"
        if key in seen:
            continue
        seen.add(key)

        ports.append({"port": port, "process": process, "pid": pid})

    # Sort by port number
    ports.sort(key=lambda p: int(p["port"]))
    return ports[:20]  # limit


def get_system_info():
    """Collect macOS system information. Returns a dict."""
    hw = _get_hardware_info()

    cpu_procs, mem_procs = _get_top_processes()

    return {
        "hostname": _get_hostname(),
        "macos_version": _get_macos_version(),
        "model": hw.get("machine_name", "Unknown"),
        "chip": hw.get("chip", "Unknown"),
        "memory_label": hw.get("physical_memory", ""),
        "serial_last4": hw.get("serial_last4", ""),
        "uptime": _get_uptime(),
        "cpu": _get_cpu_info(),
        "memory": _get_memory_info(),
        "disk": _get_disk_info(),
        "battery": _get_battery_info(),
        "network": _get_network_info(),
        "top_processes_cpu": cpu_procs,
        "top_processes_mem": mem_procs,
        "listening_ports": _get_listening_ports(),
        "generated_at": datetime.now().strftime("%I:%M %p"),
    }


def get_network_speed():
    """Public wrapper for network speed test (runs separately in thread pool)."""
    return _get_network_speed()
