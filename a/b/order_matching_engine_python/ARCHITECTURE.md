# Modular architecture (v2)

`engine/` is now the authoritative matching core (models, matcher, SQLite storage, supervisor/runtime). `producer/` contains producer worker code. `ipc/` owns the live duplex Pipe factory, message protocol constants, and counters; the engine supervisor uses this transport and records sent/received messages. `os_modules/scheduling/` contains scheduling labs; `os_modules/synchronization/` contains mutex/semaphore/producer-consumer/race exercises. `dashboard/app.py` is the FastAPI implementation and imports the authoritative `engine.*`; `web/` retains static assets and a backwards-compatible `web.app:app` entry point. `order_engine/` remains a compatibility/CLI package only.

CPU scheduling simulations and benchmark arena were removed. Matching priority remains price-time. IPC is actual multiprocessing Pipe communication between supervisor and matcher; its telemetry counts supervisor sends/receives.
