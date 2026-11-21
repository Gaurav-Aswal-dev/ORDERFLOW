# Dashboard review and synchronization proof

## Synchronization proof (actual MatchingEngine)

Open **OS Lab** and click **Run actual engine lock proof**. The action uses a temporary SQLite database and two concurrent Python threads that share one `MatchingEngine` object. It does not submit to the normal trading database.

The output includes:
- `SYNC WAIT`: a thread is about to enter `MatchingEngine.process()`.
- `SYNC ACQUIRED`: that thread has acquired the engine's real `RLock`.
- `SYNC RELEASE`: that thread leaves the protected section.

The order of events demonstrates that the engine's critical section is serialized. Both orders and any execution are displayed below the log. The existing counter experiment remains as a separate generic race-condition/mutex illustration.

## Dashboard control review

Static review verified event handlers and corresponding API routes for:
- Main order side selection, order submission, refresh, CSV/Excel/JSON replay.
- Per-symbol order placement, stock-master search/import, conditional order create/list/refresh/cancel.
- OS Lab process telemetry refresh, generic synchronization experiment, actual engine-lock proof.
- Continuous bidding submit/load book and auction create/refresh/place bid/close.

Checks performed: Python compileall, Node JavaScript syntax check, live Uvicorn smoke checks for `/os-lab` and `/api/os-lab/engine-lock-proof`. The proof endpoint returned the expected WAIT/ACQUIRED/RELEASE events and two order results.

This is a code and API smoke review, not a full browser-driven click-through of every control on every possible data state.
