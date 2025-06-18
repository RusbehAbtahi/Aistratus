"""
Unit-tests for tinyllama.gui.controllers.auth_controller.AuthController
-----------------------------------------------------------------------

Covered scenarios  (all UI-thread paths):

1. on_login() with OpenAI backend → no real login, auth_status = "ok".
2. on_login() with AWS backend  → sets status "pending", schedules async job.
3. _on_login_done() success     → token persisted, status "ok", message shown.
4. _on_login_done() error       → status "error", message shown.
5. on_logout()                  → token cleared, status "off", logout dispatched.
6. Unsupported backend          → error message, no async work.

All external dependencies (State / Service / View / AuthClient) are stubbed;
backend mapping is monkey-patched per test for isolation.
"""

import sys
import importlib
from types import ModuleType
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Generic stubs
# ─────────────────────────────────────────────────────────────────────────────
class StubState:
    def __init__(self):
        self.backend        = "AWS TinyLlama"
        self.auth_token     = ""
        self.auth_status    = "off"
        self.idle_minutes   = 5
        self.set_status_log = []
        self.set_token_log  = []

    def set_auth(self, tok: str):
        self.auth_token = tok
        self.set_token_log.append(tok)

    def set_auth_status(self, st: str):
        self.auth_status = st
        self.set_status_log.append(st)


class StubView:
    def __init__(self):
        self.busy_flags = []
        self.out_lines  = []

    def set_busy(self, flag: bool):
        self.busy_flags.append(flag)

    def append_output(self, txt: str):
        self.out_lines.append(txt)


class StubService:
    def __init__(self):
        self.async_jobs = []      # (fn, args, ui_callback)

    def run_async(self, fn, *args, ui_callback=None, **kw):
        self.async_jobs.append((fn, args, ui_callback))


# Fake AuthClient variants
class FakeAwsClientOK:
    def __init__(self): self.logout_called = False
    def login(self):  return "jwt-123"
    def logout(self): self.logout_called = True


class FakeAwsClientFail:
    def login(self):  raise RuntimeError("boom")
    def logout(self): pass


# ─────────────────────────────────────────────────────────────────────────────
# Helper – import controller fresh & patch mapping
# ─────────────────────────────────────────────────────────────────────────────
def _import_auth_ctrl(monkeypatch, backend_cls):
    mod = "tinyllama.gui.controllers.auth_controller"
    sys.modules.pop(mod, None)            # ensure clean import
    ac_mod = importlib.import_module(mod)
    monkeypatch.setitem(ac_mod._CLIENTS_BY_BACKEND, "AWS TinyLlama", backend_cls)
    return ac_mod.AuthController


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────
def test_openai_backend_needs_no_login(monkeypatch):
    AuthController = _import_auth_ctrl(monkeypatch, FakeAwsClientOK)
    st, vw, sv = StubState(), StubView(), StubService()
    st.backend = "OpenAI GPT-3.5"

    AuthController(st, sv, vw).on_login()

    assert st.auth_status == "ok"
    assert "[Auth] No login required" in vw.out_lines[-1]
    assert not sv.async_jobs and not vw.busy_flags


def test_aws_login_starts_async(monkeypatch):
    AuthController = _import_auth_ctrl(monkeypatch, FakeAwsClientOK)
    st, vw, sv = StubState(), StubView(), StubService()

    AuthController(st, sv, vw).on_login()

    # immediate effects on UI thread
    assert st.set_status_log[0] == "pending"
    assert vw.busy_flags == [True]
    assert len(sv.async_jobs) == 1


def test_login_done_success(monkeypatch):
    AuthController = _import_auth_ctrl(monkeypatch, FakeAwsClientOK)
    st, vw, sv = StubState(), StubView(), StubService()
    ctrl       = AuthController(st, sv, vw)

    ctrl._on_login_done({"ok": True, "token": "jwt-xyz"})

    assert st.auth_token == "jwt-xyz"
    assert st.auth_status == "ok"
    assert vw.busy_flags[-1] is False
    assert "[Auth] Login successful." in vw.out_lines[-1]


def test_login_done_error(monkeypatch):
    AuthController = _import_auth_ctrl(monkeypatch, FakeAwsClientOK)
    st, vw, sv = StubState(), StubView(), StubService()
    ctrl       = AuthController(st, sv, vw)

    ctrl._on_login_done({"ok": False, "error": "bad-credentials"})

    assert st.auth_status == "error"
    assert vw.busy_flags[-1] is False
    assert vw.out_lines[-1].startswith("❌ AUTH ERROR: bad-credentials")


def test_logout_clears_token_and_status(monkeypatch):
    AuthController = _import_auth_ctrl(monkeypatch, FakeAwsClientOK)
    st, vw, sv = StubState(), StubView(), StubService()
    ctrl       = AuthController(st, sv, vw)

    # pre-populate token
    st.set_auth("jwt-abc")
    ctrl.on_logout()

    assert st.auth_token == ""
    assert st.auth_status == "off"
    assert "[Auth] Logged out." in vw.out_lines[-1]
    # logout should schedule async job (even if it’s a no-op fake)
    assert sv.async_jobs


def test_unsupported_backend(monkeypatch):
    AuthController = _import_auth_ctrl(monkeypatch, FakeAwsClientOK)
    st, vw, sv = StubState(), StubView(), StubService()
    st.backend = "Imaginary-LLM"

    AuthController(st, sv, vw).on_login()

    assert "❌ Unsupported backend" in vw.out_lines[-1]
    assert not sv.async_jobs and not vw.busy_flags
