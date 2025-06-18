"""
Unit-tests for tinyllama.gui.thread_service.ThreadService

Focus:
1. run_async() executes the worker function on the background thread
   and delivers its result to ui_callback once on the UI thread.
2. schedule() registers a Tk.after call and re-schedules itself.
"""

import importlib

# ---------------------------------------------------------------------------
# Minimal fake Tk root
# ---------------------------------------------------------------------------
class _FakeTk:
    """
    Mimics `tk.Tk` just enough for ThreadService.

    * after(ms, fn, *args, **kw): records scheduled calls without recursion.
    """
    def __init__(self):
        self.after_calls = []

    def after(self, ms: int, fn, *args, **kwargs):
        # record the call for test inspection
        self.after_calls.append((ms, fn, args, kwargs))


# Load the ThreadService class
ThreadService = importlib.import_module(
    "tinyllama.gui.thread_service"
).ThreadService


def test_run_async_executes_and_returns():
    """
    run_async should:
    • execute *work* on its worker thread
    • call ui_callback exactly once with the return value on the UI thread
    """
    root = _FakeTk()
    service = ThreadService(ui_root=root)

    flag = {"worker_done": False, "ui_payload": None}

    def work(a, b):
        flag["worker_done"] = True
        return a + b

    def ui_cb(value):
        flag["ui_payload"] = value

    service.run_async(work, 2, 3, ui_callback=ui_cb)

    # Wait for worker thread to finish
    service._worker.join(timeout=0.2)

    # Pump UI callbacks
    service._pump_results()

    assert flag["worker_done"] is True
    assert flag["ui_payload"] == 5


def test_schedule_registers_after_call():
    """
    schedule(interval, tick) should register one additional Tk.after call
    besides the initial pump_results scheduling, and tick() must run when
    we invoke the scheduled callback.
    """
    root = _FakeTk()
    service = ThreadService(ui_root=root)

    counter = {"ticks": 0}

    def tick():
        counter["ticks"] += 1

    # Count initial pump_results scheduling
    initial = len(root.after_calls)

    # Invoke schedule
    service.schedule(0.01, tick)

    # Exactly one new after-call for wrap_schedule
    assert len(root.after_calls) - initial == 1

    # Extract and invoke the wrap_schedule entry
    ms, fn, args, kwargs = root.after_calls[-1]
    fn(*args, **kwargs)

    # Our tick() must have run once
    assert counter["ticks"] == 1

    # wrap_schedule re-scheduled itself
    assert len(root.after_calls) - initial == 2
