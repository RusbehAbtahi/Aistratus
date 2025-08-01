import pytest, os
from fastapi.testclient import TestClient
from api.routes import app
from tinyllama.utils.jwt_tools import make_token
from api.config import settings
client = TestClient(app)
AUD = settings.client_id

def _hdr(tok): return {"Authorization": f"Bearer {tok}"}

CASES = [
    (None, 401),
    (_hdr(make_token(aud=AUD)[:-1]+"x"), 403),  # bad sig
    (_hdr(make_token(exp_delta=-10, aud=AUD)), 403),  # expired
    (_hdr(make_token(aud=AUD)), 200),
]

@pytest.mark.parametrize("hdr,status", CASES)
def test_jwt_paths(hdr, status):
    print("DEBUG TEST hdr:", hdr)
    resp = client.post("/infer", headers=hdr or {})
    assert resp.status_code == status