# 02_tests/api/conftest.py

import requests
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env_public", override=True)


def _fake_requests_get(url, *args, **kwargs):
    if ".well-known/jwks.json" in url:
        class _Resp:
            status_code = 200
            def json(self):
                return {"keys": [
                    {"kid": "dummy", "kty": "RSA", "alg": "RS256", "use": "sig", "n": "00", "e": "AQAB"}
                ]}
            def raise_for_status(self): pass
        return _Resp()
    # fallback to real requests for all other URLs
    return requests.sessions.Session().get(url, *args, **kwargs)

requests.get = _fake_requests_get  # Only affects api tests!
