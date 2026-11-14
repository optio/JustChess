"""U5 Notifications logic and storage (justchess.notifications, justchess.vapid).

The push transport is faked: ``FakeSender`` returns scripted ``PushResult``s, so
no test reaches a push service. ``WebPushSender`` itself is driven through a
requests transport adapter mounted on its session, again with no network.
VAPID keys are generated in memory or written inside tmp_path; the project
folder is never written to.

Covers BR1.1 (event builder, final move gives only ``ended``), BR1.2 (a key is
sent once), BR1.3 (fresh visible page skips, stale or hidden sends), BR1.4
(2xx sent, 404/410 and VAPID mismatch delete, 500 failed, zero subscriptions
skipped), BR2.1 (endpoint and key validation, allowlist, trim to 5), BR2.3
(VAPID loading and refusal, generator refusal), BR2.4 (housekeeping hook,
seat transfer), and that no endpoint reaches the logs.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import stat

import pytest
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

import stockfish_install
from justchess import DomainError, games, housekeeping, notifications, rooms, vapid
from justchess.api import create_app
from justchess.db import prepare_database
from justchess.notifications import FAILED, SENT, SKIPPED, Presence, PushResult

NOW = 1_800_000_000.0
AWAY = Presence(connected=False, fresh_visible=False)
VISIBLE = Presence(connected=True, fresh_visible=True)
STALE_VISIBLE = Presence(connected=True, fresh_visible=False)  # visible flag set, but silent for > 6 s
HOSTS = notifications.DEFAULT_PUSH_HOSTS


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def browser_keys() -> dict:
    """Keys shaped like a browser's PushSubscription.toJSON().keys (a real P-256 point)."""
    point = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return {"p256dh": b64(point), "auth": b64(secrets.token_bytes(16))}


def endpoint(n: int | str = 1) -> str:
    return f"https://fcm.googleapis.com/fcm/send/test-endpoint-secret-{n}"


class FakeClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> float:
        return self.now


class FakeSender:
    """Returns the scripted results in order (the last one repeats) and records each call."""

    def __init__(self, *results: PushResult) -> None:
        self.results = list(results) or [PushResult(201)]
        self.calls: list[tuple[dict, str]] = []

    def __call__(self, info, payload, config):
        assert config.enabled, "the sender is only called with push enabled"
        self.calls.append((info, payload))
        return self.results[min(len(self.calls), len(self.results)) - 1]


@pytest.fixture
def db(tmp_path):
    return prepare_database(tmp_path / "notify.sqlite3")


@pytest.fixture
def room(db) -> str:
    with db.transaction() as conn:
        created, _seat, _token = rooms.create_room(conn, NOW)
        games.create_first_game(conn, created.code, NOW)
        rooms.join_room(conn, created.code, None, NOW)
    return created.code


@pytest.fixture
def enabled():
    return vapid.config_for(ec.generate_private_key(ec.SECP256R1()))


def subscribe(db, code, slot="B", n=1, now=NOW):
    keys = browser_keys()
    with db.transaction() as conn:
        notifications.save_subscription(conn, code, slot, endpoint(n), keys["p256dh"], keys["auth"], now)


def count_subscriptions(db, code, slot="B") -> int:
    with db.read() as conn:
        return len(notifications.list_subscriptions(conn, code, slot))


def status_of(db, event) -> str | None:
    with db.read() as conn:
        return notifications.alert_status(conn, event.room_code, event.target_slot, event.event_key)


def game(number=3, status="playing", end_reason=None) -> games.Game:
    return games.Game(1, "ROOM01", number, "A", "fen", 5, status, end_reason, None, NOW, None)


# --- BR1.1 event builder ----------------------------------------------------

