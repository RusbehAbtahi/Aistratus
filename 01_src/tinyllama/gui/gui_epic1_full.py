# ==== main.py ====

"""
tinyllama_app / main.py
Composition-root: wires state, services, controllers, and the Tkinter view.

Folder layout assumed:

01_src/tinyllama/gui/
    ├── gui_view.py          <-- TinyLlamaView class
    ├── app_state.py         <-- AppState
    ├── thread_service.py    <-- ThreadService
    └── controllers/
         ├── prompt_controller.py
         ├── gpu_controller.py
         ├── cost_controller.py
         └── auth_controller.py
"""

from pathlib import Path
import sys

# --- Import domain modules (they must exist in the package as per UML_Diagram.txt) ----------
from tinyllama.gui.gui_view import TinyLlamaView
from tinyllama.gui.app_state import AppState

from tinyllama.gui.thread_service import ThreadService
from tinyllama.gui.controllers.prompt_controller import PromptController

from tinyllama.gui.controllers.gpu_controller import GpuController

from tinyllama.gui.controllers.auth_controller import AuthController

from tinyllama.gui.controllers.cost_controller import CostController
from dotenv import load_dotenv
load_dotenv()

def main() -> None:
    """Entry point: build objects, bind callbacks, start mainloop."""
    # 1.  Global application state (observable dataclass)
    state = AppState()

    # 2.  Tkinter view (pure widgets)
    view = TinyLlamaView()

    # 3.  Thread / task scheduler (marshals work back to UI thread)
    service = ThreadService(ui_root=view.root)

    # 4.  Controllers — business logic; inject dependencies
    prompt_ctrl = PromptController(state=state, service=service, view=view)

    cost_ctrl = CostController(state=state, service=service, view=view)

    gpu_ctrl = GpuController(state=state, service=service, view=view)

    auth_ctrl = AuthController(state=state, service=service, view=view)

    # 5.  Bind view-events to controller methods or state setters
    # view.bind(
    #     {
    #         "send":  prompt_ctrl.on_send,
    #         "stop":  gpu_ctrl.on_stop_gpu,
    #         "login": auth_ctrl.on_login,
    #         "idle_changed": state.set_idle,   # direct link; simple & safe
    #         "backend_changed": state.set_backend,
    #     }
    # )
    # >>> ADD >>> real binding including login handler
    view.bind(
        {
            "send": prompt_ctrl.on_send,
            "stop": lambda: print("STOP (stub)"),
            "login": auth_ctrl.on_login,  # real login handler
            "idle_changed": state.set_idle,
            "backend_changed": state.set_backend,
        }
    )
    # <<< ADD <<<

    view.bind_state(state)

    # 6.  Kick off background cost polling
    cost_ctrl.start_polling()

    # 7.  Enter Tk main-loop
    view.root.mainloop()


if __name__ == "__main__":
    main()


# ==== gui_view.py ====

