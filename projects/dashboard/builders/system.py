"""System tab HTML builder for the Personal Dashboard.

Generates collapsible, draggable sections for system overview, CPU, memory,
disk, battery, network, network speed, top processes, and listening ports.
"""

from html import escape


def _usage_bar(pct, label=""):
    """Return an HTML usage bar with green/orange/red coloring."""
    pct = max(0, min(100, int(pct)))
    if pct >= 85:
        color = "red"
    elif pct >= 60:
        color = "orange"
    else:
        color = "green"
    aria = f' aria-label="{label} {pct}%"' if label else ""
    return (
        f'<div class="usage-bar-track"{aria}>'
        f'<div class="usage-bar-fill {color}" style="width:{pct}%"></div>'
        f'</div>'
    )


def _row(label, value):
    """Return a label-value row."""
    return (
        f'<div class="system-row">'
        f'<span class="system-label">{label}</span>'
        f'<span class="system-value">{value}</span>'
        f'</div>'
    )


def _card(body):
    """Wrap body in a system card (inner card, no title — title is in section header)."""
    return f'<div class="system-card">{body}</div>'


# ── Collapsible section wrapper (reuses fin-section CSS/JS) ──

_CHEVRON_SVG = (
    '<svg class="fin-chevron" width="18" height="18" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>'
)


def _section(section_id, title, icon_svg, body, default_open=True):
    """Wrap content in a collapsible, draggable section."""
    body_cls = "fin-section-body" if default_open else "fin-section-body collapsed"
    hdr_cls = "fin-section-header" if default_open else "fin-section-header collapsed"
    return (
        f'<div class="fin-section" id="{section_id}" data-section-id="{section_id}" draggable="true">'
        f'<div class="{hdr_cls}">'
        f'<span class="fin-drag-handle" title="Drag to reorder">&#x2807;</span>'
        f'<span class="fin-section-icon">{icon_svg}</span>'
        f'<h2>{title}</h2>'
        f'{_CHEVRON_SVG}'
        f'</div>'
        f'<div class="{body_cls}">'
        f'{body}'
        f'</div>'
        f'</div>'
    )


# ── SVG icons (Feather/Lucide style) ──

_ICON_MONITOR = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>'
_ICON_CPU = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>'
_ICON_DISK = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12H2"/><path d="M5.45 5.11L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6l-3.45-6.89A2 2 0 0016.76 4H7.24a2 2 0 00-1.79 1.11z"/><line x1="6" y1="16" x2="6.01" y2="16"/><line x1="10" y1="16" x2="10.01" y2="16"/></svg>'
_ICON_BATTERY = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="6" width="18" height="12" rx="2" ry="2"/><line x1="23" y1="13" x2="23" y2="11"/></svg>'
_ICON_NETWORK = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.55a11 11 0 0114.08 0"/><path d="M1.42 9a16 16 0 0121.16 0"/><path d="M8.53 16.11a6 6 0 016.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>'
_ICON_SPEED = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>'
_ICON_PORT = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>'
_ICON_PROC = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>'


# ── Section content builders ──

def _build_overview_content(data):
    """System overview: model, chip, OS, hostname, uptime."""
    rows = []
    if data.get("model"):
        rows.append(_row("Model", escape(data["model"])))
    if data.get("chip"):
        rows.append(_row("Chip", escape(data["chip"])))
    if data.get("memory_label"):
        rows.append(_row("Memory", escape(data["memory_label"])))
    if data.get("macos_version"):
        rows.append(_row("macOS", escape(data["macos_version"])))
    if data.get("hostname"):
        rows.append(_row("Hostname", escape(data["hostname"])))
    if data.get("uptime"):
        rows.append(_row("Uptime", escape(data["uptime"])))
    if data.get("serial_last4"):
        rows.append(_row("Serial", f"...{escape(data['serial_last4'])}"))
    return _card("\n".join(rows))


