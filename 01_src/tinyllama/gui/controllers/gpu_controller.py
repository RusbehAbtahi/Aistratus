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
