"""Demonstrate Semaphore using threading.Semaphore."""

import threading
import time


class SemaphoreDemo:

    def __init__(self, max_concurrent=3):
        self.semaphore = threading.Semaphore(max_concurrent)
        self.active_threads = 0
        self.max_active = 0
        self.counter_lock = threading.Lock()

    def access_resource(self, thread_id):

        print(f"Thread {thread_id} waiting")

        with self.semaphore:

            with self.counter_lock:
                self.active_threads += 1
                self.max_active = max(
                    self.max_active,
                    self.active_threads
                )
                current_active = self.active_threads

            print(f"Thread {thread_id} entered resource")
            print(f"Currently active threads: {current_active}")

            time.sleep(2)

            with self.counter_lock:
                self.active_threads -= 1

            print(f"Thread {thread_id} exited resource")


def semaphore_demo(workers=7, max_concurrent=3):

    demo = SemaphoreDemo(max_concurrent)

    threads = [
        threading.Thread(
            target=demo.access_resource,
            args=(i,)
        )
        for i in range(1, workers + 1)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    print("\n--- SEMAPHORE DEMONSTRATION ---")
    print("Total threads:", workers)
    print("Semaphore limit:", max_concurrent)
    print("Maximum concurrent threads:", demo.max_active)
    print("Semaphore working:", demo.max_active <= max_concurrent)


if __name__ == "__main__":
    semaphore_demo()