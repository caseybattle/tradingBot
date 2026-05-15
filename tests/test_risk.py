import pytest
from bot.risk import RiskManager


def test_size_position_long():
    rm = RiskManager(account_balance=10000, risk_pct=0.02, stop_pct=0.015, target_mult=2.0)
    size, stop, target = rm.size_position(10000, 50000, "long")
    assert stop < 50000
    assert target > 50000
    assert size > 0
    # uncapped size = 0.267 BTC but max_position_usd=5000 caps at 5000/50000 = 0.1 BTC
    assert abs(size - 0.1) < 0.01


def test_size_position_short():
    rm = RiskManager(account_balance=10000, risk_pct=0.02, stop_pct=0.015, target_mult=2.0)
    size, stop, target = rm.size_position(10000, 50000, "short")
    assert stop > 50000
    assert target < 50000
    assert size > 0


def test_max_position_cap():
    rm = RiskManager(account_balance=10000, risk_pct=0.02, stop_pct=0.015, max_position_usd=1000)
    size, _, _ = rm.size_position(10000, 50000, "long")
    assert size * 50000 <= 1000 + 0.01  # allow float rounding
