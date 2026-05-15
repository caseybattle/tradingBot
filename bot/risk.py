class RiskManager:
    """
    Fixed fractional position sizing.
    risk_pct: fraction of capital risked per trade (default 2%)
    stop_pct: stop loss distance from entry (default 1.5%)
    target_mult: reward-to-risk ratio (default 2.0)
    max_position_usd: hard cap on notional position size
    """

    def __init__(
        self,
        account_balance: float = 10000.0,
        risk_pct: float = 0.02,
        stop_pct: float = 0.015,
        target_mult: float = 2.0,
        max_position_usd: float = 5000.0,
    ):
        self.risk_pct = risk_pct
        self.stop_pct = stop_pct
        self.target_mult = target_mult
        self.max_position_usd = max_position_usd

    def size_position(self, capital: float, entry_price: float, side: str) -> tuple:
        """Returns (size_in_btc, stop_price, target_price)."""
        risk_amount = capital * self.risk_pct
        stop_distance = entry_price * self.stop_pct
        target_distance = stop_distance * self.target_mult

        if side == "long":
            stop_price = entry_price - stop_distance
            target_price = entry_price + target_distance
        else:
            stop_price = entry_price + stop_distance
            target_price = entry_price - target_distance

        size = risk_amount / stop_distance

        if size * entry_price > self.max_position_usd:
            size = self.max_position_usd / entry_price

        return round(size, 6), round(stop_price, 2), round(target_price, 2)
