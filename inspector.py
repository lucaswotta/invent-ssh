"""Distribution-agnostic, read-only Linux hardware discovery over SSH.

Primary data sources are Linux system interfaces and common utilities. Optional
privileged tools enrich the result when available, but are never required for a
successful connection. Parser functions are pure and covered by local fixtures.
"""
from __future__ import annotations

import json
import re
import shlex
import socket
import threading
import time
from pathlib import Path
from typing import Any, Optional

import paramiko

from i18n import t
from paths import get_known_hosts_path

_KNOWN_HOSTS_LOCK = threading.Lock()


def _clean_string(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _available(value: Any) -> bool:
    normalized = _clean_string(value).casefold()
    if not normalized or normalized in {"n/a", "na", "none", "unknown", "not available", "not specified", "not set"}:
        return False
    return not any(token in normalized for token in (
        "default string", "to be filled by o.e.m", "to be filled by oem",
        "system serial number", "not applicable",
    ))


def _run_command(
    client: paramiko.SSHClient,
    command: str,
    tolerant: bool = False,
    timeout: int = 12,
    max_output_bytes: int = 8_000_000,
) -> Optional[str]:
    """Run one bounded SSH command without deadlocks or truncated pipe reads."""
    channel = None
    try:
        _stdin, stdout, _stderr = client.exec_command(command, timeout=timeout)
        channel = stdout.channel
        channel.settimeout(min(float(timeout), 1.0))
        output = bytearray()
        errors = bytearray()
        deadline = time.monotonic() + timeout

        while True:
            while channel.recv_ready():
                chunk = channel.recv(32768)
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > max_output_bytes:
                    channel.close()
                    return None

            while channel.recv_stderr_ready():
                chunk = channel.recv_stderr(8192)
                if not chunk:
                    break
                # Stderr is drained to avoid blocking the remote process, but is
                # deliberately not returned: diagnostics may contain paths/identifiers.
                if len(errors) < 65536:
                    errors.extend(chunk[:65536 - len(errors)])

            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                break
            if time.monotonic() >= deadline:
                channel.close()
                return None
            time.sleep(0.01)

        exit_code = channel.recv_exit_status()
        result = output.decode("utf-8", errors="replace").strip()
        if exit_code == 0 or (tolerant and result):
            return result or None
        return None
    except (OSError, EOFError, socket.timeout, TimeoutError, paramiko.SSHException):
        if channel is not None:
            channel.close()
        return None


def _parse_os_release(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        match = re.match(r"^\s*([A-Z0-9_]+)=(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _parse_lscpu(output: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        parsed[_clean_string(label).casefold()] = _clean_string(value)
    return parsed


def _parse_meminfo(output: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in output.splitlines():
        match = re.match(r"^\s*([A-Za-z_()]+):\s*(\d+)\s*(kB|KB|B)?", line)
        if not match:
            continue
        name, amount, unit = match.groups()
        value = int(amount)
        if unit and unit.casefold() == "kb":
            value *= 1024
        result[name] = value
    return result


def _parse_memory_devices(output: str) -> dict[str, str]:
    blocks = re.split(r"(?m)^\s*Memory Device\s*$", output)
    installed: list[dict[str, Any]] = []
    for block in blocks[1:]:
        size_match = re.search(r"(?m)^\s*Size:\s*(.+?)\s*$", block)
        if not size_match:
            continue
        size_text = _clean_string(size_match.group(1))
        if size_text.casefold() in {"no module installed", "not installed", "unknown", "not specified"}:
            continue
        number = re.match(r"^([\d.]+)\s*(KB|MB|GB|TB)\b", size_text, re.I)
        if not number:
            continue
        amount, unit = float(number.group(1)), number.group(2).upper()
        size_bytes = amount * {"KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4}[unit]
        type_match = re.search(r"(?m)^\s*Type:\s*(.+?)\s*$", block)
        speed_match = re.search(r"(?m)^\s*(?:Configured Memory Speed|Speed):\s*(\d+)\s*(?:MT/s|MHz)", block)
        installed.append({
            "bytes": int(size_bytes),
            "type": _clean_string(type_match.group(1)) if type_match else "",
            "speed": int(speed_match.group(1)) if speed_match else 0,
        })

    types = []
    for module in installed:
        match = re.search(r"\bDDR[2-5]\b|\bDDR\b", module["type"], re.I)
        if match:
            label = match.group(0).upper()
            if label not in types:
                types.append(label)
    speeds = sorted({module["speed"] for module in installed if module["speed"] > 0})
    total = sum(module["bytes"] for module in installed)
    return {
        "ram_type": " / ".join(types) if types else "N/A",
        "ram_speed": f"{min(speeds)} MT/s" if len(speeds) == 1 else " / ".join(f"{speed} MT/s" for speed in speeds) if speeds else "N/A",
        "ram_slots": f"{len(installed)} populated" if installed else "N/A",
        "ram_module_total_bytes": str(total) if total else "0",
    }


def _format_capacity(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "N/A"
    if size_bytes >= 1000**4:
        value = f"{size_bytes / (1000**4):.2f}".rstrip("0").rstrip(".")
        return f"{value} TB"
    return f"{size_bytes / (1000**3):.0f} GB"


def _parse_lsblk(output: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        # Older util-linux can lack JSON output. lsblk -P emits safely quoted
        # key/value records, which shlex can parse without guessing field order.
        devices = []
        for line in str(output or "").splitlines():
            try:
                fields = {}
                for token in shlex.split(line):
                    if "=" in token:
                        key, value = token.split("=", 1)
                        fields[key.casefold()] = value
                if fields:
                    devices.append(fields)
            except ValueError:
                continue
        if not devices:
            return []
        data = {"blockdevices": devices}
    devices = data.get("blockdevices", []) if isinstance(data, dict) else []
    parsed: list[dict[str, Any]] = []
    for device in devices if isinstance(devices, list) else []:
        if not isinstance(device, dict) or str(device.get("type", "")).casefold() != "disk":
            continue
        name = _clean_string(device.get("name"))
        if not name or name.casefold().startswith(("loop", "ram", "zram")):
            continue
        try:
            size = int(device.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        if size <= 0:
            continue
        rota = str(device.get("rota", "")).strip().casefold()
        transport = _clean_string(device.get("tran")).casefold()
        if name.casefold().startswith("nvme") or transport == "nvme":
            kind = "NVMe"
        elif rota in {"1", "true", "yes"}:
            kind = "HDD"
        elif rota in {"0", "false", "no"}:
            # The kernel reports a non-rotating device; this does not prove a
            # physical SATA/NVMe SSD (USB flash and virtual disks also qualify).
            kind = "SSD / flash"
        else:
            kind = "Unknown"
        model = _clean_string(device.get("model"))
        raw_mountpoints = device.get("mountpoints", device.get("mountpoint", []))
        if isinstance(raw_mountpoints, str):
            mountpoints = [raw_mountpoints] if raw_mountpoints else []
        elif isinstance(raw_mountpoints, list):
            mountpoints = [str(value) for value in raw_mountpoints if value]
        else:
            mountpoints = []
        partitions = []
        for child in device.get("children", []) or []:
            if not isinstance(child, dict):
                continue
            child_name = _clean_string(child.get("name"))
            child_size = child.get("size")
            try:
                child_size = int(child_size or 0)
            except (TypeError, ValueError):
                child_size = 0
            child_mount = child.get("mountpoints", child.get("mountpoint", []))
            if isinstance(child_mount, str):
                child_mountpoints = [child_mount] if child_mount else []
            elif isinstance(child_mount, list):
                child_mountpoints = [str(value) for value in child_mount if value]
            else:
                child_mountpoints = []
            fstype = _clean_string(child.get("fstype")) or "filesystem unknown"
            if child_name:
                partitions.append({
                    "name": child_name,
                    "capacity": _format_capacity(child_size),
                    "filesystem": fstype,
                    "mountpoints": child_mountpoints,
                })
        parsed.append({
            "name": name,
            "kind": kind,
            "classification_basis": "NVMe transport/name" if kind == "NVMe" else "kernel rotational flag" if kind in {"HDD", "SSD / flash"} else "unavailable",
            "size_bytes": size,
            "capacity": _format_capacity(size),
            "model": model or "N/A",
            "transport": transport.upper() if transport else "N/A",
            "removable": str(device.get("rm", "0")).strip().casefold() in {"1", "true", "yes"},
            "filesystem": _clean_string(device.get("fstype")) or "N/A",
            "mountpoints": mountpoints,
            "partitions": partitions,
        })
    return parsed


def _parse_network_interfaces(output: str) -> list[str]:
    adapters: list[str] = []
    for line in output.splitlines():
        match = re.match(r"^\s*\d+:\s+([^:]+):.*?(?:\bstate\s+([A-Z]+))?", line, re.I)
        if not match:
            continue
        name = match.group(1).split("@", 1)[0].strip()
        if not name or name == "lo":
            continue
        state = (match.group(2) or "").upper()
        if not state:
            flags = re.search(r"<([^>]+)>", line)
            state = "UP" if flags and "UP" in flags.group(1).split(",") else "DOWN"
        item = f"{name} ({state.lower()})"
        if item not in adapters:
            adapters.append(item)
    return adapters


def _parse_gpus(output: str) -> list[str]:
    devices: list[str] = []
    pattern = re.compile(r"^(?:[0-9a-fA-F:.]+\s+)?(?:VGA compatible controller|3D controller|Display controller)(?:\s+\[[0-9a-fA-F]{4}\])?:\s*(.+)$", re.I)
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if match:
            device = _clean_string(match.group(1))
            if device and device not in devices:
                devices.append(device)
    return devices


def _format_uptime(output: str) -> str:
    try:
        total_seconds = max(0, int(float(output.strip().split()[0])))
    except (ValueError, IndexError, AttributeError):
        return "N/A"
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _format_gib(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "N/A"
    return f"{size_bytes / (1024**3):.1f} GiB"


_PROBE_SCRIPT = r"""
LC_ALL=C
export LC_ALL
printf '%s\n' '__INVENT_SSH_BEGIN_os_release__'
if [ -r /etc/os-release ]; then
  cat /etc/os-release
elif [ -r /etc/lsb-release ]; then
  cat /etc/lsb-release
elif [ -r /etc/redhat-release ]; then
  cat /etc/redhat-release
elif [ -r /etc/debian_version ]; then
  printf 'Debian GNU/Linux '
  cat /etc/debian_version
fi
printf '%s\n' '__INVENT_SSH_END_os_release__'

printf '%s\n' '__INVENT_SSH_BEGIN_hostname__'
hostname 2>/dev/null || uname -n 2>/dev/null || true
printf '%s\n' '__INVENT_SSH_END_hostname__'

printf '%s\n' '__INVENT_SSH_BEGIN_kernel__'
uname -r 2>/dev/null || true
printf '%s\n' '__INVENT_SSH_END_kernel__'

printf '%s\n' '__INVENT_SSH_BEGIN_architecture__'
uname -m 2>/dev/null || true
printf '%s\n' '__INVENT_SSH_END_architecture__'

printf '%s\n' '__INVENT_SSH_BEGIN_lscpu__'
if command -v lscpu >/dev/null 2>&1; then lscpu 2>/dev/null || true; fi
printf '%s\n' '__INVENT_SSH_END_lscpu__'

printf '%s\n' '__INVENT_SSH_BEGIN_cpuinfo__'
awk -F: '
/^[[:space:]]*(model name|Hardware|Processor)[[:space:]]*:/ {
  key=$1
  gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
  value=substr($0, index($0, ":")+1)
  gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
  if (key == "model name" && model == "") model=value
  else if (key == "Hardware" && hardware == "") hardware=value
  else if (key == "Processor" && processor == "") processor=value
}
/^[[:space:]]*processor[[:space:]]*:/ { logical++ }
/^[[:space:]]*(flags|Features)[[:space:]]*:/ {
  if ($0 ~ /(^|[[:space:]])vmx([[:space:]]|$)/) vmx=1
  if ($0 ~ /(^|[[:space:]])svm([[:space:]]|$)/) svm=1
}
END {
  if (model != "") print "Model name: " model
  else if (hardware != "") print "Hardware: " hardware
  else if (processor != "") print "Processor: " processor
  printf "CPU(s): %d\n", logical
  if (vmx) print "Virtualization: VT-x"
  else if (svm) print "Virtualization: AMD-V"
}' /proc/cpuinfo 2>/dev/null
printf '%s\n' '__INVENT_SSH_END_cpuinfo__'

printf '%s\n' '__INVENT_SSH_BEGIN_meminfo__'
cat /proc/meminfo 2>/dev/null || true
printf '%s\n' '__INVENT_SSH_END_meminfo__'

printf '%s\n' '__INVENT_SSH_BEGIN_memory_devices__'
if command -v dmidecode >/dev/null 2>&1; then dmidecode -t memory 2>/dev/null || true; fi
printf '%s\n' '__INVENT_SSH_END_memory_devices__'

printf '%s\n' '__INVENT_SSH_BEGIN_lsblk__'
if command -v lsblk >/dev/null 2>&1; then
  lsblk -J -b -o NAME,TYPE,SIZE,ROTA,MODEL,TRAN,RM,FSTYPE,MOUNTPOINTS 2>/dev/null ||
    lsblk -J -b -o NAME,TYPE,SIZE,ROTA,MODEL,TRAN,RM,FSTYPE,MOUNTPOINT 2>/dev/null ||
    lsblk -dn -b -P -o NAME,TYPE,SIZE,ROTA,MODEL,TRAN,RM 2>/dev/null ||
    true
fi
printf '%s\n' '__INVENT_SSH_END_lsblk__'

printf '%s\n' '__INVENT_SSH_BEGIN_dmi__'
for n in __DMI_FIELDS__; do
  printf '__DMI__%s=' "$n"
  if [ -r "/sys/class/dmi/id/$n" ]; then
    cat "/sys/class/dmi/id/$n" 2>/dev/null
  elif [ -r "/sys/devices/virtual/dmi/id/$n" ]; then
    cat "/sys/devices/virtual/dmi/id/$n" 2>/dev/null
  else
    printf '\n'
  fi
done
printf '%s\n' '__INVENT_SSH_END_dmi__'

printf '%s\n' '__INVENT_SSH_BEGIN_lspci__'
if command -v lspci >/dev/null 2>&1; then lspci -nn 2>/dev/null || lspci 2>/dev/null || true; fi
printf '%s\n' '__INVENT_SSH_END_lspci__'

printf '%s\n' '__INVENT_SSH_BEGIN_drm__'
for f in /sys/class/drm/card[0-9]*/device/uevent; do
  if [ -r "$f" ]; then cat "$f" 2>/dev/null || true; fi
done
printf '%s\n' '__INVENT_SSH_END_drm__'

printf '%s\n' '__INVENT_SSH_BEGIN_netlink__'
if command -v ip >/dev/null 2>&1; then ip -o link show 2>/dev/null || true; fi
printf '%s\n' '__INVENT_SSH_END_netlink__'

printf '%s\n' '__INVENT_SSH_BEGIN_netdetails__'
for p in /sys/class/net/*; do
  [ -e "$p" ] || continue
  name=$(basename "$p" 2>/dev/null)
  [ "$name" = "lo" ] && continue
  state=$(cat "$p/operstate" 2>/dev/null || true)
  [ -n "$state" ] || state="unknown"
  speed=$(cat "$p/speed" 2>/dev/null || true)
  case "$speed" in *[!0-9]*|'') speed="";; esac
  driver_path=$(readlink -f "$p/device/driver" 2>/dev/null || true)
  driver=""
  if [ -n "$driver_path" ]; then driver=$(basename "$driver_path" 2>/dev/null); fi
  [ "$driver" = "." ] && driver=""
  printf '%s|%s|%s|%s\n' "$name" "$state" "$speed" "$driver"
done
printf '%s\n' '__INVENT_SSH_END_netdetails__'

printf '%s\n' '__INVENT_SSH_BEGIN_uptime__'
cat /proc/uptime 2>/dev/null || true
printf '%s\n' '__INVENT_SSH_END_uptime__'

printf '%s\n' '__INVENT_SSH_BEGIN_virtualization__'
if command -v systemd-detect-virt >/dev/null 2>&1; then
  systemd-detect-virt 2>/dev/null || true
elif command -v virt-what >/dev/null 2>&1; then
  virt-what 2>/dev/null || true
fi
printf '%s\n' '__INVENT_SSH_END_virtualization__'
"""


def _build_probe_command(include_sensitive_identifiers: bool = False) -> str:
    """Build a fixed, read-only POSIX-shell probe; no target data is interpolated."""
    fields = (
        "sys_vendor product_name product_version board_vendor board_name "
        "bios_vendor bios_version bios_date"
    )
    if include_sensitive_identifiers:
        fields += " product_serial"
    return _PROBE_SCRIPT.replace("__DMI_FIELDS__", fields)


def _parse_probe_sections(output: str) -> dict[str, str]:
    """Parse named probe sections; section order is irrelevant."""
    sections: dict[str, str] = {}
    current: Optional[str] = None
    chunks: list[str] = []
    for line in output.splitlines():
        begin = re.fullmatch(r"__INVENT_SSH_BEGIN_([a-z_]+)__", line.strip())
        end = re.fullmatch(r"__INVENT_SSH_END_([a-z_]+)__", line.strip())
        if begin:
            current = begin.group(1)
            chunks = []
        elif end:
            if current == end.group(1):
                sections[current] = "\n".join(chunks).strip()
            current = None
            chunks = []
        elif current:
            chunks.append(line)
    return sections


def _parse_dmi_section(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        if not line.startswith("__DMI__") or "=" not in line:
            continue
        key, value = line[len("__DMI__"):].split("=", 1)
        value = _clean_string(value)
        if _available(value):
            values[key] = value
    return values


def _parse_network_details(output: str) -> list[dict[str, str]]:
    adapters: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        name, state, speed, driver = (_clean_string(value) for value in parts)
        if not name or name == "lo":
            continue
        if state.casefold() in {"", "unknown", "notpresent", "not present"}:
            state = "unknown"
        adapter = {"name": name, "state": state, "speed_mbps": "", "driver": driver or "N/A"}
        if speed.isdigit() and int(speed) > 0:
            adapter["speed_mbps"] = speed
        adapters.append(adapter)
    return adapters


def _count_cpu_list(value: str) -> int:
    """Count Linux CPU-list syntax such as 0-3,8,10-11 without guessing."""
    value = _clean_string(value)
    if not value:
        return 0
    total = 0
    try:
        for item in value.split(","):
            item = item.strip()
            if not item:
                return 0
            if "-" in item:
                first, last = item.split("-", 1)
                low, high = int(first), int(last)
                if low < 0 or high < low:
                    return 0
                total += high - low + 1
            else:
                total += int(item)
    except ValueError:
        return 0
    return total

def _collect_linux_hardware(
    client: paramiko.SSHClient,
    include_sensitive_identifiers: bool = False,
    timeout: int = 30,
) -> dict[str, Any]:
    """Collect a normalized Linux hardware snapshot with one SSH round trip.

    The probe is read-only and uses standard OS interfaces first. Optional tools
    enrich the snapshot but do not define whether an endpoint is reachable.
    """
    raw_output = _run_command(
        client,
        _build_probe_command(include_sensitive_identifiers),
        timeout=max(5, timeout),
    ) or ""
    sections = _parse_probe_sections(raw_output)

    os_text = sections.get("os_release", "")
    os_release = _parse_os_release(os_text)
    distro = (
        os_release.get("PRETTY_NAME")
        or os_release.get("DISTRIB_DESCRIPTION")
        or os_release.get("NAME")
        or os_release.get("DISTRIB_ID")
        or ""
    )
    if not distro:
        first_line = next((line.strip() for line in os_text.splitlines() if line.strip()), "")
        distro = first_line if first_line and "=" not in first_line else "N/A"
    if os_release.get("VERSION_ID") and distro == os_release.get("NAME"):
        distro = f"{distro} {os_release['VERSION_ID']}"
    distro = _clean_string(distro) or "N/A"

    hostname = _clean_string(sections.get("hostname", "")) or "N/A"
    kernel = _clean_string(sections.get("kernel", "")) or "N/A"
    architecture = _clean_string(sections.get("architecture", "")) or "N/A"

    lscpu_text = sections.get("lscpu", "")
    cpuinfo_text = sections.get("cpuinfo", "")
    cpu = _parse_lscpu(lscpu_text)
    cpu_fallback = _parse_lscpu(cpuinfo_text)

    cpu_model = (
        cpu.get("model name")
        or cpu.get("model")
        or cpu.get("hardware")
        or cpu.get("processor")
        or cpu_fallback.get("model name")
        or cpu_fallback.get("hardware")
        or cpu_fallback.get("processor")
        or "N/A"
    )
    if not _available(cpu_model):
        cpu_model = "N/A"

    logical_threads = 0
    for key in ("cpu(s)", "on-line cpu(s)"):
        value = cpu.get(key, "")
        if value.isdigit() and int(value) > 0:
            logical_threads = int(value)
            break
    if not logical_threads:
        logical_threads = _count_cpu_list(cpu.get("on-line cpu(s) list", ""))
    if not logical_threads:
        fallback_threads = cpu_fallback.get("cpu(s)", "")
        if fallback_threads.isdigit():
            logical_threads = int(fallback_threads)

    sockets = 0
    if cpu.get("socket(s)", "").isdigit():
        sockets = int(cpu["socket(s)"])
    cores_per_socket = 0
    if cpu.get("core(s) per socket", "").isdigit():
        cores_per_socket = int(cpu["core(s) per socket"])
    physical_cores = sockets * cores_per_socket if sockets and cores_per_socket else 0
    if not physical_cores and cpu.get("core(s)", "").isdigit():
        physical_cores = int(cpu["core(s)"])
    if not physical_cores and cpu_fallback.get("core(s)", "").isdigit():
        physical_cores = int(cpu_fallback["core(s)"])
    # Do not pretend every logical CPU is a distinct physical core. Hyperthreading,
    # containers, CPU affinity, and architecture make that inference incorrect.
    if physical_cores and logical_threads:
        cores_threads = f"{physical_cores}/{logical_threads}"
    elif physical_cores:
        cores_threads = f"{physical_cores}/N/A"
    elif logical_threads:
        cores_threads = f"N/A/{logical_threads}"
    else:
        cores_threads = "N/A"

    frequency = cpu.get("cpu max mhz") or cpu.get("cpu mhz") or "N/A"
    if _available(frequency) and frequency != "N/A":
        try:
            mhz = float(frequency.replace(",", ".").split()[0])
            frequency = f"{mhz / 1000:.2f} GHz" if mhz >= 1000 else f"{mhz:.0f} MHz"
        except (ValueError, IndexError):
            frequency = "N/A"
    virtualization_extension = cpu.get("virtualization") or cpu_fallback.get("virtualization") or "N/A"
    sockets_label = str(sockets) if sockets else "N/A"
    cpu_vendor = cpu.get("vendor id") or cpu_fallback.get("vendor id") or "N/A"
    cpu_family = cpu.get("cpu family") or cpu_fallback.get("cpu family") or "N/A"
    cpu_model_number = cpu.get("model") if cpu.get("model", "").isdigit() else "N/A"
    cpu_stepping = cpu.get("stepping") or cpu_fallback.get("stepping") or "N/A"

    meminfo_text = sections.get("meminfo", "")
    meminfo = _parse_meminfo(meminfo_text)
    total_bytes = meminfo.get("MemTotal", 0)
    available_bytes = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
    available_bytes = min(total_bytes, max(0, available_bytes)) if total_bytes else 0
    used_bytes = max(0, total_bytes - available_bytes)
    memory_devices_text = sections.get("memory_devices", "")
    memory_devices = _parse_memory_devices(memory_devices_text)
    ram_type = memory_devices.get("ram_type", "N/A")
    ram = (
        f"{total_bytes / (1024**3):.1f} GiB"
        + (f" {ram_type}" if _available(ram_type) else "")
        if total_bytes else "N/A"
    )

    lsblk_text = sections.get("lsblk", "")
    drives = _parse_lsblk(lsblk_text)
    drive_types = list(dict.fromkeys(
        drive["kind"] for drive in drives if drive["kind"] != "Unknown"
    ))
    disk_type = " + ".join(drive_types) if drive_types else "N/A"
    drive_total = sum(drive["size_bytes"] for drive in drives)
    disk_size = (
        f"{_format_capacity(drive_total)} total ({len(drives)} physical block devices)"
        if drives else "N/A"
    )
    drive_lines: list[str] = []
    for drive in drives:
        line = (
            f"{drive['name']} · {drive['kind']} · {drive['capacity']} · "
            f"{drive['model']} · transport {drive['transport']}"
        )
        if drive["mountpoints"]:
            line += " · mounted at " + ", ".join(drive["mountpoints"])
        if drive["partitions"]:
            partitions = []
            for partition in drive["partitions"]:
                part = f"{partition['name']} · {partition['capacity']} · {partition['filesystem']}"
                if partition["mountpoints"]:
                    part += " · " + ", ".join(partition["mountpoints"])
                partitions.append(part)
            line += "\n  Partitions: " + " | ".join(partitions)
        drive_lines.append(line)

    dmi = _parse_dmi_section(sections.get("dmi", ""))
    manufacturer = dmi.get("sys_vendor", "N/A")
    model = dmi.get("product_name", "N/A")
    board_vendor = dmi.get("board_vendor", "")
    board_model = dmi.get("board_name", "")
    motherboard = " — ".join(
        value for value in (board_vendor, board_model) if _available(value)
    ) or "N/A"
    bios = " · ".join(
        _clean_string(dmi.get(key, ""))
        for key in ("bios_vendor", "bios_version", "bios_date")
        if _available(dmi.get(key))
    ) or "N/A"
    system_serial = dmi.get("product_serial", "N/A") if include_sensitive_identifiers else "Not collected (opt-in)"

    gpus = _parse_gpus(sections.get("lspci", ""))
    if not gpus:
        vendor_ids = re.findall(r"(?m)^PCI_ID=(.+)$", sections.get("drm", ""))
        gpus = [f"PCI device {value}" for value in dict.fromkeys(vendor_ids)]

    net_details = _parse_network_details(sections.get("netdetails", ""))
    if not net_details:
        net_details = [
            {"name": item.split(" (", 1)[0], "state": item.rsplit("(", 1)[-1].rstrip(")"),
             "speed_mbps": "", "driver": "N/A"}
            for item in _parse_network_interfaces(sections.get("netlink", ""))
        ]
    network_lines = []
    for adapter in net_details:
        components = [adapter["name"], adapter["state"]]
        if adapter["speed_mbps"]:
            components.append(f"{adapter['speed_mbps']} Mbps")
        if _available(adapter["driver"]):
            components.append(f"driver {adapter['driver']}")
        network_lines.append(" · ".join(components))

    uptime = _format_uptime(sections.get("uptime", ""))
    virtualization = _clean_string(sections.get("virtualization", "")) or "N/A"
    if virtualization.casefold() == "none":
        virtualization = "Not detected (physical host not independently confirmed)"
    elif virtualization.casefold() in {"n/a", "not available"}:
        virtualization = "N/A"

    cpu_source = "lscpu" if _available(cpu.get("model name") or cpu.get("model")) else "/proc/cpuinfo"
    system_source = "SMBIOS sysfs" if dmi else "SMBIOS fields unavailable"
    memory_source = "/proc/meminfo" if total_bytes else "memory statistics unavailable"
    storage_source = "lsblk JSON" if drives else "lsblk unavailable or access restricted"
    source_parts = [
        f"OS: {'/etc/os-release' if os_release else 'release-file fallback'}",
        f"CPU: {cpu_source}",
        f"Memory: {memory_source}",
        f"Storage: {storage_source}",
        f"System/board/firmware: {system_source}",
        f"Graphics: {'lspci/sysfs' if gpus else 'not reported'}",
        f"Network: {'sysfs' if net_details else 'not reported'}",
    ]

    details = {
        "hostname": hostname,
        "manufacturer": manufacturer,
        "model": model,
        "architecture": architecture,
        "cpu_vendor": cpu_vendor,
        "cpu_family": cpu_family,
        "cpu_model_number": cpu_model_number,
        "cpu_stepping": cpu_stepping,
        "cpu_sockets": sockets_label,
        "cpu_max_frequency": frequency,
        "cpu_virtualization": virtualization_extension,
        "ram_speed": memory_devices.get("ram_speed", "N/A"),
        "ram_slots": memory_devices.get("ram_slots", "N/A"),
        "ram_used": _format_gib(used_bytes),
        "ram_available": _format_gib(available_bytes),
        "storage_devices": "\n".join(drive_lines) if drive_lines else "N/A",
        "storage_classification_basis": "NVMe is identified by transport/name; HDD vs non-rotating media uses the Linux kernel rotational flag. Virtual disks and flash media can affect this classification.",
        "gpu": "\n".join(gpus) if gpus else "N/A",
        "network_adapters": "\n".join(network_lines) if network_lines else "N/A",
        "bios": bios,
        "uptime": uptime,
        "virtualization": virtualization,
        "system_serial": system_serial,
        "collection_sources": "; ".join(source_parts),
    }

    required_fields = {
        "Linux distribution": _available(distro),
        "Kernel version": _available(kernel),
        "Machine architecture": _available(architecture),
        "CPU model": _available(cpu_model),
        "CPU topology": bool(physical_cores or logical_threads),
        "Usable RAM total": total_bytes > 0,
        "Storage inventory": bool(drives),
        "System vendor/model": _available(manufacturer) or _available(model),
    }
    missing = [label for label, present in required_fields.items() if not present]
    coverage = round(100 * (len(required_fields) - len(missing)) / len(required_fields))
    details["coverage_percent"] = f"{coverage}%"
    optional_missing = []
    if not _available(motherboard):
        optional_missing.append("motherboard")
    if not _available(memory_devices.get("ram_speed", "")):
        optional_missing.append("DIMM speed")
    if not gpus:
        optional_missing.append("GPU")
    if not net_details:
        optional_missing.append("network adapter detail")
    if missing:
        details["collection_notes"] = "Core data unavailable: " + ", ".join(missing)
    elif optional_missing:
        details["collection_notes"] = "Core inventory collected; optional detail unavailable: " + ", ".join(optional_missing)
    else:
        details["collection_notes"] = "Core inventory collected. Values and device classifications depend on kernel interfaces and tools available on the target."

    return {
        "status": "SUCESSO_PARCIAL" if coverage < 50 else "SUCESSO",
        "placa_mae": motherboard,
        "processador": cpu_model,
        "cores_threads": cores_threads,
        "ram": ram,
        "disk_type": disk_type,
        "disk_size": disk_size,
        "distro": distro,
        "kernel": kernel,
        "hardware_details": details,
    }


def get_hardware_info(
    ip: str,
    username: str,
    password: Optional[str],
    key_path: Optional[str],
    timeout: int = 30,
    trust_unknown_hosts: bool = False,
    include_sensitive_identifiers: bool = False,
) -> dict[str, Any]:
    """Connect to one explicitly supplied host and discover Linux hardware read-only."""
    client = paramiko.SSHClient()
    known_hosts = get_known_hosts_path()
    try:
        client.load_system_host_keys()
        with _KNOWN_HOSTS_LOCK:
            if known_hosts.is_file():
                try:
                    client.load_host_keys(str(known_hosts))
                except OSError:
                    pass
        client.set_missing_host_key_policy(
            paramiko.AutoAddPolicy() if trust_unknown_hosts else paramiko.RejectPolicy()
        )

        pkey = None
        if key_path:
            private_key = Path(key_path).expanduser()
            if not private_key.is_file():
                raise FileNotFoundError(str(private_key))
            try:
                pkey = paramiko.PKey.from_path(private_key)
            except (AttributeError, NotImplementedError):
                key_errors = []
                for key_class in (
                    getattr(paramiko, "Ed25519Key", None),
                    getattr(paramiko, "ECDSAKey", None),
                    getattr(paramiko, "RSAKey", None),
                    getattr(paramiko, "DSSKey", None),
                ):
                    if key_class is None:
                        continue
                    try:
                        pkey = key_class.from_private_key_file(str(private_key))
                        break
                    except (paramiko.SSHException, ValueError, TypeError) as exc:
                        key_errors.append(exc)
                if pkey is None and key_errors:
                    raise paramiko.SSHException("Unsupported or unreadable private key") from key_errors[-1]

        client.connect(
            hostname=ip,
            username=username,
            password=password or None,
            pkey=pkey,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            allow_agent=False,
            look_for_keys=False,
        )
        if trust_unknown_hosts:
            with _KNOWN_HOSTS_LOCK:
                try:
                    known_hosts.parent.mkdir(parents=True, exist_ok=True)
                    client.save_host_keys(str(known_hosts))
                except OSError:
                    pass
        return _collect_linux_hardware(
            client,
            include_sensitive_identifiers=include_sensitive_identifiers,
            timeout=timeout,
        )
    except paramiko.AuthenticationException:
        return {"status": "FALHA_AUTH", "erro": t("hw_auth_failed")}
    except FileNotFoundError:
        return {"status": "FALHA_AUTH", "erro": t("hw_key_not_found", key_path=key_path)}
    except (socket.timeout, paramiko.ssh_exception.NoValidConnectionsError, TimeoutError):
        return {"status": "FALHA_CONEXAO", "erro": t("hw_connection_timeout", ip=ip)}
    except paramiko.ssh_exception.BadHostKeyException:
        return {"status": "ERRO_CHAVE_HOST", "erro": t("hw_host_key_mismatch", ip=ip)}
    except paramiko.SSHException as exc:
        return {"status": "ERRO_SSH", "erro": t("hw_ssh_error", error=exc)}
    except (OSError, ValueError, TypeError) as exc:
        return {"status": "ERRO_DESCONHECIDO", "erro": t("hw_unknown_error", error=exc)}
    finally:
        client.close()
