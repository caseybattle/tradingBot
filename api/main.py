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


@app.get("/candles")
def candles_endpoint(count: int = 100):
    import os
    from bot.exchange import KrakenFutures
    demo = os.getenv("KRAKEN_DEMO", "true").lower() == "true"
    symbol = os.getenv("SYMBOL", "PI_XBTUSD")
    interval = int(os.getenv("CANDLE_INTERVAL", "15"))
    ex = KrakenFutures(demo=demo)
    df = ex.get_candles(symbol, resolution=interval, count=count)
    df = df.reset_index()
    result = []
    for _, row in df.iterrows():
        t = row["time"]
        result.append({
            "time": int(t.timestamp()),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        })
    return result


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
