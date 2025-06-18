"""
auth_controller.py
==================

Handles **login / logout** flows for whichever backend the user selects
(AWS TinyLlama vs OpenAI).  The logic is deliberately minimal and
backend-agnostic:

* When the user clicks “Login” (or the GUI detects no token) we:
    1. Read the selected backend from `AppState.backend`
    2. Delegate to the matching *AuthClient* implementation off the UI
       thread (via ThreadService)
    3. Persist the returned token (if any) in `AppState.auth_token`
    4. Update the GUI (success or error message)

Real HTTP / OAuth calls are **stubbed** so you can run the GUI today.
Replace the stub methods with live Cognito / OpenAI code later.
"""

from __future__ import annotations

import webbrowser
import time
from typing import Protocol, Dict, Any, Callable, Optional

# ------------------------------------------------------------------ protocol
class AuthClient(Protocol):
    """Minimum contract every backend-auth adapter must satisfy."""

    def login(self) -> str: ...
    def logout(self) -> None: ...


# ------------------------------------------------------- stub implementations
class AwsCognitoAuthClient:
    """
    Simulates a Cognito-hosted UI login:

    * Opens the user’s browser at LOGIN_URL
    * ‘Waits’ 1 s, then returns a fake JWT
    """

    LOGIN_URL = "https://example.auth.eu-central-1.amazoncognito.com/login"

    def login(self) -> str:
        webbrowser.open_new(self.LOGIN_URL)
        time.sleep(1.0)  # simulate user login delay
        return "eyJhbGciOiAiR0RILUVuLmZh..."

    def logout(self) -> None:
        # In real life: hit Cognito logout endpoint or forget refresh token
        print("[Stub] AWS logout")


class OpenAiDummyAuthClient:
    """
    GPT 3.5 doesn’t need a user login in this desktop app; we only need
    the API key (configured elsewhere).  We treat ‘login’ as a no-op that
    returns a sentinel token so GUI logic stays symmetric.
    """

    def login(self) -> str:
        time.sleep(0.2)
        return "<<openai-no-auth>>"

    def logout(self) -> None:
        print("[Stub] OpenAI logout (no-op)")


_CLIENTS_BY_BACKEND: Dict[str, Callable[[], AuthClient]] = {
    "AWS TinyLlama": AwsCognitoAuthClient,
    "OpenAI GPT-3.5": OpenAiDummyAuthClient,
}

# ---------------------------------------------------------------- controller
class AuthController:
    """
    Orchestrates login/logout for the selected backend.

    Dependencies are injected for testability & Tk-decoupling.
    """

    def __init__(
        self,
        state,          # AppState
        service,        # ThreadService
        view,           # TinyLlamaView
    ) -> None:
        self._state = state
        self._service = service
        self._view = view

    # ----------------------------- public API for GUI ---------------------
    def on_login(self) -> None:
        """Called by view when user clicks the *Login* button."""
        backend = self._state.backend


        if backend == "OpenAI GPT-3.5":
            self._view.append_output("[Auth] No login required for OpenAI backend.")
            self._state.set_auth_status("ok")
            return

        factory = _CLIENTS_BY_BACKEND.get(backend)
        if factory is None:
            self._view.append_output(f"❌ Unsupported backend: {backend}")
            return
        client = factory()

        # >>> ADD >>> set lamp to "pending" immediately when login starts
        self._state.set_auth_status("pending")
        # <<< ADD <<<

        self._view.set_busy(True)
        self._service.run_async(
            self._login_worker,
            client,
            ui_callback=self._on_login_done,
        )

    def on_logout(self) -> None:
        """Optional hook if you add a *Logout* button."""
        backend = self._state.backend
        factory = _CLIENTS_BY_BACKEND.get(backend)
        if factory:
            client = factory()
            self._service.run_async(client.logout)
        self._state.set_auth("")  # clear token immediately

        # >>> ADD >>> reset lamp to "off" on logout
        self._state.set_auth_status("off")
        # <<< ADD <<<

        self._view.append_output("[Auth] Logged out.")

    # ------------------------------- workers ------------------------------
    @staticmethod
    def _login_worker(client: AuthClient) -> Dict[str, Any]:
        """Runs off UI thread; returns dict with result or error."""
        try:
            token = client.login()
            return {"ok": True, "token": token}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    # --------------------------- UI-thread callback -----------------------
    def _on_login_done(self, result: Dict[str, Any]) -> None:
        self._view.set_busy(False)
        if result["ok"]:
            token: str = result["token"]
            self._state.set_auth(token)

            # >>> ADD >>> set lamp to "ok" on successful login
            self._state.set_auth_status("ok")
            # <<< ADD <<<

            self._view.append_output("[Auth] Login successful.")
        else:
            # >>> ADD >>> set lamp to "error" on login failure
            self._state.set_auth_status("error")
            # <<< ADD <<<

            self._view.append_output("❌ AUTH ERROR: " + result["error"])


# ---------------------------------------------------------------- usage tip
"""
How to wire this up (in main.py):

    from tinyllama.gui.controllers.auth_controller import AuthController
    ...
    auth_ctrl = AuthController(state=state, service=service, view=view)
    view.bind({
        "send": prompt_ctrl.on_send,
        "stop": gpu_ctrl.on_stop_gpu,
        "login": auth_ctrl.on_login,   # ★ add this
        "idle_changed": state.set_idle,
        "backend_changed": state.set_backend,
    })

Add a *Login* button in TinyLlamaView and hook its command to the "login"
 callback key."""