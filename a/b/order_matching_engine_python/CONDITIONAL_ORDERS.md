# Live Stop-Loss and Take-Profit orders

These are implemented against the company-specific matching engines and SQLite files.

## API
Create a conditional order:
```http
POST /api/stocks/TCS/conditional-orders
Content-Type: application/json
{"kind":"STOP_LOSS","side":"SELL","trigger_price":95,"quantity":10}
```
`kind` is `STOP_LOSS` or `TAKE_PROFIT`; `side` is `BUY` or `SELL`.
The monitor checks the latest executed trade price in `database/stock_data/TCS.db`.
When the condition is met, it creates a normal `Order` and submits it to the
same `MatchingEngine` used by `/api/stocks/TCS/orders`. The resulting order ID
is stored as `triggered_order_id`.

List: `GET /api/stocks/TCS/conditional-orders`

Cancel an active trigger: `DELETE /api/conditional-orders/{conditional_order_id}`

## Operational notes
- Trigger records are persisted in `database/conditional_orders.db`.
- A background thread polls once per second; it does not block FastAPI request handling.
- A conditional order is atomically claimed (`ACTIVE` -> `EXECUTING`) before submission,
  preventing duplicate firing across monitor ticks. Successful orders become `TRIGGERED`.
- A failed submission is returned to `ACTIVE` with an error field for retry.
- Stock-engine execution is serialized with the dashboard's shared reentrant lock.
- Triggered orders are ordinary limit orders at the trigger price, so they can remain
  open if the opposite book has no crossing liquidity. This is not a guaranteed fill.
- The trigger price is based on the latest actual execution stored in that company's
  database. No external market-data feed is included.

## Dashboard controls

Open the main dashboard and use **Stop-Loss & Take-Profit**:

1. Enter a listed stock symbol (for example `RELIANCE`).
2. Choose `STOP_LOSS` or `TAKE_PROFIT`, side, trigger price, and quantity.
3. Click **Create condition**. Use **Refresh** to reload conditions, or **Cancel** while a condition is ACTIVE.
4. Conditions evaluate the latest actual execution in that symbol's database. On trigger they submit a normal limit order at the trigger price; a trigger does not guarantee a fill.

## Synchronization integration

`MatchingEngine` now uses a per-instance `threading.RLock` around `process()` and `snapshot()`. This serializes concurrent order-book mutation and snapshots and prevents callers from observing an intermediate match state. The dashboard also uses its shared execution lock for company order processing and stock book/trade reads, including conditional-trigger submissions.