def test_event_builder_keys_targets_and_final_move():
    joined = notifications.joined_event("ROOM01")
    assert (joined.target_slot, joined.event_key, joined.tag, joined.title) == (
        "A", "joined", "ROOM01:joined", "Your opponent has joined")

    move = notifications.event_after_move("ROOM01", "A", game(), 17, "Nf3")
    assert (move.kind, move.target_slot, move.event_key, move.tag) == ("move", "B", "move:3:17", "ROOM01:move:3:17")
    assert (move.title, move.body, move.url) == ("Your move", "Your opponent played Nf3.", "/r/ROOM01")

    final = notifications.event_after_move("ROOM01", "B", game(status="finished", end_reason="checkmate"), 4, "Qh4#")
    assert (final.kind, final.target_slot, final.event_key) == ("ended", "A", "ended:3"), "the final move alerts once"
    assert final.body == "Game over — Checkmate"

    draw = notifications.event_after_claim("ROOM01", "A", game(status="finished", end_reason="threefold_claimed"))
    win = notifications.event_after_claim("ROOM01", "B", game(status="finished", end_reason="abandoned"))
    assert (draw.target_slot, draw.event_key, draw.body) == ("B", "ended:3", "Game over — Draw claimed (threefold repetition)")
    assert (win.target_slot, win.body) == ("A", "Game over — Opponent left")
    payload = json.loads(move.payload())
    assert payload == {"title": "Your move", "body": "Your opponent played Nf3.", "tag": "ROOM01:move:3:17",
                       "url": "/r/ROOM01", "code": "ROOM01", "key": "move:3:17"}


# --- BR1.2 / BR1.3 / BR1.4 dispatch ------------------------------------------

def test_second_dispatch_of_the_same_key_never_sends(db, room, enabled):
    subscribe(db, room)
    sender = FakeSender(PushResult(201))
    notifier = notifications.Notifier(db, enabled, sender=sender, clock=FakeClock())
    event = notifications.event_after_move(room, "A", game(1), 1, "e4")

    assert notifier.dispatch(event, AWAY) == SENT
    assert notifier.dispatch(event, AWAY) == notifications.DUPLICATE
    assert len(sender.calls) == 1 and status_of(db, event) == SENT


def test_join_request_event_alerts_seat_a_once_per_request(db, room, enabled):
    """P2 U3 BR2.5: "join-request:<id>" goes to seat A under the one-alert rule; a new request is a new key."""
    subscribe(db, room, slot="A")
    sender = FakeSender(PushResult(201))
    notifier = notifications.Notifier(db, enabled, sender=sender, clock=FakeClock())
    event = notifications.join_request_event(room, 7)
    assert (event.kind, event.target_slot, event.event_key, event.tag) == (
        "join_request", "A", "join-request:7", f"{room}:join-request:7")
    assert (event.title, event.url) == ("Someone wants to join", f"/r/{room}")

    assert notifier.dispatch(event, AWAY) == SENT
    assert notifier.dispatch(event, AWAY) == notifications.DUPLICATE, "one alert per request"
    assert notifier.dispatch(notifications.join_request_event(room, 8), VISIBLE) == SKIPPED, "a visible page shows it"
    assert len(sender.calls) == 1 and json.loads(sender.calls[0][1])["key"] == "join-request:7"


def test_fresh_visible_page_is_skipped_but_stale_or_hidden_sends(db, room, enabled):
    subscribe(db, room)
    sender = FakeSender(PushResult(201))
    notifier = notifications.Notifier(db, enabled, sender=sender, clock=FakeClock())
    visible = notifications.event_after_move(room, "A", game(1), 1, "e4")
    stale = notifications.event_after_move(room, "A", game(1), 3, "Nf3")
    hidden = notifications.event_after_move(room, "A", game(1), 5, "Bc4")

    assert notifier.dispatch(visible, VISIBLE) == SKIPPED and sender.calls == []
    assert notifier.dispatch(stale, STALE_VISIBLE) == SENT
    assert notifier.dispatch(hidden, Presence(connected=True, fresh_visible=False)) == SENT
    assert len(sender.calls) == 2 and status_of(db, visible) == SKIPPED


