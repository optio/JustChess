"""P2 U3 join-request rate limit and client address (BR3.1, NFR4): justchess.ratelimit."""

from __future__ import annotations

import logging

from starlette.requests import Request

from justchess import ratelimit
from justchess.ratelimit import RateLimiter, client_address, parse_trusted_proxies, trusted_proxies_from

T0 = 1_800_000_000.0


def request_from(peer: str, forwarded: str | None = None) -> Request:
    """A real Starlette request as the ASGI server hands it over: the peer address and the headers."""
    headers = [(b"x-forwarded-for", forwarded.encode("latin-1"))] if forwarded is not None else []
    return Request({"type": "http", "method": "POST", "path": "/api/rooms/ABC123/join",
                    "client": (peer, 50000), "headers": headers})


def test_five_attempts_are_allowed_and_the_sixth_is_refused():
    limiter = RateLimiter()
    assert [limiter.allow("203.0.113.7", T0 + i) for i in range(5)] == [True] * 5
    assert limiter.allow("203.0.113.7", T0 + 10) is False
    assert limiter.allow("198.51.100.1", T0 + 10) is True, "another address has its own window"


def test_the_window_slides_and_empty_windows_are_dropped():
    limiter = RateLimiter()
    for i in range(5):
        limiter.allow("203.0.113.7", T0 + i * 10)  # at 0, 10, 20, 30, 40 s
    assert limiter.allow("203.0.113.7", T0 + 59) is False
    assert limiter.allow("203.0.113.7", T0 + 60) is True, "the attempt at 0 s left the window"
    assert limiter.allow("203.0.113.7", T0 + 61) is False
    limiter.allow("198.51.100.1", T0 + 61)
    assert len(limiter) == 2
    limiter.allow("198.51.100.2", T0 + 200)  # every older entry has left its window: those windows go
    assert len(limiter) == 1
    assert limiter.allow("203.0.113.7", T0 + 200) is True, "a dropped window starts afresh"


def test_a_spoofed_forwarded_header_is_ignored_when_no_proxy_is_trusted(monkeypatch):
    monkeypatch.delenv("JUSTCHESS_TRUSTED_PROXIES", raising=False)
    trusted = trusted_proxies_from({})
    assert trusted == ()
    assert client_address(request_from("203.0.113.7", "1.2.3.4"), trusted) == "203.0.113.7"
    # the same header from a peer that is not listed is ignored even when proxies are set
    assert client_address(request_from("203.0.113.7", "1.2.3.4"), parse_trusted_proxies("10.0.0.5")) == "203.0.113.7"


def test_from_a_trusted_proxy_the_rightmost_untrusted_entry_is_used(monkeypatch):
    monkeypatch.setenv("JUSTCHESS_TRUSTED_PROXIES", "10.0.0.5, 10.0.0.6")
    trusted = trusted_proxies_from({"JUSTCHESS_TRUSTED_PROXIES": "10.0.0.5, 10.0.0.6"})
    # the client wrote "6.6.6.6" itself; the first proxy appended the real client 198.51.100.9
    request = request_from("10.0.0.5", "6.6.6.6, 198.51.100.9, 10.0.0.6")
    assert client_address(request, trusted) == "198.51.100.9"
    assert client_address(request_from("10.0.0.5"), trusted) == "10.0.0.5", "no header: the proxy itself"
    assert client_address(request_from("10.0.0.5", "garbage, 10.0.0.6"), trusted) == "10.0.0.5"


def test_a_cidr_entry_works_and_an_invalid_entry_is_logged_and_ignored(caplog):
    with caplog.at_level(logging.WARNING, logger="justchess.ratelimit"):
        trusted = parse_trusted_proxies("172.16.0.0/12, not-an-ip, ,2001:db8::/32, 300.1.1.1")
    assert [str(net) for net in trusted] == ["172.16.0.0/12", "2001:db8::/32"]
    assert "not-an-ip" in caplog.text and "300.1.1.1" in caplog.text
    assert client_address(request_from("172.20.1.2", "192.0.2.44"), trusted) == "192.0.2.44"
    assert client_address(request_from("2001:db8::1", "2001:db8::2, 192.0.2.45"), trusted) == "192.0.2.45"
    assert ratelimit.is_trusted("192.168.0.1", trusted) is False


def test_at_most_max_addresses_are_tracked_and_the_oldest_is_evicted():
    limiter = RateLimiter(limit=1, max_addresses=3)
    for i, address in enumerate(("192.0.2.1", "192.0.2.2", "192.0.2.3")):
        assert limiter.allow(address, T0 + i)
    assert limiter.allow("192.0.2.1", T0 + 3) is False  # full window; this also does not refresh its place
    assert limiter.allow("192.0.2.4", T0 + 4) is True
    assert len(limiter) == 3
    assert limiter.allow("192.0.2.1", T0 + 5) is True, "the oldest address was evicted, so it starts afresh"
    assert limiter.allow("192.0.2.2", T0 + 6) is True, "and the next oldest went when 192.0.2.1 came back"
