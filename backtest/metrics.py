import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class BacktestResult:
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    profit_factor: float
    equity_curve: pd.Series

    def passes_gate(self) -> bool:
        return self.sharpe_ratio >= 0.8 and self.max_drawdown_pct <= 35.0

    def summary(self) -> str:
        gate = "PASS" if self.passes_gate() else "FAIL"
        return (
            f"[GO/NO-GO: {gate}]\n"
            f"  Return:       {self.total_return_pct:.1f}%\n"
            f"  Sharpe:       {self.sharpe_ratio:.2f}  (min 0.8)\n"
            f"  Max Drawdown: {self.max_drawdown_pct:.1f}%  (max 35%)\n"
            f"  Win Rate:     {self.win_rate:.1f}%\n"
            f"  Trades:       {self.total_trades}\n"
            f"  Profit Factor:{self.profit_factor:.2f}"
        )


def compute_metrics(equity: pd.Series, trades: list) -> BacktestResult:
    """
    equity: pd.Series of portfolio value over time
    trades: list of dicts with 'pnl' key
    """
    returns = equity.pct_change().dropna()

    # Sharpe — annualized, 15-min candles = 96 candles/day * 252 trading days
    periods_per_year = 96 * 252
    sharpe = (returns.mean() / returns.std() * np.sqrt(periods_per_year)) if returns.std() > 0 else 0.0

    # Max drawdown
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max * 100
    max_drawdown = abs(drawdown.min())

    # Trade stats
    pnls = [t["pnl"] for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]
    win_rate = len(winners) / len(pnls) * 100 if pnls else 0.0
    gross_profit = sum(winners)
    gross_loss = abs(sum(losers))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    total_return = (equity.iloc[-1] / equity.iloc[0] - 1) * 100

    return BacktestResult(
        total_return_pct=total_return,
        sharpe_ratio=round(sharpe, 4),
        max_drawdown_pct=round(max_drawdown, 2),
        win_rate=round(win_rate, 2),
        total_trades=len(pnls),
        profit_factor=round(profit_factor, 3),
        equity_curve=equity,
    )
