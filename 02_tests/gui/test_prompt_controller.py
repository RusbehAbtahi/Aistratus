"""
Unit tests for tinyllama.gui.controllers.prompt_controller.PromptController

Checks:
• on_send()          – empty prompt ignored; valid prompt schedules async job
• _on_backend_reply  – success and error paths update state/UI correctly
"""

import sys
import importlib
from types import ModuleType

# ──────────────────────────────────────────────────────────────────────────────
# Minimal stubs
# ──────────────────────────────────────────────────────────────────────────────
class StubState:
    def __init__(self):
        self.backend = "AWS TinyLlama"
        self.idle_minutes = 5
        self.current_cost = 0.0
        self.cost_log = []
        self.history = []

    def set_cost(self, eur):
        self.cost_log.append(eur)
        self.current_cost = eur

    def add_history(self, line):
        self.history.append(line)


class StubView:
    def __init__(self):
        self.busy_log = []
        self.out_lines = []

    def set_busy(self, flag):
        self.busy_log.append(flag)

    def append_output(self, text):
        self.out_lines.append(text)


class StubService:
    def __init__(self):
        self.async_jobs = []

    def run_async(self, fn, *args, ui_callback=None, **kw):
        self.async_jobs.append((fn, args, ui_callback))


class FakeBackendClient:
    """Pretends to send a prompt and returns (reply, cost)."""
    def send_prompt(self, prompt, metadata):
        return f"REPLY:{prompt}", 1.23


# ──────────────────────────────────────────────────────────────────────────────
# Helper – load real controller, clearing any earlier stubs
# ──────────────────────────────────────────────────────────────────────────────
def _import_controller(monkeypatch):
    """
    Previous tests (e.g. test_main) inject stub modules under
    'tinyllama.gui.controllers'.  Remove them so we load the real package.
    """
    # Drop *all* modules under that prefix if they were added as stubs
    for key in list(sys.modules.keys()):
        if key.startswith("tinyllama.gui.controllers"):
            del sys.modules[key]

    # Import the genuine controller
    pc_mod = importlib.import_module(
        "tinyllama.gui.controllers.prompt_controller"
    )

    # Ensure mapping exists then patch our fake backend
    if not hasattr(pc_mod, "_CLIENTS_BY_NAME"):
        pc_mod._CLIENTS_BY_NAME: dict = {}
    monkeypatch.setitem(
        pc_mod._CLIENTS_BY_NAME, "AWS TinyLlama", FakeBackendClient
    )

    return pc_mod.PromptController


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
def test_on_send_empty_prompt_ignored(monkeypatch):
    PromptController = _import_controller(monkeypatch)
    st, view, svc = StubState(), StubView(), StubService()
    ctrl = PromptController(state=st, service=svc, view=view)

    ctrl.on_send("   ")

    assert view.out_lines and view.out_lines[-1].startswith("⚠️")
    assert view.busy_log == []
    assert svc.async_jobs == []


def test_on_send_happy_path(monkeypatch):
    PromptController = _import_controller(monkeypatch)
    st, view, svc = StubState(), StubView(), StubService()
    ctrl = PromptController(state=st, service=svc, view=view)

    ctrl.on_send("hello")

    assert view.busy_log == [True]
    assert len(svc.async_jobs) == 1
    fn, args, cb = svc.async_jobs[0]
    assert fn is PromptController._call_backend
    assert st.backend == "AWS TinyLlama"


def test_on_backend_reply_success(monkeypatch):
    PromptController = _import_controller(monkeypatch)
    st, view, svc = StubState(), StubView(), StubService()
    ctrl = PromptController(state=st, service=svc, view=view)

    ctrl._on_backend_reply({"ok": True, "reply": "hi", "cost": 2.0})

    assert view.busy_log[-1] is False
    assert st.current_cost == 2.0
    assert st.history and st.history[-1].endswith("hi")
    assert view.out_lines and "hi" in view.out_lines[-1]


def test_on_backend_reply_error(monkeypatch):
    PromptController = _import_controller(monkeypatch)
    st, view, svc = StubState(), StubView(), StubService()
    ctrl = PromptController(state=st, service=svc, view=view)

    ctrl._on_backend_reply({"ok": False, "error": "boom"})

    assert view.busy_log[-1] is False
    assert view.out_lines and "boom" in view.out_lines[-1]
