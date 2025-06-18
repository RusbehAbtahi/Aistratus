"""
Smoke-test for TinyLlamaView (headless).

Ensures TinyLlamaView can be imported and instantiated
without errors, even in an environment without a display
by providing a fake tkinter with StringVar, Button, and Label support.
"""

import sys
import importlib
from types import ModuleType


# ---------------------------------------------------------------------------
# Lightweight fake tkinter / ttk / messagebox modules
# ---------------------------------------------------------------------------
class _Dummy:
    def __init__(self, *_, **__):
        pass

    def pack(self, *_, **__):
        pass

    def bind(self, *_, **__):
        pass

    def config(self, *_, **__):
        pass

    def start(self, *_):
        pass

    def stop(self):
        pass

    def insert(self, *_, **__):
        pass

    def delete(self, *_, **__):
        pass

    def yview_moveto(self, *_):
        pass

    def state(self, *_):
        pass

    def create_oval(self, *_, **__):
        pass

    def after(self, *_):
        pass

    def title(self, *_):
        # view.root.title(...)
        pass

    def mainloop(self):
        pass


class _DummyStringVar:
    """Fake tk.StringVar(textvariable)."""
    def __init__(self, *args, **kwargs):
        self.value = kwargs.get("value", "")
    def get(self):
        return self.value
    def set(self, v):
        self.value = v


def _fake_tkinter_module():
    tk_mod = ModuleType("tkinter")
    # Core classes
    tk_mod.Tk = _Dummy
    tk_mod.Text = _Dummy
    tk_mod.Canvas = _Dummy
    tk_mod.StringVar = _DummyStringVar
    tk_mod.Button = _Dummy    # for Stop GPU button
    tk_mod.Label = _Dummy     # for cost_label
    tk_mod.END = "end"

    # ttk submodule
    ttk_mod = ModuleType("tkinter.ttk")
    for cls in ("Frame", "Button", "Progressbar", "Combobox", "Label", "Spinbox"):
        setattr(ttk_mod, cls, _Dummy)
    sys.modules["tkinter.ttk"] = ttk_mod
    tk_mod.ttk = ttk_mod

    # messagebox submodule
    msg_mod = ModuleType("tkinter.messagebox")
    msg_mod.showerror = lambda *_, **__: None
    sys.modules["tkinter.messagebox"] = msg_mod
    tk_mod.messagebox = msg_mod

    return tk_mod


def test_tinyllamaview_can_be_built(monkeypatch):
    """
    Smoke-test: TinyLlamaView must import and instantiate
    without raising exceptions, even headlessly.
    """
    # Arrange: inject fake tkinter
    fake_tk = _fake_tkinter_module()
    monkeypatch.setitem(sys.modules, "tkinter", fake_tk)

    # Act
    gui_view = importlib.import_module("tinyllama.gui.gui_view")
    view = gui_view.TinyLlamaView()

    # Assert
    assert hasattr(view, "root"), "Missing root attribute"
    assert callable(view.root.title), "root.title must exist"
    assert callable(view.root.mainloop), "root.mainloop must exist"
    # Check backend dropdown
    assert hasattr(view, "backend_var"), "StringVar backend_var not created"
    assert view.backend_var.get() == "AWS TinyLlama"
