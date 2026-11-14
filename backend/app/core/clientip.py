"""Resolve the real client IP for rate limiting, even behind reverse proxies.

Behind Vercel's rewrite and Render's load balancer the TCP peer is a proxy, so keying the
login throttle on it would make every user share one bucket (five wrong passwords from anyone
would lock the account for everybody). ``CADENCE_TRUSTED_PROXY_COUNT`` says how many proxies
*we operate or trust* sit between the internet and this app:

* ``0`` (default) — trust nothing; use the socket peer. ``X-Forwarded-For`` is ignored, so it
  cannot be spoofed to dodge the throttle. Correct for local dev and a directly exposed server.
* ``1`` — one trusted proxy (e.g. Render's load balancer): the client is the last
  ``X-Forwarded-For`` entry.
* ``2`` — two trusted proxies (browser → Vercel rewrite → Render): the client is the
  second-to-last entry.

We count from the *right* because each trusted proxy appends the address it saw; anything an
attacker prepends stays to the left of the trusted part and is never used.
"""

from __future__ import annotations

import ipaddress

from fastapi import Request

from app.core.config import settings


def _valid(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def client_ip(request: Request, *, trusted_proxies: int | None = None) -> str:
    peer = request.client.host if request.client else "unknown"
    hops = settings.trusted_proxy_count if trusted_proxies is None else trusted_proxies
    if hops <= 0:
        return peer
    forwarded = [p for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    # forwarded[-1] is what the nearest trusted proxy saw, forwarded[-2] the one before it, ...
    # The socket peer *is* the nearest proxy, so ``hops`` proxies => index -hops.
    if len(forwarded) < hops:
        return peer  # header shorter than expected: don't guess, fall back to the peer
    return _valid(forwarded[-hops]) or peer
