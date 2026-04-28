"""SSRF-Guard für externe URLs.

RSS-Quellen dürfen NUR public-routable HTTP/HTTPS sein. Private IP-Ranges
(RFC1918), localhost, link-local und Multicast werden geblockt.

Custom-AI-Endpoints (Phase B) nutzen einen separaten, weniger restriktiven
Guard, der Self-Hosted (localhost) erlaubt.
"""
import ipaddress
import socket
from urllib.parse import urlparse


class SSRFError(Exception):
    pass


_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # localhost
    ipaddress.ip_network("10.0.0.0/8"),         # RFC1918
    ipaddress.ip_network("172.16.0.0/12"),      # RFC1918
    ipaddress.ip_network("192.168.0.0/16"),     # RFC1918
    ipaddress.ip_network("169.254.0.0/16"),     # link-local
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),        # multicast
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def is_url_safe_for_rss(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.hostname:
        return False

    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                return False
    return True


def validate_rss_url(url: str) -> None:
    if not is_url_safe_for_rss(url):
        raise SSRFError(f"URL nicht erlaubt (private/lokale IP, ungültiges Schema o.ä.): {url}")
