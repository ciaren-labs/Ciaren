# SPDX-License-Identifier: AGPL-3.0-only
"""Optional SSRF guard for connector hosts and endpoints.

User-controlled connection fields — a SQL/Mongo ``host`` or an S3/Azure
``endpoint_url`` — otherwise let the server open a socket to *anywhere*, including
internal infrastructure and the cloud metadata endpoint (``169.254.169.254``).
When ``CONNECTOR_BLOCK_PRIVATE_HOSTS`` is enabled, every connector validates its
host through :func:`guard_host` / :func:`guard_endpoint` before connecting and
refuses any name that resolves to a loopback, link-local, private, or otherwise
non-global address.

Off by default: the common local-first setup legitimately talks to ``localhost``
or a private-network database, so this is opt-in for shared/untrusted deployments.

When enabled the guard fails closed on ambiguous values: a host containing
multi-host or URI metacharacters (``,`` ``/`` ``@`` ``?`` ``#`` whitespace, or a
``scheme://`` prefix) is refused outright, because drivers such as libpq and
pymongo would interpret it as a seed list or a full URI and dial an address the
guard never checked.

Limitation: the guard resolves DNS once, then the driver resolves again — a
determined DNS-rebinding attacker could still race the two lookups. This is a
baseline control, not a substitute for network egress policy.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.connectors.base import ConnectorError


def _enabled() -> bool:
    from app.core.config import get_settings

    return get_settings().CONNECTOR_BLOCK_PRIVATE_HOSTS


# RFC 6052 NAT64 well-known prefix: 64:ff9b::a9fe:a9fe reports is_global=True but
# NAT64-translates to 169.254.169.254 in DNS64/NAT64 environments.
_NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")

# Characters a driver could interpret as a multi-host seed list, a URI, or
# credentials-in-host (libpq comma lists, ``mongodb://`` URIs, ``user@host``).
_HOST_METACHARS = (",", "/", "@", "?", "#")


def _is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Whether an address is off-limits: loopback, link-local (incl. cloud
    metadata), private/RFC1918, unique-local, reserved, multicast, unspecified,
    or an IPv6 address embedding a blocked IPv4 (NAT64 / IPv4-mapped)."""
    if isinstance(ip, ipaddress.IPv6Address):
        if ip in _NAT64_PREFIX:
            return True
        mapped = ip.ipv4_mapped
        if mapped is not None and _is_blocked(mapped):
            return True
    return (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_private  # RFC1918 / unique-local (fc00::/7)
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _resolve(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve ``host`` to the set of IPs it maps to. An IP literal returns itself.
    A name that cannot be resolved returns ``[]`` (the driver will surface the real
    DNS error; we don't want the guard to mask it as a security block)."""
    stripped = host.strip().strip("[]")  # tolerate bracketed IPv6 literals
    try:
        return [ipaddress.ip_address(stripped)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return []
    ips: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for info in infos:
        sockaddr = info[4]
        try:
            ips.add(ipaddress.ip_address(sockaddr[0]))
        except ValueError:  # pragma: no cover - getaddrinfo always yields valid IPs
            continue
    return list(ips)


def _is_ambiguous(host: str) -> bool:
    """Whether a driver could read ``host`` as something other than a single
    hostname/IP: a ``scheme://`` URI, multi-host/URI metacharacters, or embedded
    whitespace."""
    return "://" in host or any(ch in host for ch in _HOST_METACHARS) or any(ch.isspace() for ch in host.strip())


def guard_host(host: str | None) -> None:
    """Refuse a host that resolves to an internal address — but only when the
    SSRF guard is enabled. A falsy host (file-based DB, no custom endpoint) is a
    no-op.

    Fails closed on values a driver could dial differently than the guard read
    them: comma-separated seed lists are split and every token is guarded, and a
    host carrying URI/multi-host metacharacters is refused outright even when no
    token resolves to a blocked address."""
    if not host or not _enabled():
        return
    # Defense in depth: libpq treats a comma as a multi-host seed list, so guard
    # every token before rejecting the ambiguous value as a whole.
    for token in host.split(","):
        blocked = [ip for ip in _resolve(token) if _is_blocked(ip)]
        if blocked:
            raise ConnectorError(
                f"Connection to {host!r} is blocked: it resolves to a private/internal "
                f"address ({blocked[0]}). Set CIAREN_CONNECTOR_BLOCK_PRIVATE_HOSTS=false "
                "to allow internal hosts."
            )
    if _is_ambiguous(host):
        raise ConnectorError(
            f"Connection to {host!r} is blocked: the host contains characters a "
            "driver could interpret as multiple hosts or a URI, so it cannot be "
            "safely validated. Provide a single plain hostname or IP address."
        )


def guard_endpoint(url: str | None) -> None:
    """Like :func:`guard_host` but for a full endpoint URL (S3/Azure)."""
    if not url or not _enabled():
        return
    host = urlparse(url).hostname
    if host is None:
        # A bare host without a scheme isn't parsed as a netloc; treat the whole
        # value as the host so we still guard it.
        host = url.split("/")[0].split(":")[0]
    guard_host(host)
