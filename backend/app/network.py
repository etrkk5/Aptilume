"""Operator-controlled egress policy; resolved addresses are pinned by each adapter."""

import ipaddress
import re
import socket
from urllib.parse import urlsplit
from .store import DomainError

METADATA = {"100.100.100.200", "168.63.129.16", "fd00:ec2::254"}


def hostname(value):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 253
        or value != value.strip()
        or any(x in value for x in ["/", "@", "%", "\\"])
    ):
        raise DomainError("invalid_host", "Geçerli bir sunucu adı girin.")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        if (
            not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", value)
            or ".." in value
        ):
            raise DomainError("invalid_host", "Geçerli bir sunucu adı girin.")
    return value.casefold()


def permitted_host(host, port, allowed):
    entries = {
        entry.strip().casefold() for entry in allowed.split(",") if entry.strip()
    }
    qualified = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
    if host not in entries and qualified not in entries:
        raise DomainError(
            "host_not_allowed", "Sunucu ve port işletim izin listesinde değil."
        )
    # A bare host only authorizes its protocol's standard port, enforced by callers.


def resolve_target(
    host, port, allowed, networks="", production=True, standard_port=443
):
    host = hostname(host)
    permitted_host(host, port, allowed)
    entries = {x.strip().casefold() for x in allowed.split(",") if x.strip()}
    qualified = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
    if port != standard_port and qualified not in entries:
        raise DomainError(
            "port_not_allowed",
            "Standart dışı port izin listesinde açıkça belirtilmeli.",
        )
    try:
        nets = [
            ipaddress.ip_network(x.strip(), strict=True)
            for x in networks.split(",")
            if x.strip()
        ]
    except ValueError:
        raise DomainError(
            "invalid_network_policy", "İşletim ağ izin listesi geçersiz.", 503
        )
    try:
        addresses = sorted(
            {
                row[4][0]
                for row in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            }
        )
    except OSError:
        raise DomainError("dns_error", "Sunucu adresi çözümlenemedi.", 503)
    if not addresses:
        raise DomainError("dns_error", "Sunucu adresi çözümlenemedi.", 503)
    for address in addresses:
        ip = ipaddress.ip_address(address)
        canonical = (
            ip.ipv4_mapped
            if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped
            else ip
        )
        if (
            canonical.is_loopback
            or canonical.is_link_local
            or canonical.is_multicast
            or canonical.is_unspecified
            or canonical.is_reserved
            or str(canonical) in METADATA
        ):
            raise DomainError("blocked_endpoint", "Bu ağ hedefine bağlantı engellendi.")
        if (
            production
            and not canonical.is_global
            and not any(canonical in n for n in nets if n.version == canonical.version)
        ):
            raise DomainError(
                "network_not_allowed",
                "Kurum içi ağ aralığı OUTBOUND_ALLOWED_CIDRS içinde tanımlanmalı.",
            )
    return addresses


def https_endpoint(value, allowed):
    try:
        parsed = urlsplit(value)
        port = parsed.port or 443
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or any(ord(x) < 33 or ord(x) == 127 for x in value)
        ):
            raise ValueError()
        host = hostname(parsed.hostname)
    except (ValueError, TypeError):
        raise DomainError(
            "invalid_endpoint",
            "HTTPS endpoint kullanın; URL içinde kimlik bilgisi bulunmamalı.",
        )
    permitted_host(host, port, allowed)
    entries = {x.strip().casefold() for x in allowed.split(",") if x.strip()}
    qualified = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
    if port != 443 and qualified not in entries:
        raise DomainError(
            "port_not_allowed", "Endpoint portu izin listesinde açıkça belirtilmeli."
        )
    return parsed, host, port
