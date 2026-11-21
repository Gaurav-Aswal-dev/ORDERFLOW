# Order Matching Engine with IPC (Python)

A runnable educational implementation of the project described in the supplied brief. It uses two independent processes, `multiprocessing.Pipe` for IPC, price-time-priority matching, and SQLite as the durable source of truth.

## Features implemented

- **Producer process** generates buy/sell orders and sends them one at a time.
- **Matcher process** receives and validates order messages over an IPC queue.
- **Matching rules**: a buy crosses a sell when buy price >= resting sell price; a sell crosses a buy when sell price <= resting buy price.
- **Price-time priority**: highest-priced buy and lowest-priced sell have priority; older orders win ties.
- **Partial fills**: matched quantity is traded and any remainder stays in the book.
- **SQLite persistence**: orders and trades are committed transactionally; WAL mode and `synchronous=FULL` are enabled.
- **Recovery**: on startup, open and partially-filled orders are loaded from SQLite. Completed trades remain queryable.
- **Duplicate-message protection**: a processed order ID is recorded transactionally.
- **Crash demonstration**: deliberately terminate the matcher after N processed orders, then restart it to observe recovered book state.
- **Tests** cover matching, partial fills, recovery, and duplicate delivery.

## Requirements

- Python 3.10+
- No third-party packages. Only the Python standard library is used.

## Run it

Open a terminal in this folder.

### 1. Run the producer and matcher processes

```bash
python -m order_engine --db demo.db demo --count 20
```

The demo starts separate `ProducerProcess` and `MatcherProcess` children. The Producer and supervisor communicate through a `multiprocessing.Pipe`; the supervisor forwards each order to the separate Matcher over another `multiprocessing.Pipe` and returns the acknowledgement.

### 2. Run the deterministic presentation showcase

Use a fresh database so the expected output stays easy to explain:

```bash
python -m order_engine --db showcase.db showcase
```

This runs a fixed scenario that demonstrates resting orders, a non-crossing order, matching at the resting price, and one incoming order filling against multiple resting orders.

### 3. Inspect saved orders and trades

```bash
python -m order_engine --db demo.db inspect
```

### 4. Inspect the recovered live order book

```bash
python -m order_engine --db demo.db book
```

### 5. Enter orders manually

```bash
python -m order_engine --db manual.db interactive
```

Example input:

```text
SELL 100 5
BUY 99 3
BUY 101 2
quit
```

### 6. Simulate a matcher crash

```bash
python -m order_engine --db crash-demo.db demo --count 20 --crash-after 5
```

The matcher exits abruptly after processing the configured number of orders. The supervisor detects the dead process and restarts it. The client retries the same order ID when an acknowledgement is lost, and the SQLite processed-message table makes that replay idempotent. Inspect what was committed:

```bash
python -m order_engine --db crash-demo.db inspect
python -m order_engine --db crash-demo.db book
```

Then restart normally using the same database:

```bash
python -m order_engine --db crash-demo.db demo --count 5
```

The matcher reconstructs the outstanding book from persisted open/partial orders. Random demo orders are newly generated on each run. The in-process supervisor retries an unacknowledged order with the same ID during a live run; this is not a durable producer outbox across a full machine reboot.

### 7. Run tests

From the project folder:

```bash
python -m unittest discover -s tests -v
```

## File layout

```text
order_matching_engine_python/
├── order_engine/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── matcher.py
│   ├── models.py
│   ├── producer.py
│   ├── runtime.py
│   └── storage.py
├── tests/
│   └── test_engine.py
└── README.md
```

## Matching example

