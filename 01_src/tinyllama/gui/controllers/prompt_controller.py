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
