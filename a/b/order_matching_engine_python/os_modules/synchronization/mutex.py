"""Demonstrate Mutex (Mutual Exclusion) using threading.Lock."""

import threading
import time


class ProtectedCounter:

    def __init__(self):
        self.value = 0
        self.mutex = threading.Lock()

    def increment(self):
        # Critical section protected by Mutex
        with self.mutex:
            current = self.value
            time.sleep(0)
            self.value = current + 1


def mutex_demo(workers=4, increments=1000):

    counter = ProtectedCounter()

    def worker():
        for _ in range(increments):
            counter.increment()

    threads = [
        threading.Thread(target=worker)
        for _ in range(workers)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    expected = workers * increments

    print("\n--- MUTEX DEMONSTRATION ---")
    print("Number of threads:", workers)
    print("Increments per thread:", increments)
    print("Expected value:", expected)
    print("Actual value:", counter.value)
    print("Mutex working:", counter.value == expected)


if __name__ == "__main__":
    mutex_demo()