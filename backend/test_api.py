import asyncio
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from urllib.parse import unquote

import main
import services
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
        "path": unquote(path),
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
    payload = (
        json.loads(response_body)
        if response_body and b"application/json" in headers.get(b"content-type", b"")
        else None
    )
    return status, payload, headers


class ManagedPageApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        main.provider = MockProvider(Path(self.temp_dir.name) / "test.sqlite3")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_all_dashboard_pages_return_data(self):
        for path in (
            "/api/overview",
            "/api/apps",
            "/api/apps/Figma",
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

    def test_application_create_update_detail_and_delete(self):
        new_app = {
            "name": "v3 test app",
            "category": "Productivity",
            "cost": 25000,
            "licenses": 10,
            "active": 6,
            "risk": "Low",
            "renewal": "2027-04-15",
        }
        status, created, _ = api_request("POST", "/api/apps", new_app)
        self.assertEqual(status, 201)
        self.assertEqual(created["annual"], 300000)
        self.assertEqual(created["utilization"], 60)

        updated_app = {
            **new_app,
            "name": "v3 test app renamed",
            "category": "Operations",
            "cost": 30000,
            "renewal": "2027-05-20",
        }
        status, updated, _ = api_request("PUT", "/api/apps/v3%20test%20app", updated_app)
        self.assertEqual(status, 200)
        self.assertEqual(updated["name"], "v3 test app renamed")
        self.assertEqual(updated["category"], "Operations")
        self.assertEqual(updated["cost"], 30000)

        status, _, _ = api_request("GET", "/api/apps/v3%20test%20app")
        self.assertEqual(status, 404)
        status, detail, _ = api_request("GET", "/api/apps/v3%20test%20app%20renamed")
        self.assertEqual(status, 200)
        self.assertEqual(detail["renewal"], "2027-05-20")

        restarted_provider = MockProvider(main.provider._database_path)
        persisted = next(app for app in restarted_provider.apps() if app["name"] == "v3 test app renamed")
        self.assertEqual(persisted["category"], "Operations")
        self.assertEqual(persisted["cost"], 30000)

        status, payload, _ = api_request("DELETE", "/api/apps/v3%20test%20app%20renamed")
        self.assertEqual(status, 204)
        self.assertIsNone(payload)
        after_delete = MockProvider(main.provider._database_path)
        self.assertIsNone(after_delete.app("v3 test app renamed"))
        status, _, _ = api_request("GET", "/api/apps/v3%20test%20app%20renamed")
        self.assertEqual(status, 404)

    def test_application_validation_and_duplicate_conflict(self):
        valid_app = {
            "name": "Acme",
            "category": "Productivity",
            "cost": 25000,
            "licenses": 10,
            "active": 6,
            "risk": "Low",
            "renewal": "2027-04-15",
        }
        invalid_apps = [
            {**valid_app, "name": "  "},
            {**valid_app, "category": ""},
            {**valid_app, "cost": -1},
            {**valid_app, "licenses": 0},
            {**valid_app, "active": -1},
            {**valid_app, "active": 11},
            {**valid_app, "risk": "Critical"},
            {**valid_app, "renewal": "not-a-date"},
        ]
        for invalid in invalid_apps:
            with self.subTest(invalid=invalid):
                status, _, _ = api_request("POST", "/api/apps", invalid)
                self.assertEqual(status, 422)
        status, _, _ = api_request("POST", "/api/apps", {"name": "Missing category"})
        self.assertEqual(status, 422)

        status, _, _ = api_request("POST", "/api/apps", valid_app)
        self.assertEqual(status, 201)
        status, payload, _ = api_request("POST", "/api/apps", {**valid_app, "name": "acme"})
        self.assertEqual(status, 409)
        self.assertIn("already exists", payload["detail"])

    def test_application_update_and_delete_not_found(self):
        app = {
            "name": "Missing",
            "category": "Productivity",
            "cost": 100,
            "licenses": 1,
            "active": 1,
            "risk": "Low",
            "renewal": "2027-01-01",
        }
        status, payload, _ = api_request("PUT", "/api/apps/Unknown", app)
        self.assertEqual(status, 404)
        self.assertEqual(payload["detail"], "Application not found")
        status, payload, _ = api_request("DELETE", "/api/apps/Unknown")
        self.assertEqual(status, 404)
        self.assertEqual(payload["detail"], "Application not found")

    def test_removing_savings_applications_keeps_dependent_apis_available(self):
        for name in ("Figma", "Zoom", "Slack", "Notion", "GitHub", "AWS", "Microsoft 365", "Jira"):
            status, _, _ = api_request("DELETE", f"/api/apps/{name}")
            self.assertEqual(status, 204)
        for path in ("/api/savings", "/api/licenses", "/api/renewals", "/api/overview"):
            with self.subTest(path=path):
                status, payload, _ = api_request("GET", path)
                self.assertEqual(status, 200)
                self.assertIsNotNone(payload)
        status, licenses, _ = api_request("GET", "/api/licenses")
        self.assertEqual(status, 200)
        self.assertEqual(licenses["summary"]["utilization"], 0)

    def test_renewal_review_updates_status(self):
        status, payload, _ = api_request("POST", "/api/renewals/Slack/review")
        self.assertEqual(status, 200)
        slack = next(item for item in payload["items"] if item["name"] == "Slack")
        self.assertEqual(slack["status"], "Reviewed")
        restarted_provider = MockProvider(main.provider._database_path)
        self.assertIn("slack", restarted_provider.renewal_reviews())

    def test_savings_figures_match_overview_and_application_data(self):
        status, savings_payload, _ = api_request("GET", "/api/savings")
        self.assertEqual(status, 200)
        status, overview_payload, _ = api_request("GET", "/api/overview")
        self.assertEqual(status, 200)
        self.assertEqual(savings_payload["monthly"], overview_payload["kpis"]["savings"])
        self.assertEqual(savings_payload["spend"], overview_payload["kpis"]["spend"])
        self.assertEqual(savings_payload["annual"], savings_payload["monthly"] * 12)
        self.assertEqual(savings_payload["realized_monthly"], 0)
        self.assertEqual(overview_payload["kpis"]["apps"], len(main.provider.apps()))

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


class ApplicationPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "applications.sqlite3"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initial_database_seeds_current_applications(self):
        provider = MockProvider(self.database_path)

        apps = provider.apps()

        self.assertEqual(len(apps), 8)
        self.assertEqual(apps[0]["name"], "Slack")
        self.assertEqual(apps[0]["cost"], 520000)
        self.assertEqual(apps[-1]["name"], "Jira")

    def test_application_retrieval_preserves_api_fields(self):
        provider = MockProvider(self.database_path)

        app = next(item for item in provider.apps() if item["name"] == "Figma")

        self.assertEqual(
            set(app),
            {"name", "category", "cost", "licenses", "active", "risk", "renewal", "annual"},
        )
        self.assertEqual(app["licenses"], 80)
        self.assertEqual(app["active"], 46)

    def test_application_changes_persist_after_provider_restart(self):
        first_session = MockProvider(self.database_path)
        self.assertTrue(first_session.reclaim_license_seats("Figma"))

        restarted_session = MockProvider(self.database_path)
        figma = next(item for item in restarted_session.apps() if item["name"] == "Figma")

        self.assertEqual(figma["licenses"], 46)
        self.assertEqual(figma["active"], 46)
        self.assertEqual(figma["cost"], 184000)
        self.assertEqual(figma["annual"], 2208000)
        self.assertEqual(len(restarted_session.apps()), 8)

    def test_legacy_renewal_dates_are_normalized_to_iso_on_startup(self):
        MockProvider(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute("UPDATE applications SET renewal = 'Dec 12' WHERE name = 'Figma'")

        restarted = MockProvider(self.database_path)
        figma = next(app for app in restarted.apps() if app["name"] == "Figma")
        today = date.today()
        expected_year = today.year if today <= date(today.year, 12, 12) else today.year + 1
        self.assertEqual(figma["renewal"], f"{expected_year}-12-12")


class RenewalDateTests(unittest.TestCase):
    def test_iso_renewal_date_calculations_and_classification(self):
        today = date(2026, 10, 25)
        records = [
            {"name": "December", "renewal": "2026-12-12"},
            {"name": "Next year", "renewal": "2027-01-05"},
            {"name": "Today", "renewal": today.isoformat()},
            {"name": "Overdue", "renewal": "2026-10-24"},
        ]
        for record in records:
            record.update({
                "category": "Test",
                "cost": 100,
                "annual": 1200,
                "risk": "Low",
            })

        result = services.renewals(records, set(), today=today)
        by_name = {item["name"]: item for item in result["items"]}

        self.assertEqual(by_name["December"]["renewal_date"], "2026-12-12")
        self.assertEqual(by_name["December"]["days_remaining"], 48)
        self.assertEqual(by_name["December"]["urgency"], "Low")
        self.assertEqual(by_name["Next year"]["renewal_date"], "2027-01-05")
        self.assertEqual(by_name["Next year"]["days_remaining"], 72)
        self.assertEqual(by_name["Today"]["days_remaining"], 0)
        self.assertEqual(by_name["Today"]["urgency"], "High")
        self.assertEqual(by_name["Overdue"]["days_remaining"], -1)
        self.assertEqual(by_name["Overdue"]["urgency"], "Overdue")
        self.assertEqual(result["summary"]["upcoming"], 3)
        self.assertEqual(result["summary"]["due_soon"], 1)
        self.assertEqual(result["summary"]["overdue"], 1)

    def test_missing_and_invalid_renewal_dates_are_safe(self):
        records = [
            {"name": "Missing", "renewal": None},
            {"name": "Invalid", "renewal": "not-a-date"},
        ]
        for record in records:
            record.update({"category": "Test", "cost": 100, "annual": 1200, "risk": "Low"})
        result = services.renewals(records, set(), today=date(2026, 10, 25))
        self.assertEqual(len(result["items"]), 2)
        self.assertTrue(all(item["days_remaining"] is None for item in result["items"]))
        self.assertTrue(all(item["renewal_date"] is None for item in result["items"]))
        self.assertTrue(all(item["renewal_status"] == "Unknown" for item in result["items"]))
        self.assertEqual(result["summary"]["upcoming"], 0)


class SavingsCalculationTests(unittest.TestCase):
    @staticmethod
    def app(name: str, cost: int, licenses: int, active: int) -> dict:
        return {
            "name": name,
            "category": "Test",
            "cost": cost,
            "licenses": licenses,
            "active": active,
            "risk": "Low",
            "renewal": "2026-12-12",
            "annual": cost * 12,
        }

    def test_savings_for_utilization_cases(self):
        records = [
            self.app("Full", 1000, 10, 10),
            self.app("Partial", 1000, 10, 5),
            self.app("Unused", 1000, 10, 0),
        ]
        result = services.savings_summary(records)
        by_name = {item["app"]: item for item in result["opportunities"]}

        self.assertNotIn("Full", by_name)
        self.assertEqual(by_name["Partial"]["monthly"], 500)
        self.assertEqual(by_name["Partial"]["utilization"], 50)
        self.assertEqual(by_name["Partial"]["type"], "Low utilization")
        self.assertEqual(by_name["Unused"]["monthly"], 1000)
        self.assertEqual(by_name["Unused"]["utilization"], 0)
        self.assertEqual(result["monthly"], 1500)
        self.assertEqual(result["annual"], 18000)
        self.assertEqual(result["realized_monthly"], 0)
        self.assertIn("divided by purchased licenses", by_name["Partial"]["why"])

    def test_zero_licenses_zero_cost_and_empty_dataset(self):
        records = [
            self.app("Zero licenses", 500, 0, 0),
            self.app("Zero cost", 0, 10, 0),
        ]
        result = services.savings_summary(records)
        self.assertEqual(result["monthly"], 0)
        self.assertTrue(all(item["monthly"] >= 0 for item in result["opportunities"]))
        self.assertTrue(all(item["utilization"] == 0 for item in result["opportunities"]))

        empty = services.savings_summary([])
        self.assertEqual(empty["monthly"], 0)
        self.assertEqual(empty["annual"], 0)
        self.assertEqual(empty["spend"], 0)
        self.assertEqual(empty["opportunities"], [])
        self.assertEqual(services.licenses([])["summary"]["utilization"], 0)
        overview = services.overview([], [], today=date(2026, 10, 25))
        self.assertEqual(overview["kpis"]["savings"], 0)
        self.assertEqual(overview["kpis"]["spend"], 0)
        self.assertEqual(overview["kpis"]["apps"], 0)
        self.assertEqual(overview["kpis"]["renewals"], 0)
        self.assertIsNone(overview["kpis"]["next_renewal_days"])

    def test_renewal_due_soon_boundary_and_missing_date_order(self):
        today = date(2026, 10, 25)
        records = [
            self.app("Today", 100, 1, 1) | {"renewal": today.isoformat()},
            self.app("Urgent boundary", 100, 1, 1) | {"renewal": "2026-11-08"},
            self.app("Due soon boundary", 100, 1, 1) | {"renewal": "2026-11-24"},
            self.app("Upcoming", 100, 1, 1) | {"renewal": "2026-11-25"},
            self.app("Overdue", 100, 1, 1) | {"renewal": "2026-10-24"},
        ]
        result = services.renewals(records, set(), today=today)
        by_name = {item["name"]: item for item in result["items"]}
        self.assertEqual(by_name["Urgent boundary"]["urgency"], "High")
        self.assertEqual(by_name["Due soon boundary"]["urgency"], "Medium")
        self.assertEqual(by_name["Upcoming"]["renewal_status"], "Upcoming")
        self.assertEqual(by_name["Overdue"]["renewal_status"], "Overdue")


if __name__ == "__main__":
    unittest.main()
