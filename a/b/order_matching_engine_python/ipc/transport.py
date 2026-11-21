"""Pipe transport primitives with polling, timeout and connection checks."""
from multiprocessing import Pipe
from multiprocessing.connection import Connection
from .errors import RequestTimeout, WorkerUnavailable
def create_duplex_pipe(): return Pipe(duplex=True)
def send_message(connection:Connection,message:dict):
    if connection.closed: raise WorkerUnavailable("IPC connection is closed")
    connection.send(message)
def receive_message(connection:Connection,timeout:float|None=None)->dict:
    if connection.closed: raise WorkerUnavailable("IPC connection is closed")
    if timeout is not None and not connection.poll(timeout): raise RequestTimeout(f"No IPC response within {timeout}s")
    return connection.recv()
def close_connection(connection):
    try: connection.close()
    except (OSError,ValueError): pass
