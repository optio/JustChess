import asyncio
import json
import secrets
import sqlite3
import string
from contextlib import asynccontextmanager
from pathlib import Path

import chess
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

DB = Path("justchess.sqlite3")
rooms: dict[str, set[WebSocket]] = {}
locks: dict[str, asyncio.Lock] = {}
templates = Jinja2Templates(directory="templates")

LESSONS = {
    "italian": {"name": "Italian Game", "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3"],
                "notes": ["Claim the center.", "Black contests the center.", "Develop and attack e5.", "Defend e5.", "Aim at f7.", "Black develops the bishop.", "Prepare d4."]},
    "monte-carlo": {"name": "French Defense: Monte Carlo Variation", "moves": ["e4", "e6", "d4", "d5", "exd5", "exd5", "c4"],
                    "notes": ["Claim the center.", "Black prepares d5.", "Support e4.", "Challenge the center.", "Exchange in the center.", "Black recaptures.", "Challenge Black's d5 pawn."]},
}


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db


@asynccontextmanager
async def lifespan(app):
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS games (
            code TEXT PRIMARY KEY, fen TEXT NOT NULL, moves TEXT NOT NULL DEFAULT '[]',
            white TEXT NOT NULL, black TEXT, status TEXT NOT NULL DEFAULT 'waiting',
            white_score INTEGER NOT NULL DEFAULT 0, black_score INTEGER NOT NULL DEFAULT 0
        )""")
    yield


app = FastAPI(title="JustChess", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


class Join(BaseModel):
    token: str | None = None


class Move(BaseModel):
    token: str
    uci: str


def game(code):
    with connect() as db:
        row = db.execute("SELECT * FROM games WHERE code=?", (code.upper(),)).fetchone()
    if row is None:
        raise HTTPException(404, "Room not found")
    return dict(row)


def snapshot(row):
    board = chess.Board(row["fen"])
    return {"code": row["code"], "fen": board.fen(), "turn": "white" if board.turn else "black",
            "status": row["status"], "moves": json.loads(row["moves"]),
            "legal": [m.uci() for m in board.legal_moves],
            "white_score": row["white_score"], "black_score": row["black_score"],
            "check": board.is_check(), "outcome": board.outcome(claim_draw=True).result() if board.outcome(claim_draw=True) else None}


async def broadcast(code):
    payload = json.dumps({"type": "state", **snapshot(game(code))})
    for ws in list(rooms.get(code, set())):
        try:
            await ws.send_text(payload)
        except Exception:
            rooms.get(code, set()).discard(ws)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/games")
def create():
    alphabet = string.ascii_uppercase + string.digits
    token = secrets.token_urlsafe(24)
    with connect() as db:
        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(6))
            try:
                db.execute("INSERT INTO games(code,fen,white) VALUES(?,?,?)", (code, chess.STARTING_FEN, token))
                break
            except sqlite3.IntegrityError:
                pass
    return {"code": code, "token": token, "side": "white"}


@app.post("/api/games/{code}/join")
async def join(code: str, body: Join):
    code = code.upper()
    async with locks.setdefault(code, asyncio.Lock()):
        row = game(code)
        if body.token and body.token in (row["white"], row["black"]):
            side = "white" if body.token == row["white"] else "black"
            return {"code": code, "token": body.token, "side": side}
        if row["black"]:
            raise HTTPException(409, "Room already has two players")
        token = secrets.token_urlsafe(24)
        with connect() as db:
            db.execute("UPDATE games SET black=?, status='playing' WHERE code=? AND black IS NULL", (token, code))
        await broadcast(code)
        return {"code": code, "token": token, "side": "black"}


@app.get("/api/games/{code}")
def state(code: str):
    return snapshot(game(code))


@app.post("/api/games/{code}/moves")
async def move(code: str, body: Move):
    code = code.upper()
    async with locks.setdefault(code, asyncio.Lock()):
        row = game(code)
        if row["status"] != "playing":
            raise HTTPException(409, "Game is not active")
        board = chess.Board(row["fen"])
        expected = row["white"] if board.turn else row["black"]
        if not secrets.compare_digest(body.token, expected or ""):
            raise HTTPException(403, "Not your turn")
        try:
            move = chess.Move.from_uci(body.uci)
        except ValueError:
            raise HTTPException(400, "Invalid move")
        if move not in board.legal_moves:
            raise HTTPException(400, "Illegal move")
        san = board.san(move)
        board.push(move)
        history = json.loads(row["moves"])
        history.append(san)
        outcome = board.outcome(claim_draw=True)
        status = "finished" if outcome else "playing"
        white_score = row["white_score"] + (1 if outcome and outcome.winner is True else 0)
        black_score = row["black_score"] + (1 if outcome and outcome.winner is False else 0)
        with connect() as db:
            db.execute("UPDATE games SET fen=?, moves=?, status=?, white_score=?, black_score=? WHERE code=?",
                       (board.fen(), json.dumps(history), status, white_score, black_score, code))
        await broadcast(code)
        return snapshot(game(code))


@app.get("/api/lessons")
def lessons():
    return [{"id": key, "name": lesson["name"]} for key, lesson in LESSONS.items()]


@app.get("/api/lessons/{lesson_id}")
def lesson(lesson_id: str):
    if lesson_id not in LESSONS:
        raise HTTPException(404, "Lesson not found")
    data = LESSONS[lesson_id]
    board = chess.Board()
    steps = []
    for san, note in zip(data["moves"], data["notes"]):
        move = board.parse_san(san)
        steps.append({"san": san, "uci": move.uci(), "note": note, "before": board.fen()})
        board.push(move)
    return {"name": data["name"], "steps": steps, "final": board.fen()}


@app.websocket("/ws/{code}")
async def websocket(ws: WebSocket, code: str):
    code = code.upper()
    try:
        game(code)
    except HTTPException:
        await ws.close(code=1008)
        return
    await ws.accept()
    rooms.setdefault(code, set()).add(ws)
    await ws.send_json({"type": "state", **snapshot(game(code))})
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        rooms.get(code, set()).discard(ws)
