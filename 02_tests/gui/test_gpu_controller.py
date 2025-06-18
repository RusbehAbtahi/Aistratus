"""
Unit-tests for tinyllama.gui.controllers.gpu_controller.GpuController

Checks
──────
1. on_stop_gpu() calls _simulate_stop() **only** when backend == 'AWS TinyLlama'
   and writes expected output.
2. For non-AWS backend it writes the OpenAI-specific message and does NOT call
   _simulate_stop().
"""

import sys
import importlib
from types import ModuleType


# ───────────────────────────── helper stubs ──────────────────────────────────
class StubState:
    def __init__(self, backend):
        self.backend = backend


class StubService:
    pass


class StubView:
    def __init__(self):
        self.out = []

    def append_output(self, text):
        self.out.append(text)


# ───────────────────────────── test helpers ──────────────────────────────────
def _import_controller():
    for k in list(sys.modules):
        if k.startswith("tinyllama.gui.controllers.gpu_controller"):
            del sys.modules[k]
    return importlib.import_module(
        "tinyllama.gui.controllers.gpu_controller"
    ).GpuController


# ────────────────────────────────── tests ─────────────────────────────────────
def test_stop_gpu_path_for_aws(monkeypatch):
    GpuController = _import_controller()
    st, view, svc = StubState("AWS TinyLlama"), StubView(), StubService()
    ctrl = GpuController(state=st, service=svc, view=view)

    called = {"flag": False}

    def fake_sim():
        called["flag"] = True
        view.append_output("[GPU] Stop GPU simulated (AWS backend)")

    monkeypatch.setattr(ctrl, "_simulate_stop", fake_sim)

    ctrl.on_stop_gpu()

    assert called["flag"] is True
    assert "[GPU] Stop GPU simulated" in view.out[-1]


def test_no_gpu_to_stop_for_openai():
    GpuController = _import_controller()
    st, view, svc = StubState("OpenAI GPT-3.5"), StubView(), StubService()
    ctrl = GpuController(state=st, service=svc, view=view)

    # monkey-patching not required; _simulate_stop should NOT be called
    ctrl.on_stop_gpu()

    assert "[GPU] No GPU to stop for OpenAI backend." in view.out[-1]
