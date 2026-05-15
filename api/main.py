import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from bot.state import BotState
from bot.trader import Trader
from api.db import save_trade, load_trades

log = logging.getLogger("api")
state = BotState(initial_capital=float(os.getenv("INITIAL_CAPITAL", "10000")))
_connections: set[WebSocket] = set()


async def broadcast(snapshot: dict):
    dead = set()
    msg = json.dumps(snapshot)
    for ws in _connections:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _connections.difference_update(dead)


def _on_trade_closed(trade):
    save_trade(trade)


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.register_broadcast(broadcast)
    trader = Trader(state)
    task = asyncio.create_task(trader.run())
    yield
    trader.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="BTC Trader API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/snapshot")
def snapshot():
    return state.snapshot()


@app.get("/trades")
def trades(limit: int = 100):
    return load_trades(limit)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _connections.add(ws)
    try:
        await ws.send_text(json.dumps(state.snapshot()))
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(ws)
