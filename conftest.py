# conftest.py
import sys, os
from pathlib import Path

# 1) Ensure our src folder (01_src) is on sys.path so "import tinyllama.…" and "import api.…" work
root = Path(__file__).parent
src  = root / "01_src"
if src.exists():
    sys.path.insert(0, str(src))

# 2) Auto-point the JWT logic at our local mock JWKS for test_auth
mock_jwks = root / "02_tests" / "api" / "data" / "mock_jwks.json"
if mock_jwks.exists():
    os.environ["LOCAL_JWKS_PATH"] = str(mock_jwks)
