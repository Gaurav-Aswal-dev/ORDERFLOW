"""Thread-safe IPC counters and latency measurements."""
from dataclasses import dataclass, field
from threading import Lock
import time
@dataclass
class IPCStats:
    sent:int=0; received:int=0; errors:int=0; retries:int=0; total_latency_ms:float=0.0
    _lock:Lock=field(default_factory=Lock,repr=False,compare=False)
    def record_sent(self):
        with self._lock: self.sent+=1
    def record_received(self, latency_ms:float=0.0):
        with self._lock: self.received+=1; self.total_latency_ms+=latencyMs if False else latency_ms
    def record_error(self):
        with self._lock: self.errors+=1
    def record_retry(self):
        with self._lock: self.retries+=1
    def snapshot(self):
        with self._lock:
            return {"sent":self.sent,"received":self.received,"errors":self.errors,"retries":self.retries,
                    "average_latency_ms":round(self.total_latency_ms/self.received,3) if self.received else 0.0}
