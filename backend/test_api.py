import asyncio
import json
import unittest

import main
from data import MockProvider


def api_request(method: str, path: str, payload: dict | None = None, origin: str | None = None):
    body = json.dumps(payload).encode() if payload is not None else b""
    headers = [(b"host", b"testserver"), (b"content-type", b"application/json")]
    if origin:
        headers.append((b"origin", origin.encode()))
    if method == "OPTIONS":
        headers.append((b"access-control-request-method", b"GET"))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }
    messages = []
    received = False

    async def receive():
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(main.app(scope, receive, send))
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    )
    response_headers = next(message["headers"] for message in messages if message["type"] == "http.response.start")
    headers = dict(response_headers)
    payload = json.loads(response_body) if b"application/json" in headers.get(b"content-type", b"") else None
    return status, payload, headers


class ManagedPageApiTests(unittest.TestCase):
    def setUp(self):
        main.provider = MockProvider()

    def test_all_dashboard_pages_return_data(self):
        for path in (
            "/api/overview",
            "/api/apps",
            "/api/savings",
            "/api/licenses",
            "/api/renewals",
            "/api/shadow-it",
            "/api/access",
            "/api/security",
        ):
            with self.subTest(path=path):
                status, payload, _ = api_request("GET", path)
                self.assertEqual(status, 200)
                self.assertIsNotNone(payload)

    def test_license_reclaim_updates_seats(self):
        status, payload, _ = api_request("POST", "/api/licenses/Figma/reclaim")
        self.assertEqual(status, 200)
        figma = next(item for item in payload["items"] if item["name"] == "Figma")
        self.assertEqual(figma["unused"], 0)
        self.assertEqual(figma["purchased"], figma["assigned"])

    def test_renewal_review_updates_status(self):
        status, payload, _ = api_request("POST", "/api/renewals/Slack/review")
        self.assertEqual(status, 200)
        slack = next(item for item in payload["items"] if item["name"] == "Slack")
        self.assertEqual(slack["status"], "Reviewed")

    def test_shadow_it_review_updates_status(self):
        status, payload, _ = api_request("PATCH", "/api/shadow-it/linear", {"status": "Approved"})
        self.assertEqual(status, 200)
        app = next(item for item in payload["items"] if item["id"] == "linear")
        self.assertEqual(app["status"], "Approved")

    def test_access_actions_update_user(self):
        status, payload, _ = api_request("POST", "/api/access/kabir-shah/deactivate")
        self.assertEqual(status, 200)
        user = next(item for item in payload["items"] if item["id"] == "kabir-shah")
        self.assertFalse(user["active"])

    def test_security_resolution_updates_finding(self):
        status, payload, _ = api_request("POST", "/api/security/mfa-gap/resolve")
        self.assertEqual(status, 200)
        finding = next(item for item in payload["items"] if item["id"] == "mfa-gap")
        self.assertEqual(finding["status"], "Resolved")

    def test_vite_cors_preflight_allows_configured_origin(self):
        status, _, headers = api_request("OPTIONS", "/api/licenses", origin="http://localhost:5173")
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"access-control-allow-origin"], b"http://localhost:5173")


if __name__ == "__main__":
    unittest.main()
