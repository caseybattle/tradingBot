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
