"""Data layer. Replace MockProvider with real API-backed providers later."""
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Protocol
import uuid

from tenant_migration import normalize_application_name

_APPS = [  # name, category, monthly cost (INR), licenses, active, risk, renewal, annual contract
    ("Slack", "Communication", 520000, 150, 121, "Low", "Oct 18", 6240000),
    ("Figma", "Design", 320000, 80, 46, "Medium", "Oct 12", 3840000),
    ("GitHub", "Development", 410000, 100, 94, "Low", "Nov 02", 4920000),
    ("Zoom", "Communication", 140000, 150, 51, "Medium", "Nov 14", 1680000),
    ("AWS", "Infrastructure", 840000, 40, 38, "Low", "Dec 01", 10080000),
    ("Microsoft 365", "Productivity", 480000, 200, 176, "Low", "Dec 20", 5760000),
    ("Notion", "Productivity", 210000, 120, 72, "Low", "Jan 08", 2520000),
    ("Jira", "Development", 160000, 90, 71, "Low", "Jan 22", 1920000),
]
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "saasspend.db"

class Provider(Protocol):
    def organizations_for_user(self, user_id: str) -> list[dict]: ...
    def apps(self, organization_id: str) -> list[dict]: ...
    def spend_history(self, organization_id: str) -> list[dict]: ...

