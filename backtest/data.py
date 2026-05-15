import time
import warnings
import requests
import urllib3
import pandas as pd

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KRAKEN_SPOT_BASE  = "https://api.kraken.com/0/public"
BINANCE_BASE      = "https://api.binance.us/api/v3/klines"  # US-compliant, no geo-block
_SESSION = requests.Session()
_SESSION.verify = False  # Windows SSL cert store workaround

BINANCE_INTERVAL_MAP = {1: "1m", 3: "3m", 5: "5m", 15: "15m", 30: "30m",
                        60: "1h", 120: "2h", 240: "4h", 1440: "1d"}


def fetch_binance(symbol: str = "BTCUSDT", interval: int = 15, days: int = 365) -> pd.DataFrame:
    """
    Fetch OHLCV from Binance public API. No API key needed.
    Goes back to 2017 for BTCUSDT. Paginates automatically.
    interval: minutes (1, 5, 15, 30, 60, 240, 1440)
    """
    iv = BINANCE_INTERVAL_MAP.get(interval, "15m")
    start_ms = int((time.time() - days * 86400) * 1000)
    end_ms   = int(time.time() * 1000)
    frames   = []

    while start_ms < end_ms:
        resp = _SESSION.get(BINANCE_BASE, params={
            "symbol": symbol, "interval": iv,
            "startTime": start_ms, "endTime": end_ms, "limit": 1000,
        }, timeout=15)
        resp.raise_for_status()
        raw = resp.json()
        if not raw:
            break
        df = pd.DataFrame(raw, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "taker_base", "taker_quote", "ignore"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df.set_index("time")[["open", "high", "low", "close", "volume"]].astype(float)
        frames.append(df)
        start_ms = int(raw[-1][0]) + 1  # next candle
        if len(raw) < 1000:
            break
        time.sleep(0.2)

    if not frames:
        raise RuntimeError(f"No Binance data returned for {symbol}")

    combined = pd.concat(frames)
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    return combined


def fetch_ohlcv(symbol: str = "XBTUSD", interval: int = 15, since: int = None) -> pd.DataFrame:
    """
    Fetch OHLCV from Kraken Spot public API (no auth needed).
    Returns up to 720 candles per call. Call repeatedly with last timestamp to paginate.
    interval: minutes (1, 5, 15, 30, 60, 240, 1440, 10080, 21600)
    """
    params = {"pair": symbol, "interval": interval}
    if since:
        params["since"] = since

    resp = _SESSION.get(f"{KRAKEN_SPOT_BASE}/OHLC", params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if data.get("error"):
        raise RuntimeError(f"Kraken API error: {data['error']}")

    result = data["result"]
    last = result.get("last", 0)
    pair_key = [k for k in result if k != "last"][0]
    raw = result[pair_key]

    df = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "vwap", "volume", "count"])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time").sort_index()
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df, last


def fetch_history(symbol: str = "XBTUSD", interval: int = 1440, days: int = 365) -> pd.DataFrame:
    """
    Fetch OHLCV history by paginating the Kraken spot API.
    NOTE: Kraken public API retains ~720 candles per interval.
      15m  → ~7.5 days history
      60m  → ~30 days history
      1440m (daily) → ~720 days history  ← use this for backtesting
    Default interval changed to 1440 (daily) for meaningful backtest windows.
    """
    since = int(time.time()) - days * 86400
    now = int(time.time())
    frames = []
    prev_last = None

    while True:
        df, last = fetch_ohlcv(symbol, interval, since=since)
        if df.empty:
            break
        frames.append(df)
        # stop if no new data or we've passed now
        if last == prev_last or last >= now or len(df) < 2:
            break
        prev_last = last
        since = last
        time.sleep(0.5)

    if not frames:
        raise RuntimeError(f"No data returned for {symbol}")

    combined = pd.concat(frames)
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    # trim to requested window
    cutoff = pd.Timestamp.now(tz="UTC").tz_localize(None) - pd.Timedelta(days=days)
    return combined[combined.index >= cutoff]
