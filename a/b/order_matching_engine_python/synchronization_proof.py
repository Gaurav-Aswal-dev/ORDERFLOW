
"""
Demonstrate REAL MatchingEngine synchronization using a Mutex.
Uses a temporary SQLite database; never touches dashboard/company databases.

Run: python synchronization_proof.py
"""

import logging
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from matching_engine.matcher import MatchingEngine
from matching_engine.models import Order
from matching_engine.storage import Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S"
)


def main():
    with tempfile.TemporaryDirectory(prefix="orderflow_mutex_proof_") as folder:

        db = Storage(
            str(Path(folder) / "proof.db"),
            check_same_thread=False
        )

        engine = MatchingEngine(db)

        # Mutex: only one thread can enter the critical section
        mutex = threading.Lock()

        # Force both threads to become ready together
        gate = threading.Barrier(2)

        def submit(label, side, price):

            order = Order.create(
                side,
                price,
                1,
                source="MUTEX_PROOF"
            )

            logging.info(
                "THREAD READY | %s | order=%s",
                label,
                order.order_id
            )

            gate.wait()

            logging.info("MUTEX WAIT | %s", label)

            with mutex:
                logging.info("MUTEX ACQUIRED | %s", label)

                # Actual matching engine execution
                result = engine.process(order)

                logging.info("MUTEX RELEASE | %s", label)

            logging.info(
                "THREAD DONE | %s | result=%s",
                label,
                result["status"]
            )

            return result

        print("\n--- MUTEX SYNCHRONIZATION PROOF ---")
        print("Two threads share ONE MatchingEngine instance.")

        with ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="OrderThread"
        ) as pool:

            futures = [
                pool.submit(submit, "A", "SELL", "100"),
                pool.submit(submit, "B", "BUY", "100")
            ]

            results = [f.result() for f in futures]

        print("\nRESULTS:")

        for result in results:
            print(
                f"{result['order_id']} -> "
                f"{result['status']}"
            )

        print(
            "Trades created:",
            sum(len(r.get("trades", [])) for r in results)
        )

        print("\nLook for:")
        print("MUTEX WAIT")
        print("MUTEX ACQUIRED")
        print("MUTEX RELEASE")

        db.close()


if __name__ == "__main__":
    main()
