"""
Unit-tests for tinyllama.gui.app_state.AppState
Focus:
1. Each setter stores the new value.
2. Corresponding subscribers are called exactly once with the same value.
"""

import importlib

AppState = importlib.import_module("tinyllama.gui.app_state").AppState


def _capture():
    """Return (callback, list) to collect published values."""
    box: list = []
    return (lambda v: box.append(v)), box


def test_app_state_setters_publish_events():
    state = AppState()

    # idle -------------------------------------------------------------------
    idle_cb, idle_box = _capture()
    state.subscribe("idle", idle_cb)
    state.set_idle(7)
    assert state.idle_minutes == 7
    assert idle_box == [7]

    # auth -------------------------------------------------------------------
    auth_cb, auth_box = _capture()
    state.subscribe("auth", auth_cb)
    state.set_auth("abc123")
    assert state.auth_token == "abc123"
    assert auth_box == ["abc123"]

    # auth_status ------------------------------------------------------------
    st_cb, st_box = _capture()
    state.subscribe("auth_status", st_cb)
    state.set_auth_status("ok")
    assert state.auth_status == "ok"
    assert st_box == ["ok"]

    # cost -------------------------------------------------------------------
    cost_cb, cost_box = _capture()
    state.subscribe("cost", cost_cb)
    state.set_cost(9.99)
    assert state.current_cost == 9.99
    assert cost_box == [9.99]

    # history ----------------------------------------------------------------
    hist_cb, hist_box = _capture()
    state.subscribe("history", hist_cb)
    state.add_history("foo")
    assert state.history[-1] == "foo"
    assert hist_box == ["foo"]

    # backend ----------------------------------------------------------------
    be_cb, be_box = _capture()
    state.subscribe("backend", be_cb)
    state.set_backend("OpenAI GPT-3.5")
    assert state.backend == "OpenAI GPT-3.5"
    # set_backend triggers backend AND auth_status("off") publications
    assert be_box == ["OpenAI GPT-3.5"]
