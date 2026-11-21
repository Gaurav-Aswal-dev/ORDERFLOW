"""Message factories for the local matcher IPC protocol."""
from dataclasses import dataclass, asdict
from typing import Any
from .protocol import ORDER, STOP, HEARTBEAT, ACK
@dataclass
class OrderMessage:
    order_id: str
    side: str
    price: str
    quantity: int
    created_at: float
    source: str = "ipc"
    type: str = ORDER
    def to_dict(self): return asdict(self)
@dataclass
class ControlMessage:
    type: str
    message_id: str | None = None
    payload: dict[str, Any] | None = None
    def to_dict(self): return asdict(self)
def shutdown_message(): return {"type": STOP}
def heartbeat_message(): return {"type": HEARTBEAT}
def ack_message(message_id=None): return {"type": ACK, "message_id": message_id}
