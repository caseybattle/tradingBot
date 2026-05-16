import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from api import main as api_main


client = TestClient(api_main.app)


def _make_ohlcv(n=80) -> pd.DataFrame:
    np.random.seed(11)
    close = 50000 + np.cumsum(np.random.randn(n) * 40)
    open_ = close + np.random.randn(n) * 10
    high = np.maximum(open_, close) + 50
    low = np.minimum(open_, close) - 50
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.random.rand(n) * 100,
        },
        index=pd.date_range("2024-01-01", periods=n, freq="15min"),
    )


def test_strategy_metadata_endpoint():
    res = client.get("/strategy")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "SuperTrend RSI ADX confirmation"
    assert data["parameters"]["adx_min"] == 25.0
    assert data["risk"]["protective_exits_required"] is True
    assert data["backtest_source"]["max_years"] == 5


def test_safety_defaults_to_paper(monkeypatch):
    monkeypatch.setenv("KRAKEN_DEMO", "true")
    monkeypatch.delenv("ALLOW_LIVE_TRADING", raising=False)

    res = client.get("/safety")
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "paper"
    assert data["kraken_demo"] is True
    assert data["allow_live_trading"] is False


def test_live_order_is_blocked_without_explicit_gate(monkeypatch):
    monkeypatch.setenv("KRAKEN_DEMO", "false")
    monkeypatch.delenv("ALLOW_LIVE_TRADING", raising=False)
    api_main.state.position = None
    api_main.state.last_price = 50000

    res = client.post("/order?side=long")
    assert res.status_code == 200
    data = res.json()
    assert data["error"] == "live trading is blocked"
    assert data["safety"]["mode"] == "live-blocked"


def test_chat_rejects_unsupported_live_trade_request(monkeypatch):
    monkeypatch.setenv("KRAKEN_DEMO", "true")

    res = client.post("/chat", json={"message": "buy btc live now"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "unsupported"
    assert "run_backtest" in data["approved_intents"]


def test_chat_explains_current_signal(monkeypatch):
    monkeypatch.setenv("KRAKEN_DEMO", "true")
    api_main.state.current_signal = "HOLD"
    api_main.state.rsi = 52.4
    api_main.state.supertrend_dir = 1
    api_main.state.funding_rate = 0.0001

    res = client.post("/chat", json={"message": "explain signal"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "explain_signal"
    assert data["data"]["signal"] == "HOLD"


def test_backtest_years_are_capped(monkeypatch):
    import backtest.data

    captured = {}

    def fake_fetch_binance(symbol, interval, days):
        captured["symbol"] = symbol
        captured["interval"] = interval
        captured["days"] = days
        return _make_ohlcv()

    monkeypatch.setattr(backtest.data, "fetch_binance", fake_fetch_binance)
    api_main._backtest_cache = None

    res = client.get("/backtest?years=99")
    assert res.status_code == 200
    data = res.json()
    assert data["years"] == 5
    assert captured == {"symbol": "BTCUSD", "interval": 15, "days": 5 * 365}
    assert data["data_source"] == "Binance.us BTCUSD 15m candles"
