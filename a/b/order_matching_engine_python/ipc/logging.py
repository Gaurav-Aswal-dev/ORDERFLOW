"""Structured IPC event logging helpers."""
import logging
def get_logger(name="order_matching_engine.ipc"):
    logger=logging.getLogger(name)
    if not logger.handlers:
        handler=logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [IPC] %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
def log_event(logger,event,**fields):
    logger.info("%s %s",event," ".join(f"{k}={v}" for k,v in fields.items()))
