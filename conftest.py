# conftest.py  – final form
import os, pytest
from pathlib import Path

@pytest.fixture(scope="session", autouse=True)
def _inject_env():
    root = Path(__file__).parent
    os.environ["LOCAL_JWKS_PATH"] = str((root /
        "02_tests/api/data/mock_jwks.json").resolve())
    os.environ.setdefault("COGNITO_APP_CLIENT_ID",
                          "scju2t2jhj79ed7juvt60t883")
