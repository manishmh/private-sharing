"""Derive a human-friendly device name from a User-Agent string.

Intentionally lightweight (no external UA-parsing dependency): produces strings
like "iPhone · Safari", "Samsung · Chrome", "Windows · Edge".
"""
import re


def _device(ua: str) -> str:
    u = ua.lower()
    if "ipad" in u:
        return "iPad"
    if "iphone" in u:
        return "iPhone"
    if "ipod" in u:
        return "iPod"
    if "android" in u:
        # Try to pull a model token, e.g. "SM-G991B" -> "Samsung".
        if "samsung" in u or re.search(r"\bsm-[a-z0-9]+", u):
            return "Samsung"
        if "pixel" in u:
            return "Pixel"
        if "oneplus" in u:
            return "OnePlus"
        if "xiaomi" in u or "redmi" in u or "mi " in u:
            return "Xiaomi"
        return "Android"
    if "windows" in u:
        return "Windows"
    if "macintosh" in u or "mac os" in u:
        return "Mac"
    if "cros" in u:
        return "ChromeOS"
    if "linux" in u:
        return "Linux"
    return "Device"


def _browser(ua: str) -> str:
    u = ua.lower()
    # Order matters: Edge/Brave/Samsung pretend to be Chrome; check them first.
    if "edg/" in u or "edga/" in u or "edgios/" in u:
        return "Edge"
    if "samsungbrowser" in u:
        return "Samsung Internet"
    if "opr/" in u or "opera" in u:
        return "Opera"
    if "firefox" in u or "fxios" in u:
        return "Firefox"
    if "crios" in u:
        return "Chrome"
    if "chrome" in u:
        return "Chrome"
    if "safari" in u:
        return "Safari"
    return "Browser"


def friendly_name(ua: str | None) -> str:
    if not ua:
        return "Unknown device"
    return f"{_device(ua)} · {_browser(ua)}"
