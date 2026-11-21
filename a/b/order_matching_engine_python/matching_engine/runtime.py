from __future__ import annotations
import multiprocessing as mp
from ipc.transport import create_duplex_pipe, send_message, receive_message
from ipc.protocol import STOP, ERROR, RESULT, DUPLICATE
from ipc.recovery import retry_same_message
from ipc.ipc_monitor import IPCStats
import os, random, time, uuid
from matching_engine.matcher import MatchingEngine
from matching_engine.models import Order
from matching_engine.storage import Storage


from ipc.worker import matcher_worker
from ipc.supervisor import MatcherSupervisor


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
                receive_message(conn)  # parent acknowledges only after matcher result
            except (EOFError, OSError):
                return
            if delay:
                time.sleep(delay)
        conn.send({"type": "STOP"})
    finally:
        conn.close()


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
            try: msg = receive_message(parent_conn)
            except EOFError: break
            if msg.get("type") == "STOP":
                break
            result = supervisor.submit(msg)
            send_message(parent_conn, result)
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
