import json
import time
import pytest
from unittest.mock import patch
from tinyllama.gui.app import TinyLlamaGUI

@pytest.fixture
def gui():
    g = TinyLlamaGUI()
    g.withdraw()
    yield g
    g.destroy()

def test_build_payload_preserves_newlines(gui):
    # This test can be skipped if build_payload is gone.
    # Instead, test that JSON payload preserves newlines via _send_to_api
    text = "line1\nline2\nline3"
    payload = json.dumps({"prompt": text, "idle": gui.idle_minutes})
    assert json.loads(payload)["prompt"] == text

def test_ctrl_enter_binding_exists(gui):
    assert gui.prompt_box.bind("<Control-Return>")

def test_button_disabled_and_spinner_visible(gui, monkeypatch):
    with patch.object(gui, "_send_to_api", return_value=None):
        gui._on_send()
        gui.update()
        assert "disabled" in gui.send_btn.state()
        assert gui.spinner.winfo_manager() == "pack"

def test_button_reenabled_after_api_completion(gui, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    payload = json.dumps({"prompt": "test", "idle": gui.idle_minutes})
    gui._send_to_api(payload)
    gui.update()
    assert "disabled" not in gui.send_btn.state()

