"""Persistent conditional stock orders evaluated against real executions."""
from __future__ import annotations
import sqlite3, threading, time, uuid
from pathlib import Path
from decimal import Decimal
from matching_engine.models import Order

class ConditionalOrderService:
    def __init__(self, db_path, stock_db_dir, engine_getter, execution_lock, interval=1.0):
        self.db_path=Path(db_path); self.stock_db_dir=Path(stock_db_dir)
        self.engine_getter=engine_getter; self.execution_lock=execution_lock; self.interval=interval
        self.db_path.parent.mkdir(parents=True,exist_ok=True)
        self._stop=threading.Event(); self._thread=None
        with self._connect() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS conditional_orders(
              id TEXT PRIMARY KEY, symbol TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('STOP_LOSS','TAKE_PROFIT')),
              side TEXT NOT NULL CHECK(side IN ('BUY','SELL')), trigger_price TEXT NOT NULL,
              quantity INTEGER NOT NULL CHECK(quantity>0), status TEXT NOT NULL DEFAULT 'ACTIVE',
              created_at REAL NOT NULL, triggered_at REAL, triggered_order_id TEXT, last_price TEXT, error TEXT)''')
    def _connect(self):
        c=sqlite3.connect(self.db_path,timeout=15); c.row_factory=sqlite3.Row; return c
    def create(self,symbol,kind,side,trigger_price,quantity):
        symbol=symbol.upper(); kind=kind.upper(); side=side.upper(); p=Decimal(str(trigger_price))
        if kind not in ('STOP_LOSS','TAKE_PROFIT') or side not in ('BUY','SELL'): raise ValueError('Invalid kind or side')
        if not p.is_finite() or p<=0: raise ValueError('trigger_price must be > 0')
        if isinstance(quantity,bool) or int(quantity)!=quantity or quantity<=0: raise ValueError('quantity must be a positive integer')
        oid=str(uuid.uuid4()); now=time.time()
        with self._connect() as c: c.execute('INSERT INTO conditional_orders(id,symbol,kind,side,trigger_price,quantity,created_at) VALUES(?,?,?,?,?,?,?)',(oid,symbol,kind,side,str(p),int(quantity),now))
        return self.get(oid)
    def get(self,oid):
        with self._connect() as c: r=c.execute('SELECT * FROM conditional_orders WHERE id=?',(oid,)).fetchone()
        return dict(r) if r else None
    def list(self,symbol=None):
        with self._connect() as c:
            rows=c.execute('SELECT * FROM conditional_orders'+(' WHERE symbol=?' if symbol else '')+' ORDER BY created_at DESC',(symbol.upper(),) if symbol else ()).fetchall()
        return [dict(x) for x in rows]
    def cancel(self,oid):
        with self._connect() as c: cur=c.execute("UPDATE conditional_orders SET status='CANCELLED' WHERE id=? AND status='ACTIVE'",(oid,))
        return cur.rowcount==1
    def start(self):
        if self._thread and self._thread.is_alive(): return
        self._stop.clear(); self._thread=threading.Thread(target=self._run,name='conditional-order-monitor',daemon=True); self._thread.start()
    def stop(self):
        self._stop.set()
        if self._thread: self._thread.join(timeout=3)
    def _run(self):
        while not self._stop.wait(self.interval):
            for item in self.list():
                if item['status']!='ACTIVE': continue
                try: self._check(item)
                except Exception as e:
                    with self._connect() as c: c.execute('UPDATE conditional_orders SET error=? WHERE id=? AND status=\'ACTIVE\'',(str(e)[:500],item['id']))
    def _check(self,item):
        db=self.stock_db_dir/f"{item['symbol']}.db"
        if not db.exists(): return
        with sqlite3.connect(db,timeout=2) as c:
            row=c.execute('SELECT price FROM trades ORDER BY trade_id DESC LIMIT 1').fetchone()
        if not row: return
        last=Decimal(str(row[0])); trigger=Decimal(item['trigger_price'])
        hit=(last<=trigger if item['kind']=='STOP_LOSS' and item['side']=='SELL' else
             last>=trigger if item['kind']=='TAKE_PROFIT' and item['side']=='SELL' else
             last>=trigger if item['kind']=='STOP_LOSS' and item['side']=='BUY' else last<=trigger)
        with self._connect() as c: c.execute('UPDATE conditional_orders SET last_price=? WHERE id=? AND status=\'ACTIVE\'',(str(last),item['id']))
        if not hit: return
        # Atomic claim prevents duplicate execution by overlapping scheduler ticks.
        claimed=time.time()
        with self._connect() as c:
            cur=c.execute("UPDATE conditional_orders SET status='EXECUTING',triggered_at=?,last_price=? WHERE id=? AND status='ACTIVE'",(claimed,str(last),item['id']))
            if cur.rowcount!=1: return
        try:
            order=Order.create(item['side'],trigger,item['quantity'],source=f"conditional:{item['kind']}:{item['id']}")
            with self.execution_lock: result=self.engine_getter(item['symbol']).process(order)
            with self._connect() as c: c.execute("UPDATE conditional_orders SET status='TRIGGERED',triggered_order_id=?,error=NULL WHERE id=?",(order.order_id,item['id']))
        except Exception as e:
            with self._connect() as c: c.execute("UPDATE conditional_orders SET status='ACTIVE',error=? WHERE id=?",(str(e)[:500],item['id']))
