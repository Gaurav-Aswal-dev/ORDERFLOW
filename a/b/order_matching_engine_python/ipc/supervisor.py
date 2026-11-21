"""Own matcher process lifecycle, request/response IPC, retries and metrics."""
import multiprocessing as mp, threading, time
from .transport import create_duplex_pipe,send_message,receive_message,close_connection
from .protocol import STOP,ERROR,validate_order_message
from .worker import matcher_worker
from .ipc_monitor import IPCStats
from .config import IPCConfig
from .recovery import RetryPolicy,retry_same_message
from .errors import RequestTimeout,WorkerUnavailable
from .monitor import WorkerMonitor
class MatcherSupervisor:
    def __init__(self,database_path:str,crash_after:int|None=None,config:IPCConfig|None=None):
        self.database_path=database_path; self.crash_after=crash_after
        self.config=config or IPCConfig(); self.restart_count=0
        self._ctx=mp.get_context("spawn"); self._lock=threading.RLock()
        self.ipc_stats=IPCStats(); self.retry_policy=RetryPolicy(self.config.max_retries)
        self.monitor=WorkerMonitor(); self._start()
    def _start(self):
        parent,child=create_duplex_pipe(); ready=self._ctx.Event()
        proc=self._ctx.Process(target=matcher_worker,args=(child,self.database_path,self.crash_after,ready),name=self.config.process_name)
        proc.start(); child.close()
        if not ready.wait(self.config.startup_timeout):
            proc.terminate(); proc.join(); close_connection(parent)
            raise WorkerUnavailable("Matcher worker failed startup handshake")
        self.process,self.connection=proc,parent; self.crash_after=None
    def _restart(self):
        close_connection(self.connection)
        if self.process.is_alive(): self.process.terminate()
        self.process.join(timeout=2); self.restart_count+=1; self._start()
    def submit(self,message:dict,timeout:float|None=None)->dict:
        validate_order_message(message); timeout=timeout or self.config.request_timeout
        with self._lock:
            for attempt in range(1,self.retry_policy.max_attempts+1):
                if not self.process.is_alive(): self._restart()
                started=time.perf_counter()
                try:
                    send_message(self.connection,retry_same_message(message)); self.ipc_stats.record_sent()
                    result=receive_message(self.connection,timeout)
                    self.ipc_stats.record_received((time.perf_counter()-started)*1000)
                    if result.get("type")==ERROR: raise RuntimeError(result.get("error","matcher error"))
                    self.monitor.heartbeat(); return result
                except (EOFError,OSError,RequestTimeout,WorkerUnavailable):
                    self.ipc_stats.record_error()
                    if attempt>=self.retry_policy.max_attempts: break
                    self.ipc_stats.record_retry(); self._restart()
            raise WorkerUnavailable("Matcher did not respond after IPC retry policy")
    def status(self):
        return {"pid":self.process.pid,"restart_count":self.restart_count,
                "ipc":self.ipc_stats.snapshot(),"worker":self.monitor.snapshot(self.process.is_alive())}
    def close(self):
        with self._lock:
            try:
                if self.process.is_alive(): send_message(self.connection,{"type":STOP}); self.process.join(self.config.shutdown_timeout)
                if self.process.is_alive(): self.process.terminate(); self.process.join(timeout=2)
            except Exception:
                if self.process.is_alive(): self.process.terminate(); self.process.join(timeout=2)
            close_connection(self.connection)
