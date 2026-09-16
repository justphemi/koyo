"""LAN networking helpers for the koyoapp dev server."""

from __future__ import annotations

import socket


def _looks_like_ipv4(host: str) -> bool:
    try:
        socket.inet_aton(host)
    except OSError:
        return False
    return host.count(".") == 3


def detect_lan_ip(fallback_host: str = "8.8.8.8", fallback_port: int = 80) -> str | None:
    """Return the machine's outbound LAN IP, or None when it cannot be found.

    Uses a UDP socket connected to a public address without sending any
    packets: connect() on an unconnected UDP socket only records the
    destination so that getsockname() reports the local address the kernel
    would route from. No network traffic is produced and no external
    service is contacted.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((fallback_host, fallback_port))
        ip = sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()
    if _looks_like_ipv4(ip):
        return ip
    return None