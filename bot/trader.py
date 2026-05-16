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
ALLOW_LIVE_TRADING = os.getenv("ALLOW_LIVE_TRADING", "false").lower() == "true"
ADVISOR_MODE = os.getenv("ADVISOR_MODE", "true").lower() == "true"


class Trader:
    def __init__(self, state: BotState):
        self.state = state
        self.exchange = KrakenFutures(demo=DEMO)
        self.strategy = Strategy()
        self.risk = RiskManager(account_balance=state.capital)
        self._running = False

    async def _tick(self):
        try:
            symbol = self.state.active_symbol or SYMBOL
            df = self.exchange.get_candles(symbol, resolution=INTERVAL, count=200)
            funding = self.exchange.get_funding_rate(symbol)
            ticker = self.exchange.get_ticker(symbol)
            price = ticker["last"]

            # Store market data in state for dashboard
            self.state.last_price = price
            self.state.funding_rate = funding
            self.state.last_tick_at = time.time()
            self.state.next_tick_at = time.time() + LOOP_SECONDS
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
                    reason = "STOP" if hit_stop else "TARGET"
                    if ADVISOR_MODE:
                        log.info(f"ADVISOR {reason} | {pos.side} | no automatic close")
                        if self.state._broadcast_fn:
                            await self.state._broadcast_fn(self.state.snapshot())
                        return
                    exit_price = pos.stop_price if hit_stop else pos.target_price
                    if not DEMO:
                        if not ALLOW_LIVE_TRADING:
                            log.warning("Live close blocked because ALLOW_LIVE_TRADING is false")
                            return
                        close_side = "sell" if pos.side == "long" else "buy"
                        self.exchange.place_order(symbol, close_side, pos.size)
                    from api.db import clear_position
                    trade = self.state.close_position(exit_price)
                    clear_position()
                    log.info(f"CLOSE {reason} | {trade.side} | pnl={trade.pnl:.2f}")

            # look for new signal only when flat
            if not self.state.position:
                signal = self.strategy.compute(df, funding)
                self.state.current_signal = signal.value.upper()
                if signal in (Signal.BUY, Signal.SELL):
                    side = "long" if signal == Signal.BUY else "short"
                    size, stop, target = self.risk.size_position(self.state.capital, price, side)
                    if ADVISOR_MODE:
                        log.info(f"ADVISOR {side.upper()} | price={price} size={size} stop={stop} target={target}")
                        if self.state._broadcast_fn:
                            await self.state._broadcast_fn(self.state.snapshot())
                        return
                    if not DEMO and not ALLOW_LIVE_TRADING:
                        log.warning("Live entry blocked because ALLOW_LIVE_TRADING is false")
                        return
                    order_id = None
                    if not DEMO:
                        order_side = "buy" if side == "long" else "sell"
                        resp = self.exchange.place_order(symbol, order_side, size)
                        order_id = resp.get("sendStatus", {}).get("order_id")
                    from api.db import save_position
                    self.state.open_position(side, price, size, stop, target, order_id)
                    save_position(self.state.position)
                    log.info(f"OPEN {side.upper()} | price={price} size={size} stop={stop} target={target}")

            # push snapshot to WebSocket subscribers
            if self.state._broadcast_fn:
                await self.state._broadcast_fn(self.state.snapshot())

        except Exception as e:
            log.error(f"Tick error: {e}")

    async def _price_loop(self):
        """Fast loop: update price every 10s for live dashboard sync."""
        while self._running:
            try:
                ticker = self.exchange.get_ticker(self.state.active_symbol or SYMBOL)
                price = ticker["last"]
                if price and price != self.state.last_price:
                    self.state.last_price = price
                    # update unrealized pnl in state via broadcast
                    if self.state._broadcast_fn:
                        await self.state._broadcast_fn(self.state.snapshot())
            except Exception:
                pass
            await asyncio.sleep(10)

    async def run(self):
        self._running = True
        log.info(f"Trader started | symbol={self.state.active_symbol or SYMBOL} interval={INTERVAL}m demo={DEMO} advisor={ADVISOR_MODE}")
        asyncio.create_task(self._price_loop())
        while self._running:
            start = time.monotonic()
            await self._tick()
            elapsed = time.monotonic() - start
            sleep_for = max(0, LOOP_SECONDS - elapsed)
            await asyncio.sleep(sleep_for)

    def stop(self):
        self._running = False
