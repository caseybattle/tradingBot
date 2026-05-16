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
    SuperTrend(10, 3.0) + RSI(14) + ADX(14) + session filter + confirmation candle.

    Entry rules:
    - BUY:  SuperTrend flips bullish AND RSI < rsi_upper AND funding < threshold
            AND ADX > adx_min (trending) AND not in dead session AND confirmation candle bullish
    - SELL: inverse
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
        adx_min: float = 25.0,           # 0 = disabled
        use_session_filter: bool = True,  # avoid 0-4am ET
        use_confirmation: bool = True,    # wait for candle after flip
    ):
        self.st_period = supertrend_period
        self.st_mult = supertrend_mult
        self.rsi_period = rsi_period
        self.rsi_upper = rsi_upper
        self.rsi_lower = rsi_lower
        self.funding_threshold = funding_rate_threshold
        self.adx_min = adx_min
        self.use_session_filter = use_session_filter
        self.use_confirmation = use_confirmation

    def _adx_ok(self, df: pd.DataFrame) -> bool:
        if self.adx_min <= 0:
            return True
        adx = ta.adx(df["high"], df["low"], df["close"], length=14)
        if adx is None or adx.empty:
            return True
        col = [c for c in adx.columns if c.startswith("ADX_")]
        if not col:
            return True
        val = float(adx[col[0]].iloc[-1])
        return not np.isnan(val) and val >= self.adx_min

    def _session_ok(self, df: pd.DataFrame) -> bool:
        if not self.use_session_filter:
            return True
        ts = df.index[-1]
        if hasattr(ts, "hour"):
            # Dead zone: 0-4am ET = 4-9 UTC (approx, EDT)
            utc_hour = ts.hour
            return not (4 <= utc_hour < 9)
        return True

    def get_indicators(self, df: pd.DataFrame) -> tuple[float, int]:
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

        st = ta.supertrend(df["high"], df["low"], df["close"],
                           length=self.st_period, multiplier=self.st_mult)
        dir_cols = [c for c in st.columns if "SUPERTd" in c]
        if not dir_cols:
            return Signal.HOLD
        direction_col = dir_cols[0]

        current_dir = int(st[direction_col].iloc[-1])
        prev_dir    = int(st[direction_col].iloc[-2])

        rsi_series = ta.rsi(df["close"], length=self.rsi_period)
        current_rsi = float(rsi_series.iloc[-1])
        if np.isnan(current_rsi):
            return Signal.HOLD

        # With confirmation candle: flip must have happened on prev candle, current closes in trend
        if self.use_confirmation:
            prev_prev_dir = int(st[direction_col].iloc[-3]) if len(df) >= 3 else prev_dir
            bullish_flip = prev_dir == 1 and prev_prev_dir == -1
            bearish_flip = prev_dir == -1 and prev_prev_dir == 1
            # Confirmation: current candle closes in trend direction
            conf_bull = df["close"].iloc[-1] > df["open"].iloc[-1]
            conf_bear = df["close"].iloc[-1] < df["open"].iloc[-1]
        else:
            bullish_flip = current_dir == 1 and prev_dir == -1
            bearish_flip = current_dir == -1 and prev_dir == 1
            conf_bull = conf_bear = True

        if not self._session_ok(df):
            return Signal.HOLD
        if not self._adx_ok(df):
            return Signal.HOLD

        if bullish_flip and conf_bull and current_rsi < self.rsi_upper and funding_rate < self.funding_threshold:
            return Signal.BUY
        if bearish_flip and conf_bear and current_rsi > self.rsi_lower and funding_rate > -self.funding_threshold:
            return Signal.SELL
        return Signal.HOLD
