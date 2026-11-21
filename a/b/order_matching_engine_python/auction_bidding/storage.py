
import sqlite3
from contextlib import closing
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "database" / "auction_bidding.db"
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
                CREATE TABLE IF NOT EXISTS auctions (
                    auction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL CHECK (length(trim(symbol)) > 0),
                    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                    starting_price REAL NOT NULL CHECK (starting_price >= 0),
                    status TEXT NOT NULL CHECK (
                        status IN ('OPEN', 'CLOSED', 'CANCELLED')
                    ),
                    created_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,
                    closed_at TEXT,
                    winner TEXT,
                    winning_bid REAL CHECK (
                        winning_bid IS NULL OR winning_bid >= 0
                    )
                );

                CREATE TABLE IF NOT EXISTS bids (
                    bid_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auction_id INTEGER NOT NULL,
                    bidder TEXT NOT NULL CHECK (length(trim(bidder)) > 0),
                    amount REAL NOT NULL CHECK (amount >= 0),
                    placed_at TEXT NOT NULL,
                    FOREIGN KEY (auction_id)
                        REFERENCES auctions(auction_id)
                        ON DELETE CASCADE
                );
            """)


def now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
