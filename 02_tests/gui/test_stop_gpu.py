import types
import pytest
from unittest.mock import patch
from tinyllama.gui.app import TinyLlamaGUI
import tinyllama.gui.app as app_mod

@pytest.fixture
def gui():
    g = TinyLlamaGUI()
    g.withdraw()
    yield g
    g.destroy()

def test_stop_button_properties(gui):
    assert gui.stop_btn["text"] == "Stop GPU"
    assert gui.stop_btn["bg"] == "#d9534f"

def test_stop_gpu_success_toast_and_metric(gui, monkeypatch):
    # Patch threading.Thread to run target synchronously
    monkeypatch.setattr(
        app_mod.threading, "Thread",
        lambda target, args=(), daemon=None:
            types.SimpleNamespace(start=lambda: target(*args))
    )
    # Mock HTTP POST /stop as 200 OK
    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: types.SimpleNamespace(status_code=200, raise_for_status=lambda: None)
    )
    # Spy on toast
    called = {"info": False}
    monkeypatch.setattr(
        "tkinter.messagebox.showinfo",
        lambda *a, **k: called.__setitem__("info", True)
    )

    gui._on_stop_gpu()
    gui.update()
    assert called["info"] is True
    assert gui.stop_btn["state"] == "normal"

def test_stop_gpu_failure_shows_error(gui, monkeypatch):
    # Patch threading.Thread to run target synchronously
    monkeypatch.setattr(
        app_mod.threading, "Thread",
        lambda target, args=(), daemon=None:
            types.SimpleNamespace(start=lambda: target(*args))
    )
    # Mock HTTP POST /stop to raise an error
    monkeypatch.setattr(
        "requests.post",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("net down"))
    )
    # Spy on toast
    called = {"err": False}
    monkeypatch.setattr(
        "tkinter.messagebox.showerror",
        lambda *a, **k: called.__setitem__("err", True)
    )

    gui._on_stop_gpu()
    gui.update()
    assert called["err"] is True
    assert gui.stop_btn["state"] == "normal"

