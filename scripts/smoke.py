"""Check the local Compose stack through HTTP; failures exit nonzero."""

import json
from urllib.request import urlopen

for endpoint, expected in [("live", "ok"), ("ready", "ready")]:
    with urlopen(
        f"http://localhost:8080/api/v1/health/{endpoint}", timeout=10
    ) as response:
        body = json.load(response)
        assert response.status == 200
        assert body["data"]["status"] == expected
        assert body["meta"]["request_id"] == response.headers["X-Request-ID"]
    print(f"Verified /api/v1/health/{endpoint}")

with urlopen("http://localhost:8080/app/overview", timeout=10) as response:
    assert response.status == 200
    assert b'<div id="root"></div>' in response.read()
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
print("Verified frontend route and security headers")
