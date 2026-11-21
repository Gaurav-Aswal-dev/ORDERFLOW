"""Retry policy preserving order IDs for idempotent database recovery."""
from dataclasses import dataclass
@dataclass
class RetryPolicy:
    max_attempts:int=3
    def should_retry(self,attempt:int)->bool: return attempt < self.max_attempts
def retry_same_message(message:dict)->dict:
    # Never generate a new order_id during retry.
    return dict(message)