def test_send_results_mark_sent_delete_gone_and_mark_failed(db, room, enabled):
    for n in (1, 2, 3, 4):
        subscribe(db, room, n=n, now=NOW + n)
    sender = FakeSender(PushResult(410), PushResult(404), PushResult(403, "VAPID credentials mismatch"),
                        PushResult(201))
    notifier = notifications.Notifier(db, enabled, sender=sender, clock=FakeClock())
    event = notifications.event_after_move(room, "A", game(1), 1, "e4")

    assert notifier.dispatch(event, AWAY) == SENT  # one 2xx is enough
    assert count_subscriptions(db, room) == 1, "410, 404 and the VAPID mismatch deleted three subscriptions"

    failing = notifications.Notifier(db, enabled, sender=FakeSender(PushResult(500, "boom")), clock=FakeClock())
    second = notifications.event_after_move(room, "A", game(1), 3, "Nf3")
    assert failing.dispatch(second, AWAY) == FAILED
    assert count_subscriptions(db, room) == 1, "a 500 keeps the subscription"
    assert failing.dispatch(second, AWAY) == notifications.DUPLICATE, "a failed claim is not retried"
    plain_forbidden = notifications.Notifier(db, enabled, sender=FakeSender(PushResult(403, "quota")), clock=FakeClock())
    assert plain_forbidden.dispatch(notifications.event_after_move(room, "A", game(1), 5, "Bc4"), AWAY) == FAILED
    assert count_subscriptions(db, room) == 1, "a 403 that names no key mismatch keeps it"


def test_zero_subscriptions_or_disabled_push_marks_skipped(db, room, enabled):
    sender = FakeSender()
    event = notifications.joined_event(room)
    assert notifications.Notifier(db, enabled, sender=sender).dispatch(event, AWAY) == SKIPPED
    subscribe(db, room, slot="A")
    off = notifications.Notifier(db, vapid.disabled("no key"), sender=sender)
    other = notifications.event_after_move(room, "B", game(1), 2, "e5")
    assert off.dispatch(other, AWAY) == SKIPPED
    assert sender.calls == [] and status_of(db, event) == SKIPPED


def test_no_endpoint_or_key_appears_in_the_logs(db, room, enabled, caplog):
    subscribe(db, room, n=1)
    subscribe(db, room, n=2, now=NOW + 1)
    sender = FakeSender(PushResult(500, "upstream"), PushResult(410))
    caplog.set_level(logging.DEBUG)
    notifications.Notifier(db, enabled, sender=sender).dispatch(notifications.event_after_move(room, "A", game(1), 1, "e4"), AWAY)

    lines = [record.getMessage() for record in caplog.records]
    assert any("fcm.googleapis.com" in line for line in lines), "the host is logged"
    with db.read() as conn:
        stored = notifications.list_subscriptions(conn, room, "B")
    for line in lines:
        assert "test-endpoint-secret" not in line and "/fcm/send/" not in line
        for sub in stored:
            assert sub.p256dh not in line and sub.auth not in line


# --- BR2.1 subscribe validation and storage ---------------------------------

@pytest.mark.parametrize("bad", [
    "http://fcm.googleapis.com/fcm/send/x",            # not https
    "https://fcm.googleapis.com:8443/fcm/send/x",       # port
    "https://user:pw@fcm.googleapis.com/fcm/send/x",    # user info
    "https://127.0.0.1/fcm/send/x",                     # IPv4 literal
    "https://[::1]/fcm/send/x",                         # IPv6 literal
    "https://localhost/push",                           # localhost
    "https://printer.local/push",                       # mDNS
    "https://evil.example.com/push",                    # not a push service
    "https://fcm.googleapis.com.evil.example/x",        # allowlisted name as a prefix
    "https://push.services.mozilla.com/x",              # wildcard needs a subdomain
    "https://127.0.0.1\\.push.apple.com/x",             # backslash: requests would contact 127.0.0.1
    "https://evil.com\\.push.apple.com/x",              # backslash: requests would contact evil.com
    "https://evil.com%5C.push.apple.com/x",             # percent-escaped backslash
    "https://web.push.apple.com.:443/x",                # trailing dot
    "https://fcm.googleapis.com/fcm/send/x y",          # whitespace
    "https://fcm.googleapis.com/" + "x" * 1100,         # too long
    "",
    None,
])
def test_subscribe_endpoint_validation_refuses(bad):
    with pytest.raises(DomainError) as refused:
        notifications.validate_endpoint(bad, HOSTS)
    assert (refused.value.status, refused.value.message) == (400, "Invalid push subscription")


