"""Demonstrate a race condition and its prevention using a Mutex (Lock)."""

import threading
import time


def counter_demo(workers=4, increments=1000):
    unsafe = [0]
    safe = [0]

    mutex = threading.Lock()

    def work():
        for _ in range(increments):

            # UNSAFE: Read-modify-write without synchronization
            current = unsafe[0]
            time.sleep(0)  # Encourage thread switching
            unsafe[0] = current + 1

            # SAFE: Entire critical section protected by Mutex
            with mutex:
                current = safe[0]
                time.sleep(0)
                safe[0] = current + 1

    threads = [
        threading.Thread(target=work)
        for _ in range(workers)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    expected = workers * increments

    return {
        "unsafe": unsafe[0],
        "safe": safe[0],
        "expected": expected,
        "race_detected": unsafe[0] != expected,
        "mutex_correct": safe[0] == expected
    }


if __name__ == "__main__":
    print("\n--- RACE CONDITION DEMONSTRATION ---")

    result = counter_demo()

    print("Unsafe counter:", result["unsafe"])
    print("Mutex counter:", result["safe"])
    print("Expected:", result["expected"])

    print("Race detected:", result["race_detected"])
    print("Mutex correct:", result["mutex_correct"])