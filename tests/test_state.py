import pytest
from bot.state import BotState


def test_initial_state():
    s = BotState(initial_capital=10000)
    assert s.capital == 10000
    assert s.position is None
    assert s.trades == []


def test_open_and_close_long():
    s = BotState(initial_capital=10000)
    s.open_position("long", entry=50000, size=0.1, stop=49250, target=51500)
    assert s.position is not None
    trade = s.close_position(exit_price=51500)
    assert trade.pnl == pytest.approx(150.0, rel=0.001)
    assert s.capital == pytest.approx(10150.0, rel=0.001)
    assert s.position is None


def test_open_and_close_short():
    s = BotState(initial_capital=10000)
    s.open_position("short", entry=50000, size=0.1, stop=50750, target=48500)
    trade = s.close_position(exit_price=48500)
    assert trade.pnl == pytest.approx(150.0, rel=0.001)


def test_close_stop_loss():
    s = BotState(initial_capital=10000)
    s.open_position("long", entry=50000, size=0.1, stop=49250, target=51500)
    trade = s.close_position(exit_price=49250)
    assert trade.pnl == pytest.approx(-75.0, rel=0.001)
    assert s.capital == pytest.approx(9925.0, rel=0.001)


def test_close_no_position_raises():
    s = BotState()
    with pytest.raises(RuntimeError):
        s.close_position(50000)


def test_snapshot_keys():
    s = BotState()
    snap = s.snapshot()
    assert "capital" in snap
    assert "pnl_total" in snap
    assert "pnl_pct" in snap
    assert "position" in snap
    assert "trades" in snap
