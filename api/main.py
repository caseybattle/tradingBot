import asyncio
import json
import logging
import math
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bot.state import BotState
from bot.trader import Trader
from api.db import save_trade, load_trades, save_position, load_position, clear_position

log = logging.getLogger("api")
state = BotState(initial_capital=float(os.getenv("INITIAL_CAPITAL", "10000")))
_connections: set[WebSocket] = set()
_trader: Trader | None = None
_trader_task: asyncio.Task | None = None


class ChatRequest(BaseModel):
    message: str


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"


def _is_demo_mode() -> bool:
    return _env_bool("KRAKEN_DEMO", "true")


def _live_trading_allowed() -> bool:
    return _env_bool("ALLOW_LIVE_TRADING", "false")


def _can_place_exchange_orders() -> bool:
    return _is_demo_mode() or _live_trading_allowed()


def _bot_running() -> bool:
    return _trader_task is not None and not _trader_task.done()


async def _start_trader() -> bool:
    global _trader, _trader_task
    if _bot_running():
        return False
    _trader = Trader(state)
    _trader_task = asyncio.create_task(_trader.run())
    return True


async def _stop_trader() -> bool:
    global _trader, _trader_task
    if not _bot_running():
        _trader = None
        _trader_task = None
        return False
    _trader.stop()
    _trader_task.cancel()
    try:
        await _trader_task
    except asyncio.CancelledError:
        pass
    _trader = None
    _trader_task = None
    return True


def _strategy_metadata() -> dict:
    from bot.strategy import Strategy
    from bot.risk import RiskManager

    strategy = Strategy()
    risk = RiskManager(account_balance=state.capital)
    return {
        "name": "SuperTrend RSI ADX confirmation",
        "market": {
            "symbol": os.getenv("SYMBOL", "PI_XBTUSD"),
            "exchange": "Kraken Futures",
            "candle_interval_minutes": int(os.getenv("CANDLE_INTERVAL", "15")),
        },
        "parameters": {
            "supertrend_period": strategy.st_period,
            "supertrend_multiplier": strategy.st_mult,
            "rsi_period": strategy.rsi_period,
            "rsi_upper": strategy.rsi_upper,
            "rsi_lower": strategy.rsi_lower,
            "funding_rate_threshold": strategy.funding_threshold,
            "adx_min": strategy.adx_min,
            "session_filter": strategy.use_session_filter,
            "confirmation_candle": strategy.use_confirmation,
        },
        "entry_rules": {
            "long": "SuperTrend bullish flip, bullish confirmation candle, RSI below upper guard, funding below threshold, ADX trend filter, session filter open.",
            "short": "SuperTrend bearish flip, bearish confirmation candle, RSI above lower guard, funding above negative threshold, ADX trend filter, session filter open.",
            "hold": "Any missing confirmation, stale or insufficient candles, blocked session, weak ADX, or funding crowding filter.",
        },
        "risk": {
            "risk_per_trade_pct": risk.risk_pct * 100,
            "stop_distance_pct": risk.stop_pct * 100,
            "target_multiple": risk.target_mult,
            "max_position_usd": risk.max_position_usd,
            "protective_exits_required": True,
        },
        "backtest_source": {
            "data": "Binance.us BTCUSD 15m candles",
            "max_years": 5,
            "initial_capital": 10_000,
            "commission_pct": 0.05,
            "slippage": "not modeled",
            "gate": "PASS when Sharpe >= 0.8 and max drawdown <= 35%",
        },
    }


def _safety_state() -> dict:
    demo = _is_demo_mode()
    live_allowed = _live_trading_allowed()
    return {
        "mode": "paper" if demo else "live-blocked" if not live_allowed else "live",
        "kraken_demo": demo,
        "allow_live_trading": live_allowed,
        "can_place_exchange_orders": _can_place_exchange_orders(),
        "bot_running": _bot_running(),
        "live_trading_default": "disabled",
        "guardrails": [
            "Paper trading is the default execution path.",
            "Live orders require KRAKEN_DEMO=false and ALLOW_LIVE_TRADING=true.",
            "Manual and chat live order paths are blocked unless the explicit live gate is enabled.",
            "Every opened position must include stop and target prices.",
            "Position size is capped by max_position_usd.",
        ],
        "kraken_docs": {
            "futures_intro": "https://docs.kraken.com/api/docs/guides/futures-introduction",
            "rest_auth": "https://docs.kraken.com/api/docs/guides/futures-rest",
            "send_order": "https://docs.kraken.com/api/docs/futures-api/trading/send-order",
            "dead_man_switch": "https://docs.kraken.com/api/docs/futures-api/trading/cancel-all-orders-after/",
        },
    }


def _signal_explanation() -> dict:
    snap = state.snapshot()
    metadata = _strategy_metadata()
    signal = snap["current_signal"]
    return {
        "signal": signal,
        "summary": (
            f"Current signal is {signal}. RSI is {snap['rsi']}, "
            f"SuperTrend direction is {snap['supertrend_dir']}, "
            f"funding is {snap['funding_rate']}."
        ),
        "position": snap["position"],
        "rules": metadata["entry_rules"],
    }


