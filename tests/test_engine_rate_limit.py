"""P2 U4 per-address limits on the engine routes (BR6.2): 10 creations, 20 hints, 30 computer-moves per minute."""

from __future__ import annotations

from tests.fakes.computer_api import computer_client, computer_clock, create_computer, wait_idle  # noqa: F401


def test_computer_room_creation_is_limited_to_ten_a_minute(computer_client, computer_clock) -> None:
    client = computer_client([])
    for _ in range(10):
        create_computer(client, colour="white")
    refused = client.post("/api/rooms", json={"kind": "computer", "level": "casual", "colour": "white"})
    assert refused.status_code == 429 and refused.headers["Retry-After"] == "60"
    assert refused.json()["error"] == "too_many"
    assert all(client.post("/api/rooms").status_code == 201 for _ in range(3)), "friend rooms are not limited"
    computer_clock.advance(60)
    create_computer(client, colour="white")


def test_hints_are_limited_to_twenty_a_minute(computer_client) -> None:
    client = computer_client([])
    room = create_computer(client, colour="white")
    body = {"token": room["token"], "version": 0}
    answers = [client.post(f"/api/rooms/{room['code']}/hint", json=body).status_code for _ in range(20)]
    assert answers == [200] * 20
    refused = client.post(f"/api/rooms/{room['code']}/hint", json=body)
    assert refused.status_code == 429 and refused.headers["Retry-After"] == "60"


def test_computer_move_is_limited_to_thirty_a_minute(computer_client) -> None:
    client = computer_client([])
    room = create_computer(client, colour="white")
    body = {"token": room["token"]}
    answers = [client.post(f"/api/rooms/{room['code']}/computer-move", json=body).status_code for _ in range(30)]
    assert answers == [200] * 30
    refused = client.post(f"/api/rooms/{room['code']}/computer-move", json=body)
    assert refused.status_code == 429 and refused.headers["Retry-After"] == "60"
    wait_idle(client)
