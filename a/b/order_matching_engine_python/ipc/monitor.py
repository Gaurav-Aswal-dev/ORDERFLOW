"""Worker liveness and heartbeat snapshot."""
from dataclasses import dataclass, field
import time
@dataclass
class WorkerMonitor:
    started_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    heartbeats: int = 0
    def heartbeat(self):
        self.last_seen=time.time(); self.heartbeats+=1
    def snapshot(self, alive: bool):
        return {"alive":alive,"uptime_seconds":round(time.time()-self.started_at,3),
                "last_seen":self.last_seen,"heartbeats":self.heartbeats}
