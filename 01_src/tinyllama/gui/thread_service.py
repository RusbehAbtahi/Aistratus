"""
thread_service.py

Background thread + Tk-safe result return for TinyLlama GUI.
- run_async(fn, ...) runs blocking code off the UI thread, result/exception sent to UI callback.
- schedule(interval_s, fn, ...) ticks on the UI thread (Tk after).
"""

from __future__ import annotations
import threading
import queue
import time
from typing import Any, Callable, Dict, Tuple, Optional

class ThreadService:
    def __init__(self, ui_root) -> None:
        self._ui_root = ui_root
        # Separate queues for jobs and results
        self._job_q: queue.Queue[Dict[str, Any]] = queue.Queue()
        self._result_q: queue.Queue[Tuple[Optional[Callable], Tuple[Any, ...], Dict[str, Any]]] = queue.Queue()

        self._worker = threading.Thread(
            target=self._worker_loop,
            name="ThreadServiceWorker",
            daemon=True,
        )
        self._worker.start()
        self._pump_results()

    def run_async(
        self,
        fn: Callable[..., Any],
        *args: Any,
        ui_callback: Optional[Callable[[Any], None]] = None,
        **kwargs: Any
    ) -> None:
        # Push background job to worker; result will call ui_callback on main thread
        job = {
            "fn": fn,
            "args": args,
            "kwargs": kwargs,
            "callback": ui_callback,
        }
        self._job_q.put(job)

    def schedule(
        self,
        interval_s: int,
        fn: Callable[..., None],
        *args: Any,
        **kwargs: Any
    ) -> str:
        # Recurring UI-thread call of fn every interval_s seconds (Tk after)
        ms = max(1000, int(interval_s * 1000))
        return self._ui_root.after(
            ms,
            self._wrap_schedule,
            ms,
            fn,
            args,
            kwargs,
        )

    def _worker_loop(self) -> None:
        # Background thread: run jobs and push results back for UI thread
        while True:
            job = self._job_q.get()
            fn: Callable = job["fn"]
            cb: Optional[Callable] = job["callback"]
            args, kwargs = job["args"], job["kwargs"]
            try:
                result = fn(*args, **kwargs)
                payload = result
            except Exception as exc:
                payload = exc
            # enqueue callback for UI
            self._result_q.put((cb, (payload,), {}))

    def _pump_results(self) -> None:
        # UI thread: execute all result callbacks (if any)
        try:
            while True:
                cb, cb_args, cb_kwargs = self._result_q.get_nowait()
                if cb:
                    try:
                        cb(*cb_args, **cb_kwargs)
                    except Exception as ui_exc:
                        print(f"[ThreadService] UI callback error: {ui_exc}")
        except queue.Empty:
            pass
        self._ui_root.after(50, self._pump_results)

    def _wrap_schedule(
        self,
        ms: int,
        fn: Callable,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any]
    ) -> None:
        # Internal: run fn, then reschedule
        try:
            fn(*args, **kwargs)
        finally:
            self._ui_root.after(ms, self._wrap_schedule, ms, fn, args, kwargs)
