import pandas as pd
import numpy as np
import pandas_ta as ta
from bot.risk import RiskManager
from backtest.metrics import compute_metrics, BacktestResult


class BacktestEngine:
    """
    Vectorized backtest: pre-computes all indicators once, then walks candle-by-candle.
    O(n) instead of O(n²) — runs 1 year of 15m data in seconds.
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
        adx_min: float = 25.0,
        use_session_filter: bool = True,
        use_confirmation: bool = True,
    ):
        self.initial_capital     = initial_capital
        self.funding_rate        = funding_rate
        self.commission_pct      = commission_pct
        self.adx_min             = adx_min
        self.use_session_filter  = use_session_filter
        self.use_confirmation    = use_confirmation
        self.risk_manager        = RiskManager(
            account_balance=initial_capital,
            risk_pct=risk_pct,
            stop_pct=stop_pct,
            target_mult=target_mult,
            max_position_usd=max_position_usd,
        )
        # Strategy params (mirrors Strategy defaults)
        self.st_period   = 10
        self.st_mult     = 3.0
        self.rsi_period  = 14
        self.rsi_upper   = 65.0
        self.rsi_lower   = 35.0

    def _precompute(self, df: pd.DataFrame):
        """Compute SuperTrend + RSI + ADX once for the full dataframe."""
        st = ta.supertrend(df["high"], df["low"], df["close"],
                           length=self.st_period, multiplier=self.st_mult)
        dir_cols = [c for c in st.columns if "SUPERTd" in c]
        direction = st[dir_cols[0]] if dir_cols else pd.Series(0, index=df.index)

        rsi = ta.rsi(df["close"], length=self.rsi_period)

        adx_val = None
        if self.adx_min > 0:
            adx_df = ta.adx(df["high"], df["low"], df["close"], length=14)
            if adx_df is not None and not adx_df.empty:
                adx_cols = [c for c in adx_df.columns if c.startswith("ADX_")]
                if adx_cols:
                    adx_val = adx_df[adx_cols[0]]

        return direction, rsi, adx_val

    def run(self, df: pd.DataFrame) -> BacktestResult:
        MIN_WINDOW = 51  # enough for SuperTrend(10) + RSI(14) to warm up
        if len(df) < MIN_WINDOW + 1:
            raise ValueError(f"Need at least {MIN_WINDOW + 1} candles, got {len(df)}")

        direction, rsi, adx_series = self._precompute(df)

        capital  = self.initial_capital
        equity   = []
        trades   = []
        position = None

        for i in range(MIN_WINDOW, len(df)):
            current  = df.iloc[i]
            ts       = df.index[i]
            curr_dir = int(direction.iloc[i])
            prev_dir = int(direction.iloc[i - 1])
            curr_rsi = float(rsi.iloc[i]) if not np.isnan(rsi.iloc[i]) else 50.0

            # Check stop/target on open position
            if position:
                hi, lo = current["high"], current["low"]
                closed = False

                if position["side"] == "long":
                    if lo <= position["stop"]:
                        exit_price, closed = position["stop"], True
                    elif hi >= position["target"]:
                        exit_price, closed = position["target"], True
                else:
                    if hi >= position["stop"]:
                        exit_price, closed = position["stop"], True
                    elif lo <= position["target"]:
                        exit_price, closed = position["target"], True

                if closed:
                    if position["side"] == "long":
                        pnl = (exit_price - position["entry"]) * position["size"]
                    else:
                        pnl = (position["entry"] - exit_price) * position["size"]
                    pnl -= exit_price * position["size"] * self.commission_pct
                    capital += pnl
                    trades.append({
                        "entry_time": position["entry_time"],
                        "exit_time":  ts,
                        "side":       position["side"],
                        "entry":      position["entry"],
                        "exit":       exit_price,
                        "size":       position["size"],
                        "pnl":        pnl,
                    })
                    position = None

            # Look for signal when flat
            if not position:
                # Session filter: skip UTC 4-9am (0-4am ET)
                if self.use_session_filter and hasattr(ts, "hour") and (4 <= ts.hour < 9):
                    equity.append(capital)
                    continue

                # ADX filter
                if adx_series is not None:
                    adx_val = float(adx_series.iloc[i])
                    if not np.isnan(adx_val) and adx_val < self.adx_min:
                        equity.append(capital)
                        continue

                # Flip detection with optional confirmation candle
                if self.use_confirmation and i >= 2:
                    prev_prev_dir = int(direction.iloc[i - 2])
                    bullish_flip = prev_dir == 1 and prev_prev_dir == -1
                    bearish_flip = prev_dir == -1 and prev_prev_dir == 1
                    conf_bull = current["close"] > current["open"]
                    conf_bear = current["close"] < current["open"]
                else:
                    bullish_flip = curr_dir == 1 and prev_dir == -1
                    bearish_flip = curr_dir == -1 and prev_dir == 1
                    conf_bull = conf_bear = True

                side = None
                if bullish_flip and conf_bull and curr_rsi < self.rsi_upper and self.funding_rate < 0.0005:
                    side = "long"
                elif bearish_flip and conf_bear and curr_rsi > self.rsi_lower and self.funding_rate > -0.0005:
                    side = "short"

                if side:
                    entry_price = current["open"]
                    size, stop, target = self.risk_manager.size_position(capital, entry_price, side)
                    capital -= entry_price * size * self.commission_pct
                    position = {
                        "side": side, "entry": entry_price, "size": size,
                        "stop": stop, "target": target, "entry_time": ts,
                    }

            equity.append(capital)

        equity_series = pd.Series(equity, index=df.index[MIN_WINDOW:])
        return compute_metrics(equity_series, trades)
