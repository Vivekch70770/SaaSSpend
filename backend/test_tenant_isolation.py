import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import main
from auth import AuthenticatedUser, require_authenticated_user
from tenant_migration import LEGACY_ORGANIZATION_ID
from test_api import TEST_USER_ID, api_request, create_legacy_database

SECOND_USER_ID = "0273f707-e619-41d0-a6c4-e978f700a2e3"
VIEWER_USER_ID = "4c3f4d14-9afe-4094-afde-63cb96259ee8"
EDITOR_USER_ID = "d1969fd4-17ea-4d4a-9c13-89fb94c025f6"
ADMIN_USER_ID = "10edc15d-6373-449a-9f4b-5a50fc053b11"


class TenantIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "tenants.sqlite3"
        self.provider = create_legacy_database(self.database_path)
        self.candidate_path = Path(f"{self.database_path}.stage2.1.candidate")
        self.org_b = self.provider.create_organization("Second workspace", SECOND_USER_ID)["id"]
        self.current_user_id = TEST_USER_ID
        main.app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
            user_id=self.current_user_id
        )
        main.app.dependency_overrides[main.get_provider] = lambda: self.provider

    def tearDown(self):
        main.app.dependency_overrides.pop(require_authenticated_user, None)
        main.app.dependency_overrides.pop(main.get_provider, None)
        self.temp_dir.cleanup()

    def as_user(self, user_id: str) -> None:
        self.current_user_id = user_id

    def test_reads_and_assistant_are_scoped_to_selected_organization(self):
        self.provider.create_app(
            self.org_b,
            {
                "name": "Only in second workspace",
                "category": "Test",
                "cost": 1200,
                "licenses": 4,
                "active": 2,
                "risk": "Low",
                "renewal": "2027-12-01",
                "annual": 14400,
            },
        )

        status, legacy_apps, _ = api_request("GET", "/api/apps")
        self.assertEqual(status, 200)
        self.assertEqual(len(legacy_apps), 8)

        self.as_user(SECOND_USER_ID)
        status, second_apps, _ = api_request(
            "GET", "/api/apps", organization_id=self.org_b
        )
        self.assertEqual(status, 200)
        self.assertEqual([app["name"] for app in second_apps], ["Only in second workspace"])

        status, overview, _ = api_request(
            "GET", "/api/overview", organization_id=self.org_b
        )
        self.assertEqual(status, 200)
        self.assertEqual(overview["kpis"]["apps"], 1)
        self.assertEqual(overview["kpis"]["spend"], 1200)

        status, assistant, _ = api_request(
            "POST",
            "/api/assistant/chat",
            {"message": "Which application costs the most?"},
            organization_id=self.org_b,
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            [item["application"] for item in assistant["items"]],
            ["Only in second workspace"],
        )

        for path in ("/api/shadow-it", "/api/access", "/api/security"):
            status, data, _ = api_request("GET", path, organization_id=self.org_b)
            self.assertEqual(status, 200)
            self.assertEqual(data["items"], [])

    def test_nonmember_cannot_read_or_write_any_business_route(self):
        self.provider.create_app(
            self.org_b,
            {
                "name": "Private app",
                "category": "Test",
                "cost": 100,
                "licenses": 1,
                "active": 1,
                "risk": "Low",
                "renewal": "2027-12-01",
                "annual": 1200,
            },
        )
        self.as_user(TEST_USER_ID)
        reads = (
            ("GET", "/api/overview", None),
            ("GET", "/api/apps", None),
            ("GET", "/api/apps/Private%20app", None),
            ("GET", "/api/savings", None),
            ("GET", "/api/licenses", None),
            ("GET", "/api/renewals", None),
            ("GET", "/api/shadow-it", None),
            ("GET", "/api/access", None),
            ("GET", "/api/security", None),
            ("POST", "/api/assistant/chat", {"message": "summarize the portfolio"}),
        )
        for method, path, body in reads:
            with self.subTest(method=method, path=path):
                status, _, _ = api_request(
                    method, path, body, organization_id=self.org_b
                )
                self.assertEqual(status, 403)

        writes = (
            ("POST", "/api/apps", {
                "name": "Intrusion",
                "category": "Test",
                "cost": 1,
                "licenses": 1,
                "active": 1,
                "risk": "Low",
                "renewal": "2027-12-01",
            }),
            ("PUT", "/api/apps/Private%20app", {
                "name": "Private app",
                "category": "Changed",
                "cost": 2,
                "licenses": 1,
                "active": 1,
                "risk": "Low",
                "renewal": "2027-12-01",
            }),
            ("DELETE", "/api/apps/Private%20app", None),
            ("POST", "/api/licenses/Private%20app/reclaim", None),
            ("POST", "/api/renewals/Private%20app/review", None),
            ("PATCH", "/api/shadow-it/linear", {"status": "Approved"}),
            ("POST", "/api/access/kabir-shah/review", None),
            ("POST", "/api/access/kabir-shah/deactivate", None),
            ("POST", "/api/security/mfa-gap/resolve", None),
        )
        for method, path, body in writes:
            with self.subTest(method=method, path=path):
                status, _, _ = api_request(
                    method, path, body, organization_id=self.org_b
                )
                self.assertEqual(status, 403)
        self.assertEqual(
            [app["name"] for app in self.provider.apps(self.org_b)],
            ["Private app"],
        )

    def test_missing_and_invalid_organization_selectors_fail_closed(self):
        for organization_id, expected_status in ((None, 400), ("invalid", 400)):
            with self.subTest(organization_id=organization_id):
                status, _, _ = api_request(
                    "GET", "/api/apps", organization_id=organization_id
                )
                self.assertEqual(status, expected_status)

    def test_application_names_are_unique_within_but_not_across_organizations(self):
        data = {
            "name": "Shared suite",
            "category": "Test",
            "cost": 1200,
            "licenses": 2,
            "active": 1,
            "risk": "Low",
            "renewal": "2027-12-01",
        }
        status, _, _ = api_request("POST", "/api/apps", data)
        self.assertEqual(status, 201)

        self.as_user(SECOND_USER_ID)
        status, _, _ = api_request(
            "POST", "/api/apps", data, organization_id=self.org_b
        )
        self.assertEqual(status, 201)

        self.as_user(TEST_USER_ID)
        status, conflict, _ = api_request(
            "POST",
            "/api/apps",
            {**data, "name": "  SHARED SUITE  "},
        )
        self.assertEqual(status, 409)
        self.assertIn("already exists", conflict["detail"])

        self.as_user(SECOND_USER_ID)
        status, second_apps, _ = api_request(
            "GET", "/api/apps", organization_id=self.org_b
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            [app["name"] for app in second_apps],
            ["Shared suite"],
        )

    def test_viewer_editor_admin_and_owner_write_permissions(self):
        route_cases = (
            (
                "create application",
                "editor",
                "POST",
                "/api/apps",
                {
                    "name": "Matrix application",
                    "category": "Test",
                    "cost": 100,
                    "licenses": 2,
                    "active": 1,
                    "risk": "Low",
                    "renewal": "2027-01-01",
                },
                201,
            ),
            (
                "update application",
                "editor",
                "PUT",
                "/api/apps/Slack",
                {
                    "name": "Slack",
                    "category": "Updated",
                    "cost": 520000,
                    "licenses": 150,
                    "active": 121,
                    "risk": "Low",
                    "renewal": "2027-01-01",
                },
                200,
            ),
            ("delete application", "editor", "DELETE", "/api/apps/Jira", None, 204),
            (
                "reclaim licenses",
                "editor",
                "POST",
                "/api/licenses/Figma/reclaim",
                None,
                200,
            ),
            (
                "review renewal",
                "editor",
                "POST",
                "/api/renewals/Slack/review",
                None,
                200,
            ),
            (
                "update shadow IT status",
                "editor",
                "PATCH",
                "/api/shadow-it/linear",
                {"status": "Approved"},
                200,
            ),
            (
                "review access",
                "editor",
                "POST",
                "/api/access/kabir-shah/review",
                None,
                200,
            ),
            (
                "deactivate access user",
                "admin",
                "POST",
                "/api/access/kabir-shah/deactivate",
                None,
                200,
            ),
            (
                "resolve security finding",
                "editor",
                "POST",
                "/api/security/mfa-gap/resolve",
                None,
                200,
            ),
        )
        role_users = (
            ("viewer", VIEWER_USER_ID),
            ("editor", EDITOR_USER_ID),
            ("admin", ADMIN_USER_ID),
            ("owner", TEST_USER_ID),
            ("nonmember", SECOND_USER_ID),
        )
        role_level = {
            "nonmember": -1,
            "viewer": 0,
            "editor": 1,
            "admin": 2,
            "owner": 3,
        }
        required_level = {"editor": 1, "admin": 2}

        for role, user_id in role_users:
            with self.subTest(role=role):
                with tempfile.TemporaryDirectory() as role_directory:
                    database_path = Path(role_directory) / "role-matrix.sqlite3"
                    self.provider = create_legacy_database(database_path)
                    candidate_path = Path(
                        f"{database_path}.stage2.1.candidate"
                    )
                    if role not in ("owner", "nonmember"):
                        with closing(sqlite3.connect(candidate_path)) as connection:
                            connection.execute(
                                """
                                INSERT INTO organization_memberships
                                    (organization_id, supabase_user_id, role, created_at)
                                VALUES (?, ?, ?, datetime('now'))
                                """,
                                (LEGACY_ORGANIZATION_ID, user_id, role),
                            )
                            connection.commit()

                    self.as_user(user_id)
                    read_status, _, _ = api_request("GET", "/api/apps")
                    self.assertEqual(read_status, 403 if role == "nonmember" else 200)

                    for (
                        route_name,
                        minimum_role,
                        method,
                        path,
                        payload,
                        success_status,
                    ) in route_cases:
                        expected_status = (
                            success_status
                            if role_level[role] >= required_level[minimum_role]
                            else 403
                        )
                        with self.subTest(role=role, route=route_name):
                            status, _, _ = api_request(
                                method,
                                path,
                                payload,
                                organization_id=LEGACY_ORGANIZATION_ID,
                            )
                            self.assertEqual(status, expected_status)

    def test_new_organization_has_no_legacy_application_or_fixture_data(self):
        self.as_user(SECOND_USER_ID)
        status, organizations, _ = api_request("GET", "/api/organizations")
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in organizations], [self.org_b])
        status, apps, _ = api_request("GET", "/api/apps", organization_id=self.org_b)
        self.assertEqual(status, 200)
        self.assertEqual(apps, [])
        status, response, _ = api_request(
            "POST",
            "/api/organizations",
            {"name": "Another workspace"},
            organization_id=None,
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["role"], "owner")
        self.assertEqual(self.provider.apps(response["id"]), [])


class ImportSafetyTests(unittest.TestCase):
    def test_importing_main_does_not_open_or_initialize_a_database(self):
        import os
        import subprocess
        import sys

        backend_dir = Path(__file__).resolve().parent
        script = (
            "import sqlite3\n"
            "calls = []\n"
            "sqlite3.connect = lambda *args, **kwargs: calls.append(args)\n"
            "import main\n"
            "assert not calls, calls\n"
            "assert main._provider is None\n"
        )
        environment = os.environ.copy()
        environment["SAASSPEND_DATABASE_PATH"] = str(
            Path(tempfile.gettempdir()) / "must-not-be-created.sqlite3"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=backend_dir,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
