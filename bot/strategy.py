from enum import Enum
import pandas as pd
import numpy as np
import pandas_ta as ta


class Signal(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class Strategy:
    """
    SuperTrend(10, 3.0) + RSI(14) filter + funding rate overlay.

    Entry rules:
    - BUY:  SuperTrend flips bullish AND RSI < rsi_upper AND funding_rate < threshold
    - SELL: SuperTrend flips bearish AND RSI > rsi_lower AND funding_rate > -threshold
    - HOLD: otherwise
    """

    MIN_CANDLES = 50

    def __init__(
        self,
        supertrend_period: int = 10,
        supertrend_mult: float = 3.0,
        rsi_period: int = 14,
        rsi_upper: float = 65.0,
        rsi_lower: float = 35.0,
        funding_rate_threshold: float = 0.0005,
    ):
        self.st_period = supertrend_period
        self.st_mult = supertrend_mult
        self.rsi_period = rsi_period
        self.rsi_upper = rsi_upper
        self.rsi_lower = rsi_lower
        self.funding_threshold = funding_rate_threshold

    def get_indicators(self, df: pd.DataFrame) -> tuple[float, int]:
        """Returns (rsi, supertrend_direction) for latest candle."""
        st = ta.supertrend(df["high"], df["low"], df["close"],
                           length=self.st_period, multiplier=self.st_mult)
        dir_cols = [c for c in st.columns if "SUPERTd" in c]
        st_dir = int(st[dir_cols[0]].iloc[-1]) if dir_cols else 0
        rsi_series = ta.rsi(df["close"], length=self.rsi_period)
        rsi = float(rsi_series.iloc[-1]) if not np.isnan(rsi_series.iloc[-1]) else 50.0
        return rsi, st_dir

    def compute(self, df: pd.DataFrame, funding_rate: float) -> Signal:
        if len(df) < self.MIN_CANDLES:
            raise ValueError(f"Not enough candles: need {self.MIN_CANDLES}, got {len(df)}")

        # SuperTrend
        st = ta.supertrend(
            df["high"], df["low"], df["close"],
            length=self.st_period, multiplier=self.st_mult
        )

        # Find direction column (SUPERTd_10_3.0)
        dir_cols = [c for c in st.columns if "SUPERTd" in c]
        if not dir_cols:
            return Signal.HOLD
        direction_col = dir_cols[0]

        current_dir = int(st[direction_col].iloc[-1])
        prev_dir = int(st[direction_col].iloc[-2])

        # RSI
        rsi_series = ta.rsi(df["close"], length=self.rsi_period)
        current_rsi = float(rsi_series.iloc[-1])
        if np.isnan(current_rsi):
            return Signal.HOLD

        # Flip detection
        bullish_flip = current_dir == 1 and prev_dir == -1
        bearish_flip = current_dir == -1 and prev_dir == 1

        if bullish_flip and current_rsi < self.rsi_upper and funding_rate < self.funding_threshold:
            return Signal.BUY
        if bearish_flip and current_rsi > self.rsi_lower and funding_rate > -self.funding_threshold:
            return Signal.SELL
        return Signal.HOLD
