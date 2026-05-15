import pandas as pd
import numpy as np
import pytest
from backtest.engine import BacktestEngine
from backtest.metrics import compute_metrics, BacktestResult


def _make_ohlcv(n=300, trend="up") -> pd.DataFrame:
    np.random.seed(7)
    if trend == "up":
        close = 50000 + np.cumsum(np.abs(np.random.randn(n)) * 150)
    else:
        close = 50000 - np.cumsum(np.abs(np.random.randn(n)) * 150)
    close = np.maximum(close, 1000)
    return pd.DataFrame({
        "open": close * (1 - np.abs(np.random.randn(n)) * 0.001),
        "high": close + np.abs(np.random.randn(n)) * 200,
        "low": close - np.abs(np.random.randn(n)) * 200,
        "close": close,
        "volume": np.abs(np.random.randn(n)) * 1000 + 100,
    }, index=pd.date_range("2024-01-01", periods=n, freq="15min"))


def test_engine_returns_result():
    df = _make_ohlcv(300)
    engine = BacktestEngine(initial_capital=10000)
    result = engine.run(df)
    assert isinstance(result, BacktestResult)
    assert result.total_trades >= 0
    assert result.max_drawdown_pct >= 0


def test_engine_requires_min_candles():
    df = _make_ohlcv(20)
    engine = BacktestEngine()
    with pytest.raises(ValueError, match="candles"):
        engine.run(df)


def test_equity_never_negative():
    df = _make_ohlcv(300)
    engine = BacktestEngine(initial_capital=10000)
    result = engine.run(df)
    assert (result.equity_curve >= 0).all()


def test_metrics_gate_pass():
    equity = pd.Series([10000 + i * 10 for i in range(500)],
                       index=pd.date_range("2024-01-01", periods=500, freq="15min"))
    trades = [{"pnl": 50}] * 40 + [{"pnl": -20}] * 10
    result = compute_metrics(equity, trades)
    assert result.passes_gate()


def test_metrics_gate_fail_drawdown():
    # large drawdown scenario
    vals = [10000] * 100 + [5000] * 100 + [8000] * 100
    equity = pd.Series(vals, index=pd.date_range("2024-01-01", periods=300, freq="15min"))
    trades = [{"pnl": -100}] * 10
    result = compute_metrics(equity, trades)
    assert not result.passes_gate()


def test_win_rate_calculation():
    equity = pd.Series([10000] * 100, index=pd.date_range("2024-01-01", periods=100, freq="15min"))
    trades = [{"pnl": 100}] * 3 + [{"pnl": -50}] * 1
    result = compute_metrics(equity, trades)
    assert result.win_rate == 75.0
    assert result.profit_factor == pytest.approx(300 / 50, rel=0.01)
