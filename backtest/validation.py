from collections.abc import Callable

import pandas as pd

from backtest.metrics import BacktestResult


STRICT_GATE = {
    "min_sharpe": 0.8,
    "max_drawdown_pct": 35.0,
    "min_profit_factor": 1.1,
    "min_trades": 20,
}

MIN_VALIDATION_CANDLES = 80


def metrics_payload(result: BacktestResult) -> dict:
    return {
        "status": "ok",
        "gate": "PASS" if result.passes_gate() else "FAIL",
        "total_return_pct": result.total_return_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "max_drawdown_pct": result.max_drawdown_pct,
        "win_rate": result.win_rate,
        "total_trades": result.total_trades,
        "profit_factor": result.profit_factor,
    }


def strict_checks(metrics: dict) -> dict:
    if metrics.get("status") != "ok":
        return {
            "gate": "FAIL",
            "checks": {
                "sharpe": False,
                "drawdown": False,
                "profit_factor": False,
                "trade_count": False,
            },
        }

    profit_factor = metrics.get("profit_factor")
    profit_factor_ok = profit_factor is not None and profit_factor >= STRICT_GATE["min_profit_factor"]
    checks = {
        "sharpe": bool(metrics.get("sharpe_ratio", 0) >= STRICT_GATE["min_sharpe"]),
        "drawdown": bool(metrics.get("max_drawdown_pct", 999) <= STRICT_GATE["max_drawdown_pct"]),
        "profit_factor": bool(profit_factor_ok),
        "trade_count": bool(metrics.get("total_trades", 0) >= STRICT_GATE["min_trades"]),
    }
    return {"gate": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def _run_segment(engine_factory: Callable[[], object], df: pd.DataFrame, label: str) -> dict:
    if len(df) < MIN_VALIDATION_CANDLES:
        metrics = {
            "status": "insufficient_data",
            "gate": "FAIL",
            "label": label,
            "candles": len(df),
            "detail": f"Need at least {MIN_VALIDATION_CANDLES} candles, got {len(df)}",
        }
        metrics.update(strict_checks(metrics))
        return metrics

    result = engine_factory().run(df)
    metrics = metrics_payload(result)
    metrics["label"] = label
    metrics["candles"] = len(df)
    metrics["start"] = str(df.index[0])
    metrics["end"] = str(df.index[-1])
    metrics.update(strict_checks(metrics))
    return metrics


def build_validation_report(
    df: pd.DataFrame,
    engine_factory: Callable[[], object],
    *,
    symbol: str,
    data_source: str,
    interval_minutes: int,
    years: int,
    fee_pct: float,
    slippage_pct: float,
) -> dict:
    if len(df) < MIN_VALIDATION_CANDLES * 2:
        return {
            "status": "insufficient_data",
            "gate": "FAIL",
            "strict_pass": False,
            "symbol": symbol,
            "data_source": data_source,
            "interval_minutes": interval_minutes,
            "years": years,
            "candles": len(df),
            "assumptions": _assumptions(fee_pct, slippage_pct),
            "reason": f"Need at least {MIN_VALIDATION_CANDLES * 2} candles for split validation.",
        }

    split = max(MIN_VALIDATION_CANDLES, int(len(df) * 0.7))
    if len(df) - split < MIN_VALIDATION_CANDLES:
        split = len(df) - MIN_VALIDATION_CANDLES

    full = _run_segment(engine_factory, df, "full_sample")
    in_sample = _run_segment(engine_factory, df.iloc[:split], "in_sample")
    out_of_sample = _run_segment(engine_factory, df.iloc[split:], "out_of_sample")

    folds = []
    fold_count = 3
    fold_size = len(df) // fold_count
    for idx in range(fold_count):
        start = idx * fold_size
        end = len(df) if idx == fold_count - 1 else (idx + 1) * fold_size
        fold_df = df.iloc[start:end]
        folds.append(_run_segment(engine_factory, fold_df, f"walk_forward_{idx + 1}"))

    passing_folds = sum(1 for fold in folds if fold.get("gate") == "PASS")
    strict_pass = (
        full.get("gate") == "PASS"
        and in_sample.get("gate") == "PASS"
        and out_of_sample.get("gate") == "PASS"
        and passing_folds >= 2
    )
    return {
        "status": "ok",
        "gate": "PASS" if strict_pass else "FAIL",
        "strict_pass": strict_pass,
        "symbol": symbol,
        "data_source": data_source,
        "interval_minutes": interval_minutes,
        "years": years,
        "candles": len(df),
        "date_range": {"start": str(df.index[0]), "end": str(df.index[-1])},
        "assumptions": _assumptions(fee_pct, slippage_pct),
        "strict_gate": STRICT_GATE,
        "full_sample": full,
        "in_sample": in_sample,
        "out_of_sample": out_of_sample,
        "walk_forward": folds,
        "reason": "Requires full sample, in-sample, out-of-sample, and at least 2 of 3 walk-forward windows to pass strict gates.",
    }


def _assumptions(fee_pct: float, slippage_pct: float) -> dict:
    return {
        "fee_pct_per_fill": round(fee_pct * 100, 4),
        "slippage_pct_per_fill": round(slippage_pct * 100, 4),
        "position_sizing": "fixed fractional risk with max notional cap",
        "execution": "advisor-only; no automatic exchange orders",
    }
