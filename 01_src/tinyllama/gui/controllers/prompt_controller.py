"""
prompt_controller.py
====================

Orchestrates the flow for a *single* prompt:

    1. Collect user prompt from TinyLlamaView            (UI thread)
    2. Validate / enrich payload if needed               (UI thread)
    3. Call the selected backend **off** the UI thread   (ThreadService)
    4. When the backend returns, update AppState + UI    (back on UI thread)

The controller remains testable and UI-toolkit agnostic.
"""
from __future__ import annotations
import os
import time
import uuid
import requests
from typing import Protocol, Dict, Any
from typing import Callable

# ------------------------ minimal BackendClient interface --------------------

class BackendClient(Protocol):
    """A very small contract every backend adapter must satisfy."""
    def send_prompt(self, prompt: str, metadata: Dict[str, Any]) -> str: ...

# ------------------------ real backend implementations -----------------------

class AwsTinyLlamaClient:
    """
    Calls the AWS TinyLlama API Gateway `/infer` endpoint,
    using a provided JWT token for authentication.
    """
    def __init__(self, token: str) -> None:
        self._token = token

    def send_prompt(self, prompt: str, metadata: Dict[str, Any]) -> str:
        print("DEBUG API_BASE_URL in send_prompt:", os.environ.get("API_BASE_URL"))

        api_base = os.environ.get("API_BASE_URL")
        if not api_base:
            raise Exception("API_BASE_URL environment variable is not set")
        api_url = api_base.rstrip('/') + "/infer"
        if not self._token:
            raise Exception("AUTH_TOKEN is not set (login required)")
        headers = {"Authorization": f"Bearer {self._token}"}
        payload = {"prompt": prompt, "idle": metadata.get("idle", 5)}
        print("DEBUG Authorization header:", headers)
        print("DEBUG JSON payload:", payload)
        print("RAW Authorization header being sent:", headers["Authorization"])

        resp = requests.post(api_url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("reply", data.get("status", ""))

class OpenAiApiClient:
    """
    Real ChatGPT-3.5 implementation.
    """
    def send_prompt(self, prompt: str, metadata: Dict[str, Any]) -> str:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise Exception("OPENAI_API_KEY environment variable is not set")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 512,
                "temperature": 0.7,
            }
        )
        response.raise_for_status()
        resp = response.json()
        return resp["choices"][0]["message"]["content"].strip()

# Map backend names to client factories
_CLIENTS_BY_NAME: Dict[str, Callable[..., BackendClient]] = {
    "OpenAI GPT-3.5": OpenAiApiClient,
}

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
        self._state = state
        self._service = service
        self._view = view

    def on_send(self, user_prompt: str) -> None:
        prompt = user_prompt.strip()
        if not prompt:
            self._view.append_output("⚠️  Empty prompt ignored.")
            return

        self._view.set_busy(True)
        backend_name = self._state.backend

        # Choose client based on backend
        if backend_name == "AWS TinyLlama":
            token = self._state.auth_token
            client = AwsTinyLlamaClient(token)
        else:
            client_factory = _CLIENTS_BY_NAME.get(backend_name)
            if client_factory is None:
                self._view.append_output(f"❌ Unsupported backend: {backend_name}")
                self._view.set_busy(False)
                return
            client = client_factory()

        meta = {"id": str(uuid.uuid4()), "timestamp": time.time(), "idle": self._state.idle_minutes}
        self._service.run_async(
            self._call_backend,
            client,
            prompt,
            meta,
            ui_callback=self._on_backend_reply,
        )

    @staticmethod
    def _call_backend(
        client: BackendClient,
        prompt: str,
        meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            reply = client.send_prompt(prompt, meta)
            return {"ok": True, "reply": reply}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _on_backend_reply(self, result: Dict[str, Any]) -> None:
        self._view.set_busy(False)
        if result.get("ok"):
            self._view.append_output(result["reply"])
        else:
            self._view.append_output("❌ BACKEND ERROR: " + result.get("error", ""))
