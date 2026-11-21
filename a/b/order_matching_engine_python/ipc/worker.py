"""Matcher process entry point and IPC worker loop."""
import os
from matching_engine.models import Order
from matching_engine.matcher import MatchingEngine
from matching_engine.storage import Storage
from .protocol import STOP, ORDER, ERROR, READY
from .transport import send_message, receive_message
def matcher_worker(conn,database_path:str,crash_after:int|None=None,ready=None):
    storage=Storage(database_path)
    try:
        engine=MatchingEngine(storage)
        if ready is not None: ready.set()
        processed=0
        while True:
            try: msg=receive_message(conn)
            except (EOFError,OSError): break
            if msg.get("type")==STOP: break
            try:
                if msg.get("type")!=ORDER: raise ValueError(f"Unsupported IPC message type: {msg.get('type')}")
                order=Order.from_message(msg); result=engine.process(order)
                send_message(conn,result)
                if result.get("type") in ("RESULT","DUPLICATE"): processed+=1
                if crash_after is not None and processed>=crash_after: os._exit(17)
            except Exception as exc:
                try: send_message(conn,{"type":ERROR,"error":str(exc),"order_id":msg.get("order_id")})
                except (BrokenPipeError,EOFError,OSError): break
    finally:
        storage.close(); conn.close()