def test_allowlisted_hosts_and_the_extra_hosts_variable_are_accepted():
    for good in ("https://fcm.googleapis.com/fcm/send/abc", "https://updates.push.services.mozilla.com/wpush/v2/abc",
                 "https://wns2-db5p.notify.windows.com/w/?token=abc", "https://web.push.apple.com/QF1",
                 "https://api.push.apple.com:443/3/device/abc"):
        assert notifications.validate_endpoint(good, HOSTS) == good
    extra = notifications.allowed_hosts({"JUSTCHESS_PUSH_HOSTS": " push.example.org, *.relay.example.net ,bad host"})
    assert notifications.validate_endpoint("https://push.example.org/x", extra)
    assert notifications.validate_endpoint("https://eu.relay.example.net/x", extra)
    with pytest.raises(DomainError):
        notifications.validate_endpoint("https://push.example.org/x", HOSTS)


def test_key_lengths_and_encoding_are_checked():
    keys = browser_keys()
    assert notifications.validate_subscription(endpoint(), keys, HOSTS)[1:] == (keys["p256dh"], keys["auth"])
    for bad in ({**keys, "auth": b64(secrets.token_bytes(12))},          # auth not 16 bytes
                {**keys, "p256dh": b64(secrets.token_bytes(64))},        # p256dh not 65 bytes
                {**keys, "p256dh": b64(b"\x04" + b"\x00" * 64)},         # 65 bytes, not a curve point
                {**keys, "auth": "not base64url!"},
                {"p256dh": keys["p256dh"]},
                "not-a-dict"):
        with pytest.raises(DomainError):
            notifications.validate_subscription(endpoint(), bad, HOSTS)


def test_upsert_and_trim_to_the_five_newest(db, room):
    for n in range(1, 8):
        subscribe(db, room, n=n, now=NOW + n)
    subscribe(db, room, n=3, now=NOW + 100)  # re-subscribing an endpoint refreshes it, no duplicate row

    with db.read() as conn:
        kept = [s.endpoint for s in notifications.list_subscriptions(conn, room, "B")]
    assert kept == [endpoint(3), endpoint(7), endpoint(6), endpoint(5), endpoint(4)]
    with db.transaction() as conn:
        assert notifications.delete_subscription(conn, room, "B", endpoint(7)) == 1
        assert notifications.delete_subscription(conn, room, "B", endpoint(7)) == 0
    assert count_subscriptions(db, room) == 4


# --- BR2.4 cleanup and seat transfer ----------------------------------------

