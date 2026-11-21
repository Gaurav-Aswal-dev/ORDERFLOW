from __future__ import annotations
import multiprocessing as mp
import os, random, time, uuid
from .matcher import MatchingEngine
from .models import Order
from .storage import Storage


def matcher_worker(conn, database_path: str, crash_after: int | None = None, ready=None):
    storage = Storage(database_path)
    try:
        engine = MatchingEngine(storage)
        if ready is not None:
            ready.set()
        processed = 0
        while True:
            try:
                msg = conn.recv()
            except (EOFError, OSError):
                break
            if msg.get("type") == "STOP":
                break
            try:
                order = Order.from_message(msg)
                result = engine.process(order)
                conn.send(result)
                if result.get("type") in ("RESULT", "DUPLICATE"):
                    processed += 1
                if crash_after is not None and processed >= crash_after:
                    os._exit(17)
            except Exception as exc:
                try:
                    conn.send({"type": "ERROR", "error": str(exc), "order_id": msg.get("order_id")})
                except (BrokenPipeError, EOFError, OSError):
                    break
    finally:
        storage.close()
        conn.close()


def producer_worker(conn, count: int, seed: int = 42, delay: float = 0.05):
    rng = random.Random(seed)
    try:
        for i in range(count):
            conn.send({
                "type": "ORDER", "order_id": f"demo-{uuid.uuid4()}",
                "side": rng.choice(["BUY", "SELL"]), "price": str(rng.choice([98,99,100,101,102])),
                "quantity": rng.randint(1,10), "created_at": time.time(), "source": f"producer-{i}",
            })
            try:
                conn.recv()  # parent acknowledges only after matcher result
            except (EOFError, OSError):
                return
            if delay:
                time.sleep(delay)
        conn.send({"type": "STOP"})
    finally:
        conn.close()


class MatcherSupervisor:
    """Owns the matcher process and its Pipe; retries the same order ID after restart."""
    def __init__(self, database_path: str, crash_after: int | None = None):
        self.database_path = database_path
        self.crash_after = crash_after
        self.restart_count = 0
        self._ctx = mp.get_context("spawn")
        self._lock = __import__("threading").RLock()
        self._start()

    def _start(self):
        parent, child = self._ctx.Pipe(duplex=True)
        ready = self._ctx.Event()
        proc = self._ctx.Process(target=matcher_worker,
            args=(child, self.database_path, self.crash_after, ready), name="MatcherProcess")
        proc.start()
        child.close()
        if not ready.wait(10):
            proc.terminate()
            proc.join()
            raise RuntimeError("Matcher failed to become ready")
        self.process, self.connection = proc, parent
        self.crash_after = None  # crash injection happens only once

    def _restart(self):
        try: self.connection.close()
        except Exception: pass
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(timeout=2)
        self.restart_count += 1
        print(f"[supervisor] Restarting matcher (restart #{self.restart_count})")
        self._start()

    def submit(self, message: dict, timeout: float = 5.0) -> dict:
        with self._lock:
            for attempt in range(3):
                if not self.process.is_alive():
                    self._restart()
                try:
                    self.connection.send(message)
                    if self.connection.poll(timeout):
                        result = self.connection.recv()
                        if result.get("type") == "ERROR":
                            raise RuntimeError(result.get("error", "matcher error"))
                        return result
                except (BrokenPipeError, EOFError, OSError):
                    pass
                self._restart()
                # Re-send identical order ID: SQLite deduplication makes retry safe
                # if the original transaction committed but its acknowledgement was lost.
            raise RuntimeError("Matcher did not respond after restart/retry")

    def close(self):
        with self._lock:
            try:
                if self.process.is_alive():
                    self.connection.send({"type":"STOP"})
                    self.process.join(timeout=3)
                if self.process.is_alive():
                    self.process.terminate()
                    self.process.join(timeout=2)
            except Exception:
                if self.process.is_alive():
                    self.process.terminate()
                    self.process.join(timeout=2)
            try: self.connection.close()
            except Exception: pass


def run_demo(database_path="database/order_engine.db", count=20, delay=0.05, crash_after=None):
    ctx = mp.get_context("spawn")
    parent_conn, producer_conn = ctx.Pipe(duplex=True)
    producer = ctx.Process(target=producer_worker, args=(producer_conn, count, 42, delay), name="ProducerProcess")
    producer.start()
    producer_conn.close()
    supervisor = MatcherSupervisor(database_path, crash_after=crash_after)
    processed = 0
    try:
        while True:
            if not parent_conn.poll(0.2):
                if not producer.is_alive():
                    break
                if not supervisor.process.is_alive():
                    supervisor._restart()
                continue
            try: msg = parent_conn.recv()
            except EOFError: break
            if msg.get("type") == "STOP":
                break
            result = supervisor.submit(msg)
            parent_conn.send(result)
            if result.get("type") == "RESULT":
                processed += 1
                print(f"[matcher] {result['status']:7} {msg['side']} {msg['price']} x {msg['quantity']} "
                      f"trades={len(result.get('trades', []))}")
            elif result.get("type") == "DUPLICATE":
                print(f"[matcher] duplicate safely acknowledged: {msg['order_id']}")
    finally:
        parent_conn.close()
        if producer.is_alive():
            producer.terminate()
        producer.join(timeout=2)
        supervisor.close()
    storage = Storage(database_path)
    try:
        engine = MatchingEngine(storage)
        print(f"Summary: processed={processed}, matcher_restarts={supervisor.restart_count}, stats={storage.stats()}")
        print(f"Recovered book: buys={len(engine.buys)}, sells={len(engine.sells)}")
    finally:
        storage.close()


def run_showcase(database_path="database/showcase.db"):
    supervisor = MatcherSupervisor(database_path)
    scenario = [
        ("showcase-sell-1","SELL","100",5), ("showcase-sell-2","SELL","101",4),
        ("showcase-buy-1","BUY","99",3), ("showcase-buy-2","BUY","100",2),
        ("showcase-buy-3","BUY","102",5),
    ]
    try:
        for i,(oid,side,price,qty) in enumerate(scenario):
            msg={"type":"ORDER","order_id":oid,"side":side,"price":price,"quantity":qty,
                 "created_at":time.time()+i*.001,"source":"deterministic-showcase"}
            result=supervisor.submit(msg)
            print(f"{side} {price} x {qty}: {result.get('status',result.get('type'))}; "
                  f"trades={len(result.get('trades',[]))}; remaining={result.get('remaining_quantity','-')}")
            for trade in result.get("trades",[]):
                print(f"  TRADE {trade['quantity']} @ {trade['price']}")
    finally:
        supervisor.close()
    storage=Storage(database_path)
    try:
        engine=MatchingEngine(storage)
        print(f"Final book: buys={len(engine.buys)}, sells={len(engine.sells)}; stats={storage.stats()}")
    finally: storage.close()


def run_matcher_only(database_path="database/order_engine.db"):
    storage=Storage(database_path)
    try:
        engine=MatchingEngine(storage)
        print("Matcher ready. Enter: BUY price quantity | SELL price quantity | quit")
        while True:
            raw=input("> ").strip()
            if raw.lower() in {"quit","exit"}: break
            parts=raw.split()
            if len(parts)!=3:
                print("Use: BUY price quantity"); continue
            try:
                order=Order.create(parts[0],parts[1],int(parts[2]),source="interactive")
                print(engine.process(order))
            except Exception as exc: print(f"Invalid order: {exc}")
    finally: storage.close()
