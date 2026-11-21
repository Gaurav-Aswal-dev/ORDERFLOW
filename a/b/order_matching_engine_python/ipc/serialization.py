"""Safe, explicit dictionary serialization for IPC messages (Pipe uses pickle internally)."""
import json
from typing import Any
def encode_json(message: dict[str, Any]) -> bytes:
    return json.dumps(message, separators=(",",":"), default=str).encode("utf-8")
def decode_json(payload: bytes | str) -> dict[str, Any]:
    value=json.loads(payload.decode("utf-8") if isinstance(payload,bytes) else payload)
    if not isinstance(value,dict): raise ValueError("IPC payload must decode to an object")
    return value
