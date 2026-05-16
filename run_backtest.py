"""
Run backtest against Kraken historical data.
Fetches ~365 days of 15-min BTC/USD candles, runs the strategy,
prints the go/no-go gate result.
"""
import sys
from backtest.data import fetch_history
from backtest.engine import BacktestEngine

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 365


def main():
    print(f"Fetching {DAYS} days of BTC/USD 15m candles from Kraken...")
    try:
        df = fetch_history(symbol="XBTUSD", interval=15, days=DAYS)
    except Exception as e:
        print(f"Data fetch failed: {e}")
        sys.exit(1)

    print(f"Got {len(df)} candles ({df.index[0].date()} to {df.index[-1].date()})")

    engine = BacktestEngine(
        initial_capital=10_000.0,
        risk_pct=0.02,
        stop_pct=0.015,
        target_mult=2.0,
        max_position_usd=5_000.0,
        commission_pct=0.0005,
    )

    print("Running backtest...")
    result = engine.run(df)
    print()
    print(result.summary())
    print()

    if result.passes_gate():
        print("GO - strategy cleared. Safe to paper trade.")
    else:
        print("NO-GO - strategy failed gate. Do NOT trade live.")
        print("  Adjust strategy params or gather more data.")

    return 0 if result.passes_gate() else 1


if __name__ == "__main__":
    sys.exit(main())
