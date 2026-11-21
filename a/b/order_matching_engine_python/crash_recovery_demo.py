"""Manual integration demonstration: matcher crash, supervisor restart, idempotent replay."""
from __future__ import annotations
import tempfile
import time
from pathlib import Path
from order_engine.runtime import MatcherSupervisor
from order_engine.storage import Storage


def main():
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "crash-recovery.db")
        supervisor = MatcherSupervisor(db, crash_after=1)
        first = {
            "type": "ORDER", "order_id": "crash-demo-sell-1", "side": "SELL",
            "price": "100", "quantity": 5, "created_at": time.time(), "source": "crash-demo"
        }
        try:
            print("1) Submit order to matcher")
            result = supervisor.submit(first)
            print("   Result:", result)
            print("2) Matcher has been configured to crash after its first acknowledged order.")
            # Give the child a moment to exit after it sends its response.
            supervisor.process.join(timeout=2)
            print("   Matcher exit code:", supervisor.process.exitcode)
            print("3) Submit another order. Supervisor should detect/restart matcher.")
            second = {
                "type": "ORDER", "order_id": "crash-demo-buy-1", "side": "BUY",
                "price": "99", "quantity": 2, "created_at": time.time()+1, "source": "crash-demo"
            }
            print("   Result:", supervisor.submit(second))
            print("   Restarts:", supervisor.restart_count)
            print("4) Replay the first order ID; it must not be inserted twice.")
            print("   Replay:", supervisor.submit(first))
        finally:
            supervisor.close()
        store = Storage(db)
        try:
            print("5) Durable database stats:", store.stats())
            print("   Orders:", len(store.list_orders()), "Trades:", len(store.list_trades()))
        finally:
            store.close()


if __name__ == "__main__":
    main()
