import json
from tinyllama.gui.app import TinyLlamaGUI
from unittest.mock import MagicMock

def test_build_payload_preserves_newlines():
    gui = TinyLlamaGUI()
    text = "line1\nline2\nline3"
    payload = gui.build_payload(text)
    assert json.loads(payload)["prompt"] == text

def test_ctrl_enter_binding_exists():
    gui = TinyLlamaGUI()
    assert gui.prompt_box.bind("<Control-Return>")

def test_on_send_event_calls_on_send():
    gui = TinyLlamaGUI()
    gui._on_send = MagicMock()         # Replace real handler with a mock
    gui._on_send_event(event=None)     # Simulate event call
    assert gui._on_send.called         # Check the handler was actually called
