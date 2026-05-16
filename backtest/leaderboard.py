import math
from collections.abc import Callable

import pandas as pd

from backtest.engine import BacktestEngine
from backtest.metrics import compute_metrics, BacktestResult
from backtest.validation import build_validation_report
from bot.risk import RiskManager


class MomentumEngine:
    """
    Simple time-series momentum baseline.
    Uses past return as direction, then applies the same risk model, fees,
    slippage, stop, target, and max hold rules as a sanity benchmark.
    """

    def __init__(
        self,
        *,
        lookback_candles: int,
        threshold_pct: float,
        max_hold_candles: int,
        initial_capital: float = 10000.0,
        risk_pct: float = 0.02,
        stop_pct: float = 0.015,
        target_mult: float = 2.0,
        max_position_usd: float = 5000.0,
        commission_pct: float = 0.0005,
        slippage_pct: float = 0.0002,
    ):
        self.lookback_candles = lookback_candles
        self.threshold_pct = threshold_pct
        self.max_hold_candles = max_hold_candles
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.risk_manager = RiskManager(
            account_balance=initial_capital,
            risk_pct=risk_pct,
            stop_pct=stop_pct,
            target_mult=target_mult,
            max_position_usd=max_position_usd,
        )

    def run(self, df: pd.DataFrame) -> BacktestResult:
        min_window = max(self.lookback_candles + 1, 52)
        if len(df) <= min_window:
            raise ValueError(f"Need at least {min_window + 1} candles, got {len(df)}")

        capital = self.initial_capital
        equity = []
        trades = []
        position = None

        for i in range(min_window, len(df)):
            current = df.iloc[i]
            ts = df.index[i]

            if position:
                high = current["high"]
                low = current["low"]
                held = i - position["entry_index"]
                exit_price = None

                if position["side"] == "long":
                    if low <= position["stop"]:
                        exit_price = position["stop"]
                    elif high >= position["target"]:
                        exit_price = position["target"]
                else:
                    if high >= position["stop"]:
                        exit_price = position["stop"]
                    elif low <= position["target"]:
                        exit_price = position["target"]

                if exit_price is None and held >= self.max_hold_candles:
                    exit_price = current["close"]

                if exit_price is not None:
                    if position["side"] == "long":
                        fill_price = exit_price * (1 - self.slippage_pct)
                        pnl = (fill_price - position["entry"]) * position["size"]
                    else:
                        fill_price = exit_price * (1 + self.slippage_pct)
                        pnl = (position["entry"] - fill_price) * position["size"]
                    pnl -= fill_price * position["size"] * self.commission_pct
                    capital += pnl
                    trades.append({
                        "entry_time": position["entry_time"],
                        "exit_time": ts,
                        "side": position["side"],
                        "entry": position["entry"],
                        "exit": fill_price,
                        "size": position["size"],
                        "pnl": pnl,
                    })
                    position = None

            if not position:
                past_close = df["close"].iloc[i - self.lookback_candles]
                latest_close = df["close"].iloc[i - 1]
                momentum = latest_close / past_close - 1
                side = None
                if momentum >= self.threshold_pct:
                    side = "long"
                elif momentum <= -self.threshold_pct:
                    side = "short"

                if side:
                    entry_price = current["open"]
                    fill_price = entry_price * (1 + self.slippage_pct) if side == "long" else entry_price * (1 - self.slippage_pct)
                    size, stop, target = self.risk_manager.size_position(capital, fill_price, side)
                    capital -= fill_price * size * self.commission_pct
                    position = {
                        "side": side,
                        "entry": fill_price,
                        "size": size,
                        "stop": stop,
                        "target": target,
                        "entry_time": ts,
                        "entry_index": i,
                    }

            equity.append(capital)

        equity_series = pd.Series(equity, index=df.index[min_window:])
        return compute_metrics(equity_series, trades)


