from __future__ import annotations

import random
import time
from multiprocessing.queues import Queue


def producer_worker(queue: Queue, count: int, seed: int | None = None, delay: float = 0.1) -> None:
    """Generate deterministic-ish demo orders and send them to the matcher."""
    rng = random.Random(seed)
    for index in range(count):
        side = rng.choice(["BUY", "SELL"])
        # A small price range makes it likely that some orders cross.
        price = rng.choice([98, 99, 100, 101, 102])
        quantity = rng.randint(1, 10)
        queue.put({
            "type": "ORDER",
            "order_id": f"demo-{time.time_ns()}-{index}",
            "side": side,
            "price": str(price),
            "quantity": quantity,
            "created_at": time.time(),
            "source": "demo-producer",
        })
        if delay:
            time.sleep(delay)
    queue.put({"type": "STOP"})














# if __name__ == "__main__":
#     from multiprocessing import Queue

#     order_queue = Queue()

#     producer_worker(
#         queue=order_queue,
#         count=10,
#         seed=42,
#         delay=0.1
#     )

#     print("\nGenerated orders:")
#     for _ in range(10):
#         print(order_queue.get())

#     order_queue.close()