"""
TinyLlamaView – pure Tkinter presentation layer.
Implements all widgets and UI helpers; **no business logic or HTTP calls**.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Dict, Literal, Any

# _EventKey defines the exact allowed strings for callback keys.
_EventKey = Literal[
    "send",
    "stop",
    "login",
    "idle_changed",
    # >>> ADD >>> backend selection event
    "backend_changed",
    # <<< ADD <<<
]

class TinyLlamaView:
    def __init__(self) -> None:
        # Main application window (Tk root object)
        self.root = tk.Tk()
        self.root.title("TinyLlama Prompt")

        # Multiline text input for user prompt (the main typing area)
        self.prompt_box = tk.Text(self.root, width=80, height=5, wrap="word")
        self.prompt_box.pack(padx=10, pady=10)

        # Control bar holds buttons and spinbox
        ctrl = ttk.Frame(self.root)
        ctrl.pack(fill="x", padx=10, pady=5)

        # "Send" button for submitting prompt
        self.send_btn = ttk.Button(ctrl, text="Send")
        self.send_btn.pack(side="left")

        # >>> ADD >>> login button for authentication
        self.login_btn = ttk.Button(ctrl, text="Login")
        self.login_btn.pack(side="left", padx=(5, 0))
        # <<< ADD <<<

        # Spinner: shows activity while sending (hidden by default)
        self.spinner = ttk.Progressbar(ctrl, mode="indeterminate", length=120)

        # >>> ADD >>> backend dropdown
        ttk.Label(ctrl, text="Backend:").pack(side="left", padx=(15, 2))
        self.backend_var = tk.StringVar(value="AWS TinyLlama")
        self.backend_menu = ttk.Combobox(
            ctrl,
            textvariable=self.backend_var,
            values=["AWS TinyLlama", "OpenAI GPT-3.5"],
            state="readonly",
            width=18
        )
        self.backend_menu.pack(side="left", padx=(0, 4))
        self.backend_menu.bind(
            "<<ComboboxSelected>>",
            lambda e: self._on_backend_select(self.backend_var.get())
        )
        # <<< ADD <<<

        # >>> ADD >>> authentication status lamp
        self.auth_lamp = tk.Canvas(ctrl, width=16, height=16, highlightthickness=1, highlightbackground="black")
        self.auth_lamp.pack(side="left", padx=(5, 0))
        self.update_auth_lamp("off")   # use mapped color instead of invalid "off"
        # <<< ADD <<<

        # "Idle-min" label and spinbox for selecting idle timeout in minutes
        ttk.Label(ctrl, text="Idle-min:").pack(side="left", padx=(15, 2))
        self.idle_spin = ttk.Spinbox(ctrl, from_=1, to=30, width=3)
        self.idle_spin.pack(side="left")

        # "Stop GPU" button for stopping GPU (red button)
        self.stop_btn = tk.Button(
            ctrl, text="Stop GPU", bg="#d9534f", fg="white"
        )
        self.stop_btn.pack(side="right", padx=(10, 0))

        # Cost label (shows current cost)
        self.cost_var = tk.StringVar(value="€ --.--")
        self.cost_label = tk.Label(self.root, textvariable=self.cost_var, font=("TkDefaultFont", 9))
        self.cost_label.pack(pady=(0, 10))

        # Keyboard shortcut: Ctrl+Enter triggers send
        self.prompt_box.bind("<Control-Return>", self._on_ctrl_enter)

        # _callbacks: stores event-to-function mapping, filled by bind()
        self._callbacks: Dict[_EventKey, Callable] = {}

    def bind(self, controller_map: Dict[_EventKey, Callable[..., Any]]) -> None:
        """
        Connects UI button events and spinbox changes to controller callbacks.
        controller_map is a dictionary like {"send": ..., "stop": ..., ...}
        """
        self._callbacks = controller_map
        # Bind "Send" button to its handler
        self.send_btn.config(command=self._on_send_click)
        # Bind "Login" button to its handler
        self.login_btn.config(command=self._on_login_click)
        # Bind "Stop GPU" button to its handler
        self.stop_btn.config(command=self._on_stop_click)
        # Bind Idle spinbox change to its handler
        self.idle_spin.config(command=self._on_idle_spin_change)

    def get_prompt(self) -> str:
        """
        Returns the text entered in the prompt box, stripping trailing newlines.
        """
        return self.prompt_box.get("1.0", tk.END).rstrip("\n")

    def clear_prompt(self) -> None:
        """
        Clears the user input area.
        """
        self.prompt_box.delete("1.0", tk.END)

    def update_cost(self, eur: float) -> None:
        """
        Updates the cost label. Changes color depending on the value.
        """
        self.cost_var.set(f"€ {eur:,.2f} (today)")
        if eur > 15:
            color = "#d9534f"
        elif eur > 10:
            color = "#f0ad4e"
        else:
            color = "#212529"
        self.cost_label.config(fg=color)

    def append_output(self, text: str) -> None:
        """
        Appends output text to the output pane (creating it the first time).
        """
        if not hasattr(self, "_out_pane"):
            self._out_pane = tk.Text(self.root, width=80, height=15, state="disabled")
            self._out_pane.pack(padx=10, pady=(10, 0), fill="both", expand=True)
        self._out_pane.config(state="normal")
        self._out_pane.insert(tk.END, text + "\n")
        self._out_pane.yview_moveto(1.0)
        self._out_pane.config(state="disabled")

    def set_busy(self, flag: bool) -> None:
        """
        Shows or hides the spinner, disables/enables the send button.
        """
        if flag:
            self.send_btn.state(["disabled"])
            self.spinner.pack(side="left", padx=10)
            self.spinner.start(10)
        else:
            self.spinner.stop()
            self.spinner.pack_forget()
            self.send_btn.state(["!disabled"])

    # -------------------- UI Event Handlers (private) --------------------------

    def _on_send_click(self) -> None:
        if cb := self._callbacks.get("send"):
            cb(self.get_prompt())

    def _on_login_click(self) -> None:
        self.update_auth_lamp("pending")
        if cb := self._callbacks.get("login"):
            cb()

    def _on_stop_click(self) -> None:
        if cb := self._callbacks.get("stop"):
            cb()

    def _on_ctrl_enter(self, _event) -> str:
        self._on_send_click()
        return "break"

    def _on_idle_spin_change(self) -> None:
        try:
            minutes = int(self.idle_spin.get())
            if cb := self._callbacks.get("idle_changed"):
                cb(minutes)
        except ValueError:
            messagebox.showerror("Idle-minutes", "Value must be an integer 1–30")

    def _on_backend_select(self, selection: str) -> None:
        if cb := self._callbacks.get("backend_changed"):
            cb(selection)
        # reset lamp when backend changes
        self.update_auth_lamp("off")

    # -------------------- Lamp helper methods -------------------------------

    def _draw_lamp(self, color: str) -> None:
        """
        Internal: draw the auth status lamp with given fill color.
        """
        self.auth_lamp.delete("all")
        self.auth_lamp.create_oval(2, 2, 14, 14, fill=color)

    def update_auth_lamp(self, status: str) -> None:
        """
        Update authentication lamp.
        status in {"off","pending","ok","error"}.
        """
        colors = {"off": "grey", "pending": "yellow", "ok": "green", "error": "red"}
        self._draw_lamp(colors.get(status, "grey"))

    # >>> ADD >>> -----------------------------------------------------------------
    def bind_state(self, state) -> None:
        """
        Subscribe this view to AppState so the authentication lamp
        automatically reflects every change to ``auth_status``.
        """
        state.subscribe("auth_status", self.update_auth_lamp)
    # <<< ADD <<<

# -------------------- Manual test run: open window, no backend required -------------------
if __name__ == "__main__":
    def noop(*_a, **_kw): ...
    v = TinyLlamaView()
    v.bind({
        "send": noop,
        "stop": noop,
        "login": noop,
        "idle_changed": noop,
        "backend_changed": lambda b: print("backend ->", b),
    })
    v.root.mainloop()


# ==== app_state.py ====

"""
app_state.py
============
Central, thread-safe data store + tiny publish/subscribe bus for TinyLlama GUI.
"""

from __future__ import annotations
import threading
from typing import Callable, Dict, List, Any


class AppState:
    def __init__(self) -> None:
        # ---- public state values (simple, typed) ----
        self.idle_minutes: int = 5
        self.auth_token: str = ""
        self.auth_status: str = "off"       # login status: off | pending | ok | error
        self.current_cost: float = 0.0
        self.history: List[str] = []

        self.backend: str = "AWS TinyLlama"

        # ---- internals ----
        self._lock = threading.Lock()
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {
            "idle": [],
            "auth": [],
            "auth_status": [],
            "cost": [],
            "history": [],
            "backend": [],
        }

    # ---------------- subscription helpers ----------------
    def subscribe(self, event: str, cb: Callable[[Any], None]) -> None:
        """
        Register *cb* to be invoked when *event* changes.
        Valid events: idle, auth, auth_status, cost, history, backend.
        """
        if event not in self._subscribers:
            raise ValueError(f"Unknown event: {event}")
        self._subscribers[event].append(cb)

    def _publish(self, event: str, data: Any) -> None:
        """Invoke all callbacks registered for *event*, passing *data*."""
        for cb in list(self._subscribers.get(event, [])):
            try:
                cb(data)
            except Exception as exc:          # pragma: no cover
                print(f"[AppState] subscriber error on '{event}': {exc}")

    # ---------------- setters ----------------
    def set_idle(self, minutes: int) -> None:
        with self._lock:
            self.idle_minutes = minutes
        self._publish("idle", minutes)

    def set_auth(self, token: str) -> None:
        with self._lock:
            self.auth_token = token
        self._publish("auth", token)

    def set_auth_status(self, status: str) -> None:
        """
        Update login status and notify subscribers.
        *status* must be one of {"off", "pending", "ok", "error"}.
        """
        with self._lock:
            self.auth_status = status
        self._publish("auth_status", status)

    def set_cost(self, eur: float) -> None:
        with self._lock:
            self.current_cost = eur
        self._publish("cost", eur)

    def add_history(self, line: str) -> None:
        with self._lock:
            self.history.append(line)
        self._publish("history", line)

    def set_backend(self, name: str) -> None:
        """Update selected backend and notify subscribers."""
        with self._lock:
            self.backend = name
        self._publish("backend", name)
        # >>> ADD >>> reset auth-status whenever backend changes
        #           (puts lamp back to grey instantly in the GUI)
        self.set_auth_status("off")
        # <<< ADD <<<


# ==== thread_service.py ====

"""
thread_service.py