class MockProvider:
    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self._database_path = Path(database_path)
        self._shadow_apps = [
            {"id": "linear", "name": "Linear", "category": "Project management", "monthly_cost": 68000,
             "risk": "Medium", "discovered": "2026-10-18", "owner": "Engineering", "status": "Pending review"},
            {"id": "miro", "name": "Miro", "category": "Collaboration", "monthly_cost": 42000,
             "risk": "Low", "discovered": "2026-10-12", "owner": "Product", "status": "Pending review"},
            {"id": "grammarly", "name": "Grammarly", "category": "Productivity", "monthly_cost": 18500,
             "risk": "High", "discovered": "2026-09-28", "owner": "People", "status": "Pending review"},
        ]
        self._access_users = [
            {"id": "ananya-rao", "name": "Ananya Rao", "email": "ananya@novalabs.example", "department": "Engineering",
             "last_active": "2026-10-24", "active": True, "reviewed": False,
             "assignments": [{"app": "GitHub", "role": "Admin"}, {"app": "AWS", "role": "Admin"},
                             {"app": "Slack", "role": "Member"}, {"app": "Figma", "role": "Editor"}]},
            {"id": "rohan-mehta", "name": "Rohan Mehta", "email": "rohan@novalabs.example", "department": "Design",
             "last_active": "2026-10-24", "active": True, "reviewed": False,
             "assignments": [{"app": "Figma", "role": "Editor"}, {"app": "Slack", "role": "Member"}]},
            {"id": "isha-kapoor", "name": "Isha Kapoor", "email": "isha@novalabs.example", "department": "Marketing",
             "last_active": "2026-07-02", "active": False, "reviewed": False,
             "assignments": [{"app": "Microsoft 365", "role": "Member"}, {"app": "Notion", "role": "Editor"},
                             {"app": "Slack", "role": "Member"}]},
            {"id": "kabir-shah", "name": "Kabir Shah", "email": "kabir@novalabs.example", "department": "Engineering",
             "last_active": "2026-10-23", "active": True, "reviewed": False,
             "assignments": [{"app": "GitHub", "role": "Member"}, {"app": "Jira", "role": "Admin"}]},
            {"id": "meera-nair", "name": "Meera Nair", "email": "meera@novalabs.example", "department": "Finance",
             "last_active": "2026-06-18", "active": False, "reviewed": False,
             "assignments": [{"app": "Microsoft 365", "role": "Member"}, {"app": "Zoom", "role": "Member"}]},
        ]
        self._security_findings = [
            {"id": "mfa-gap", "title": "Multi-factor authentication not enforced",
             "severity": "High", "application": "Slack", "affected": "12 users",
             "recommendation": "Require MFA for all workspace members and review recovery methods.",
             "status": "Open"},
            {"id": "inactive-admin", "title": "Inactive account retains administrator access",
             "severity": "High", "application": "AWS", "affected": "Isha Kapoor",
             "recommendation": "Deactivate the account and revoke its administrator role.",
             "status": "Open"},
            {"id": "public-sharing", "title": "Public sharing setting may expose documents",
             "severity": "Medium", "application": "Notion", "affected": "3 workspaces",
             "recommendation": "Review public-link settings and restrict external sharing where not needed.",
             "status": "Open"},
            {"id": "unused-app", "title": "Unreviewed application has broad data permissions",
             "severity": "Low", "application": "Grammarly", "affected": "1 application",
             "recommendation": "Validate the requested permissions with the application owner.",
             "status": "Open"},
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"{self._database_path.resolve().as_uri()}?mode=rw",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _legacy_organization_id(self, connection: sqlite3.Connection) -> str | None:
        row = connection.execute(
            "SELECT value FROM application_metadata WHERE key = 'legacy_organization_id'"
        ).fetchone()
        return row["value"] if row else None

    def organizations_for_user(self, user_id: str) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT o.id, o.name, m.role
                FROM organization_memberships AS m
                JOIN organizations AS o ON o.id = m.organization_id
                WHERE m.supabase_user_id = ?
                ORDER BY o.name COLLATE NOCASE
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def membership_role(self, organization_id: str, user_id: str) -> str | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT role FROM organization_memberships
                WHERE organization_id = ? AND supabase_user_id = ?
                """,
                (organization_id, user_id),
            ).fetchone()
        return row["role"] if row else None

    def create_organization(self, name: str, owner_user_id: str) -> dict:
        organization = {
            "id": str(uuid.uuid4()),
            "name": name,
            "role": "owner",
        }
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO organizations (id, name, created_at) VALUES (?, ?, datetime('now'))",
                    (organization["id"], name),
                )
                connection.execute(
                    """
                    INSERT INTO organization_memberships
                        (organization_id, supabase_user_id, role, created_at)
                    VALUES (?, ?, 'owner', datetime('now'))
                    """,
                    (organization["id"], owner_user_id),
                )
        return organization

    def apps(self, organization_id: str) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, name, category, cost, licenses, active, risk, renewal, annual
                FROM applications WHERE organization_id = ? ORDER BY rowid
                """,
                (organization_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def app(self, organization_id: str, name: str) -> dict | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT id, name, category, cost, licenses, active, risk, renewal, annual
                FROM applications
                WHERE organization_id = ? AND normalized_name = ?
                """,
                (organization_id, normalize_application_name(name)),
            ).fetchone()
        return dict(row) if row else None

    def create_app(self, organization_id: str, app: dict) -> dict:
        record = {
            **app,
            "id": str(uuid.uuid4()),
            "normalized_name": normalize_application_name(app["name"]),
        }
        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO applications
                            (id, organization_id, name, normalized_name, category, cost,
                             licenses, active, risk, renewal, annual, renewal_reviewed)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                        """,
                        (
                            record["id"], organization_id, record["name"], record["normalized_name"],
                            record["category"], record["cost"], record["licenses"], record["active"],
                            record["risk"], record["renewal"], record["annual"],
                        ),
                    )
        except sqlite3.IntegrityError as error:
            if "applications.organization_id, applications.normalized_name" in str(error):
                raise ValueError("An application with this name already exists") from error
            raise
        created = self.app(organization_id, app["name"])
        if created is None:
            raise RuntimeError("Created application could not be reloaded")
        return created

    def update_app(self, organization_id: str, current_name: str, app: dict) -> dict | None:
        current_normalized = normalize_application_name(current_name)
        next_normalized = normalize_application_name(app["name"])
        try:
            with closing(self._connect()) as connection:
                with connection:
                    existing = connection.execute(
                        """
                        SELECT id FROM applications
                        WHERE organization_id = ? AND normalized_name = ?
                        """,
                        (organization_id, current_normalized),
                    ).fetchone()
                    if existing is None:
                        return None
                    cursor = connection.execute(
                        """
                        UPDATE applications
                        SET name = ?, normalized_name = ?, category = ?, cost = ?,
                            licenses = ?, active = ?, risk = ?, renewal = ?, annual = ?
                        WHERE organization_id = ? AND id = ?
                        """,
                        (
                            app["name"], next_normalized, app["category"], app["cost"],
                            app["licenses"], app["active"], app["risk"], app["renewal"],
                            app["annual"], organization_id, existing["id"],
                        ),
                    )
                    if cursor.rowcount == 0:
                        return None
        except sqlite3.IntegrityError as error:
            if "applications.organization_id, applications.normalized_name" in str(error):
                raise ValueError("An application with this name already exists") from error
            raise
        return self.app(organization_id, app["name"])

    def delete_app(self, organization_id: str, name: str) -> bool:
        with closing(self._connect()) as connection:
            with connection:
                app = connection.execute(
                    """
                    SELECT id FROM applications
                    WHERE organization_id = ? AND normalized_name = ?
                    """,
                    (organization_id, normalize_application_name(name)),
                ).fetchone()
                if app is None:
                    return False
                cursor = connection.execute(
                    "DELETE FROM applications WHERE organization_id = ? AND id = ?",
                    (organization_id, app["id"]),
                )
        return cursor.rowcount > 0

    def spend_history(self, organization_id: str) -> list[dict]:
        with closing(self._connect()) as connection:
            if organization_id != self._legacy_organization_id(connection):
                return []
        months = "Nov Dec Jan Feb Mar Apr May Jun Jul Aug Sep Oct".split()
        vals = [22, 24, 26, 25, 28, 31, 33, 35, 37, 39, 41, 42.2]
        return [{"month": month, "lakh": value} for month, value in zip(months, vals)]

    def reclaim_license_seats(self, organization_id: str, name: str) -> bool:
        with closing(self._connect()) as connection:
            with connection:
                app = connection.execute(
                    """
                    SELECT id, cost, licenses, active
                    FROM applications
                    WHERE organization_id = ? AND normalized_name = ?
                    """,
                    (organization_id, normalize_application_name(name)),
                ).fetchone()
                if app is None or app["licenses"] == app["active"]:
                    return False
                seat_cost = app["cost"] / app["licenses"]
                updated_cost = round(seat_cost * app["active"])
                connection.execute(
                    """
                    UPDATE applications SET cost = ?, licenses = ?, annual = ?
                    WHERE organization_id = ? AND id = ?
                    """,
                    (
                        updated_cost, app["active"], round(seat_cost * app["active"] * 12),
                        organization_id, app["id"],
                    ),
                )
        return True

    def renewal_reviews(self, organization_id: str) -> set[str]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT normalized_name FROM applications
                WHERE organization_id = ? AND renewal_reviewed = 1
                """,
                (organization_id,),
            ).fetchall()
        return {row["normalized_name"] for row in rows}

    def review_renewal(self, organization_id: str, name: str) -> bool:
        with closing(self._connect()) as connection:
            with connection:
                app = connection.execute(
                    """
                    SELECT id FROM applications
                    WHERE organization_id = ? AND normalized_name = ?
                    """,
                    (organization_id, normalize_application_name(name)),
                ).fetchone()
                if app is None:
                    return False
                cursor = connection.execute(
                    """
                    UPDATE applications SET renewal_reviewed = 1
                    WHERE organization_id = ? AND id = ?
                    """,
                    (organization_id, app["id"]),
                )
        return cursor.rowcount > 0

    def _is_legacy_organization(self, organization_id: str) -> bool:
        with closing(self._connect()) as connection:
            return organization_id == self._legacy_organization_id(connection)

    def shadow_apps(self, organization_id: str) -> list[dict]:
        if not self._is_legacy_organization(organization_id):
            return []
        return [dict(app) for app in self._shadow_apps]

    def update_shadow_status(self, organization_id: str, app_id: str, status: str) -> bool:
        if not self._is_legacy_organization(organization_id):
            return False
        app = next((item for item in self._shadow_apps if item["id"] == app_id), None)
        if app is None:
            return False
        app["status"] = status
        return True

    def access_users(self, organization_id: str) -> list[dict]:
        if not self._is_legacy_organization(organization_id):
            return []
        return [
            {**user, "assignments": [dict(assignment) for assignment in user["assignments"]]}
            for user in self._access_users
        ]

    def update_access_user(
        self,
        organization_id: str,
        user_id: str,
        *,
        active: bool | None = None,
        reviewed: bool | None = None,
    ) -> bool:
        if not self._is_legacy_organization(organization_id):
            return False
        user = next((item for item in self._access_users if item["id"] == user_id), None)
        if user is None:
            return False
        if active is not None:
            user["active"] = active
        if reviewed is not None:
            user["reviewed"] = reviewed
        return True

    def security_findings(self, organization_id: str) -> list[dict]:
        if not self._is_legacy_organization(organization_id):
            return []
        return [dict(finding) for finding in self._security_findings]

    def resolve_security_finding(self, organization_id: str, finding_id: str) -> bool:
        if not self._is_legacy_organization(organization_id):
            return False
        finding = next((item for item in self._security_findings if item["id"] == finding_id), None)
        if finding is None:
            return False
        finding["status"] = "Resolved"
        return True
