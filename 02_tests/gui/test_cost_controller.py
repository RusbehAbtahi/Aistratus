"""
Unit-tests for tinyllama.gui.controllers.cost_controller.CostController

Checks
──────
1.  __init__() immediately pushes 0 € to both AppState and TinyLlamaView.
2.  view.update_cost() is invoked whenever AppState.set_cost() is called later.
"""

import sys
import importlib
from types import ModuleType


# ───────────────────────────── helper stubs ──────────────────────────────────
class StubView:
    def __init__(self):
        self.cost_calls = []          # records € values passed in

    def update_cost(self, eur: float):
        self.cost_calls.append(eur)


class StubService:
    """Unused by CostController stub version, but required for ctor parity."""
    pass


class StubState:
    def __init__(self):
        self.current_cost = None
        self.subscribers = {}

    # publisher / subscriber minimals
    def subscribe(self, event, cb):
        self.subscribers.setdefault(event, []).append(cb)

    def set_cost(self, eur):
        self.current_cost = eur
        for cb in self.subscribers.get("cost", []):
            cb(eur)


# ───────────────────────────── test helpers ──────────────────────────────────
def _import_controller():
    """
    Ensure we load the *real* cost_controller even if another
    test already inserted a stub package under the same namespace.
    """
    for k in list(sys.modules):
        if k.startswith("tinyllama.gui.controllers.cost_controller"):
            del sys.modules[k]
    return importlib.import_module(
        "tinyllama.gui.controllers.cost_controller"
    ).CostController


# ────────────────────────────────── tests ─────────────────────────────────────
def test_initialises_with_zero_cost():
    CostController = _import_controller()
    st, view, svc = StubState(), StubView(), StubService()

    CostController(state=st, service=svc, view=view)

    assert st.current_cost == 0.0
    assert view.cost_calls == [0.0]


def test_subscribes_and_updates_later():
    CostController = _import_controller()
    st, view, svc = StubState(), StubView(), StubService()
    CostController(state=st, service=svc, view=view)

    st.set_cost(7.77)        # simulate later polling cycle

    assert view.cost_calls[-1] == 7.77