def _build_cpu_memory_content(cpu, mem):
    """CPU usage + memory usage with bars."""
    parts = []

    if cpu:
        core_info = ""
        if cpu.get("cores_physical"):
            p = cpu["cores_physical"]
            l = cpu.get("cores_logical", p)
            core_info = f"{p} cores" if p == l else f"{p}P + {l - p}E cores"
        parts.append(_row("CPU Cores", core_info))
        parts.append(_row("CPU Usage", f'{cpu.get("usage_total", 0)}%'))
        parts.append(
            f'<div class="usage-bar-label">User {cpu.get("usage_user", 0)}% · '
            f'System {cpu.get("usage_sys", 0)}% · '
            f'Idle {cpu.get("usage_idle", 0)}%</div>'
        )
        parts.append(_usage_bar(cpu.get("usage_total", 0), "CPU"))
        parts.append('<div class="system-divider"></div>')

    if mem:
        total = mem.get("total_gb", 0)
        used = mem.get("used_gb", 0)
        avail = mem.get("available_gb", 0)
        pct = mem.get("used_pct", 0)
        parts.append(_row("RAM Used", f"{used} GB / {total} GB"))
        parts.append(_row("Available", f"{avail} GB"))
        parts.append(_usage_bar(pct, "Memory"))
        if mem.get("swap_used_gb", 0) > 0.01:
            parts.append(_row("Swap Used", f'{mem["swap_used_gb"]} GB'))

    return _card("\n".join(parts))


def _build_storage_content(disks):
    """Storage volumes with usage bars."""
    if not disks:
        return _card('<span class="system-label">No volumes found</span>')

    parts = []
    for i, vol in enumerate(disks):
        if i > 0:
            parts.append('<div class="system-divider"></div>')
        name = escape(vol.get("name", vol.get("mount", "/")))
        pct = vol.get("percent_used", 0)
        parts.append(_row(name, f'{vol.get("used_gb", 0)} GB / {vol.get("total_gb", 0)} GB'))
        parts.append(
            f'<div class="usage-bar-detail">'
            f'{vol.get("free_gb", 0)} GB free · {pct}% used'
            f'</div>'
        )
        parts.append(_usage_bar(pct, name))

    return _card("\n".join(parts))


def _build_battery_content(battery):
    """Battery content — returns None for desktops."""
    if not battery:
        return None

    pct = battery.get("percent", 0)
    parts = []

    status = "Charging" if battery.get("charging") else "On Battery"
    source = battery.get("power_source", "")
    if source:
        status = source

    parts.append(_row("Level", f"{pct}%"))
    parts.append(_usage_bar(100 - pct, "Battery"))
    parts.append(_row("Status", escape(status)))
    if battery.get("time_remaining"):
        parts.append(_row("Time Remaining", escape(battery["time_remaining"])))
    if battery.get("cycle_count") and battery["cycle_count"] != "N/A":
        parts.append(_row("Cycle Count", str(battery["cycle_count"])))
    if battery.get("condition") and battery["condition"] != "N/A":
        parts.append(_row("Condition", escape(battery["condition"])))

    return _card("\n".join(parts))


def _build_network_content(net):
    """Network info: interface, SSID, IP, MAC."""
    parts = []
    if net.get("type"):
        parts.append(_row("Type", escape(net["type"])))
    if net.get("interface"):
        parts.append(_row("Interface", escape(net["interface"])))
    if net.get("wifi_ssid"):
        parts.append(_row("Wi-Fi SSID", escape(net["wifi_ssid"])))
    if net.get("local_ip"):
        parts.append(_row("Local IP", escape(net["local_ip"])))
    if net.get("mac_address"):
        parts.append(_row("MAC Address", escape(net["mac_address"])))

    if not parts:
        parts.append('<span class="system-label">No network connection</span>')

    return _card("\n".join(parts))


