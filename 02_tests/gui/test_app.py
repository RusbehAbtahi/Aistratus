import builtins, time, types
import pytest
from unittest.mock import MagicMock, patch
from tinyllama.gui.app import TinyLlamaGUI


@pytest.fixture
def gui():
    # Tk builds the real window – keep hidden during tests
    g = TinyLlamaGUI()
    g.withdraw()
    yield g
    g.destroy()


def test_button_disabled_and_spinner_visible(gui, monkeypatch):
    monkeypatch.setattr(gui, "after", lambda *a, **k: None)
    with patch.object(gui, "_send_to_api", return_value=None):
        gui._on_send()
        gui.update()                             # process geometry
        assert "disabled" in gui.send_btn.state()
        assert gui.spinner.winfo_manager() == "pack"







def test_button_reenabled_after_api_completion(gui, monkeypatch):
    # monkeypatch time.sleep to instant, but keep call to simulate 2-s API
    monkeypatch.setattr("time.sleep", lambda s: None)

    # call real _send_to_api in same thread (no need for background)
    gui._send_to_api(gui.build_payload("test"))

    # allow Tk event loop to process re-enable (0 ms after)
    gui.update_idletasks()
    assert "disabled" not in gui.send_btn.state()


def test_ctrl_enter_binding_exists(gui):
    assert gui.prompt_box.bind("<Control-Return>")
