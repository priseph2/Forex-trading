import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone


DB_PATH = os.getenv("BOT_DB_PATH", "bot_state.db")

_CREATE_TRADES = """
CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pair            TEXT    NOT NULL,
    broker          TEXT    NOT NULL,
    direction       TEXT    NOT NULL,
    entry_price     REAL    NOT NULL,
    stop_loss       REAL    NOT NULL,
    take_profit     REAL    NOT NULL,
    units           REAL    NOT NULL,
    broker_trade_id TEXT,
    opened_at       TEXT    NOT NULL,
    closed_at       TEXT,
    exit_price      REAL,
    pnl             REAL,
    status          TEXT    NOT NULL DEFAULT 'open'
);
"""

_CREATE_DAILY = """
CREATE TABLE IF NOT EXISTS daily_summary (
    date         TEXT    PRIMARY KEY,
    total_trades INTEGER DEFAULT 0,
    wins         INTEGER DEFAULT 0,
    losses       INTEGER DEFAULT 0,
    gross_pnl    REAL    DEFAULT 0.0,
    net_pnl      REAL    DEFAULT 0.0
);
"""


class TradeState:
    def __init__(self, db_path: str = DB_PATH):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _get_conn(self):
        with self._lock:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(_CREATE_TRADES)
            conn.execute(_CREATE_DAILY)

    def insert_trade(
        self,
        pair: str,
        broker: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        units: float,
        broker_trade_id: str,
    ) -> int:
        opened_at = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO trades
                   (pair, broker, direction, entry_price, stop_loss, take_profit,
                    units, broker_trade_id, opened_at, status)
                   VALUES (?,?,?,?,?,?,?,?,?,'open')""",
                (pair, broker, direction, entry_price, stop_loss, take_profit,
                 units, broker_trade_id, opened_at),
            )
            return cur.lastrowid

    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        pnl: float,
        closed_at: str,
        status: str = "closed",
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE trades
                   SET exit_price=?, pnl=?, closed_at=?, status=?
                   WHERE id=?""",
                (exit_price, pnl, closed_at, status, trade_id),
            )

    def get_open_trades(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM trades WHERE status='open'"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_open_trade_count(self) -> int:
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM trades WHERE status='open'"
            ).fetchone()[0]

    def is_pair_already_open(self, pair: str) -> bool:
        with self._get_conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE pair=? AND status='open'",
                (pair,),
            ).fetchone()[0]
            return count > 0

    def get_all_trades_for_date(self, date: str) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM trades WHERE opened_at LIKE ?",
                (f"{date}%",),
            ).fetchall()
            return [dict(r) for r in rows]

    def upsert_daily_summary(self, date: str) -> None:
        with self._get_conn() as conn:
            trades = conn.execute(
                "SELECT pnl, status FROM trades WHERE opened_at LIKE ? AND status='closed'",
                (f"{date}%",),
            ).fetchall()
            total = len(trades)
            wins = sum(1 for t in trades if t["pnl"] and t["pnl"] > 0)
            losses = sum(1 for t in trades if t["pnl"] and t["pnl"] <= 0)
            gross_pnl = sum(t["pnl"] for t in trades if t["pnl"])
            conn.execute(
                """INSERT INTO daily_summary (date, total_trades, wins, losses, gross_pnl, net_pnl)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(date) DO UPDATE SET
                     total_trades=excluded.total_trades,
                     wins=excluded.wins,
                     losses=excluded.losses,
                     gross_pnl=excluded.gross_pnl,
                     net_pnl=excluded.net_pnl""",
                (date, total, wins, losses, round(gross_pnl, 2), round(gross_pnl * 0.998, 2)),
            )

    def get_daily_summary(self, date: str) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM daily_summary WHERE date=?", (date,)
            ).fetchone()
            return dict(row) if row else None
