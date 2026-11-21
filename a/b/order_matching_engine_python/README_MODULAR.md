# Order Matching Engine Modular V4

## Packages
- `matching_engine/`: order models, price-time matcher, SQLite persistence, producer and demo runtime.
- `ipc/`: transport, protocol validation/constants, message factories, JSON serialization, worker, supervisor, dispatcher, recovery policy, health monitor, metrics, config, exceptions and structured logging.
- `os_modules/synchronization/`: mutex, semaphore, producer-consumer and race-condition demonstrations.
- `dashboard/`: FastAPI dashboard, stock-master validation and file replay API.
- `web/static/`: browser assets.
- `order_engine/`: original compatibility package retained for legacy CLI commands.

## IPC flow
Dashboard/CLI -> `IPCDispatcher`/`MatcherSupervisor` -> multiprocessing Pipe -> `ipc.worker.matcher_worker` -> `MatchingEngine` -> SQLite.
Supervisor startup handshake, bounded request timeouts, worker liveness checks, retry policy, stable order-ID retry, restart counting, IPC error/latency metrics and status endpoint are implemented.

## File imports
Dashboard `/api/import/file` accepts CSV, XLSX and JSON. All require `symbol,side,price,quantity`. Set `replay=false` to validate without submitting orders. Excel requires `openpyxl` (included in `requirements-web.txt`).



## Database location

All default SQLite files are stored under `database/`. The dashboard uses
`database/web_demo.db` by default; set `ORDER_ENGINE_DB` to override its path.
CLI demos use `database/order_engine.db` (and `database/showcase.db` for the
showcase). Stock catalog and per-symbol databases live in `database/stock_master.db`
and `database/stock_data/<SYMBOL>.db`. Database files are created automatically
and are not included in the source ZIP.