def test_housekeeping_hook_removes_subscriptions_and_alert_records(db, room, enabled):
    def u5_rows() -> tuple[int, int]:
        with db.read() as conn:
            return (conn.execute("SELECT count(*) FROM push_subscriptions").fetchone()[0],
                    conn.execute("SELECT count(*) FROM alert_records").fetchone()[0])

    subscribe(db, room)
    notifications.Notifier(db, enabled, sender=FakeSender()).dispatch(notifications.joined_event(room), AWAY)
    assert u5_rows() == (1, 1)
    # the hook itself deletes by room code, inside the caller's transaction (the room is still there)
    with pytest.raises(RuntimeError):
        with db.transaction() as conn:
            notifications.delete_room_data(conn, room)
            assert conn.execute("SELECT count(*) FROM alert_records").fetchone()[0] == 0
            raise RuntimeError("roll back")
    assert u5_rows() == (1, 1), "rolled back with the caller's transaction"
    with db.transaction() as conn:
        notifications.delete_room_data(conn, room)
    assert u5_rows() == (0, 0)
    subscribe(db, room)  # and again through a housekeeping run that deletes the idle room
    later = NOW + housekeeping.RETENTION + 3600

    assert housekeeping.run_cleanup(db, later, hooks=[notifications.delete_room_data]) == 1

    with db.read() as conn:
        assert conn.execute("SELECT count(*) FROM push_subscriptions").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM alert_records").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM rooms").fetchone()[0] == 0


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("JUSTCHESS_ORIGIN", raising=False)
    monkeypatch.setattr(stockfish_install, "ensure_stockfish",
                        lambda _dir, _env: stockfish_install.EngineResult(error="disabled in tests"))
    monkeypatch.delenv("JUSTCHESS_VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("JUSTCHESS_VAPID_KEY_FILE", raising=False)
    with TestClient(create_app(db_path=tmp_path / "transfer.sqlite3", engine_dir=tmp_path / "engines")) as started:
        yield started


def test_continue_redeem_deletes_the_seats_subscriptions(client):
    a = client.post("/api/rooms").json()
    client.post(f"/api/rooms/{a['code']}/join", json={})
    db = client.app.state.services.db
    subscribe(db, a["code"], slot="A", n=1)
    subscribe(db, a["code"], slot="B", n=2)
    assert count_subscriptions(db, a["code"], "A") == 1

    link = client.post(f"/api/rooms/{a['code']}/continue-link", json={"token": a["token"]}).json()
    redeemed = client.post(f"/api/rooms/{a['code']}/continue", json={"continueToken": link["continueToken"]})

    assert redeemed.status_code == 200
    assert count_subscriptions(db, a["code"], "A") == 0, "the moved seat subscribes again from the new device"
    assert count_subscriptions(db, a["code"], "B") == 1


# --- BR2.3 VAPID ------------------------------------------------------------

def pem_of(key) -> str:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode("ascii")


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    return root


def test_vapid_from_env_pem_and_raw(project):
    key = ec.generate_private_key(ec.SECP256R1())
    from_pem = vapid.load_vapid({"JUSTCHESS_VAPID_PRIVATE_KEY": pem_of(key)}, project)
    raw = b64(key.private_numbers().private_value.to_bytes(32, "big"))
    from_raw = vapid.load_vapid({"JUSTCHESS_VAPID_PRIVATE_KEY": raw, "JUSTCHESS_VAPID_SUBJECT": "mailto:me@example.org"},
                                project)

    assert from_pem.enabled and from_raw.enabled
    assert from_pem.public_key == from_raw.public_key == vapid.public_key_b64(key)
    assert len(base64.urlsafe_b64decode(from_raw.public_key + "=")) == 65
    assert from_raw.subject == "mailto:me@example.org" and from_pem.subject == vapid.DEFAULT_SUBJECT
    assert "PRIVATE" not in repr(from_pem) and raw not in repr(from_raw)


def test_vapid_file_outside_the_project_is_used_inside_is_refused(tmp_path, project, caplog):
    outside = tmp_path / "keys" / "vapid.pem"
    outside.parent.mkdir()
    key = ec.generate_private_key(ec.SECP256R1())
    outside.write_text(pem_of(key))
    assert vapid.load_vapid({"JUSTCHESS_VAPID_KEY_FILE": str(outside)}, project).public_key == vapid.public_key_b64(key)

    inside = project / "vapid.pem"
    inside.write_text(pem_of(key))
    link = tmp_path / "keys" / "looks-outside.pem"
    link.symlink_to(inside)
    caplog.set_level(logging.WARNING, logger="justchess.vapid")
    for refused in (inside, link):
        config = vapid.load_vapid({"JUSTCHESS_VAPID_KEY_FILE": str(refused)}, project)
        assert not config.enabled and "inside the project" in config.reason
    assert sum("Web Push is disabled" in r.getMessage() for r in caplog.records) == 2
    assert not any("BEGIN" in r.getMessage() for r in caplog.records)


def test_missing_or_invalid_keys_disable_push(project, caplog):
    caplog.set_level(logging.WARNING, logger="justchess.vapid")
    missing = vapid.load_vapid({}, project)
    garbage = vapid.load_vapid({"JUSTCHESS_VAPID_PRIVATE_KEY": "c2hvcnQ"}, project)
    other_curve = vapid.load_vapid({"JUSTCHESS_VAPID_PRIVATE_KEY": pem_of(ec.generate_private_key(ec.SECP384R1()))}, project)
    unreadable = vapid.load_vapid({"JUSTCHESS_VAPID_KEY_FILE": "/nonexistent/vapid.pem"}, project)

    for config in (missing, garbage, other_curve, unreadable):
        assert not config.enabled and config.public_key is None and config.reason
    assert "neither" in missing.reason and "P-256" in other_curve.reason
    assert len([r for r in caplog.records if "Web Push is disabled" in r.getMessage()]) == 4


def test_generator_writes_0600_outside_and_refuses_inside_the_project(tmp_path, project):
    target = tmp_path / "config" / "justchess" / "vapid.pem"
    public = vapid.generate(target, project)
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o600
    assert vapid.load_vapid({"JUSTCHESS_VAPID_KEY_FILE": str(target)}, project).public_key == public
    with pytest.raises(vapid.VapidKeyError, match="already exists"):
        vapid.generate(target, project)

    link_dir = tmp_path / "link-to-project"
    link_dir.symlink_to(project)
    for inside in (project / "vapid.pem", link_dir / "vapid.pem"):
        with pytest.raises(vapid.VapidKeyError, match="inside the project"):
            vapid.generate(inside, project)
        assert not (project / "vapid.pem").exists()
    # the default root is this repository: refused before anything is written
    with pytest.raises(vapid.VapidKeyError, match="inside the project"):
        vapid.generate(vapid.PROJECT_ROOT / "tests" / "never-written.pem")
    assert not (vapid.PROJECT_ROOT / "tests" / "never-written.pem").exists()


def test_generator_cli_refuses_a_path_in_this_repository(capsys):
    target = vapid.PROJECT_ROOT / "never-written-by-cli.pem"
    assert vapid.main(["generate", str(target)]) == 2
    assert "inside the project" in capsys.readouterr().err and not target.exists()


# --- WebPushSender: no redirects, statuses mapped, no network ----------------

class ScriptedAdapter(requests.adapters.BaseAdapter):
    """A requests transport that answers every request with one status and counts the calls."""

    def __init__(self, status: int, headers: dict | None = None, text: str = "") -> None:
        super().__init__()
        self.status, self.headers, self.text, self.calls = status, headers or {}, text, []

    def send(self, request, **kwargs):
        self.calls.append((request.url, kwargs.get("timeout")))
        response = requests.Response()
        response.status_code, response.url, response.request = self.status, request.url, request
        response.headers.update(self.headers)
        response._content = self.text.encode()
        return response

    def close(self):
        pass


def scripted_sender(adapter: ScriptedAdapter) -> notifications.WebPushSender:
    def factory():
        session = notifications.NoRedirectSession()
        session.mount("https://", adapter)
        return session
    return notifications.WebPushSender(session_factory=factory)


def test_webpush_sender_never_follows_a_redirect_and_maps_statuses(enabled):
    info = {"endpoint": endpoint(), "keys": browser_keys()}
    redirect = ScriptedAdapter(302, {"Location": "http://169.254.169.254/latest/meta-data"})
    # max_redirects = 0 makes requests refuse the 302 outright: a failed send, and no second request
    assert scripted_sender(redirect)(info, '{"title":"t"}', enabled) == PushResult(0, "TooManyRedirects")
    assert len(redirect.calls) == 1 and redirect.calls[0][0] == endpoint(), "the redirect was not followed"
    assert notifications.NoRedirectSession().max_redirects == 0

    accepted = ScriptedAdapter(201)
    assert scripted_sender(accepted)(info, "{}", enabled).status == 201
    assert accepted.calls[0][1] == notifications.SEND_TIMEOUT
    gone = scripted_sender(ScriptedAdapter(410, text="push subscription has unsubscribed or expired"))(info, "{}", enabled)
    assert gone.status == 410 and notifications.is_gone(gone)
    assert notifications.is_gone(PushResult(400, "VapidPkHashMismatch"))
    assert not notifications.is_gone(PushResult(500, "VAPID")) and not notifications.is_gone(PushResult(429))
