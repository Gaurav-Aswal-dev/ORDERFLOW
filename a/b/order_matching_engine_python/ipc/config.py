"""IPC runtime configuration."""
from dataclasses import dataclass
@dataclass(frozen=True)
class IPCConfig:
    startup_timeout: float = 10.0
    request_timeout: float = 5.0
    shutdown_timeout: float = 3.0
    max_retries: int = 3
    process_name: str = "MatcherProcess"
    heartbeat_interval: float = 1.0
