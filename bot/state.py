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
        self.equity_history: list[tuple[float, float]] = []

        # Market data (updated each tick)
        self.last_price: float = 0.0
        self.rsi: float = 0.0
        self.supertrend_dir: int = 0   # 1=bull, -1=bear, 0=unknown
        self.funding_rate: float = 0.0

        # Performance tracking
        self.wins: int = 0
        self.losses: int = 0
        self.best_trade: Optional[float] = None
        self.worst_trade: Optional[float] = None

        self._broadcast_fn = None

    def register_broadcast(self, fn):
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

        if pnl > 0:
            self.wins += 1
        else:
            self.losses += 1
        if self.best_trade is None or pnl > self.best_trade:
            self.best_trade = pnl
        if self.worst_trade is None or pnl < self.worst_trade:
            self.worst_trade = pnl

        return trade

    def snapshot(self) -> dict:
        pos = None
        if self.position:
            if self.last_price > 0:
                if self.position.side == "long":
                    unrealized = (self.last_price - self.position.entry_price) * self.position.size
                else:
                    unrealized = (self.position.entry_price - self.last_price) * self.position.size
            else:
                unrealized = 0.0
            pos = {
                "side": self.position.side,
                "entry": self.position.entry_price,
                "size": self.position.size,
                "stop": self.position.stop_price,
                "target": self.position.target_price,
                "opened_at": self.position.opened_at,
                "unrealized_pnl": round(unrealized, 2),
            }

        total = self.wins + self.losses
        recent = self.trades[-20:]
        return {
            "capital": round(self.capital, 2),
            "pnl_total": round(self.capital - self.initial_capital, 2),
            "pnl_pct": round((self.capital / self.initial_capital - 1) * 100, 2),
            "last_price": self.last_price,
            "rsi": round(self.rsi, 1),
            "supertrend_dir": self.supertrend_dir,
            "funding_rate": self.funding_rate,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.wins / total * 100, 1) if total > 0 else 0.0,
            "best_trade": round(self.best_trade, 2) if self.best_trade is not None else 0.0,
            "worst_trade": round(self.worst_trade, 2) if self.worst_trade is not None else 0.0,
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
