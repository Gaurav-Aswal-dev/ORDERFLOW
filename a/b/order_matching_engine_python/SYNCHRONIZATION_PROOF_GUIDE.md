# Synchronization proof (actual MatchingEngine)

This proof calls the **real** `matching_engine.MatchingEngine.process()` from two Python threads concurrently. Both threads share one engine instance, and its `_state_lock` (`RLock`) protects the order-book mutation.

## Run

From this directory:

```powershell
python synchronization_proof.py
```

It creates a temporary SQLite database and deletes it automatically afterward. It does not touch your company databases or dashboard orders.

## What to show your teacher

1. Both `THREAD READY` lines show two worker threads ready at the same time.
2. `SYNC WAIT` means a thread is about to enter `process()`.
3. `SYNC ACQUIRED` means it entered the critical section and owns the real engine lock.
4. `SYNC RELEASE` means it finished the protected section.
5. Observe that the ACQUIRED/RELEASE sequence does not overlap: one thread releases before the other acquires.
6. One SELL and one BUY at the same price produce one trade, showing the shared book was matched consistently.

The proof is intentionally isolated in a temporary DB. The existing OS-Lab counter page remains a separate race-condition-vs-mutex simulation; it does not submit trading orders.
