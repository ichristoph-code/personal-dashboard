"""Shared helper functions and constants for HTML builders."""

from datetime import datetime


# Calendar color palette — must match JS CAL_COLOR_PALETTE
CAL_COLOR_PALETTE = [
    '#667eea', '#e53e3e', '#38a169', '#d69e2e', '#9f7aea',
    '#ed8936', '#3182ce', '#dd6b20', '#319795', '#b83280',
    '#2b6cb0', '#c05621', '#2c7a7b', '#6b46c1', '#c53030'
]

_PIE_RGB = [
    (102, 126, 234), (118, 75, 162), (72, 187, 120), (56, 178, 172),
    (237, 137, 54), (245, 101, 101), (66, 153, 225), (159, 122, 234),
    (246, 173, 85), (72, 187, 166), (203, 83, 152), (99, 179, 237),
    (129, 230, 217), (252, 129, 74), (144, 205, 244), (183, 148, 244),
    (104, 211, 145), (251, 182, 206), (190, 227, 248), (254, 215, 170),
    (198, 246, 213), (214, 188, 250), (255, 204, 153), (163, 191, 250),
    (178, 245, 234), (255, 163, 163), (167, 243, 208),
]

PIE_COLORS = [f'rgba({r}, {g}, {b}, 0.85)' for r, g, b in _PIE_RGB]
PIE_BORDER_COLORS = [f'rgba({r}, {g}, {b}, 1)' for r, g, b in _PIE_RGB]


def _cal_color(cal_name):
    """Get a consistent color for a calendar name (matches JS getCalColor)."""
    h = 0
    for ch in cal_name:
        h = ((h << 5) - h) + ord(ch)
        h = h & 0xFFFFFFFF  # keep as 32-bit
        if h >= 0x80000000:
            h -= 0x100000000
    return CAL_COLOR_PALETTE[abs(h) % len(CAL_COLOR_PALETTE)]


def format_currency(milliunits):
    """Convert YNAB milliunits to dollars."""
    return milliunits / 1000.0


def _relative_time(dt):
    """Convert a datetime to a relative time string like '2h ago'."""
    if not dt:
        return ""
    now = datetime.now()
    # Handle timezone-aware datetimes
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    diff = now - dt
    secs = int(diff.total_seconds())
    if secs < 0:
        return "just now"
    if secs < 60:
        return "just now"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hrs = mins // 60
    if hrs < 24:
        return f"{hrs}h ago"
    days = hrs // 24
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days}d ago"
    return dt.strftime("%b %d")
