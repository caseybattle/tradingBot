from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class Position:
    side: str          # "long" | "short"
    entry_price: float
    size: float        # BTC
    stop_price: float
    target_price: float
    opened_at: float = field(default_factory=time.time)
    order_id: Optional[str] = None


@dataclass
class Trade:
    side: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    opened_at: float
    closed_at: float


class BotState:
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position: Optional[Position] = None
        self.trades: list[Trade] = []
        self.equity_history: list[tuple[float, float]] = []  # (timestamp, equity)
        self._broadcast_fn = None

    def register_broadcast(self, fn):
        """Inject async broadcast callback from the API layer."""
        self._broadcast_fn = fn

    def open_position(self, side: str, entry: float, size: float,
                      stop: float, target: float, order_id: str = None):
        self.position = Position(
            side=side, entry_price=entry, size=size,
            stop_price=stop, target_price=target, order_id=order_id
        )

    def close_position(self, exit_price: float) -> Trade:
        p = self.position
        if p is None:
            raise RuntimeError("No open position to close")
        if p.side == "long":
            pnl = (exit_price - p.entry_price) * p.size
        else:
            pnl = (p.entry_price - exit_price) * p.size
        self.capital += pnl
        trade = Trade(
            side=p.side, entry_price=p.entry_price, exit_price=exit_price,
            size=p.size, pnl=round(pnl, 2),
            opened_at=p.opened_at, closed_at=time.time()
        )
        self.trades.append(trade)
        self.position = None
        self.equity_history.append((trade.closed_at, self.capital))
        return trade

    def snapshot(self) -> dict:
        pos = None
        if self.position:
            pos = {
                "side": self.position.side,
                "entry": self.position.entry_price,
                "size": self.position.size,
                "stop": self.position.stop_price,
                "target": self.position.target_price,
            }
        recent = self.trades[-20:]
        return {
            "capital": round(self.capital, 2),
            "pnl_total": round(self.capital - self.initial_capital, 2),
            "pnl_pct": round((self.capital / self.initial_capital - 1) * 100, 2),
            "position": pos,
            "trades": [
                {
                    "side": t.side, "entry": t.entry_price, "exit": t.exit_price,
                    "size": t.size, "pnl": t.pnl, "time": t.closed_at,
                }
                for t in recent
            ],
            "equity_history": self.equity_history[-200:],
        }
