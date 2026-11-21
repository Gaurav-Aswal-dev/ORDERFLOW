"""Small synchronous dispatcher for order requests."""
from .protocol import validate_order_message
class IPCDispatcher:
    def __init__(self, supervisor): self.supervisor=supervisor
    def dispatch(self, message: dict, timeout: float | None=None) -> dict:
        validate_order_message(message)
        return self.supervisor.submit(message, timeout=timeout) if timeout is not None else self.supervisor.submit(message)
