import asyncio
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import unquote

import jwt
import main
import services
from cryptography.hazmat.primitives.asymmetric import ec
from data import MockProvider, _APPS
from auth import AuthenticatedUser, require_authenticated_user
import auth
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from tenant_migration import LEGACY_ORGANIZATION_ID, prepare_migration_candidate

TEST_USER_ID = "72f62a26-0d1c-4e6c-a91b-8349bf1b6a40"


def create_legacy_database(database_path: Path) -> MockProvider:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            """
            CREATE TABLE applications (
                name TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                cost INTEGER NOT NULL,
                licenses INTEGER NOT NULL,
                active INTEGER NOT NULL,
                risk TEXT NOT NULL,
                renewal TEXT NOT NULL,
                annual INTEGER NOT NULL,
                renewal_reviewed INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO applications
                (name, category, cost, licenses, active, risk, renewal, annual, renewal_reviewed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(*app, int(index == 1)) for index, app in enumerate(_APPS)],
        )
        connection.commit()
    with patch.dict(os.environ, {"SAASSPEND_LEGACY_OWNER_USER_ID": TEST_USER_ID}):
        candidate_path = prepare_migration_candidate(database_path)
    return MockProvider(candidate_path)


def api_request(
    method: str,
    path: str,
    payload: dict | None = None,
    origin: str | None = None,
    token: str | None = None,
    organization_id: str | None = LEGACY_ORGANIZATION_ID,
):
    body = json.dumps(payload).encode() if payload is not None else b""
    headers = [(b"host", b"testserver"), (b"content-type", b"application/json")]
    if origin:
        headers.append((b"origin", origin.encode()))
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    if organization_id:
        headers.append((b"x-organization-id", organization_id.encode()))
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
        main.provider = create_legacy_database(Path(self.temp_dir.name) / "test.sqlite3")
        self.provider = main.provider
        main.app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
            user_id=TEST_USER_ID
        )
        main.app.dependency_overrides[main.get_provider] = lambda: self.provider

    def tearDown(self):
        main.app.dependency_overrides.pop(require_authenticated_user, None)
        main.app.dependency_overrides.pop(main.get_provider, None)
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
        persisted = next(
            app for app in restarted_provider.apps(LEGACY_ORGANIZATION_ID)
            if app["name"] == "v3 test app renamed"
        )
        self.assertEqual(persisted["category"], "Operations")
        self.assertEqual(persisted["cost"], 30000)

        status, payload, _ = api_request("DELETE", "/api/apps/v3%20test%20app%20renamed")
        self.assertEqual(status, 204)
        self.assertIsNone(payload)
        after_delete = MockProvider(main.provider._database_path)
        self.assertIsNone(after_delete.app(LEGACY_ORGANIZATION_ID, "v3 test app renamed"))
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
        self.assertIn("slack", restarted_provider.renewal_reviews(LEGACY_ORGANIZATION_ID))

    def test_savings_figures_match_overview_and_application_data(self):
        status, savings_payload, _ = api_request("GET", "/api/savings")
        self.assertEqual(status, 200)
        status, overview_payload, _ = api_request("GET", "/api/overview")
        self.assertEqual(status, 200)
        self.assertEqual(savings_payload["monthly"], overview_payload["kpis"]["savings"])
        self.assertEqual(savings_payload["spend"], overview_payload["kpis"]["spend"])
        self.assertEqual(savings_payload["annual"], savings_payload["monthly"] * 12)
        self.assertEqual(savings_payload["realized_monthly"], 0)
        self.assertEqual(
            overview_payload["kpis"]["apps"],
            len(main.provider.apps(LEGACY_ORGANIZATION_ID)),
        )

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
        self.assertIn(b"authorization", headers[b"access-control-allow-headers"].lower())
        self.assertIn(
            b"x-organization-id",
            headers[b"access-control-allow-headers"].lower(),
        )

    def test_api_rejects_requests_without_authentication(self):
        main.app.dependency_overrides.pop(require_authenticated_user, None)
        status, payload, headers = api_request("GET", "/api/apps")
        self.assertEqual(status, 401)
        self.assertEqual(payload["detail"], "Authentication required")
        self.assertEqual(headers[b"www-authenticate"], b"Bearer")
        status, payload, _ = api_request("DELETE", "/api/apps/Slack")
        self.assertEqual(status, 401)
        self.assertIsNotNone(main.provider.app(LEGACY_ORGANIZATION_ID, "Slack"))


class AssistantApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        main.provider = create_legacy_database(Path(self.temp_dir.name) / "assistant.sqlite3")
        self.provider = main.provider
        main.app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
            user_id=TEST_USER_ID
        )
        main.app.dependency_overrides[main.get_provider] = lambda: self.provider

    def tearDown(self):
        main.app.dependency_overrides.pop(require_authenticated_user, None)
        main.app.dependency_overrides.pop(main.get_provider, None)
        self.temp_dir.cleanup()

    def create_app(self, name: str, cost: int, licenses: int, active: int, renewal: str) -> dict:
        return {
            "name": name,
            "category": "Test",
            "cost": cost,
            "licenses": licenses,
            "active": active,
            "risk": "Low",
            "renewal": renewal,
        }

    def ask(self, question: str):
        return api_request("POST", "/api/assistant/chat", {"message": question})

    def test_highest_spend_uses_persisted_application_records(self):
        status, _, _ = api_request(
            "POST",
            "/api/apps",
            self.create_app("Persistent premium app", 9999999, 10, 10, "2027-12-12"),
        )
        self.assertEqual(status, 201)

        status, payload, _ = self.ask("Which applications cost us the most?")

        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "highest_spend")
        self.assertEqual(payload["items"][0]["application"], "Persistent premium app")
        self.assertEqual(payload["items"][0]["monthly_cost"], 9999999)
        restarted = MockProvider(main.provider._database_path)
        self.assertEqual(
            restarted.app(LEGACY_ORGANIZATION_ID, "Persistent premium app")["cost"],
            9999999,
        )

    def test_license_and_savings_questions_use_shared_calculations(self):
        status, license_answer, _ = self.ask("Which subscriptions have the most unused licenses?")
        self.assertEqual(status, 200)
        self.assertEqual(license_answer["intent"], "license_utilization")
        self.assertTrue(license_answer["items"])
        self.assertTrue(all(item["unused"] > 0 for item in license_answer["items"]))

        status, savings_answer, _ = self.ask("How much potential savings do we have?")
        self.assertEqual(status, 200)
        self.assertEqual(savings_answer["intent"], "savings")
        status, savings_api, _ = api_request("GET", "/api/savings")
        self.assertEqual(status, 200)
        self.assertIn(f"₹{savings_api['estimated_monthly']:,}", savings_answer["answer"])
        self.assertEqual(savings_answer["items"][0]["estimated_monthly_savings"],
                         savings_api["opportunities"][0]["estimated_monthly_savings"])
        self.assertTrue(savings_answer["items"][0]["reason"])

    def test_access_security_and_general_summary_responses_are_grounded(self):
        status, access, _ = self.ask("Summarize user access risks")
        self.assertEqual(status, 200)
        self.assertEqual(access["intent"], "access")
        self.assertIn("illustrative provider records", access["answer"])

        status, security, _ = self.ask("What security findings are open?")
        self.assertEqual(status, 200)
        self.assertEqual(security["intent"], "security")
        self.assertIn("simulated security findings", security["answer"])

        status, summary, _ = self.ask("Give me an overall portfolio summary")
        self.assertEqual(status, 200)
        self.assertEqual(summary["intent"], "summary")
        self.assertIn(
            str(len(main.provider.apps(LEGACY_ORGANIZATION_ID))),
            summary["answer"],
        )

    def test_upcoming_and_overdue_renewal_questions(self):
        today = date.today()
        self.assertEqual(
            api_request(
                "POST",
                "/api/apps",
                self.create_app("Assistant overdue", 1000, 2, 2, (today - timedelta(days=1)).isoformat()),
            )[0],
            201,
        )
        self.assertEqual(
            api_request(
                "POST",
                "/api/apps",
                self.create_app("Assistant upcoming", 2000, 2, 2, (today + timedelta(days=45)).isoformat()),
            )[0],
            201,
        )
        self.assertEqual(
            api_request(
                "POST",
                "/api/apps",
                self.create_app("Assistant due soon", 1500, 2, 2, (today + timedelta(days=7)).isoformat()),
            )[0],
            201,
        )

        status, upcoming, _ = self.ask("What renewals are coming up?")
        self.assertEqual(status, 200)
        self.assertEqual(upcoming["intent"], "renewals")
        self.assertIn("Assistant upcoming", [item["application"] for item in upcoming["items"]])

        status, due_soon, _ = self.ask("Which renewals are due soon?")
        self.assertEqual(status, 200)
        self.assertEqual(due_soon["intent"], "due_soon_renewals")
        due_soon_items = {item["application"]: item for item in due_soon["items"]}
        self.assertIn("Assistant due soon", due_soon_items)
        self.assertTrue(all(item["status"] == "Due soon" for item in due_soon["items"]))

        status, overdue, _ = self.ask("Which renewals are overdue?")
        self.assertEqual(status, 200)
        self.assertEqual(overdue["intent"], "overdue_renewals")
        item = next(item for item in overdue["items"] if item["application"] == "Assistant overdue")
        self.assertEqual(item["days_remaining"], -1)
        self.assertEqual(item["renewal_date"], (today - timedelta(days=1)).isoformat())

    def test_empty_unsupported_and_invalid_messages(self):
        status, payload, _ = self.ask("What is our payroll forecast?")
        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "unsupported")

        for message in ("", "   ", "x" * 1001):
            with self.subTest(message_length=len(message)):
                status, _, _ = self.ask(message)
                self.assertEqual(status, 422)

        for name in ("Slack", "Figma", "GitHub", "Zoom", "AWS", "Microsoft 365", "Notion", "Jira"):
            self.assertTrue(main.provider.delete_app(LEGACY_ORGANIZATION_ID, name))
        status, payload, _ = self.ask("Summarize the portfolio")
        self.assertEqual(status, 200)
        self.assertEqual(payload["intent"], "no_data")
        self.assertIn("no application records", payload["answer"].lower())

    def test_chat_requests_do_not_modify_application_or_review_data(self):
        before_apps = main.provider.apps(LEGACY_ORGANIZATION_ID)
        before_reviews = main.provider.renewal_reviews(LEGACY_ORGANIZATION_ID)

        for question in (
            "Which applications cost us the most?",
            "How much potential savings do we have?",
            "What renewals are coming up?",
            "Show me security findings",
        ):
            status, _, _ = self.ask(question)
            self.assertEqual(status, 200)

        self.assertEqual(main.provider.apps(LEGACY_ORGANIZATION_ID), before_apps)
        self.assertEqual(
            main.provider.renewal_reviews(LEGACY_ORGANIZATION_ID), before_reviews
        )


class AuthenticationTests(unittest.TestCase):
    supabase_url = "https://project-ref.supabase.co"
    user_id = "72f62a26-0d1c-4e6c-a91b-8349bf1b6a40"

    def setUp(self):
        self.private_key = ec.generate_private_key(ec.SECP256R1())

    def token(self, **overrides) -> str:
        now = int(datetime.now(timezone.utc).timestamp())
        claims = {
            "iss": f"{self.supabase_url}/auth/v1",
            "aud": "authenticated",
            "sub": self.user_id,
            "iat": now,
            "exp": now + 300,
        }
        claims.update(overrides)
        return jwt.encode(claims, self.private_key, algorithm="ES256", headers={"kid": "test"})

    def verify(self, token: str, allowed_ids: str | None = None):
        user_ids = allowed_ids if allowed_ids is not None else self.user_id
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with (
            patch.dict(
                os.environ,
                {
                    "SUPABASE_URL": self.supabase_url,
                    "SAASSPEND_ALLOWED_USER_IDS": user_ids,
                },
            ),
            patch.object(
                auth,
                "_jwks_client",
                return_value=SimpleNamespace(
                    get_signing_key_from_jwt=lambda _token: SimpleNamespace(
                        key=self.private_key.public_key()
                    )
                ),
            ),
        ):
            return require_authenticated_user(credentials)

    def test_supabase_token_signature_and_claims_are_verified(self):
        verified = self.verify(self.token())
        self.assertEqual(verified, AuthenticatedUser(user_id=self.user_id))

        invalid_claims = (
            {"aud": "wrong-audience"},
            {"iss": "https://attacker.example/auth/v1"},
            {"exp": int(datetime.now(timezone.utc).timestamp()) - 10},
        )
        for claims in invalid_claims:
            with self.subTest(claims=claims), self.assertRaises(HTTPException) as raised:
                self.verify(self.token(**claims))
            self.assertEqual(raised.exception.status_code, 401)

    def test_unlisted_user_is_forbidden(self):
        with self.assertRaises(HTTPException) as raised:
            self.verify(self.token(), allowed_ids="another-user-id")
        self.assertEqual(raised.exception.status_code, 403)

    def test_missing_allowlist_fails_closed(self):
        with self.assertRaises(HTTPException) as raised:
            self.verify(self.token(), allowed_ids="")
        self.assertEqual(raised.exception.status_code, 503)

    def test_invalid_signature_is_rejected(self):
        other_key = ec.generate_private_key(ec.SECP256R1())
        now = int(datetime.now(timezone.utc).timestamp())
        token = jwt.encode(
            {
                "iss": f"{self.supabase_url}/auth/v1",
                "aud": "authenticated",
                "sub": self.user_id,
                "iat": now,
                "exp": now + 300,
            },
            other_key,
            algorithm="ES256",
            headers={"kid": "test"},
        )
        with self.assertRaises(HTTPException) as raised:
            self.verify(token)
        self.assertEqual(raised.exception.status_code, 401)

    def test_token_parse_error_during_key_lookup_is_rejected_safely(self):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="not-a-jwt",
        )
        with (
            patch.dict(
                os.environ,
                {
                    "SUPABASE_URL": self.supabase_url,
                    "SAASSPEND_ALLOWED_USER_IDS": self.user_id,
                },
            ),
            patch.object(
                auth,
                "_jwks_client",
                return_value=SimpleNamespace(
                    get_signing_key_from_jwt=Mock(
                        side_effect=jwt.DecodeError("malformed token")
                    )
                ),
            ),
            self.assertLogs("auth", level="WARNING") as logs,
        ):
            with self.assertRaises(HTTPException) as raised:
                require_authenticated_user(credentials)

        self.assertEqual(raised.exception.status_code, 401)
        self.assertIn("token_parse_failed", logs.output[0])
        self.assertNotIn(credentials.credentials, "\n".join(logs.output))

    def test_auth_me_route_accepts_verified_allowlisted_bearer_token(self):
        with patch.object(
            auth,
            "_jwks_client",
            return_value=SimpleNamespace(
                get_signing_key_from_jwt=lambda _token: SimpleNamespace(
                    key=self.private_key.public_key()
                )
            ),
        ), patch.dict(
            os.environ,
            {
                "SUPABASE_URL": self.supabase_url,
                "SAASSPEND_ALLOWED_USER_IDS": self.user_id,
            },
        ):
            status, payload, _ = api_request(
                "GET",
                "/api/auth/me",
                token=self.token(),
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"authenticated": True})


class ApplicationPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "applications.sqlite3"
        self.provider = create_legacy_database(self.database_path)
        self.candidate_path = Path(f"{self.database_path}.stage2.1.candidate")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initial_database_seeds_current_applications(self):
        apps = self.provider.apps(LEGACY_ORGANIZATION_ID)

        self.assertEqual(len(apps), 8)
        self.assertEqual(apps[0]["name"], "Slack")
        self.assertEqual(apps[0]["cost"], 520000)
        self.assertEqual(apps[-1]["name"], "Jira")

    def test_application_retrieval_preserves_api_fields(self):
        app = next(
            item for item in self.provider.apps(LEGACY_ORGANIZATION_ID)
            if item["name"] == "Figma"
        )

        self.assertEqual(
            set(app),
            {"id", "name", "category", "cost", "licenses", "active", "risk", "renewal", "annual"},
        )
        self.assertEqual(app["licenses"], 80)
        self.assertEqual(app["active"], 46)

    def test_application_changes_persist_after_provider_restart(self):
        first_session = self.provider
        self.assertTrue(first_session.reclaim_license_seats(LEGACY_ORGANIZATION_ID, "Figma"))

        restarted_session = MockProvider(self.candidate_path)
        figma = next(
            item for item in restarted_session.apps(LEGACY_ORGANIZATION_ID)
            if item["name"] == "Figma"
        )

        self.assertEqual(figma["licenses"], 46)
        self.assertEqual(figma["active"], 46)
        self.assertEqual(figma["cost"], 184000)
        self.assertEqual(figma["annual"], 2208000)
        self.assertEqual(len(restarted_session.apps(LEGACY_ORGANIZATION_ID)), 8)

    def test_legacy_renewal_dates_and_review_flags_are_preserved(self):
        figma = next(
            app for app in self.provider.apps(LEGACY_ORGANIZATION_ID)
            if app["name"] == "Figma"
        )
        self.assertEqual(figma["renewal"], "Oct 12")
        with closing(sqlite3.connect(self.candidate_path)) as connection:
            row = connection.execute(
                """
                SELECT renewal_reviewed FROM applications
                WHERE organization_id = ? AND id = ?
                """,
                (LEGACY_ORGANIZATION_ID, figma["id"]),
            ).fetchone()
        self.assertEqual(row[0], 1)


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
