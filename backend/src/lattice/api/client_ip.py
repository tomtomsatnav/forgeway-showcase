"""The real client IP behind trusted proxies.

Production runs Cloudflare -> Caddy -> API. Caddy sets `CF-Connecting-IP` from Cloudflare's
header (`header_up`) and appends to `X-Forwarded-For`. Those headers are believed only when the
connecting peer is a trusted proxy; from anyone else they are ignored, so a client cannot choose
the address its rate limits key on.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Sequence

IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network
UNKNOWN = "unknown"


def parse_networks(spec: str) -> tuple[IpNetwork, ...]:
    """Comma-separated CIDRs or bare addresses, e.g. "172.16.0.0/12, ::1". Raises ValueError."""
    return tuple(
        ipaddress.ip_network(part.strip(), strict=False) for part in spec.split(",") if part.strip()
    )


def _valid(candidate: str | None) -> str | None:
    if not candidate:
        return None
    try:
        return str(ipaddress.ip_address(candidate.strip()))
    except ValueError:
        return None


def resolve(
    peer: str | None,
    headers: dict[str, str],
    trusted: Sequence[IpNetwork],
) -> str:
    """The client's IP: `CF-Connecting-IP`, else the first `X-Forwarded-For` hop, when `peer` is
    trusted; otherwise `peer` itself. `headers` has lower-case names."""
    peer_ip = _valid(peer)
    if peer_ip is None:
        return peer or UNKNOWN
    if not any(ipaddress.ip_address(peer_ip) in network for network in trusted):
        return peer_ip
    forwarded = headers.get("x-forwarded-for", "").split(",")[0]
    return _valid(headers.get("cf-connecting-ip")) or _valid(forwarded) or peer_ip
