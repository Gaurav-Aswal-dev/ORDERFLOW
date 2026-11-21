# Database files

SQLite databases are generated here at runtime. This folder is intentionally shipped
without database files so every fresh checkout starts clean.

- `web_demo.db`: dashboard's default order book (override with `ORDER_ENGINE_DB`).
- `order_engine.db`: CLI/demo matching engine database.
- `showcase.db`: deterministic showcase database.
- `stock_master.db`: stock symbol catalog.
- `stock_data/<SYMBOL>.db`: per-symbol order books.

The application creates this directory and any nested directories automatically.
