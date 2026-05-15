import pandas as pd
import numpy as np
import pytest
from bot.strategy import Strategy, Signal


def _make_ohlcv(n=200, trend="up") -> pd.DataFrame:
    np.random.seed(42)
    if trend == "up":
        close = 50000 + np.cumsum(np.abs(np.random.randn(n)) * 200)
    else:
        close = 50000 - np.cumsum(np.abs(np.random.randn(n)) * 200)
    close = np.maximum(close, 1000)
    return pd.DataFrame({
        "open": close - np.abs(np.random.randn(n) * 100),
        "high": close + np.abs(np.random.randn(n) * 200),
        "low": close - np.abs(np.random.randn(n) * 200),
        "close": close,
        "volume": np.abs(np.random.randn(n) * 1000) + 100,
    }, index=pd.date_range("2024-01-01", periods=n, freq="15min"))


def test_signal_enum():
    assert Signal.BUY.value == "buy"
    assert Signal.SELL.value == "sell"
    assert Signal.HOLD.value == "hold"


def test_compute_returns_valid_signal():
    df = _make_ohlcv(200)
    s = Strategy()
    signal = s.compute(df, funding_rate=0.0001)
    assert signal in [Signal.BUY, Signal.SELL, Signal.HOLD]


def test_high_funding_blocks_buy():
    df = _make_ohlcv(200)
    s = Strategy(funding_rate_threshold=0.0005)
    signal = s.compute(df, funding_rate=0.002)
    assert signal != Signal.BUY


def test_negative_funding_blocks_sell():
    df = _make_ohlcv(200)
    s = Strategy(funding_rate_threshold=0.0005)
    signal = s.compute(df, funding_rate=-0.002)
    assert signal != Signal.SELL


def test_requires_min_candles():
    df = _make_ohlcv(10)
    s = Strategy()
    with pytest.raises(ValueError, match="Not enough candles"):
        s.compute(df, funding_rate=0.0)
