import asyncio
import json
import logging
import math
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bot.state import BotState
from bot.trader import Trader
from api.db import (
    save_trade,
    load_trades,
    save_position,
    load_position,
    clear_position,
    save_advisor_signal,
    load_advisor_signals,
    advisor_signal_summary,
)

log = logging.getLogger("api")
state = BotState(initial_capital=float(os.getenv("INITIAL_CAPITAL", "10000")))
_connections: set[WebSocket] = set()
_trader: Trader | None = None
_trader_task: asyncio.Task | None = None


class ChatRequest(BaseModel):
    message: str


class MarketRequest(BaseModel):
    symbol: str


SUPPORTED_MARKETS = [
    {
        "symbol": "PI_XBTUSD",
        "label": "Bitcoin perpetual",
        "base": "BTC",
        "quote": "USD",
        "exchange": "Kraken Futures",
        "backtest_symbol": "BTCUSD",
    },
    {
        "symbol": "PI_ETHUSD",
        "label": "Ether perpetual",
        "base": "ETH",
        "quote": "USD",
        "exchange": "Kraken Futures",
        "backtest_symbol": "ETHUSD",
    },
]

state.active_symbol = os.getenv("SYMBOL", "PI_XBTUSD")


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"


def _is_demo_mode() -> bool:
    return _env_bool("KRAKEN_DEMO", "true")


def _live_trading_allowed() -> bool:
    return _env_bool("ALLOW_LIVE_TRADING", "false")


def _advisor_mode() -> bool:
    return _env_bool("ADVISOR_MODE", "true")


def _can_place_exchange_orders() -> bool:
    return (not _advisor_mode()) and (_is_demo_mode() or _live_trading_allowed())


def _market_config(symbol: str | None = None) -> dict:
    active = symbol or state.active_symbol or os.getenv("SYMBOL", "PI_XBTUSD")
    for market in SUPPORTED_MARKETS:
        if market["symbol"] == active:
            return market
    return {**SUPPORTED_MARKETS[0], "symbol": active, "label": f"{active} custom"}


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
    market = _market_config()
    return {
        "name": "SuperTrend RSI ADX confirmation",
        "status": "candidate",
        "research_basis": "Regime-filtered time-series momentum, using SuperTrend direction, RSI guards, ADX trend filter, funding crowding filter, session filter, and confirmation candle.",
        "market": {
            "symbol": market["symbol"],
            "label": market["label"],
            "exchange": market["exchange"],
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
            "data": f"Binance.us {market['backtest_symbol']} 15m candles",
            "max_years": 5,
            "initial_capital": 10_000,
            "commission_pct": 0.05,
            "slippage_pct": 0.02,
            "gate": "Strict PASS requires full sample, in-sample, out-of-sample, and at least 2 of 3 walk-forward windows.",
        },
    }


