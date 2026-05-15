import hashlib
import hmac
import base64
import time
import urllib.parse
import urllib3
import requests
import pandas as pd
from dotenv import load_dotenv
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

LIVE_BASE = "https://futures.kraken.com/derivatives/api/v3"
DEMO_BASE = "https://demo-futures.kraken.com/derivatives/api/v3"
LIVE_CHARTS = "https://futures.kraken.com/api/charts/v1"
DEMO_CHARTS = "https://demo-futures.kraken.com/api/charts/v1"
_SESSION = requests.Session()
_SESSION.verify = False  # Windows SSL cert store workaround


class KrakenFutures:
    def __init__(self, demo: bool = True):
        self.base = DEMO_BASE if demo else LIVE_BASE
        self.charts_base = DEMO_CHARTS if demo else LIVE_CHARTS
        self.api_key = os.getenv("KRAKEN_API_KEY", "")
        self.api_secret = os.getenv("KRAKEN_API_SECRET", "")

    def _sign(self, endpoint: str, nonce: str, post_data: str = "") -> str:
        message = post_data + nonce + endpoint
        sha256_hash = hashlib.sha256(message.encode("utf-8")).digest()
        secret = base64.b64decode(self.api_secret)
        sig = hmac.new(secret, sha256_hash, hashlib.sha512).digest()
        return base64.b64encode(sig).decode()

    def _headers(self, endpoint: str, nonce: str, post_data: str = "") -> dict:
        return {
            "APIKey": self.api_key,
            "Nonce": nonce,
            "Authent": self._sign(endpoint, nonce, post_data),
        }

    def _get(self, endpoint: str, params: dict = None) -> dict:
        nonce = str(int(time.time() * 1000))
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base}{endpoint}"
        resp = _SESSION.get(
            url, params=params,
            headers=self._headers(endpoint, nonce, query),
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, data: dict = None) -> dict:
        nonce = str(int(time.time() * 1000))
        post_data = urllib.parse.urlencode(data or {})
        url = f"{self.base}{endpoint}"
        resp = _SESSION.post(
            url, data=data,
            headers={
                **self._headers(endpoint, nonce, post_data),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()

    def get_ticker(self, symbol: str) -> dict:
        data = self._get("/tickers")
        for t in data.get("tickers", []):
            if t["symbol"] == symbol:
                return {
                    "last": t.get("last", t.get("markPrice", 0)),
                    "bid": t.get("bid", 0),
                    "ask": t.get("ask", 0),
                }
        raise ValueError(f"Symbol {symbol} not found in tickers")

    def get_candles(self, symbol: str, resolution: int = 15, count: int = 200) -> pd.DataFrame:
        """Fetch OHLCV candles. Resolution in minutes."""
        url = f"{self.charts_base}/trade/{symbol}/{resolution}m"
        resp = _SESSION.get(url, params={
            "from": int(time.time()) - count * resolution * 60,
            "to": int(time.time()),
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        candles_raw = data.get("candles", [])

        df = pd.DataFrame(candles_raw)
        if df.empty:
            raise RuntimeError(f"No candle data returned for {symbol}")

        # Normalize column names
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], unit="ms")
        elif "timestamp" in df.columns:
            df["time"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.drop(columns=["timestamp"])

        df = df.set_index("time").sort_index()
        needed = ["open", "high", "low", "close", "volume"]
        df = df[[c for c in needed if c in df.columns]].astype(float)
        return df.tail(count)

    def get_funding_rate(self, symbol: str) -> float:
        """Returns current funding rate for perpetual contract."""
        try:
            data = self._get("/instruments")
            for inst in data.get("instruments", []):
                if inst.get("symbol") == symbol:
                    return float(inst.get("fundingRate", 0.0))
        except Exception:
            pass
        return 0.0

    def get_open_positions(self) -> list:
        data = self._get("/openpositions")
        return data.get("openPositions", [])

    def get_account(self) -> dict:
        data = self._get("/accounts")
        return data.get("accounts", {})

    def place_order(self, symbol: str, side: str, size: float,
                    order_type: str = "mkt", limit_price: float = None) -> dict:
        """side: 'buy' or 'sell'. order_type: 'mkt' or 'lmt'."""
        payload = {
            "orderType": order_type,
            "symbol": symbol,
            "side": side,
            "size": size,
        }
        if limit_price:
            payload["limitPrice"] = limit_price
        return self._post("/sendorder", payload)

    def cancel_order(self, order_id: str) -> dict:
        return self._post("/cancelorder", {"order_id": order_id})