def _build_speed_content(speed):
    """Network speed test results."""
    if not speed:
        return _card('<span class="system-label">Speed test unavailable</span>')

    parts = []
    parts.append(_row("Download", escape(speed.get("download", "N/A"))))
    parts.append(_row("Upload", escape(speed.get("upload", "N/A"))))
    parts.append(_row("Latency", f'{speed.get("latency_ms", "N/A")} ms'))

    # Visual bar for download speed (scale: 0-500 Mbps)
    dl_mbps = speed.get("dl_mbps", 0)
    dl_pct = min(100, dl_mbps / 5)  # 500 Mbps = 100%
    parts.append(
        f'<div class="usage-bar-label">Download speed</div>'
        f'<div class="usage-bar-track">'
        f'<div class="usage-bar-fill green" style="width:{dl_pct:.0f}%"></div>'
        f'</div>'
    )

    # Upload bar
    ul_mbps = speed.get("ul_mbps", 0)
    ul_pct = min(100, ul_mbps / 5)
    parts.append(
        f'<div class="usage-bar-label">Upload speed</div>'
        f'<div class="usage-bar-track">'
        f'<div class="usage-bar-fill green" style="width:{ul_pct:.0f}%"></div>'
        f'</div>'
    )

    return _card("\n".join(parts))


def _build_ports_content(ports):
    """Listening TCP ports table."""
    if not ports:
        return _card('<span class="system-label">No listening ports</span>')

    rows = []
    for p in ports:
        rows.append(
            f'<tr>'
            f'<td class="port-num">{escape(str(p["port"]))}</td>'
            f'<td>{escape(p["process"])}</td>'
            f'<td class="port-pid">{escape(str(p["pid"]))}</td>'
            f'</tr>'
        )

    table = (
        '<table class="process-table">'
        '<thead><tr><th>Port</th><th>Process</th><th>PID</th></tr></thead>'
        '<tbody>' + "\n".join(rows) + '</tbody>'
        '</table>'
    )
    return _card(table)


def _build_processes_content(procs):
    """Top processes table."""
    if not procs:
        return _card('<span class="system-label">No process data</span>')

    rows = []
    for i, p in enumerate(procs, 1):
        rows.append(
            f'<tr>'
            f'<td class="proc-rank">{i}</td>'
            f'<td>{escape(p["name"])}</td>'
            f'<td class="proc-num">{escape(p["cpu"])}%</td>'
            f'<td class="proc-num">{escape(p["mem"])}%</td>'
            f'<td class="port-pid">{escape(str(p["pid"]))}</td>'
            f'</tr>'
        )

    table = (
        '<table class="process-table">'
        '<thead><tr><th>#</th><th>Process</th><th>CPU</th><th>Mem</th><th>PID</th></tr></thead>'
        '<tbody>' + "\n".join(rows) + '</tbody>'
        '</table>'
    )
    return _card(table)


# ── Main builder ──

def build_system_html(data):
    """Build the full System tab HTML from collected system data."""
    if not data:
        return '<div class="system-card"><p class="system-label">System information unavailable.</p></div>'

    sections = []

    sections.append(_section(
        "sys-overview", "System Overview", _ICON_MONITOR,
        _build_overview_content(data),
    ))
    sections.append(_section(
        "sys-cpu-mem", "CPU & Memory", _ICON_CPU,
        _build_cpu_memory_content(data.get("cpu", {}), data.get("memory", {})),
    ))
    sections.append(_section(
        "sys-storage", "Storage", _ICON_DISK,
        _build_storage_content(data.get("disk", [])),
    ))

    battery_content = _build_battery_content(data.get("battery"))
    if battery_content:
        sections.append(_section(
            "sys-battery", "Battery", _ICON_BATTERY,
            battery_content,
        ))

    sections.append(_section(
        "sys-network", "Network", _ICON_NETWORK,
        _build_network_content(data.get("network", {})),
    ))
    sections.append(_section(
        "sys-speed", "Network Speed", _ICON_SPEED,
        _build_speed_content(data.get("network_speed")),
    ))
    sections.append(_section(
        "sys-ports", "Listening Ports", _ICON_PORT,
        _build_ports_content(data.get("listening_ports", [])),
    ))
    sections.append(_section(
        "sys-procs-cpu", "Top Processes (CPU)", _ICON_PROC,
        _build_processes_content(data.get("top_processes_cpu", [])),
    ))
    sections.append(_section(
        "sys-procs-mem", "Top Processes (Memory)", _ICON_PROC,
        _build_processes_content(data.get("top_processes_mem", [])),
    ))

    return "\n".join(sections)
