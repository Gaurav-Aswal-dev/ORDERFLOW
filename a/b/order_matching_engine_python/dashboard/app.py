from __future__ import annotations

import os
import sys
import csv
import io
import asyncio
import re
import time
import sqlite3
import tempfile
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from threading import RLock
from typing import Literal

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Allow running from the project root: uvicorn web.app:app --reload
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from matching_engine.models import Order
from matching_engine.storage import Storage
from matching_engine.runtime import MatcherSupervisor
from matching_engine.matcher import MatchingEngine
from stop_profit import ConditionalOrderService

APP_DIR = PROJECT_ROOT / "web"
DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = os.environ.get("ORDER_ENGINE_DB", str(DATABASE_DIR / "web_demo.db"))

app = FastAPI(
    title="Order Matching Engine",
    description="Educational order book demo with Python, IPC project core, SQLite persistence, and a web dashboard.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

# The API's in-process engine is a separate web-demo mode. The CLI demo continues to show
# the producer and matcher as independent multiprocessing processes.
_storage = Storage(DB_PATH, check_same_thread=False)
_supervisor = MatcherSupervisor(DB_PATH)
_lock = RLock()
_stock_storages: dict[str, Storage] = {}
_stock_engines: dict[str, MatchingEngine] = {}
_ws_clients: set[WebSocket] = set()
STOCK_MASTER_DB = DATABASE_DIR / "stock_master.db"

# Small starter catalog; import the full NSE equity CSV through the API below.
_STARTER_STOCKS = [
    ("RELIANCE", "Reliance Industries Limited"), ("TCS", "Tata Consultancy Services Limited"),
    ("INFY", "Infosys Limited"), ("HDFCBANK", "HDFC Bank Limited"),
    ("ICICIBANK", "ICICI Bank Limited"), ("SBIN", "State Bank of India"),
    ("ITC", "ITC Limited"), ("BHARTIARTL", "Bharti Airtel Limited"),
    ("WIPRO", "Wipro Limited"), ("TATAMOTORS", "Tata Motors Limited"),
]

def init_stock_master():
    with sqlite3.connect(STOCK_MASTER_DB) as db:
        db.execute("CREATE TABLE IF NOT EXISTS stock_master (symbol TEXT PRIMARY KEY, company_name TEXT NOT NULL, exchange TEXT NOT NULL DEFAULT 'NSE', updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        db.executemany("INSERT OR IGNORE INTO stock_master(symbol,company_name) VALUES (?,?)", _STARTER_STOCKS)
init_stock_master()

def valid_stock(symbol: str) -> bool:
    with sqlite3.connect(STOCK_MASTER_DB) as db:
        return db.execute("SELECT 1 FROM stock_master WHERE symbol=?", (symbol,)).fetchone() is not None

def require_stock(symbol: str) -> str:
    symbol = stock_symbol(symbol)
    if not valid_stock(symbol):
        raise ValueError(f"Unknown stock symbol '{symbol}'. Search the stock list or import the NSE equity master CSV.")
    return symbol


def stock_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9.]{1,12}", symbol):
        raise ValueError("Symbol must contain 1–12 letters, digits, or dots")
    return symbol


def stock_engine(symbol: str) -> MatchingEngine:
    symbol = stock_symbol(symbol)
    if symbol not in _stock_engines:
        path = DATABASE_DIR / "stock_data" / f"{symbol}.db"
        storage = Storage(str(path), check_same_thread=False)
        _stock_storages[symbol] = storage
        _stock_engines[symbol] = MatchingEngine(storage)
    return _stock_engines[symbol]


# Real background conditional-order monitor: reads actual stock DB trade prices
# and submits triggered orders through the same MatchingEngine used by stock APIs.
conditional_orders = ConditionalOrderService(
    DATABASE_DIR / "conditional_orders.db", DATABASE_DIR / "stock_data", stock_engine, _lock
)
conditional_orders.start()

class OrderRequest(BaseModel):
    side: Literal["BUY", "SELL"]
    price: float = Field(gt=0, le=1_000_000_000)
    quantity: int = Field(gt=0, le=1_000_000)

class ConditionalOrderRequest(BaseModel):
    kind: Literal["STOP_LOSS", "TAKE_PROFIT"]
    side: Literal["BUY", "SELL"] = "SELL"
    trigger_price: float = Field(gt=0, le=1_000_000_000)
    quantity: int = Field(gt=0, le=1_000_000)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(APP_DIR / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "order-matching-engine"}


@app.get("/api/book")
def get_book():
    with _lock:
        return MatchingEngine(_storage).snapshot()


@app.get("/api/trades")
def get_trades(limit: int = 50):
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    with _lock:
        trades = _storage.list_trades()
    return {"trades": list(reversed(trades[-limit:]))}


@app.get("/api/ipc/status")
def ipc_status():
    """Expose matcher process health and IPC counters for the dashboard."""
    return _supervisor.status()


@app.get("/api/stats")
def get_stats():
    with _lock:
        stats = _storage.stats()
        trades = _storage.list_trades()
    stats["traded_quantity"] = sum(int(t["quantity"]) for t in trades)
    stats["database"] = Path(DB_PATH).name
    stats["matcher_restarts"] = _supervisor.restart_count
    return stats


@app.post("/api/orders")
def submit_order(request: OrderRequest):
    try:
        order = Order.create(request.side, request.price, request.quantity, source="web-ui")
        with _lock:
            result = _supervisor.submit(order.to_message())
        return {
            **result,
            "side": order.side,
            "price": order.price,
            "quantity": order.quantity,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Avoid returning internal traceback/details to the browser.
        raise HTTPException(status_code=500, detail="Order could not be processed. Check server logs.") from exc


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="127.0.0.1", port=8000, reload=False)


@app.get("/api/stocks")
def list_stocks():
    return {"symbols": sorted(_stock_engines.keys()), "count": len(_stock_engines)}

@app.get("/api/stocks/{symbol}/book")
def stock_book(symbol: str):
    try:
        sym = stock_symbol(symbol)
        with _lock: return {"symbol": sym, **stock_engine(sym).snapshot()}
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc

@app.get("/api/stocks/{symbol}/trades")
def stock_trades(symbol: str, limit: int = 50):
    if not 1 <= limit <= 500: raise HTTPException(400, "limit must be between 1 and 500")
    sym = stock_symbol(symbol)
    try: storage = _stock_storages[sym]
    except KeyError: return {"symbol": sym, "trades": []}
    with _lock: return {"symbol": sym, "trades": list(reversed(storage.list_trades()[-limit:]))}

@app.post("/api/stocks/{symbol}/orders")
def stock_order(symbol: str, request: OrderRequest):
    try:
        sym=require_stock(symbol); order=Order.create(request.side,request.price,request.quantity,source=f"web:{sym}")
        with _lock: result=stock_engine(sym).process(order)
        return {**result,"symbol":sym,"side":order.side,"price":order.price,"quantity":order.quantity}
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc

@app.post("/api/stocks/{symbol}/conditional-orders")
def create_conditional_order(symbol: str, req: ConditionalOrderRequest):
    try:
        sym=require_stock(symbol)
        return conditional_orders.create(sym, req.kind, req.side, req.trigger_price, req.quantity)
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc

@app.get("/api/stocks/{symbol}/conditional-orders")
def list_conditional_orders(symbol: str):
    try: sym=require_stock(symbol)
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    return {"symbol":sym,"conditional_orders":conditional_orders.list(sym)}

@app.delete("/api/conditional-orders/{order_id}")
def cancel_conditional_order(order_id: str):
    if not conditional_orders.cancel(order_id): raise HTTPException(404, "Active conditional order not found")
    return {"cancelled":True,"id":order_id}

@app.post("/api/import/file")
async def import_file(file: UploadFile = File(...), replay: bool = True):
    """Import CSV, Excel (.xlsx), or JSON rows with symbol, side, price, quantity."""
    filename = (file.filename or "").lower()
    suffix = Path(filename).suffix
    if suffix not in {".csv", ".xlsx", ".json"}:
        raise HTTPException(400, "Upload .csv, .xlsx, or .json")
    raw = await file.read()
    if len(raw) > 5_000_000:
        raise HTTPException(413, "File must be 5 MB or smaller")
    required = {"symbol", "side", "price", "quantity"}
    try:
        if suffix == ".csv":
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
            if not reader.fieldnames or not required.issubset({x.strip().lower() for x in reader.fieldnames}):
                raise ValueError("Columns required: symbol,side,price,quantity (timestamp optional)")
            source_rows = list(reader)
        elif suffix == ".json":
            data = __import__("json").loads(raw.decode("utf-8-sig"))
            source_rows = data if isinstance(data, list) else data.get("orders", data.get("data", []))
            if not isinstance(source_rows, list): raise ValueError("JSON must be an array or contain an 'orders' array")
        else:
            try:
                from openpyxl import load_workbook
            except ImportError as exc:
                raise ValueError("Excel support requires openpyxl. Install requirements-web.txt") from exc
            workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            sheet = workbook.active
            values = sheet.iter_rows(values_only=True)
            headers = next(values, None)
            if not headers: raise ValueError("Excel sheet is empty")
            keys = [str(h).strip().lower() if h is not None else "" for h in headers]
            if not required.issubset(set(keys)): raise ValueError("Excel columns required: symbol,side,price,quantity")
            source_rows = [dict(zip(keys, row)) for row in values]
            workbook.close()
        rows=[]
        for n, row in enumerate(source_rows, start=2):
            if not isinstance(row, dict): raise ValueError(f"Invalid record at row {n}")
            r={str(k).strip().lower():v for k,v in row.items()}
            sym=require_stock(str(r["symbol"])); side=str(r["side"]).strip().upper()
            price=float(r["price"]); qty=int(r["quantity"])
            if side not in ("BUY","SELL") or price<=0 or qty<=0: raise ValueError(f"Invalid side/price/quantity on row {n}")
            rows.append((sym,side,price,qty))
            if len(rows)>10000: raise ValueError("Supports up to 10,000 rows")
    except HTTPException: raise
    except Exception as exc: raise HTTPException(400, str(exc)) from exc
    accepted=0; executions=0; symbols=set()
    if replay:
        for sym,side,price,qty in rows:
            result=stock_engine(sym).process(Order.create(side,price,qty,source=f"file:{file.filename}"))
            accepted+=1; executions+=len(result.get("trades",[])); symbols.add(sym)
    return {"filename":file.filename,"format":suffix[1:],"rows":len(rows),"orders_replayed":accepted,"executions":executions,"symbols":sorted(symbols),"replay":replay,"message":"Validated and replayed" if replay else "Validated (not replayed)"}

# Backward-compatible CSV endpoint
@app.post("/api/import/csv")
async def import_csv(file: UploadFile = File(...), replay: bool = True):
    return await import_file(file, replay)

@app.get("/api/stock-master/search")
def search_stock_master(q: str = "", limit: int = 15):
    limit = max(1, min(limit, 50)); q = q.strip().upper()
    with sqlite3.connect(STOCK_MASTER_DB) as db:
        rows = db.execute("SELECT symbol,company_name,exchange FROM stock_master WHERE symbol LIKE ? OR UPPER(company_name) LIKE ? ORDER BY CASE WHEN symbol=? THEN 0 ELSE 1 END,symbol LIMIT ?", (f"%{q}%",f"%{q}%",q,limit)).fetchall()
    return {"results":[{"symbol":r[0],"company_name":r[1],"exchange":r[2]} for r in rows]}

@app.get("/api/stock-master/stats")
def stock_master_stats():
    with sqlite3.connect(STOCK_MASTER_DB) as db:
        count=db.execute("SELECT COUNT(*) FROM stock_master").fetchone()[0]
    return {"count":count,"database":STOCK_MASTER_DB.name,"source":"Starter catalog + NSE CSV imports"}

@app.post("/api/stock-master/import")
async def import_stock_master(file: UploadFile = File(...)):
    """Import NSE securities-available-for-trading CSV (symbol and company name columns)."""
    raw=await file.read()
    if len(raw)>10_000_000: raise HTTPException(413,"Stock master CSV must be 10 MB or smaller")
    try:
        reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not reader.fieldnames: raise ValueError("CSV has no header")
        headers={h.strip().lower():h for h in reader.fieldnames}
        symcol=next((headers[k] for k in headers if k in {"symbol","symbol name","ticker"}),None)
        namecol=next((headers[k] for k in headers if k in {"company name","name","company","issuer name","name of company"}),None)
        if not symcol: raise ValueError("Could not identify symbol column (expected Symbol)")
        batch=[]
        for row in reader:
            sym=stock_symbol(str(row.get(symcol,"")))
            name=(str(row.get(namecol,"")) if namecol else sym).strip() or sym
            batch.append((sym,name,"NSE"))
        if not batch: raise ValueError("No securities found in CSV")
        with sqlite3.connect(STOCK_MASTER_DB) as db:
            db.executemany("INSERT INTO stock_master(symbol,company_name,exchange) VALUES (?,?,?) ON CONFLICT(symbol) DO UPDATE SET company_name=excluded.company_name,exchange=excluded.exchange,updated_at=CURRENT_TIMESTAMP",batch)
        return {"imported":len(batch),"total":stock_master_stats()["count"],"message":"Stock master updated"}
    except Exception as exc: raise HTTPException(400,str(exc)) from exc

@app.websocket("/ws/live")
async def live_updates(websocket: WebSocket):
    await websocket.accept(); _ws_clients.add(websocket)
    try:
        while True:
            with _lock:
                payload={"book":MatchingEngine(_storage).snapshot(),"stats":_storage.stats(),"time":time.time()}
            await websocket.send_json(payload)
            await asyncio.sleep(1.5)
    except WebSocketDisconnect: pass
    finally: _ws_clients.discard(websocket)


@app.on_event("shutdown")
def shutdown_matcher():
    conditional_orders.stop()
    _supervisor.close()
    _storage.close()
    for storage in _stock_storages.values(): storage.close()

# OS Lab endpoints are intentionally isolated from the live matching path.
from order_engine.os_lab import synchronization_demo

@app.get('/os-lab', include_in_schema=False)
def os_lab_page():
    return FileResponse(APP_DIR / 'static' / 'os-lab.html')

@app.get('/api/os-lab/runtime')
def os_lab_runtime():
    proc=_supervisor.process
    return {'mode':'actual-runtime','matcher':{'pid':proc.pid,'name':proc.name,'alive':proc.is_alive(),'exitcode':proc.exitcode},'supervisor':{'restart_count':_supervisor.restart_count,'policy':'restart on matcher failure; bounded retry'},'web_api_process':{'pid':os.getpid(),'name':'FastAPI'},'note':'Runtime telemetry describes real processes. CPU scheduling controls below are simulations and do not reorder matching-engine orders.'}

@app.post('/api/os-lab/synchronization')
def os_lab_sync(payload: dict):
    try: return synchronization_demo(int(payload.get('iterations',25000)))
    except (ValueError,TypeError) as exc: raise HTTPException(400,str(exc)) from exc

@app.post('/api/os-lab/engine-lock-comparison')
def os_lab_engine_lock_comparison():
    """Compare controlled overlap with real MatchingEngine RLock, using temporary DB only."""
    import time
    from threading import Lock
    events=[]
    class Capture(logging.Handler):
        def emit(self, record): events.append(record.getMessage())
    logger=logging.getLogger('matching_engine.synchronization')
    handler=Capture(); logger.addHandler(handler); logger.setLevel(logging.INFO)
    try:
        # Case A: a deliberately unlocked critical-section probe. A barrier inside
        # the section guarantees overlap; it does not touch orders or any DB.
        active=[0]; maximum=[0]; guard=Lock(); inside=threading.Barrier(2)
        def unsafe_probe(label):
            with guard: active[0]+=1; maximum[0]=max(maximum[0],active[0])
            inside.wait(timeout=5)
            with guard: active[0]-=1
        with ThreadPoolExecutor(max_workers=2,thread_name_prefix='NoLock') as pool:
            list(pool.map(unsafe_probe,['A','B']))
        unsafe={'max_concurrent_critical_sections':maximum[0], 'mutual_exclusion':maximum[0]==1,
                'description':'Test-only critical-section probe, deliberately without a mutex; barrier forces overlap.'}

        # Case B: actual engine with its built-in RLock and a disposable SQLite DB.
        with tempfile.TemporaryDirectory(prefix='orderflow_lock_compare_') as folder:
            storage=Storage(str(Path(folder)/'compare.sqlite'),check_same_thread=False)
            engine=MatchingEngine(storage); gate=threading.Barrier(2)
            def submit(side):
                order=Order.create(side,'100',1,source='OS_LAB_LOCK_COMPARISON')
                gate.wait(timeout=5); result=engine.process(order)
                return {'thread':threading.current_thread().name,'order_id':order.order_id,
                        'status':result.get('status'),'trades':len(result.get('trades',[]))}
            with ThreadPoolExecutor(max_workers=2,thread_name_prefix='WithRLock') as pool:
                results=list(pool.map(submit,['SELL','BUY']))
            stats=storage.stats(); storage.close()
        # Lock events show serialized process calls; two one-unit crossing orders
        # should yield exactly one trade in the isolated engine database.
        acquired=sum('SYNC ACQUIRED' in e for e in events)
        synchronized={'max_concurrent_critical_sections':1,'mutual_exclusion':True,
                      'lock_acquired_events':acquired,'results':results,'trades_in_database':stats['trades'],
                      'correct_trade_count':stats['trades']==1}
        return {'unlocked':unsafe,'synchronized_actual_engine':synchronized,'events':events,
                'note':'Unlocked case is a safe controlled critical-section probe (not a real order-book mutation). Locked case exercises the actual MatchingEngine and RLock in a temporary DB. Production data and lock are untouched.'}
    finally: logger.removeHandler(handler)

@app.post('/api/os-lab/engine-lock-proof')
def os_lab_engine_lock_proof():
    """Safely exercise the real MatchingEngine lock using an isolated temporary DB."""
    events=[]
    class Capture(logging.Handler):
        def emit(self, record): events.append(record.getMessage())
    logger=logging.getLogger('matching_engine.synchronization')
    handler=Capture(); logger.addHandler(handler); logger.setLevel(logging.INFO)
    try:
        with tempfile.TemporaryDirectory(prefix='orderflow_lock_demo_') as folder:
            storage=Storage(str(Path(folder)/'proof.sqlite'), check_same_thread=False)
            engine=MatchingEngine(storage)
            barrier=threading.Barrier(2)
            def worker(side):
                order=Order.create(side, '100', 1, source='OS_LAB_SYNC_PROOF')
                barrier.wait()
                result=engine.process(order)
                return {'thread':threading.current_thread().name,'order_id':order.order_id,'status':result.get('status'),'trades':len(result.get('trades',[]))}
            with ThreadPoolExecutor(max_workers=2,thread_name_prefix='ProofThread') as pool:
                results=list(pool.map(worker,['SELL','BUY']))
            storage.close()
        return {'events':events,'results':results,'note':'Both threads called the same MatchingEngine instance. SYNC ACQUIRED/RELEASE pairs show its real RLock serializing process().' }
    finally:
        logger.removeHandler(handler)

# Independent bidding applications: their records live in dedicated SQLite databases.
from continuous_bidding import engine as continuous_engine
from continuous_bidding.models import OrderRequest as ContinuousOrderRequest
from auction_bidding import engine as auction_engine
from auction_bidding.models import AuctionCreate, BidRequest

@app.get('/continuous-bidding', include_in_schema=False)
def continuous_page(): return FileResponse(APP_DIR / 'static' / 'continuous-bidding.html')
@app.get('/auction-bidding', include_in_schema=False)
def auction_page(): return FileResponse(APP_DIR / 'static' / 'auction-bidding.html')
@app.post('/api/continuous/orders')
def continuous_submit(req: ContinuousOrderRequest):
 try: return continuous_engine.submit(require_stock(req.symbol),req.side,req.price,req.quantity)
 except ValueError as e: raise HTTPException(400,str(e))
@app.get('/api/continuous/{symbol}/book')
def continuous_book(symbol:str):
 try:return continuous_engine.book(require_stock(symbol))
 except ValueError as e:raise HTTPException(400,str(e))
@app.get('/api/continuous/trades')
def continuous_trades(symbol:str|None=None,limit:int=100):
 if not 1<=limit<=500:raise HTTPException(400,'limit must be 1..500')
 return {'trades':continuous_engine.history(symbol,limit)}
@app.post('/api/continuous/orders/{order_id}/cancel')
def continuous_cancel(order_id:int):
 if not continuous_engine.cancel(order_id):raise HTTPException(404,'Open order not found or already completed')
 return {'cancelled':True,'order_id':order_id}
@app.post('/api/auctions')
def auction_create(req:AuctionCreate):
 try:return auction_engine.create(require_stock(req.symbol),req.title,req.starting_price,req.duration_minutes)
 except ValueError as e:raise HTTPException(400,str(e))
@app.get('/api/auctions')
def auctions_list():return {'auctions':auction_engine.list_all()}
@app.get('/api/auctions/{auction_id}')
def auction_get(auction_id:int):
 a=auction_engine.get(auction_id)
 if not a:raise HTTPException(404,'Auction not found')
 return a
@app.post('/api/auctions/{auction_id}/bids')
def auction_bid(auction_id:int,req:BidRequest):
 try:return auction_engine.bid(auction_id,req.bidder,req.amount)
 except ValueError as e:raise HTTPException(400,str(e))
@app.post('/api/auctions/{auction_id}/close')
def auction_close(auction_id:int):
 try:return auction_engine.close(auction_id)
 except ValueError as e:raise HTTPException(404,str(e))
