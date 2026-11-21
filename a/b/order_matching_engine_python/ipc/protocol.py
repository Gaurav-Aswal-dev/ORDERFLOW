"""Protocol constants and validation."""
from typing import Any
ORDER="ORDER"; STOP="STOP"; RESULT="RESULT"; ERROR="ERROR"; DUPLICATE="DUPLICATE"
HEARTBEAT="HEARTBEAT"; ACK="ACK"; READY="READY"
def message_type(message: dict[str, Any]) -> str: return str(message.get("type",""))
def validate_order_message(message: dict[str, Any]) -> None:
    missing=[k for k in ("order_id","side","price","quantity") if k not in message]
    if missing: raise ValueError("Order message missing fields: "+", ".join(missing))
    if message["side"] not in ("BUY","SELL"): raise ValueError("side must be BUY or SELL")
    if int(message["quantity"]) <= 0: raise ValueError("quantity must be positive")