Background thread + Tk-safe result return for TinyLlama GUI.
- run_async(fn, ...) runs blocking code off the UI thread, result/exception sent to UI callback.
- schedule(interval_s, fn, ...) ticks on the UI thread (Tk after).
"""

from __future__ import annotations
import threading
import queue
import time
from typing import Any, Callable, Dict, Tuple, Optional

class ThreadService:
    def __init__(self, ui_root) -> None:
        self._ui_root = ui_root
        # Separate queues for jobs and results
        self._job_q: queue.Queue[Dict[str, Any]] = queue.Queue()
        self._result_q: queue.Queue[Tuple[Optional[Callable], Tuple[Any, ...], Dict[str, Any]]] = queue.Queue()

        self._worker = threading.Thread(
            target=self._worker_loop,
            name="ThreadServiceWorker",
            daemon=True,
        )
        self._worker.start()
        self._pump_results()

    def run_async(
        self,
        fn: Callable[..., Any],
        *args: Any,
        ui_callback: Optional[Callable[[Any], None]] = None,
        **kwargs: Any
    ) -> None:
        # Push background job to worker; result will call ui_callback on main thread
        job = {
            "fn": fn,
            "args": args,
            "kwargs": kwargs,
            "callback": ui_callback,
        }
        self._job_q.put(job)

    def schedule(
        self,
        interval_s: int,
        fn: Callable[..., None],
        *args: Any,
        **kwargs: Any
    ) -> str:
        # Recurring UI-thread call of fn every interval_s seconds (Tk after)
        ms = max(1000, int(interval_s * 1000))
        return self._ui_root.after(
            ms,
            self._wrap_schedule,
            ms,
            fn,
            args,
            kwargs,
        )

    def _worker_loop(self) -> None:
        # Background thread: run jobs and push results back for UI thread
        while True:
            job = self._job_q.get()
            fn: Callable = job["fn"]
            cb: Optional[Callable] = job["callback"]
            args, kwargs = job["args"], job["kwargs"]
            try:
                result = fn(*args, **kwargs)
                payload = result
            except Exception as exc:
                payload = exc
            # enqueue callback for UI
            self._result_q.put((cb, (payload,), {}))

    def _pump_results(self) -> None:
        # UI thread: execute all result callbacks (if any)
        try:
            while True:
                cb, cb_args, cb_kwargs = self._result_q.get_nowait()
                if cb:
                    try:
                        cb(*cb_args, **cb_kwargs)
                    except Exception as ui_exc:
                        print(f"[ThreadService] UI callback error: {ui_exc}")
        except queue.Empty:
            pass
        self._ui_root.after(50, self._pump_results)

    def _wrap_schedule(
        self,
        ms: int,
        fn: Callable,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any]
    ) -> None:
        # Internal: run fn, then reschedule
        try:
            fn(*args, **kwargs)
        finally:
            self._ui_root.after(ms, self._wrap_schedule, ms, fn, args, kwargs)


# ==== controllers\auth_controller.py ====

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

# ==== controllers\cost_controller.py ====

"""
cost_controller.py
==================

