import types, json, pytest
import tinyllama.gui.app as app_mod
from tinyllama.gui.app import TinyLlamaGUI

@pytest.fixture
def gui(monkeypatch):
    # Patch cost poll thread to run synchronously in tests
    monkeypatch.setattr(
        app_mod.threading, "Thread",
        lambda target, args=(), daemon=None:
            types.SimpleNamespace(start=lambda: None)
    )
    g = TinyLlamaGUI(); g.withdraw(); yield g; g.destroy()

def test_initial_text(gui):
    assert gui.cost_var.get().startswith("€")

def test_set_cost_colours(gui):
    gui._set_cost(8.0)
    assert gui.cost_label["fg"] == "#212529"
    gui._set_cost(12.0)
    assert gui.cost_label["fg"] == "#f0ad4e"
    gui._set_cost(16.1)
    assert gui.cost_label["fg"] == "#d9534f"

def test_polling_uses_api(gui, monkeypatch):
    called = {"cnt": 0}
    monkeypatch.setattr(gui, "_fetch_cost_api", lambda: called.__setitem__("cnt", called["cnt"]+1) or 3.21)
    monkeypatch.setattr(app_mod.time, "sleep", lambda s: None)          # skip actual wait
    gui._cost_poller()                                                 # run once
    assert called["cnt"] == 1
    assert "3.21" in gui.cost_var.get()
