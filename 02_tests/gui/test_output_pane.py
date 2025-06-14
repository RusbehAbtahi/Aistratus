import types, time, json
from datetime import datetime
import tinyllama.gui.app as app_mod
from tinyllama.gui.app import TinyLlamaGUI
import pytest

@pytest.fixture
def gui(monkeypatch, tmp_path):
    # Avoid real threads
    monkeypatch.setattr(app_mod.threading, "Thread",
                        lambda target, args=(), daemon=None:
                            types.SimpleNamespace(start=lambda: target(*args)))
    # Isolate INI to temp dir
    ini = tmp_path / "test.ini"
    monkeypatch.setattr(app_mod, "INI_PATH", ini)

    g = TinyLlamaGUI(); g.withdraw(); yield g; g.destroy()

def test_append_order_and_timestamp(gui, monkeypatch):
    fixed = datetime(2025, 1, 1, 12, 0, 0)
    monkeypatch.setattr(app_mod, "datetime", types.SimpleNamespace(
        now=lambda: fixed, datetime=datetime))
    gui.prompt_box.insert("1.0", "Hello")
    gui._on_send()                 # triggers user append and bot echo
    # Bot echo occurs via _send_to_api immediate call
    content = gui.out_pane.get("1.0", "end-1c").splitlines()
    assert content[0].startswith("[12:00:00] USER:")
    assert content[1].startswith("[12:00:00] BOT : Echo:")
    # Ensure order is preserved
    assert "USER" in content[0] and "BOT" in content[1]

def test_scroll_persistence(gui, tmp_path):
    gui._append_output("[00:00:01] USER: X\n")
    gui.out_pane.yview_moveto(0.3)
    gui._persist_scroll_position()
    assert (tmp_path / "test.ini").read_text().find("scroll") != -1
