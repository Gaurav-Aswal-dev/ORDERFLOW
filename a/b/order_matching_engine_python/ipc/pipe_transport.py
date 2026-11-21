"""Live multiprocessing Pipe transport primitives."""
from multiprocessing import Pipe

def create_duplex_pipe():
    return Pipe(duplex=True)
