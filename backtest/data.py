import time
import warnings
import requests
import urllib3
import pandas as pd

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KRAKEN_SPOT_BASE = "https://api.kraken.com/0/public"
_SESSION = requests.Session()
_SESSION.verify = False  # Windows SSL cert store workaround


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
