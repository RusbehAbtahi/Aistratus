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
