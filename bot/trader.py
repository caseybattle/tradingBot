import asyncio
import logging
import os
import time
from dotenv import load_dotenv

from bot.exchange import KrakenFutures
from bot.strategy import Strategy, Signal
from bot.risk import RiskManager
from bot.state import BotState

load_dotenv()

log = logging.getLogger("trader")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SYMBOL = os.getenv("SYMBOL", "PI_XBTUSD")
INTERVAL = int(os.getenv("CANDLE_INTERVAL", "15"))
LOOP_SECONDS = INTERVAL * 60
DEMO = os.getenv("KRAKEN_DEMO", "true").lower() == "true"


class Trader:
    def __init__(self, state: BotState):
        self.state = state
        self.exchange = KrakenFutures(demo=DEMO)
        self.strategy = Strategy()
        self.risk = RiskManager(account_balance=state.capital)
        self._running = False

    async def _tick(self):
        try:
            df = self.exchange.get_candles(SYMBOL, resolution=INTERVAL, count=200)
            funding = self.exchange.get_funding_rate(SYMBOL)
            ticker = self.exchange.get_ticker(SYMBOL)
            price = ticker["last"]

            # Store market data in state for dashboard
            self.state.last_price = price
            self.state.funding_rate = funding
            try:
                rsi, st_dir = self.strategy.get_indicators(df)
                self.state.rsi = rsi
                self.state.supertrend_dir = st_dir
            except Exception:
                pass

            # check stop/target on open position
            pos = self.state.position
            if pos:
                hit_stop = (pos.side == "long" and price <= pos.stop_price) or \
                           (pos.side == "short" and price >= pos.stop_price)
                hit_target = (pos.side == "long" and price >= pos.target_price) or \
                             (pos.side == "short" and price <= pos.target_price)

                if hit_stop or hit_target:
                    exit_price = pos.stop_price if hit_stop else pos.target_price
                    reason = "STOP" if hit_stop else "TARGET"
                    if not DEMO:
                        close_side = "sell" if pos.side == "long" else "buy"
                        self.exchange.place_order(SYMBOL, close_side, pos.size)
                    trade = self.state.close_position(exit_price)
                    log.info(f"CLOSE {reason} | {trade.side} | pnl={trade.pnl:.2f}")

            # look for new signal only when flat
            if not self.state.position:
                signal = self.strategy.compute(df, funding)
                if signal in (Signal.BUY, Signal.SELL):
                    side = "long" if signal == Signal.BUY else "short"
                    size, stop, target = self.risk.size_position(self.state.capital, price, side)
                    order_id = None
                    if not DEMO:
                        order_side = "buy" if side == "long" else "sell"
                        resp = self.exchange.place_order(SYMBOL, order_side, size)
                        order_id = resp.get("sendStatus", {}).get("order_id")
                    self.state.open_position(side, price, size, stop, target, order_id)
                    log.info(f"OPEN {side.upper()} | price={price} size={size} stop={stop} target={target}")

            # push snapshot to WebSocket subscribers
            if self.state._broadcast_fn:
                await self.state._broadcast_fn(self.state.snapshot())

        except Exception as e:
            log.error(f"Tick error: {e}")

    async def run(self):
        self._running = True
        log.info(f"Trader started | symbol={SYMBOL} interval={INTERVAL}m demo={DEMO}")
        while self._running:
            start = time.monotonic()
            await self._tick()
            elapsed = time.monotonic() - start
            sleep_for = max(0, LOOP_SECONDS - elapsed)
            await asyncio.sleep(sleep_for)

    def stop(self):
        self._running = False
