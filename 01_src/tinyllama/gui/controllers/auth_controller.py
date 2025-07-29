from __future__ import annotations
import boto3
import time
from typing import Protocol, Dict, Any, Callable


# ------------------------------------------------------------------ protocol
class AuthClient(Protocol):
    """Minimum contract every backend-auth adapter must satisfy."""
    def login(self) -> str: ...
    def logout(self) -> None: ...

# ------------------------------------------------------- real implementations
class AwsCognitoAuthClient:
    """
    Authenticates against AWS Cognito User Pool dynamically discovering the App Client ID.
    """
    def __init__(self, state) -> None:
        self._state = state
        self._region = 'eu-central-1'

    def login(self) -> str:
        from tinyllama.utils.ssm import get_id
        # grab credentials from AppState
        username = self._state.username
        password = self._state.password

        # Initialize Cognito IDP client
        client = boto3.client('cognito-idp', region_name=self._region)

        # Discover User Pool ID from SSM
        user_pool_id = get_id("cognito_user_pool_id")
        print("SSM cognito_user_pool_id =", user_pool_id)

        # List clients for the pool
        response = client.list_user_pool_clients(
            UserPoolId=user_pool_id,
            MaxResults=60
        )
        clients = response.get('UserPoolClients', [])
        if not clients:
            raise Exception(f"No user pool clients found for pool {user_pool_id}")

        # Optionally filter by name or take the first
        app_client_id = clients[0]['ClientId']
        print("Discovered app_client_id      =", app_client_id)

        # Perform authentication
        auth_response = client.initiate_auth(
            ClientId=app_client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password,
            }
        )
        return auth_response['AuthenticationResult']['AccessToken']

    def logout(self) -> None:
        # No tokens to revoke for this simple implementation
        print("[Auth] Logout invoked (no-op)")

class OpenAiDummyAuthClient:
    def login(self) -> str:
        time.sleep(0.2)
        return "<<openai-no-auth>>"

    def logout(self) -> None:
        print("[Auth] OpenAI logout")

# Map backend names to auth client factories
_CLIENTS_BY_BACKEND: Dict[str, Callable[..., AuthClient]] = {
    "AWS TinyLlama": AwsCognitoAuthClient,
    "OpenAI GPT-3.5": OpenAiDummyAuthClient,
}

# ---------------------------------------------------------------- controller
class AuthController:
    """
    Orchestrates login/logout for the selected backend.
    """
    def __init__(
        self,
        state,    # AppState
        service,  # ThreadService
        view,     # TinyLlamaView
    ) -> None:
        self._state = state
        self._service = service
        self._view = view

    def on_login(self) -> None:
        # Capture credentials and store
        username = self._view.get_username()
        password = self._view.get_password()
        self._state.set_username(username)
        self._state.set_password(password)

        backend = self._state.backend
        if backend == "OpenAI GPT-3.5":
            self._view.append_output("[Auth] No login required for OpenAI backend.")
            self._state.set_auth_status("ok")
            return

        factory = _CLIENTS_BY_BACKEND.get(backend)
        if factory is None:
            self._view.append_output(f"❌ Unsupported backend: {backend}")
            return
        client = factory(self._state)

        self._state.set_auth_status("pending")
        self._view.set_busy(True)
        self._service.run_async(
            self._login_worker,
            client,
            ui_callback=self._on_login_done,
        )

    def on_logout(self) -> None:
        backend = self._state.backend
        factory = _CLIENTS_BY_BACKEND.get(backend)
        if factory:
            client = factory(self._state)
            self._service.run_async(client.logout)
        self._state.set_auth("")
        self._state.set_auth_status("off")
        self._view.append_output("[Auth] Logged out.")

    @staticmethod
    def _login_worker(client: AuthClient) -> Dict[str, Any]:
        try:
            token = client.login()
            return {"ok": True, "token": token}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _on_login_done(self, result: Dict[str, Any]) -> None:
        self._view.set_busy(False)
        if result.get("ok"):
            token = result.get("token", "")
            self._state.set_auth(token)
            self._state.set_auth_status("ok")
            self._view.append_output("[Auth] Login successful.")
        else:
            self._state.set_auth_status("error")
            error_msg = result.get("error", "Unknown error")
            self._view.append_output("❌ AUTH ERROR: " + error_msg)
