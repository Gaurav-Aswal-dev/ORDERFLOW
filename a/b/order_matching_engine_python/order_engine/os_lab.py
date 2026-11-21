"""OS lab simulations kept isolated from the production matching path."""
from __future__ import annotations
import threading, time



def synchronization_demo(iterations=100000):
    """Safe threaded race-vs-lock demonstration using shared counter."""
    iterations=max(1000,min(int(iterations),500000)); workers=4
    def run(locked):
        counter=[0]; lock=threading.Lock(); barrier=threading.Barrier(workers)
        def worker():
            barrier.wait()
            for _ in range(iterations):
                if locked:
                    with lock: counter[0]+=1
                else:
                    # Deliberately split read/write to make race visible; demo only.
                    v=counter[0]; v+=1; counter[0]=v
        ts=[threading.Thread(target=worker) for _ in range(workers)]; start=time.perf_counter()
        [x.start() for x in ts]; [x.join() for x in ts]
        return {'counter':counter[0],'expected':workers*iterations,'elapsed_ms':round((time.perf_counter()-start)*1000,2)}
    return {'workers':workers,'iterations_per_worker':iterations,'unsafe':run(False),'locked':run(True),'note':'Isolated demonstration only; it does not touch engine orders or databases.'}