def _json_safe_number(value):
    if isinstance(value, (int, float)):
        return value if math.isfinite(value) else None
    return value


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
    await _start_trader()
    yield
    await _stop_trader()


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


@app.get("/strategy")
def strategy_endpoint():
    return _strategy_metadata()


@app.get("/safety")
def safety_endpoint():
    return _safety_state()


@app.get("/mode")
def mode_endpoint():
    safety = _safety_state()
    return {
        "mode": safety["mode"],
        "bot_running": safety["bot_running"],
        "kraken_demo": safety["kraken_demo"],
        "allow_live_trading": safety["allow_live_trading"],
    }


@app.post("/mode/start")
async def start_mode_endpoint():
    started = await _start_trader()
    if state._broadcast_fn:
        await state._broadcast_fn(state.snapshot())
    return {"status": "started" if started else "already_running", **mode_endpoint()}


@app.post("/mode/stop")
async def stop_mode_endpoint():
    stopped = await _stop_trader()
    if state._broadcast_fn:
        await state._broadcast_fn(state.snapshot())
    return {"status": "stopped" if stopped else "already_stopped", **mode_endpoint()}


@app.post("/order")
async def place_manual_order(side: str, size: float = None):
    """Manual trade: side=long|short. Uses risk manager if size omitted."""
    import os
    from bot.risk import RiskManager
    from bot.exchange import KrakenFutures
    DEMO = os.getenv("KRAKEN_DEMO", "true").lower() == "true"
    SYMBOL = os.getenv("SYMBOL", "PI_XBTUSD")

    if not _can_place_exchange_orders():
        return {
            "error": "live trading is blocked",
            "detail": "Set KRAKEN_DEMO=true for paper trading or explicitly enable ALLOW_LIVE_TRADING=true.",
            "safety": _safety_state(),
        }
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


@app.post("/open")
async def open_position_endpoint(side: str, size: float = None):
    return await place_manual_order(side=side, size=size)


@app.post("/close")
async def close_position_endpoint():
    """Close the current open position."""
    import os
    from bot.exchange import KrakenFutures
    DEMO = os.getenv("KRAKEN_DEMO", "true").lower() == "true"
    SYMBOL = os.getenv("SYMBOL", "PI_XBTUSD")

    if not _can_place_exchange_orders():
        return {
            "error": "live trading is blocked",
            "detail": "Close is blocked because the app is configured for live Kraken without ALLOW_LIVE_TRADING=true.",
            "safety": _safety_state(),
        }
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
    years = max(1, min(years, 5))  # Binance.us 15m data starts Sep 2019
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
            "total_return_pct": _json_safe_number(result.total_return_pct),
            "sharpe_ratio": _json_safe_number(result.sharpe_ratio),
            "max_drawdown_pct": _json_safe_number(result.max_drawdown_pct),
            "win_rate": _json_safe_number(result.win_rate),
            "total_trades": result.total_trades,
            "profit_factor": _json_safe_number(result.profit_factor),
            "years": years,
            "filters": filters_label,
            "data_source": "Binance.us BTCUSD 15m candles",
            "fees": "0.05% commission per fill",
            "slippage": "not modeled",
            "gate_rules": "PASS when Sharpe >= 0.8 and max drawdown <= 35%",
            "strategy": _strategy_metadata(),
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


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    text = request.message.strip().lower()
    if not text:
        return {"intent": "empty", "answer": "Send a command or status question."}

    if any(term in text for term in ("backtest", "run test", "performance")):
        data = backtest_endpoint(years=1)
        return {
            "intent": "run_backtest",
            "answer": "Ran the 1 year paper backtest with current filters.",
            "data": data,
        }

    if any(term in text for term in ("signal", "why", "explain")):
        return {
            "intent": "explain_signal",
            "answer": "Here is the current deterministic signal state.",
            "data": _signal_explanation(),
        }

    if any(term in text for term in ("risk", "safety", "guardrail", "mode")):
        return {
            "intent": "show_risk",
            "answer": "Paper trading is the active safety path. Live trading is disabled unless explicitly gated.",
            "data": {"strategy": _strategy_metadata()["risk"], "safety": _safety_state()},
        }

    if "start" in text and any(term in text for term in ("bot", "paper", "trading")):
        result = await start_mode_endpoint()
        return {"intent": "start_paper_bot", "answer": "Paper bot start command handled.", "data": result}

    if "stop" in text and any(term in text for term in ("bot", "paper", "trading")):
        result = await stop_mode_endpoint()
        return {"intent": "stop_paper_bot", "answer": "Paper bot stop command handled.", "data": result}

    if "close" in text and any(term in text for term in ("position", "trade", "paper")):
        if not _is_demo_mode():
            return {
                "intent": "close_paper_position",
                "answer": "Close rejected because the app is not in paper mode.",
                "data": _safety_state(),
            }
        result = await close_position_endpoint()
        return {"intent": "close_paper_position", "answer": "Paper close command handled.", "data": result}

    return {
        "intent": "unsupported",
        "answer": "Approved commands: run backtest, explain signal, show risk, start paper bot, stop paper bot, close paper position.",
        "approved_intents": [
            "run_backtest",
            "explain_signal",
            "show_risk",
            "start_paper_bot",
            "stop_paper_bot",
            "close_paper_position",
        ],
    }


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
