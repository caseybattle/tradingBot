import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from api import main as api_main
from api.db import clear_advisor_signals


client = TestClient(api_main.app)


def _make_ohlcv(n=260) -> pd.DataFrame:
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
    monkeypatch.delenv("ADVISOR_MODE", raising=False)

    res = client.get("/safety")
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "advisor"
    assert data["advisor_mode"] is True
    assert data["kraken_demo"] is True
    assert data["allow_live_trading"] is False
    assert data["can_place_exchange_orders"] is False


def test_live_order_is_blocked_without_explicit_gate(monkeypatch):
    monkeypatch.setenv("KRAKEN_DEMO", "false")
    monkeypatch.delenv("ALLOW_LIVE_TRADING", raising=False)
    monkeypatch.delenv("ADVISOR_MODE", raising=False)
    api_main.state.position = None
    api_main.state.last_price = 50000

    res = client.post("/order?side=long")
    assert res.status_code == 200
    data = res.json()
    assert data["error"] == "live trading is blocked"
    assert data["safety"]["mode"] == "advisor"


def test_advisor_mode_blocks_demo_order(monkeypatch):
    monkeypatch.setenv("KRAKEN_DEMO", "true")
    monkeypatch.delenv("ADVISOR_MODE", raising=False)
    api_main.state.position = None
    api_main.state.last_price = 50000
    api_main.state.current_signal = "BUY"

    res = client.post("/order?side=long")
    assert res.status_code == 200
    data = res.json()
    assert data["error"] == "advisor mode is read only"
    assert data["advisor"]["places_orders"] is False
    assert data["advisor"]["recommendation"]["action"] == "consider_entry"


def test_advisor_endpoint_returns_trade_plan_without_order(monkeypatch):
    monkeypatch.setenv("KRAKEN_DEMO", "true")
    api_main.state.position = None
    api_main.state.last_price = 50000
    api_main.state.current_signal = "SELL"
    api_main.state.rsi = 52.0
    api_main.state.supertrend_dir = -1
    api_main.state.funding_rate = -0.0001

    res = client.get("/advisor")
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "advisor"
    assert data["places_orders"] is False
    assert data["recommendation"]["side"] == "short"
    assert data["recommendation"]["stop"] > data["recommendation"]["entry_reference"]


def test_advisor_endpoint_records_actionable_signal(monkeypatch):
    monkeypatch.setenv("KRAKEN_DEMO", "true")
    clear_advisor_signals()
    try:
        api_main.state.position = None
        api_main.state.active_symbol = "PI_XBTUSD"
        api_main.state.last_price = 50000
        api_main.state.last_tick_at = 1710000000
        api_main.state.current_signal = "BUY"
        api_main.state.rsi = 48.0
        api_main.state.supertrend_dir = 1
        api_main.state.funding_rate = 0.0001

        first = client.get("/advisor")
        second = client.get("/advisor")
        assert first.status_code == 200
        assert second.status_code == 200

        journal = client.get("/advisor/journal").json()
        assert journal["summary"]["actionable"] == 1
        assert journal["signals"][0]["symbol"] == "PI_XBTUSD"
        assert journal["signals"][0]["side"] == "long"
        assert journal["signals"][0]["seen_count"] == 2
    finally:
        clear_advisor_signals()


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
    assert "in_sample" in data
    assert "out_of_sample" in data


def test_strategy_validation_reports_split_windows(monkeypatch):
    import backtest.data

    def fake_fetch_binance(symbol, interval, days):
        return _make_ohlcv(360)

    monkeypatch.setattr(backtest.data, "fetch_binance", fake_fetch_binance)
    api_main._validation_cache = None

    res = client.get("/strategy/validation?years=2")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["strict_pass"] in (True, False)
    assert data["in_sample"]["label"] == "in_sample"
    assert data["out_of_sample"]["label"] == "out_of_sample"
    assert len(data["walk_forward"]) == 3
    assert data["assumptions"]["slippage_pct_per_fill"] == 0.02


def test_strategy_leaderboard_ranks_candidates(monkeypatch):
    import backtest.data

    calls = []

    def fake_fetch_binance(symbol, interval, days):
        calls.append(symbol)
        return _make_ohlcv(420)

    monkeypatch.setattr(backtest.data, "fetch_binance", fake_fetch_binance)
    api_main._leaderboard_cache = None

    res = client.get("/strategy/leaderboard?years=1")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["candidate_count"] == 6
    assert {row["symbol"] for row in data["rows"]} == {"PI_XBTUSD", "PI_ETHUSD"}
    assert {row["strategy_id"] for row in data["rows"]} == {"supertrend_rsi_adx", "tsmom_4h", "tsmom_1d"}
    assert [row["rank"] for row in data["rows"]] == [1, 2, 3, 4, 5, 6]
    assert calls == ["BTCUSD", "ETHUSD"]


def test_validation_fails_when_trade_count_breaks_gate():
    from backtest.validation import strict_checks

    metrics = {
        "status": "ok",
        "sharpe_ratio": 2.0,
        "max_drawdown_pct": 5.0,
        "profit_factor": 2.0,
        "total_trades": 1,
    }
    result = strict_checks(metrics)
    assert result["gate"] == "FAIL"
    assert result["checks"]["trade_count"] is False


def test_market_selector_changes_symbol_without_strategy_math():
    api_main.state.position = None
    api_main.state.active_symbol = "PI_XBTUSD"

    res = client.post("/markets/active", json={"symbol": "PI_ETHUSD"})
    assert res.status_code == 200
    data = res.json()
    assert data["active_symbol"] == "PI_ETHUSD"

    strategy = client.get("/strategy").json()
    assert strategy["market"]["symbol"] == "PI_ETHUSD"
    assert strategy["parameters"]["supertrend_period"] == 10
    assert strategy["parameters"]["adx_min"] == 25.0

    api_main.state.active_symbol = "PI_XBTUSD"
