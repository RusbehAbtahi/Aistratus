# 02_tests/conftest.py
import os
import sys

print("[debug] conftest imported from", __file__, file=sys.stderr)

def pytest_configure(config):            # no underscore
    print("[debug] pytest_configure running", file=sys.stderr)
    os.environ.setdefault("COGNITO_USER_POOL_ID", "eu-central-1_TEST")
    os.environ.setdefault("COGNITO_CLIENT_ID", "local-test-client-id")

# add at bottom of 02_tests/conftest.py  AFTER the hook above
def _fake_requests_get(*_args, **_kwargs):
    class _Resp:
        status_code = 200
        def json(self):
            return {
                "keys": [
                    {
                        "kid": "dummy",
                        "kty": "RSA",
                        "alg": "RS256",
                        "use": "sig",
                        "n": "00",
                        "e": "AQAB",
                    }
                ]
            }
        def raise_for_status(self):
            pass
    return _Resp()

#import requests
#pyrequests.get = _fake_requests_get  # monkey-patch once, no import cycles