🔹 **Purpose (stub version)**
    • Simulate AWS-cost polling by _always_ displaying **0 €** in the GUI.
    • Provide a drop-in place where real CloudWatch / Cost Explorer calls
      can be added later.

🔹 **Key design points**
    • Runs no network I/O; zero dependencies beyond the project.
    • Subscribes the GUI to future `AppState.set_cost()` updates so that
      real polling logic can simply call that setter.
    • Keeps an empty `start_polling()` stub that you will later replace
      with a ThreadService‐scheduled task.

Usage:
    from tinyllama.gui.controllers.cost_controller import CostController
    cost_ctrl = CostController(state, service, view)
    cost_ctrl.start_polling()   # currently does nothing, but ready
"""

from __future__ import annotations
from typing import Any


class CostController:
    """
    Minimal stub that pushes *0 €* to the GUI and wires a cost listener.
    """

    def __init__(self, state, service, view) -> None:  # noqa: D401
        """
        Parameters
        ----------
        state   : AppState       – shared application state
        service : ThreadService  – (unused for now; kept for parity)
        view    : TinyLlamaView  – GUI object; exposes update_cost()
        """
        self._state = state
        self._service = service
        self._view = view

        # --- one-time initial display -----------------------------------
        self._state.set_cost(0.0)          # publish to state
        self._view.update_cost(0.0)        # immediate GUI refresh

        # --- subscribe GUI for future cost changes ----------------------
        # When real polling sets state.set_cost(), the view auto-updates.
        self._state.subscribe("cost", self._view.update_cost)

    # ------------------------------------------------------------------
    # Public API (kept for future extension)
    # ------------------------------------------------------------------
    def start_polling(self) -> None:
        """
        Begin periodic cost polling.

        Stub → does *nothing* for now.  Replace the body with:
            self._service.schedule(30, self._fetch_cost)
        plus a private _fetch_cost() that calls AWS cost APIs and then
        self._state.set_cost(eur).
        """
        pass  # pragma: no cover (stub)


# ==== controllers\gpu_controller.py ====

"""
gpu_controller.py
=================

