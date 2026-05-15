import time
import requests
import pandas as pd


KRAKEN_SPOT_BASE = "https://api.kraken.com/0/public"


def fetch_ohlcv(symbol: str = "XBTUSD", interval: int = 15, since: int = None) -> pd.DataFrame:
    """
    Fetch OHLCV from Kraken Spot public API (no auth needed).
    Returns up to 720 candles per call. Call repeatedly with last timestamp to paginate.
    interval: minutes (1, 5, 15, 30, 60, 240, 1440, 10080, 21600)
    """
    params = {"pair": symbol, "interval": interval}
    if since:
        params["since"] = since

    resp = requests.get(f"{KRAKEN_SPOT_BASE}/OHLC", params=params, timeout=10)
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


def fetch_history(symbol: str = "XBTUSD", interval: int = 15, days: int = 365) -> pd.DataFrame:
    """Fetch up to `days` of OHLCV history by paginating the Kraken spot API."""
    since = int(time.time()) - days * 86400
    frames = []

    while True:
        df, last = fetch_ohlcv(symbol, interval, since=since)
        if df.empty:
            break
        frames.append(df)
        if last == since or len(df) < 2:
            break
        since = last
        time.sleep(0.5)  # rate limit courtesy

    if not frames:
        raise RuntimeError(f"No data returned for {symbol}")

    combined = pd.concat(frames)
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    return combined
