import os
import time
from sqlalchemy import create_engine, Column, Float, String, Integer
from sqlalchemy.orm import DeclarativeBase, Session

DB_PATH = os.getenv("DB_PATH", "data/trades.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


class Base(DeclarativeBase):
    pass


class TradeRecord(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    side = Column(String)
    entry_price = Column(Float)
    exit_price = Column(Float)
    size = Column(Float)
    pnl = Column(Float)
    opened_at = Column(Float)
    closed_at = Column(Float)


class OpenPosition(Base):
    __tablename__ = "open_position"
    id = Column(Integer, primary_key=True, default=1)
    side = Column(String)
    entry_price = Column(Float)
    size = Column(Float)
    stop_price = Column(Float)
    target_price = Column(Float)
    opened_at = Column(Float)
    order_id = Column(String, nullable=True)


class AdvisorSignalRecord(Base):
    __tablename__ = "advisor_signals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    fingerprint = Column(String, unique=True, index=True)
    symbol = Column(String, index=True)
    signal = Column(String)
    action = Column(String)
    side = Column(String, nullable=True)
    confidence = Column(String)
    thesis = Column(String)
    invalidation = Column(String)
    entry_reference = Column(Float, nullable=True)
    size = Column(Float, nullable=True)
    stop = Column(Float, nullable=True)
    target = Column(Float, nullable=True)
    risk_usd = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    rsi = Column(Float, nullable=True)
    supertrend_dir = Column(Integer, nullable=True)
    funding_rate = Column(Float, nullable=True)
    created_at = Column(Float, default=time.time)
    last_seen_at = Column(Float, default=time.time)
    seen_count = Column(Integer, default=1)
    outcome_status = Column(String, default="open")
    outcome_note = Column(String, nullable=True)
    outcome_pnl = Column(Float, nullable=True)


Base.metadata.create_all(engine)


def save_trade(trade) -> None:
    with Session(engine) as session:
        session.add(TradeRecord(
            side=trade.side,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            size=trade.size,
            pnl=trade.pnl,
            opened_at=trade.opened_at,
            closed_at=trade.closed_at,
        ))
        session.commit()


def save_position(pos) -> None:
    with Session(engine) as session:
        session.query(OpenPosition).delete()
        session.add(OpenPosition(
            id=1, side=pos.side, entry_price=pos.entry_price, size=pos.size,
            stop_price=pos.stop_price, target_price=pos.target_price,
            opened_at=pos.opened_at, order_id=pos.order_id,
        ))
        session.commit()


def load_position() -> dict | None:
    with Session(engine) as session:
        row = session.query(OpenPosition).first()
        if not row:
            return None
        return {
            "side": row.side, "entry_price": row.entry_price, "size": row.size,
            "stop_price": row.stop_price, "target_price": row.target_price,
            "opened_at": row.opened_at, "order_id": row.order_id,
        }


def clear_position() -> None:
    with Session(engine) as session:
        session.query(OpenPosition).delete()
        session.commit()


def load_trades(limit: int = 100) -> list[dict]:
    with Session(engine) as session:
        rows = session.query(TradeRecord).order_by(TradeRecord.closed_at.desc()).limit(limit).all()
        return [
            {
                "side": r.side, "entry": r.entry_price, "exit": r.exit_price,
                "size": r.size, "pnl": r.pnl,
                "opened_at": r.opened_at, "closed_at": r.closed_at,
            }
            for r in rows
        ]


def save_advisor_signal(record: dict) -> dict:
    now = time.time()
    fingerprint = record["fingerprint"]
    with Session(engine) as session:
        row = session.query(AdvisorSignalRecord).filter_by(fingerprint=fingerprint).first()
        if row:
            row.last_seen_at = now
            row.seen_count = (row.seen_count or 0) + 1
            row.price = record.get("price")
            row.rsi = record.get("rsi")
            row.supertrend_dir = record.get("supertrend_dir")
            row.funding_rate = record.get("funding_rate")
        else:
            row = AdvisorSignalRecord(
                fingerprint=fingerprint,
                symbol=record.get("symbol"),
                signal=record.get("signal"),
                action=record.get("action"),
                side=record.get("side"),
                confidence=record.get("confidence"),
                thesis=record.get("thesis"),
                invalidation=record.get("invalidation"),
                entry_reference=record.get("entry_reference"),
                size=record.get("size"),
                stop=record.get("stop"),
                target=record.get("target"),
                risk_usd=record.get("risk_usd"),
                price=record.get("price"),
                rsi=record.get("rsi"),
                supertrend_dir=record.get("supertrend_dir"),
                funding_rate=record.get("funding_rate"),
                created_at=now,
                last_seen_at=now,
                seen_count=1,
                outcome_status="open",
            )
            session.add(row)
        session.commit()
        session.refresh(row)
        return _advisor_signal_payload(row)


def load_advisor_signals(limit: int = 25, symbol: str | None = None) -> list[dict]:
    with Session(engine) as session:
        query = session.query(AdvisorSignalRecord)
        if symbol:
            query = query.filter_by(symbol=symbol)
        rows = query.order_by(AdvisorSignalRecord.last_seen_at.desc()).limit(limit).all()
        return [_advisor_signal_payload(row) for row in rows]


def advisor_signal_summary(symbol: str | None = None) -> dict:
    records = load_advisor_signals(limit=500, symbol=symbol)
    actionable = [r for r in records if r["action"] in ("consider_entry", "manage_existing_position")]
    long_count = sum(1 for r in actionable if r["side"] == "long")
    short_count = sum(1 for r in actionable if r["side"] == "short")
    return {
        "total": len(records),
        "actionable": len(actionable),
        "long": long_count,
        "short": short_count,
        "open_outcomes": sum(1 for r in actionable if r["outcome_status"] == "open"),
    }


def clear_advisor_signals() -> None:
    with Session(engine) as session:
        session.query(AdvisorSignalRecord).delete()
        session.commit()


def _advisor_signal_payload(row: AdvisorSignalRecord) -> dict:
    return {
        "id": row.id,
        "fingerprint": row.fingerprint,
        "symbol": row.symbol,
        "signal": row.signal,
        "action": row.action,
        "side": row.side,
        "confidence": row.confidence,
        "thesis": row.thesis,
        "invalidation": row.invalidation,
        "entry_reference": row.entry_reference,
        "size": row.size,
        "stop": row.stop,
        "target": row.target,
        "risk_usd": row.risk_usd,
        "price": row.price,
        "rsi": row.rsi,
        "supertrend_dir": row.supertrend_dir,
        "funding_rate": row.funding_rate,
        "created_at": row.created_at,
        "last_seen_at": row.last_seen_at,
        "seen_count": row.seen_count,
        "outcome_status": row.outcome_status,
        "outcome_note": row.outcome_note,
        "outcome_pnl": row.outcome_pnl,
    }
