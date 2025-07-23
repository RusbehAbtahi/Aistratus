import requests

def test_ping_endpoint():
    print("DEBUG (in-test) requests.get module:", requests.get.__module__)

    url = "https://rjg3dvt5el.execute-api.eu-central-1.amazonaws.com/health"


    resp = requests.get(url, timeout=5)

    print("DEBUG (in-test) resp type:", type(resp))
    print("DEBUG (in-test) resp dir:", dir(resp))
    print("DEBUG (in-test) resp.status_code:", resp.status_code)
    print("DEBUG (in-test) resp.text:", getattr(resp, "text", None))

    if hasattr(resp, "text"):
        content = resp.text
    elif hasattr(resp, "json"):
        # Try to use the JSON result, fallback to string
        try:
            content = str(resp.json())
        except Exception:
            content = ""
    else:
        # Could add other attributes if your mock changes
        content = ""
    print("DEBUG (in-test) content:", content)
    assert resp.status_code == 400
    assert "invalid_request" in resp.text

