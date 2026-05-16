import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from bot.state import BotState
from bot.trader import Trader
from api.db import save_trade, load_trades, save_position, load_position, clear_position

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
    # Restore open position from DB across restarts
    saved_pos = load_position()
    if saved_pos:
        state.open_position(
            saved_pos["side"], saved_pos["entry_price"], saved_pos["size"],
            saved_pos["stop_price"], saved_pos["target_price"], saved_pos["order_id"],
        )
        state.position.opened_at = saved_pos["opened_at"]
        log.info(f"Restored position from DB: {saved_pos['side']} @ {saved_pos['entry_price']}")
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


@app.post("/order")
async def place_manual_order(side: str, size: float = None):
    """Manual trade: side=long|short. Uses risk manager if size omitted."""
    import os
    from bot.risk import RiskManager
    from bot.exchange import KrakenFutures
    DEMO = os.getenv("KRAKEN_DEMO", "true").lower() == "true"
    SYMBOL = os.getenv("SYMBOL", "PI_XBTUSD")

    if state.position:
        return {"error": "position already open"}
    if state.last_price == 0:
        return {"error": "no price data yet"}
    if side not in ("long", "short"):
        return {"error": "side must be long or short"}

    rm = RiskManager(account_balance=state.capital)
    calc_size, stop, target = rm.size_position(state.capital, state.last_price, side)
    trade_size = size or calc_size

    order_id = None
    if not DEMO:
        ex = KrakenFutures(demo=False)
        order_side = "buy" if side == "long" else "sell"
        resp = ex.place_order(SYMBOL, order_side, trade_size)
        order_id = resp.get("sendStatus", {}).get("order_id")

    state.open_position(side, state.last_price, trade_size, stop, target, order_id)
    save_position(state.position)
    state.current_signal = "HOLD"
    if state._broadcast_fn:
        await state._broadcast_fn(state.snapshot())
    return {"status": "ok", "side": side, "entry": state.last_price, "size": trade_size, "stop": stop, "target": target, "demo": DEMO}


@app.post("/close")
async def close_position_endpoint():
    """Close the current open position."""
    import os
    from bot.exchange import KrakenFutures
    DEMO = os.getenv("KRAKEN_DEMO", "true").lower() == "true"
    SYMBOL = os.getenv("SYMBOL", "PI_XBTUSD")

    if not state.position:
        return {"error": "no open position"}
    price = state.last_price
    if not DEMO:
        ex = KrakenFutures(demo=False)
        close_side = "sell" if state.position.side == "long" else "buy"
        ex.place_order(SYMBOL, close_side, state.position.size)

    trade = state.close_position(price)
    clear_position()
    if state._broadcast_fn:
        await state._broadcast_fn(state.snapshot())
    return {"status": "ok", "pnl": trade.pnl}


@app.get("/snapshot")
def snapshot():
    return state.snapshot()


_backtest_cache: dict | None = None


@app.get("/backtest")
def backtest_endpoint(
    years: int = 1,
    adx_min: float = 25.0,
    session_filter: bool = True,
    confirmation: bool = True,
):
    global _backtest_cache
    years = min(years, 5)  # Binance.us 15m data starts Sep 2019
    cache_key = f"y{years}_adx{adx_min}_s{int(session_filter)}_c{int(confirmation)}"
    if _backtest_cache and _backtest_cache.get("_key") == cache_key:
        return _backtest_cache
    try:
        from backtest.data import fetch_binance
        from backtest.engine import BacktestEngine

        df = fetch_binance(symbol="BTCUSD", interval=15, days=years * 365)

        engine = BacktestEngine(
            initial_capital=10_000.0,
            risk_pct=0.02, stop_pct=0.015,
            target_mult=2.0, max_position_usd=5_000.0,
            commission_pct=0.0005,
            adx_min=adx_min,
            use_session_filter=session_filter,
            use_confirmation=confirmation,
        )
        result = engine.run(df)
        filters_desc = []
        if adx_min > 0: filters_desc.append(f"ADX>{adx_min:.0f}")
        if session_filter: filters_desc.append("session")
        if confirmation: filters_desc.append("confirm")
        filters_label = "+".join(filters_desc) if filters_desc else "baseline"
        _backtest_cache = {
            "_key": cache_key,
            "status": "ok",
            "gate": "PASS" if result.passes_gate() else "FAIL",
            "total_return_pct": result.total_return_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown_pct": result.max_drawdown_pct,
            "win_rate": result.win_rate,
            "total_trades": result.total_trades,
            "profit_factor": result.profit_factor,
            "years": years,
            "filters": filters_label,
            "note": f"{len(df):,} candles · {df.index[0].date()} → {df.index[-1].date()} · Binance BTCUSDT 15m · {filters_label}",
        }
    except Exception as e:
        _backtest_cache = {"_key": cache_key, "status": "error", "detail": str(e)}
    return _backtest_cache


@app.post("/backtest/reset")
def backtest_reset():
    global _backtest_cache
    _backtest_cache = None
    return {"status": "cache cleared"}


@app.get("/candles")
def candles_endpoint(count: int = 100, interval: int = None):
    import os
    from bot.exchange import KrakenFutures
    demo = os.getenv("KRAKEN_DEMO", "true").lower() == "true"
    symbol = os.getenv("SYMBOL", "PI_XBTUSD")
    interval = interval or int(os.getenv("CANDLE_INTERVAL", "15"))
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
