"""IPC exception hierarchy."""
class IPCError(RuntimeError): pass
class ProtocolError(IPCError): pass
class WorkerUnavailable(IPCError): pass
class RequestTimeout(IPCError): pass
class WorkerCrashed(IPCError): pass