def strategy_variants() -> list[dict]:
    return [
        {
            "id": "supertrend_rsi_adx",
            "name": "SuperTrend RSI ADX",
            "family": "regime_filtered_momentum",
            "description": "Current candidate strategy with SuperTrend flip, RSI guard, ADX, session, and confirmation filters.",
            "factory": lambda: BacktestEngine(adx_min=25.0, use_session_filter=True, use_confirmation=True),
        },
        {
            "id": "tsmom_4h",
            "name": "TSMOM 4H",
            "family": "time_series_momentum",
            "description": "Four-hour lookback momentum benchmark with same risk, fees, slippage, stops, and targets.",
            "factory": lambda: MomentumEngine(lookback_candles=16, threshold_pct=0.003, max_hold_candles=32),
        },
        {
            "id": "tsmom_1d",
            "name": "TSMOM 1D",
            "family": "time_series_momentum",
            "description": "One-day lookback momentum benchmark with same risk, fees, slippage, stops, and targets.",
            "factory": lambda: MomentumEngine(lookback_candles=96, threshold_pct=0.01, max_hold_candles=96),
        },
    ]


def build_leaderboard_rows(
    *,
    df: pd.DataFrame,
    symbol: str,
    label: str,
    data_source: str,
    interval_minutes: int,
    years: int,
    fee_pct: float,
    slippage_pct: float,
    variants: list[dict] | None = None,
) -> list[dict]:
    rows = []
    for variant in variants or strategy_variants():
        report = build_validation_report(
            df,
            variant["factory"],
            symbol=symbol,
            data_source=data_source,
            interval_minutes=interval_minutes,
            years=years,
            fee_pct=fee_pct,
            slippage_pct=slippage_pct,
        )
        rows.append(_row_from_report(report, variant, label))
    return rows


def rank_rows(rows: list[dict]) -> list[dict]:
    ranked = sorted(rows, key=lambda row: (row["strict_pass"], row["score"]), reverse=True)
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
    return ranked


def _row_from_report(report: dict, variant: dict, market_label: str) -> dict:
    full = report.get("full_sample", {}) if report.get("status") == "ok" else {}
    in_sample = report.get("in_sample", {}) if report.get("status") == "ok" else {}
    out_sample = report.get("out_of_sample", {}) if report.get("status") == "ok" else {}
    score = _score(full, out_sample, report.get("strict_pass", False))
    return {
        "rank": None,
        "strategy_id": variant["id"],
        "strategy_name": variant["name"],
        "family": variant["family"],
        "description": variant["description"],
        "symbol": report.get("symbol"),
        "market_label": market_label,
        "gate": report.get("gate", "FAIL"),
        "strict_pass": bool(report.get("strict_pass", False)),
        "score": score,
        "status": report.get("status"),
        "reason": report.get("reason"),
        "full_sample": _compact_metrics(full),
        "in_sample": _compact_metrics(in_sample),
        "out_of_sample": _compact_metrics(out_sample),
        "assumptions": report.get("assumptions", {}),
    }


def _compact_metrics(metrics: dict) -> dict:
    return {
        "gate": metrics.get("gate", "FAIL"),
        "sharpe_ratio": metrics.get("sharpe_ratio"),
        "max_drawdown_pct": metrics.get("max_drawdown_pct"),
        "profit_factor": metrics.get("profit_factor"),
        "total_return_pct": metrics.get("total_return_pct"),
        "total_trades": metrics.get("total_trades"),
    }


def _score(full: dict, out_sample: dict, strict_pass: bool) -> float:
    if not full:
        return -9999.0
    sharpe = float(out_sample.get("sharpe_ratio") or full.get("sharpe_ratio") or 0)
    drawdown = float(out_sample.get("max_drawdown_pct") or full.get("max_drawdown_pct") or 100)
    profit_factor = full.get("profit_factor") or 0
    if math.isinf(profit_factor):
        profit_factor = 5.0
    trade_count = min(float(full.get("total_trades") or 0), 200.0)
    total_return = float(full.get("total_return_pct") or 0)
    trust_bonus = 1000.0 if strict_pass else 0.0
    return round(trust_bonus + sharpe * 100.0 + float(profit_factor) * 25.0 + total_return * 0.5 + trade_count * 0.1 - drawdown * 2.0, 2)
