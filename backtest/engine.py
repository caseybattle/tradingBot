import pandas as pd
import numpy as np
from bot.strategy import Strategy, Signal
from bot.risk import RiskManager
from backtest.metrics import compute_metrics, BacktestResult


class BacktestEngine:
    """
    Event-driven backtest on historical OHLCV.
    Walks candle-by-candle, feeds a rolling window to Strategy,
    simulates fills at next open (avoid look-ahead).
    """

    def __init__(
        self,
        initial_capital: float = 10000.0,
        risk_pct: float = 0.02,
        stop_pct: float = 0.015,
        target_mult: float = 2.0,
        max_position_usd: float = 5000.0,
        funding_rate: float = 0.0001,
        commission_pct: float = 0.0005,
    ):
        self.initial_capital = initial_capital
        self.funding_rate = funding_rate
        self.commission_pct = commission_pct
        self.strategy = Strategy()
        self.risk_manager = RiskManager(
            account_balance=initial_capital,
            risk_pct=risk_pct,
            stop_pct=stop_pct,
            target_mult=target_mult,
            max_position_usd=max_position_usd,
        )

    def run(self, df: pd.DataFrame) -> BacktestResult:
        min_window = Strategy.MIN_CANDLES + 1  # +1 so prev candle exists
        if len(df) < min_window:
            raise ValueError(f"Need at least {min_window} candles, got {len(df)}")

        capital = self.initial_capital
        equity = []
        trades = []
        position = None  # dict: {side, entry, size, stop, target, entry_time}

        for i in range(min_window, len(df)):
            window = df.iloc[: i]
            current = df.iloc[i]
            ts = df.index[i]

            # --- check open position for stop/target ---
            if position:
                hi = current["high"]
                lo = current["low"]
                closed = False

                if position["side"] == "long":
                    if lo <= position["stop"]:
                        exit_price = position["stop"]
                        closed = True
                    elif hi >= position["target"]:
                        exit_price = position["target"]
                        closed = True
                else:  # short
                    if hi >= position["stop"]:
                        exit_price = position["stop"]
                        closed = True
                    elif lo <= position["target"]:
                        exit_price = position["target"]
                        closed = True

                if closed:
                    if position["side"] == "long":
                        pnl = (exit_price - position["entry"]) * position["size"]
                    else:
                        pnl = (position["entry"] - exit_price) * position["size"]
                    pnl -= (exit_price * position["size"] * self.commission_pct)
                    capital += pnl
                    trades.append({
                        "entry_time": position["entry_time"],
                        "exit_time": ts,
                        "side": position["side"],
                        "entry": position["entry"],
                        "exit": exit_price,
                        "size": position["size"],
                        "pnl": pnl,
                    })
                    position = None

            # --- no open position: check for signal ---
            if not position:
                try:
                    signal = self.strategy.compute(window, self.funding_rate)
                except ValueError:
                    equity.append(capital)
                    continue

                if signal in (Signal.BUY, Signal.SELL):
                    entry_price = current["open"]  # fill at next open
                    side = "long" if signal == Signal.BUY else "short"
                    size, stop, target = self.risk_manager.size_position(capital, entry_price, side)
                    commission = entry_price * size * self.commission_pct
                    capital -= commission
                    position = {
                        "side": side,
                        "entry": entry_price,
                        "size": size,
                        "stop": stop,
                        "target": target,
                        "entry_time": ts,
                    }

            equity.append(capital)

        equity_series = pd.Series(equity, index=df.index[min_window:])
        return compute_metrics(equity_series, trades)
