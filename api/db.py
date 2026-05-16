import os
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
