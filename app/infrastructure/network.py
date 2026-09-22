"""LAN/private-network access guard."""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


def parse_networks(values: Iterable[str]) -> tuple[ipaddress._BaseNetwork, ...]:
    networks: list[ipaddress._BaseNetwork] = []
    for value in values:
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            continue
    return tuple(networks)


def ip_allowed(address: str | None, networks: tuple[ipaddress._BaseNetwork, ...]) -> bool:
    if not address:
        return False
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    if any(parsed in network for network in networks):
        return True
    mapped = getattr(parsed, "ipv4_mapped", None)
    return mapped is not None and any(mapped in network for network in networks)


class PrivateNetworkMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allowed_networks: Iterable[str], *, allow_testclient: bool = False) -> None:
        super().__init__(app)
        self.networks = parse_networks(allowed_networks)
        self.allow_testclient = allow_testclient

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else None
        if not (self.allow_testclient and client == "testclient") and not ip_allowed(client, self.networks):
            return JSONResponse(
                status_code=403,
                content={"success": False, "status": "error", "error_code": "LAN_ONLY", "message": "LAN access only"},
            )
        return await call_next(request)