If a resting `SELL 100 x 5` exists and a new `BUY 102 x 3` arrives, 3 units trade at 100 (the resting order's price). The sell order remains in the book with quantity 2.

## Important design notes and limitations

This is a learning project, not a production exchange.

1. The demo has one matcher process and one producer process. A single matcher serializes book updates, avoiding concurrent matching races. The supervisor relays producer messages and owns the matcher Pipe.
2. SQLite is the source of truth. Open order quantities and each trade are committed in one transaction.
3. The book is reconstructed from open and partially-filled orders, not from trades alone. Completed trades cannot reveal every still-open order.
4. `multiprocessing.Pipe` is a simple IPC channel, not a durable message broker. A hard crash can lose messages that were queued but not committed. A production version would need acknowledgements, replayable input logs, or a durable broker and a carefully designed idempotency protocol.
5. The crash demo exercises process restart and idempotent retry within a running supervisor. It is still an educational prototype: it does not have a durable producer outbox across machine failure.
6. Prices are stored as decimal strings to avoid binary floating-point comparisons.
7. This prototype does not implement authentication, market symbols, cancel/replace requests, exchange sessions, regulatory controls, or high-throughput performance engineering.

## Concept map

- **OS**: process creation, IPC, blocking queue reads, abnormal termination, restart.
- **DBMS**: transactions, constraints, durability settings, persisted state, recovery.
- **Algorithms**: price-time priority, crossing-price check, partial fills.


## Web dashboard (HTML/CSS/JavaScript)

The `web/` folder adds a browser dashboard backed by FastAPI. The UI is plain HTML, CSS, and JavaScript; the backend calls the existing Python matching engine and SQLite storage.

### Start on Windows

From the project root (the folder containing `order_engine`, `web`, and `tests`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-web.txt
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` in your browser. Stop the server with Ctrl+C.

### API endpoints

- `GET /api/health` - health check
- `GET /api/book` - current open order book
- `GET /api/trades?limit=10` - latest trade records
- `GET /api/stats` - order/trade counts and traded quantity
- `POST /api/orders` - submit a simulated order, JSON such as `{"side":"BUY","price":101,"quantity":3}`

FastAPI's interactive API docs are at `http://127.0.0.1:8000/docs`.

### Important architecture note

The web server routes submitted orders through a supervised matcher child process over `multiprocessing.Pipe`. The CLI demo also runs a separate Producer process and Matcher process, with a parent supervisor relaying messages. The dashboard reads persisted state from SQLite. This is a local educational demo, not a real trading service; do not expose it to the public internet.


### 8. Run the focused crash/restart demonstration

```powershell
python crash_recovery_demo.py
```

This injects one matcher crash, verifies that the supervisor restarts it for the next request, and replays the first order ID to show deduplication. Run this from the project root. Use a fresh database for each showcase.

## Dashboard features

The dashboard includes order entry, stock-specific books, CSV replay/import, stock master management, live runtime monitoring, and a synchronization demo. Benchmark Arena and CPU Scheduling simulations have been removed.

## File replay formats
Upload CSV, Excel (`.xlsx`), or JSON files containing `symbol`, `side`, `price`, and `quantity` fields. JSON may be a list of order objects or an object with an `orders` list. Files are limited to 5 MB and 10,000 records.

## Stock master validation

Multi-stock order entry and file replay now require a symbol present in the local `stock_master.db` catalog. A starter catalog of 10 NSE companies is inserted on first launch; this is only a starter, not the complete exchange list. Search the stock selector by ticker or company name.

To load the complete/current catalog, download the NSE **Securities available for Equity segment (.csv)** file from [NSE Securities available for trading](https://www.nseindia.com/static/market-data/securities-available-for-trading), then use **Import NSE master** in the Stock books panel. The importer accepts a CSV with a `Symbol` column and (optionally) `Company Name`; existing symbols are updated. NSE also publishes a daily MII security master in its [All Reports](https://www.nseindia.com/all-reports) section. This catalog confirms listing identity only; it is not live prices or a guarantee of current tradability.

API: `GET /api/stock-master/search?q=...`, `GET /api/stock-master/stats`, and `POST /api/stock-master/import` (multipart `file`). Unknown symbols are rejected for per-stock orders and CSV/XLSX/JSON replay.

## Operating Systems Lab (`/os-lab`)

The OS Lab page contains live process telemetry and an isolated race-condition-vs-mutex synchronization demo. It does not simulate CPU scheduling or control the Windows scheduler.

## Organized module folders
See `ARCHITECTURE.md` for the new module map. Existing commands/imports remain compatible during this first safe refactor.


## v2 modular architecture
The `engine/` package is authoritative; IPC Pipe transport is in `ipc/`; producer worker is in `producer/`; OS labs are under `os_modules/`; FastAPI implementation is `dashboard/app.py` with assets in `web/static/`. Existing `uvicorn web.app:app --reload` remains supported.

## V7: Bidding modules

Two independent simulated bidding applications are available from the dashboard sidebar:

- **Continuous Bidding** (`/continuous-bidding`): multi-symbol limit orders, price-time priority, partial fills, order cancellation, order book and execution history. API endpoints live under `/api/continuous`; records are in `database/continuous_bidding.db`.
- **Auction Bidding** (`/auction-bidding`): create stock auctions with a starting price and duration, submit ascending bids, inspect bid history, and close auctions to record the winner. API endpoints live under `/api/auctions`; records are in `database/auction_bidding.db`.

Both validate symbols against `database/stock_master.db` and support catalogued symbols (for example RELIANCE, ICICIBANK, and TATAMOTORS). They do not alter the original exchange database or company-specific `database/stock_data/<SYMBOL>.db` files. All activity is simulated; no broker or real-money integration exists.

Run from this project folder: `uvicorn web.app:app --reload`. API documentation: `/docs`.
