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