🔹 **Purpose (stub version)**
    • Simulate the “Stop GPU” button in TinyLlama Desktop.
    • Behaviour depends on the currently-selected backend:
        - backend == "AWS TinyLlama"  →  append "[GPU] Stop GPU simulated (AWS backend)"
        - backend == "OpenAI GPT-3.5" →  append "[GPU] No GPU to stop for OpenAI backend."

🔹 **Design**
    • No real AWS calls; everything happens instantly on the UI thread.
    • Mirrors the public method signature used in the UML: `on_stop_gpu()`.
    • Ready to be extended later: replace the body of `_simulate_stop()` with
      real API Gateway / Lambda logic, but *do not* change the public API.

Usage snippet (already patched into main.py):
    gpu_ctrl = GpuController(state, service, view)
    view._callbacks["stop"] = gpu_ctrl.on_stop_gpu
"""

from __future__ import annotations


class GpuController:
    """
    Minimal stub controller for the “Stop GPU” button.
    """

    def __init__(self, state, service, view) -> None:
        """
        Parameters
        ----------
        state   : AppState       – for reading current backend
        service : ThreadService  – unused for stub; kept for parity/later async
        view    : TinyLlamaView  – to append output to the GUI
        """
        self._state = state
        self._service = service
        self._view = view

    def on_stop_gpu(self) -> None:
        """
        Called by the *Stop GPU* button.
        Shows a simulated message based on AppState.backend.
        """
        backend = self._state.backend
        if backend == "AWS TinyLlama":
            self._simulate_stop()
        else:
            self._view.append_output("[GPU] No GPU to stop for OpenAI backend.")

    def _simulate_stop(self) -> None:
        """
        Stub for AWS GPU stop.
        Extend or replace this with real network calls later.
        """
        self._view.append_output("[GPU] Stop GPU simulated (AWS backend)")


# ==== controllers\prompt_controller.py ====

"""
prompt_controller.py
====================

Orchestrates the flow for a *single* prompt:

    1. Collect user prompt from TinyLlamaView            (UI thread)
    2. Validate / enrich payload if needed               (UI thread)
    3. Call the selected backend **off** the UI thread   (ThreadService)
    4. When the backend returns, update AppState + UI    (back on UI thread)

The controller is backend-agnostic: it consults AppState.backend
("AWS TinyLlama"  or  "OpenAI GPT-3.5") and delegates to the matching
BackendClient implementation.