def _safety_state() -> dict:
    demo = _is_demo_mode()
    live_allowed = _live_trading_allowed()
    advisor = _advisor_mode()
    return {
        "mode": "advisor" if advisor else "paper" if demo else "live-blocked" if not live_allowed else "live",
        "advisor_mode": advisor,
        "kraken_demo": demo,
        "allow_live_trading": live_allowed,
        "can_place_exchange_orders": _can_place_exchange_orders(),
        "bot_running": _bot_running(),
        "live_trading_default": "disabled",
        "guardrails": [
            "Advisor mode is the default execution path.",
            "Advisor mode tracks live data and produces trade plans without placing orders.",
            "Live orders require KRAKEN_DEMO=false and ALLOW_LIVE_TRADING=true.",
            "Manual and chat order paths are blocked while ADVISOR_MODE=true.",
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


def _advisor_state(record: bool = True) -> dict:
    from bot.risk import RiskManager

    snap = state.snapshot()
    signal = snap["current_signal"]
    price = snap["last_price"]
    rm = RiskManager(account_balance=state.capital)
    side = "long" if signal == "BUY" else "short" if signal == "SELL" else None
    plan = None
    reasons = []

    if snap["position"]:
        position = snap["position"]
        plan = {
            "action": "manage_existing_position",
            "side": position["side"],
            "entry": position["entry"],
            "size": position["size"],
            "stop": position["stop"],
            "target": position["target"],
            "invalidation": "Stop price reached",
            "profit_target": "Target price reached",
        }
    elif price <= 0:
        reasons.append("No live price yet.")
    elif side:
        size, stop, target = rm.size_position(state.capital, price, side)
        plan = {
            "action": "consider_entry",
            "side": side,
            "entry_reference": price,
            "size": size,
            "stop": stop,
            "target": target,
            "risk_usd": round(abs(price - stop) * size, 2),
            "reward_usd": round(abs(target - price) * size, 2),
            "invalidation": "Signal invalid if confirmation breaks or stop is reached.",
        }
    else:
        reasons.extend(_hold_reasons(snap))

    advisor = {
        "mode": "advisor",
        "places_orders": False,
        "live_gate": "locked",
        "symbol": state.active_symbol,
        "signal": signal,
        "confidence": "medium" if side else "low",
        "recommendation": plan or {
            "action": "wait",
            "reason": "No trade plan until all entry filters align.",
            "do_nothing_reason": "; ".join(reasons),
        },
        "risk": _strategy_metadata()["risk"],
        "snapshot": {
            "price": price,
            "rsi": snap["rsi"],
            "supertrend_dir": snap["supertrend_dir"],
            "funding_rate": snap["funding_rate"],
        },
    }
    if record:
        _record_advisor_signal(advisor)
    return advisor


def _record_advisor_signal(advisor: dict) -> dict | None:
    rec = advisor.get("recommendation", {})
    action = rec.get("action")
    if action not in {"consider_entry", "manage_existing_position"}:
        return None

    snap = advisor.get("snapshot", {})
    signal = advisor.get("signal", "HOLD")
    symbol = advisor.get("symbol", state.active_symbol)
    side = rec.get("side")
    entry = rec.get("entry_reference", rec.get("entry"))
    stop = rec.get("stop")
    target = rec.get("target")
    bucket = int((state.last_tick_at or time.time()) // (15 * 60))
    fingerprint = "|".join([
        str(symbol),
        str(signal),
        str(action),
        str(side),
        _fp_number(entry),
        _fp_number(stop),
        _fp_number(target),
        str(bucket),
    ])
    thesis = _advisor_thesis(advisor)
    return save_advisor_signal({
        "fingerprint": fingerprint,
        "symbol": symbol,
        "signal": signal,
        "action": action,
        "side": side,
        "confidence": advisor.get("confidence"),
        "thesis": thesis,
        "invalidation": rec.get("invalidation") or rec.get("do_nothing_reason") or rec.get("reason"),
        "entry_reference": entry,
        "size": rec.get("size"),
        "stop": stop,
        "target": target,
        "risk_usd": rec.get("risk_usd"),
        "price": snap.get("price"),
        "rsi": snap.get("rsi"),
        "supertrend_dir": snap.get("supertrend_dir"),
        "funding_rate": snap.get("funding_rate"),
    })


def _fp_number(value) -> str:
    if value is None:
        return ""
    try:
        return str(round(float(value), 2))
    except (TypeError, ValueError):
        return str(value)


def _advisor_thesis(advisor: dict) -> str:
    rec = advisor.get("recommendation", {})
    side = rec.get("side") or "position"
    entry = rec.get("entry_reference", rec.get("entry"))
    stop = rec.get("stop")
    target = rec.get("target")
    if rec.get("action") == "manage_existing_position":
        return f"Manage existing {side} position. Stop {_fp_number(stop)}, target {_fp_number(target)}."
    return f"Consider {side} entry near {_fp_number(entry)} only if filters remain aligned. Stop {_fp_number(stop)}, target {_fp_number(target)}."


def _hold_reasons(snap: dict) -> list[str]:
    reasons = []
    if snap["supertrend_dir"] == 0:
        reasons.append("SuperTrend direction unknown.")
    else:
        reasons.append("No confirmed SuperTrend flip.")
    if snap["rsi"] >= 65:
        reasons.append("RSI upper guard blocks long entries.")
    if snap["rsi"] <= 35:
        reasons.append("RSI lower guard blocks short entries.")
    if abs(snap["funding_rate"]) >= 0.0005:
        reasons.append("Funding crowding filter is active.")
    if not reasons:
        reasons.append("Filters do not align.")
    return reasons


def _json_safe_number(value):
    if isinstance(value, (int, float)):
        return value if math.isfinite(value) else None
    return value


def _json_safe(value):
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return _json_safe_number(value)


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


@app.get("/strategy/validation")
def strategy_validation_endpoint(years: int = 5, symbol: str = None):
    return _run_validation_report(years=years, symbol=symbol)


@app.get("/strategy/leaderboard")
def strategy_leaderboard_endpoint(years: int = 1, symbols: str = None):
    return _run_leaderboard(years=years, symbols=symbols)


@app.get("/safety")
def safety_endpoint():
    return _safety_state()


@app.get("/advisor")
def advisor_endpoint():
    return _advisor_state()


@app.get("/advisor/journal")
def advisor_journal_endpoint(limit: int = 25, symbol: str = None):
    clean_symbol = symbol.strip().upper() if symbol else None
    return {
        "status": "ok",
        "symbol": clean_symbol or "all",
        "summary": advisor_signal_summary(clean_symbol),
        "signals": load_advisor_signals(limit=max(1, min(limit, 100)), symbol=clean_symbol),
    }


@app.get("/markets")
def markets_endpoint():
    return {
        "active_symbol": state.active_symbol,
        "markets": SUPPORTED_MARKETS,
        "scope": "Kraken crypto first. BTC is the first validated instrument.",
    }


@app.post("/markets/active")
async def set_active_market(request: MarketRequest):
    global _backtest_cache, _validation_cache, _leaderboard_cache
    symbol = request.symbol.strip().upper()
    supported = {market["symbol"] for market in SUPPORTED_MARKETS}
    if symbol not in supported:
        raise HTTPException(status_code=400, detail=f"Unsupported Kraken market: {symbol}")
    if state.position:
        raise HTTPException(status_code=409, detail="Close the current position before changing markets.")
    state.active_symbol = symbol
    state.current_signal = "HOLD"
    state.last_price = 0.0
    state.rsi = 0.0
    state.supertrend_dir = 0
    state.funding_rate = 0.0
    _backtest_cache = None
    _validation_cache = None
    _leaderboard_cache = None
    if state._broadcast_fn:
        await state._broadcast_fn(state.snapshot())
    return markets_endpoint()


@app.get("/mode")
def mode_endpoint():
    safety = _safety_state()
    return {
        "mode": safety["mode"],
        "advisor_mode": safety["advisor_mode"],
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
    SYMBOL = state.active_symbol or os.getenv("SYMBOL", "PI_XBTUSD")

    if not DEMO and not _live_trading_allowed():
        return {
            "error": "live trading is blocked",
            "detail": "Set KRAKEN_DEMO=true for paper trading or explicitly enable ALLOW_LIVE_TRADING=true.",
            "safety": _safety_state(),
        }
    if _advisor_mode():
        return {
            "error": "advisor mode is read only",
            "detail": "ADVISOR_MODE=true blocks manual and automatic order placement. Use /advisor for the trade plan.",
            "advisor": _advisor_state(),
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
    SYMBOL = state.active_symbol or os.getenv("SYMBOL", "PI_XBTUSD")

    if not DEMO and not _live_trading_allowed():
        return {
            "error": "live trading is blocked",
            "detail": "Close is blocked because the app is configured for live Kraken without ALLOW_LIVE_TRADING=true.",
            "safety": _safety_state(),
        }
    if _advisor_mode():
        return {
            "error": "advisor mode is read only",
            "detail": "ADVISOR_MODE=true blocks manual and automatic closes. Use /advisor for the exit plan.",
            "advisor": _advisor_state(),
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
_validation_cache: dict | None = None
_leaderboard_cache: dict | None = None


def _run_validation_report(years: int = 5, symbol: str = None) -> dict:
    global _validation_cache
    from backtest.data import fetch_binance
    from backtest.engine import BacktestEngine
    from backtest.validation import build_validation_report

    years = max(1, min(years, 5))
    market = _market_config(symbol)
    cache_key = f"{market['symbol']}_y{years}_strict"
    if _validation_cache and _validation_cache.get("_key") == cache_key:
        return _validation_cache

    fee_pct = 0.0005
    slippage_pct = 0.0002
    try:
        df = fetch_binance(symbol=market["backtest_symbol"], interval=15, days=years * 365)

        def engine_factory():
            return BacktestEngine(
                initial_capital=10_000.0,
                risk_pct=0.02,
                stop_pct=0.015,
                target_mult=2.0,
                max_position_usd=5_000.0,
                commission_pct=fee_pct,
                slippage_pct=slippage_pct,
            )

        report = build_validation_report(
            df,
            engine_factory,
            symbol=market["symbol"],
            data_source=f"Binance.us {market['backtest_symbol']} 15m candles",
            interval_minutes=15,
            years=years,
            fee_pct=fee_pct,
            slippage_pct=slippage_pct,
        )
        _validation_cache = {"_key": cache_key, **_json_safe(report)}
    except Exception as e:
        _validation_cache = {
            "_key": cache_key,
            "status": "error",
            "gate": "FAIL",
            "strict_pass": False,
            "symbol": market["symbol"],
            "detail": str(e),
        }
    return _validation_cache


def _run_leaderboard(years: int = 1, symbols: str = None) -> dict:
    global _leaderboard_cache
    from backtest.data import fetch_binance
    from backtest.leaderboard import build_leaderboard_rows, rank_rows, strategy_variants

    years = max(1, min(years, 5))
    selected_symbols = _selected_market_symbols(symbols)
    cache_key = f"leaderboard_y{years}_{','.join(selected_symbols)}"
    if _leaderboard_cache and _leaderboard_cache.get("_key") == cache_key:
        return _leaderboard_cache

    rows = []
    errors = []
    fee_pct = 0.0005
    slippage_pct = 0.0002
    variants = strategy_variants()

    for market_symbol in selected_symbols:
        market = _market_config(market_symbol)
        try:
            df = fetch_binance(symbol=market["backtest_symbol"], interval=15, days=years * 365)
            rows.extend(build_leaderboard_rows(
                df=df,
                symbol=market["symbol"],
                label=market["label"],
                data_source=f"Binance.us {market['backtest_symbol']} 15m candles",
                interval_minutes=15,
                years=years,
                fee_pct=fee_pct,
                slippage_pct=slippage_pct,
                variants=variants,
            ))
        except Exception as e:
            errors.append({"symbol": market["symbol"], "detail": str(e)})

    ranked = rank_rows(rows)
    _leaderboard_cache = {
        "_key": cache_key,
        "status": "ok" if ranked else "error",
        "years": years,
        "symbols": selected_symbols,
        "candidate_count": len(ranked),
        "trusted_count": sum(1 for row in ranked if row["strict_pass"]),
        "trust_state": "locked" if not any(row["strict_pass"] for row in ranked) else "candidate_passed",
        "rows": _json_safe(ranked),
        "errors": errors,
        "assumptions": {
            "fee_pct_per_fill": round(fee_pct * 100, 4),
            "slippage_pct_per_fill": round(slippage_pct * 100, 4),
            "live_orders": "blocked; advisor-only",
        },
    }
    return _leaderboard_cache


def _selected_market_symbols(symbols: str | None) -> list[str]:
    supported = {market["symbol"] for market in SUPPORTED_MARKETS}
    if not symbols:
        return [market["symbol"] for market in SUPPORTED_MARKETS]
    selected = []
    for raw in symbols.split(","):
        symbol = raw.strip().upper()
        if symbol in supported and symbol not in selected:
            selected.append(symbol)
    return selected or [state.active_symbol or SUPPORTED_MARKETS[0]["symbol"]]


@app.get("/backtest")
def backtest_endpoint(
    years: int = 1,
    symbol: str = None,
    adx_min: float = 25.0,
    session_filter: bool = True,
    confirmation: bool = True,
):
    global _backtest_cache
    years = max(1, min(years, 5))  # Binance.us 15m data starts Sep 2019
    market = _market_config(symbol)
    cache_key = f"{market['symbol']}_y{years}_adx{adx_min}_s{int(session_filter)}_c{int(confirmation)}"
    if _backtest_cache and _backtest_cache.get("_key") == cache_key:
        return _backtest_cache
    try:
        from backtest.data import fetch_binance
        from backtest.engine import BacktestEngine

        df = fetch_binance(symbol=market["backtest_symbol"], interval=15, days=years * 365)

        engine = BacktestEngine(
            initial_capital=10_000.0,
            risk_pct=0.02, stop_pct=0.015,
            target_mult=2.0, max_position_usd=5_000.0,
            commission_pct=0.0005,
            slippage_pct=0.0002,
            adx_min=adx_min,
            use_session_filter=session_filter,
            use_confirmation=confirmation,
        )
        result = engine.run(df)
        validation = _run_validation_report(years=years, symbol=market["symbol"])
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
            "symbol": market["symbol"],
            "filters": filters_label,
            "data_source": f"Binance.us {market['backtest_symbol']} 15m candles",
            "fees": "0.05% commission per fill",
            "slippage": "0.02% modeled per fill",
            "gate_rules": "Strict PASS requires full sample, in-sample, out-of-sample, and at least 2 of 3 walk-forward windows.",
            "validation": validation,
            "in_sample": validation.get("in_sample"),
            "out_of_sample": validation.get("out_of_sample"),
            "walk_forward": validation.get("walk_forward"),
            "strategy": _strategy_metadata(),
            "note": f"{len(df):,} candles · {df.index[0].date()} to {df.index[-1].date()} · {market['backtest_symbol']} 15m · {filters_label}",
        }
    except Exception as e:
        _backtest_cache = {"_key": cache_key, "status": "error", "detail": str(e)}
    return _backtest_cache


@app.post("/backtest/reset")
def backtest_reset():
    global _backtest_cache, _validation_cache, _leaderboard_cache
    _backtest_cache = None
    _validation_cache = None
    _leaderboard_cache = None
    return {"status": "cache cleared"}


@app.get("/candles")
def candles_endpoint(count: int = 100, interval: int = None):
    import os
    from bot.exchange import KrakenFutures
    demo = os.getenv("KRAKEN_DEMO", "true").lower() == "true"
    symbol = state.active_symbol or os.getenv("SYMBOL", "PI_XBTUSD")
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

    if any(term in text for term in ("leaderboard", "rank", "compare strategies", "best strategy")):
        data = strategy_leaderboard_endpoint(years=1)
        return {
            "intent": "show_leaderboard",
            "answer": "Validation leaderboard loaded. Live gate stays locked until a candidate passes strict proof.",
            "data": data,
        }

    if any(term in text for term in ("journal", "signal log", "signal history")):
        data = advisor_journal_endpoint(limit=25)
        return {
            "intent": "show_advisor_journal",
            "answer": "Advisor signal journal loaded. It records actionable advisor plans without placing orders.",
            "data": data,
        }

    if any(term in text for term in ("validation", "proof", "proven")):
        data = strategy_validation_endpoint(years=5)
        return {
            "intent": "show_validation",
            "answer": "Strict validation report loaded. Strategy is a candidate until the proof gate passes.",
            "data": data,
        }

    if any(term in text for term in ("advisor", "advise", "trade plan")):
        return {
            "intent": "show_advisor",
            "answer": "Advisor mode gives a trade plan without placing orders.",
            "data": _advisor_state(),
        }

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
            "answer": "Advisor mode is the active safety path. Live trading is disabled unless explicitly gated.",
            "data": {"strategy": _strategy_metadata()["risk"], "safety": _safety_state()},
        }

    if "start" in text and any(term in text for term in ("bot", "paper", "trading")):
        result = await start_mode_endpoint()
        return {"intent": "start_paper_bot", "answer": "Advisor scanner start command handled.", "data": result}

    if "stop" in text and any(term in text for term in ("bot", "paper", "trading")):
        result = await stop_mode_endpoint()
        return {"intent": "stop_paper_bot", "answer": "Advisor scanner stop command handled.", "data": result}

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
        "answer": "Approved commands: show advisor, show journal, show leaderboard, show validation, run backtest, explain signal, show risk, start paper bot, stop paper bot, close paper position.",
        "approved_intents": [
            "show_advisor",
            "show_advisor_journal",
            "show_leaderboard",
            "show_validation",
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
