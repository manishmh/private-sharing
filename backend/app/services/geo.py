"""Approximate-location lookup from an IP address.

Uses the free, no-key ip-api.com service. For a loopback/private client IP
(the usual case when everything runs locally) there is no routable address to
locate, so we geolocate the *server's own public IP* instead — i.e. the actual
approximate location of the machine running Vault. Results are cached and the
lookup degrades gracefully to local labels when offline / rate-limited.

NOTE: this makes an outbound HTTP call (the only part of Vault that leaves the
machine). It is pluggable — swap `_geo_api` for an offline MaxMind/GeoIP2 reader
if you must stay fully local.
"""
import ipaddress
import json
import urllib.request

_ENDPOINT = "http://ip-api.com/json/"
_FIELDS = "status,country,regionName,city"
_TIMEOUT = 2.5

# Cache only SUCCESSFUL lookups (key: the queried IP, "" = server's public IP),
# so a transient failure isn't remembered for the life of the process.
_cache: dict[str, str] = {}


def _geo_api(ip_query: str) -> str:
    """Query ip-api.com. ``ip_query=""`` geolocates the caller (this server).
    Returns a "City, Region, Country" label, or "" on any failure."""
    if ip_query in _cache:
        return _cache[ip_query]
    url = f"{_ENDPOINT}{ip_query}?fields={_FIELDS}"
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - network/parse errors must never break access
        return ""
    if data.get("status") != "success":
        return ""
    label = ", ".join(p for p in (data.get("city"), data.get("regionName"),
                                  data.get("country")) if p)
    if label:
        _cache[ip_query] = label
    return label


def lookup(ip: str | None) -> str:
    """Return an approximate location label for an IP. Never raises."""
    # Decide what to geolocate: a public client IP directly; for loopback/private
    # (local) IPs, geolocate the server's own public IP (empty query).
    query = ""
    if ip:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            addr = None
        if addr is not None and not (addr.is_loopback or addr.is_private):
            query = ip

    label = _geo_api(query)
    if label:
        return label

    # Offline / rate-limited fallback.
    if not ip:
        return "Unknown"
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return "Unknown"
    if addr.is_loopback:
        return "Localhost"
    if addr.is_private:
        return "Local network"
    return "Unknown (public IP)"