If you later add more backends, just register another client class
in `_CLIENTS_BY_NAME`.
"""

from __future__ import annotations
import os
import openai
import time
import uuid
from typing import Protocol, Dict, Callable, Any

# ------------------------ minimal BackendClient interface --------------------


class BackendClient(Protocol):
    """A very small contract every backend adapter must satisfy."""

    def send_prompt(self, prompt: str, metadata: Dict[str, Any]) -> str:
        """Blocking call that returns the model reply as plain text."""
        ...


# ------------------------ stub backend implementations -----------------------

# NOTE: these are *placeholders* so you can see the round-trip immediately.
# Replace them with real HTTP/AWS/OpenAI calls later.

class AwsTinyLlamaClient:
    def send_prompt(self, prompt: str, metadata: Dict[str, Any]) -> str:
        # Replace with real API Gateway call.
        time.sleep(1.0)  # simulate latency
        return f"[AWS-TinyLlama] echoed: {prompt[:100]}..."


class OpenAiApiClient:
    """
    Real ChatGPT-3.5 implementation.
    Returns (reply_text, cost_eur) tuple.
    """

    # USD prices per 1 000 tokens (June 2025)
    _IN_USD  = 0.0015   # prompt/input
    _OUT_USD = 0.0020   # completion/output
    _USD_TO_EUR = 0.92  # fixed conversion rate

    def send_prompt(self, prompt: str, metadata: dict) -> tuple[str, float]:
        api_key = os.environ["OPENAI_API_KEY"]
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.7,
        )
        reply_text = response.choices[0].message.content.strip()
        usage = response.usage
        in_tok = usage.prompt_tokens
        out_tok = usage.completion_tokens
        cost_usd = (in_tok * self._IN_USD + out_tok * self._OUT_USD) / 1000
        cost_eur = cost_usd * self._USD_TO_EUR
        return reply_text, cost_eur

_CLIENTS_BY_NAME: Dict[str, Callable[[], BackendClient]] = {
    "AWS TinyLlama": AwsTinyLlamaClient,
    "OpenAI GPT-3.5": OpenAiApiClient,
}


# ----------------------------- PromptController ------------------------------


class PromptController:
    """
    Handles the Send-prompt workflow.

    Dependencies are injected so that the controller remains testable
    and UI-toolkit agnostic.
    """

    def __init__(
        self,
        state,
        service,
        view,
    ) -> None:
        self._state = state              # AppState
        self._service = service          # ThreadService
        self._view = view                # TinyLlamaView

    # --------------------------------------------------------------------- API
    def on_send(self, user_prompt: str) -> None:
        """
        Called by TinyLlamaView when user presses *Send* or hits Ctrl+Enter.
        Runs instantly on the UI thread.
        """

        prompt = user_prompt.strip()
        if not prompt:
            self._view.append_output("⚠️  Empty prompt ignored.")
            return

        # 1. UI feedback → busy
        self._view.set_busy(True)

        # 2. capture snapshot of backend selection *right now*
        backend_name = self._state.backend
        client_factory = _CLIENTS_BY_NAME.get(backend_name)
        if client_factory is None:
            self._view.append_output(f"❌ Unsupported backend: {backend_name}")
            self._view.set_busy(False)
            return
        client = client_factory()

        # 3. Build metadata (extensible)
        meta = {
            "id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "idle": self._state.idle_minutes,
        }

        # 4. Hand off to background thread
        self._service.run_async(
            self._call_backend,
            client,
            prompt,
            meta,
            ui_callback=self._on_backend_reply,  # executed back on UI thread
        )

    # --------------------------- private helpers -------------------------

    @staticmethod
    def _call_backend(
        client: BackendClient,
        prompt: str,
        meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Runs in a background worker thread.
        Returns a dict with success|error + message.
        """
        try:
            reply, cost_eur = client.send_prompt(prompt, meta)
            return {"ok": True, "reply": reply, "cost": cost_eur, "meta": meta}
        except Exception as exc:  # noqa: broad-except
            return {"ok": False, "error": str(exc), "meta": meta}

    # ---

    def _on_backend_reply(self, result: Dict[str, Any]) -> None:
        """
        Executed back on UI thread.
        Updates AppState cost + history + GUI.
        """
        self._view.set_busy(False)  # always stop spinner first

        if result["ok"]:
            reply = result["reply"]
            cost = result.get("cost", 0.0)

            # accumulate session cost
            new_total = self._state.current_cost + cost
            self._state.set_cost(new_total)

            # Store in history then show
            self._state.add_history(reply)
            eur_str = f" (cost €{cost:.2f})" if cost else ""
            self._view.append_output(reply + eur_str)
        else:
            self._view.append_output("❌ BACKEND ERROR: " + result["error"])


# ------------------------------------------------------------------------- END


