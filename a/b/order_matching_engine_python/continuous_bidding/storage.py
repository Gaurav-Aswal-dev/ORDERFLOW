# import sqlite3
# from pathlib import Path
# from datetime import datetime, timezone
# DB=Path(__file__).resolve().parents[1]/'database'/'continuous_bidding.db'
# DB.parent.mkdir(parents=True,exist_ok=True)
# def connect():
#  c=sqlite3.connect(DB,timeout=15); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
# def init():
#  with connect() as c:
#   c.executescript('''CREATE TABLE IF NOT EXISTS orders(order_id INTEGER PRIMARY KEY AUTOINCREMENT,symbol TEXT NOT NULL,side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),price REAL NOT NULL,quantity INTEGER NOT NULL,remaining INTEGER NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
#   CREATE INDEX IF NOT EXISTS idx_cb_book ON orders(symbol,side,status,price,created_at);
#   CREATE TABLE IF NOT EXISTS trades(trade_id INTEGER PRIMARY KEY AUTOINCREMENT,symbol TEXT NOT NULL,buy_order_id INTEGER NOT NULL,sell_order_id INTEGER NOT NULL,price REAL NOT NULL,quantity INTEGER NOT NULL,executed_at TEXT NOT NULL);''')
# def now(): return datetime.now(timezone.utc).isoformat()



import sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone

DB = Path(__file__).resolve().parents[1] / "database" / "continuous_bidding.db"
DB.parent.mkdir(parents=True, exist_ok=True)


def connect():
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def init():
    with closing(connect()) as c:
        with c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL CHECK (length(trim(symbol)) > 0),
                    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
                    price REAL NOT NULL CHECK (price >= 0),
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    remaining INTEGER NOT NULL CHECK (
                        remaining >= 0 AND remaining <= quantity
                    ),
                    status TEXT NOT NULL CHECK (
                        status IN ('OPEN', 'PARTIAL', 'FILLED', 'CANCELLED')
                    ),
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS trades (
                    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL CHECK (length(trim(symbol)) > 0),
                    buy_order_id INTEGER NOT NULL,
                    sell_order_id INTEGER NOT NULL,
                    price REAL NOT NULL CHECK (price >= 0),
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    executed_at TEXT NOT NULL,
                    FOREIGN KEY (buy_order_id)
                        REFERENCES orders(order_id),
                    FOREIGN KEY (sell_order_id)
                        REFERENCES orders(order_id)
                );
            """)


def now():
    return datetime.now(timezone.utc).isoformat()
