"""Data layer. Replace MockProvider with real API-backed providers later."""
import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

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
    def apps(self) -> list[dict]: ...
    def spend_history(self) -> list[dict]: ...

class MockProvider:
    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()
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

    def _initialize_database(self) -> None:
        with closing(sqlite3.connect(self._database_path)) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    name TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    cost INTEGER NOT NULL,
                    licenses INTEGER NOT NULL,
                    active INTEGER NOT NULL,
                    risk TEXT NOT NULL,
                    renewal TEXT NOT NULL,
                    annual INTEGER NOT NULL
                )
                """
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(applications)").fetchall()
            }
            if "renewal_reviewed" not in columns:
                connection.execute(
                    "ALTER TABLE applications ADD COLUMN renewal_reviewed INTEGER NOT NULL DEFAULT 0"
                )
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                count = connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
                if count == 0:
                    connection.executemany(
                        """
                        INSERT INTO applications
                            (name, category, cost, licenses, active, risk, renewal, annual)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (*app[:6], self._legacy_renewal_date(app[6]), app[7])
                            for app in _APPS
                        ],
                    )
                self._normalize_legacy_renewal_dates(connection)

    @staticmethod
    def _legacy_renewal_date(value: str) -> str:
        today = date.today()
        parsed = datetime.strptime(f"{value} 2000", "%b %d %Y")
        year = today.year
        while True:
            try:
                renewal_date = date(year, parsed.month, parsed.day)
            except ValueError:
                year += 1
                continue
            if renewal_date >= today:
                return renewal_date.isoformat()
            year += 1

    @classmethod
    def _normalize_legacy_renewal_dates(cls, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            "SELECT name, renewal FROM applications WHERE renewal NOT GLOB '????-??-??'"
        ).fetchall()
        for name, renewal in rows:
            try:
                normalized = cls._legacy_renewal_date(renewal)
            except (ValueError, IndexError):
                continue
            connection.execute(
                "UPDATE applications SET renewal = ? WHERE name = ?",
                (normalized, name),
            )

    def apps(self) -> list[dict]:
        with closing(sqlite3.connect(self._database_path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT name, category, cost, licenses, active, risk, renewal, annual
                FROM applications ORDER BY rowid
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def app(self, name: str) -> dict | None:
        with closing(sqlite3.connect(self._database_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT name, category, cost, licenses, active, risk, renewal, annual
                FROM applications WHERE name = ? COLLATE NOCASE
                """,
                (name,),
            ).fetchone()
        return dict(row) if row else None

    def create_app(self, app: dict) -> dict:
        with closing(sqlite3.connect(self._database_path)) as connection:
            connection.row_factory = sqlite3.Row
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute(
                    "SELECT 1 FROM applications WHERE name = ? COLLATE NOCASE",
                    (app["name"],),
                ).fetchone():
                    raise ValueError("An application with this name already exists")
                connection.execute(
                    """
                    INSERT INTO applications
                        (name, category, cost, licenses, active, risk, renewal, annual)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    tuple(app[key] for key in ("name", "category", "cost", "licenses", "active", "risk", "renewal", "annual")),
                )
                row = connection.execute(
                    """
                    SELECT name, category, cost, licenses, active, risk, renewal, annual
                    FROM applications WHERE name = ?
                    """,
                    (app["name"],),
                ).fetchone()
        return dict(row)

    def update_app(self, current_name: str, app: dict) -> dict | None:
        with closing(sqlite3.connect(self._database_path)) as connection:
            connection.row_factory = sqlite3.Row
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT name FROM applications WHERE name = ? COLLATE NOCASE",
                    (current_name,),
                ).fetchone()
                if existing is None:
                    return None
                duplicate = connection.execute(
                    """
                    SELECT 1 FROM applications
                    WHERE name = ? COLLATE NOCASE AND name != ? COLLATE NOCASE
                    """,
                    (app["name"], existing["name"]),
                ).fetchone()
                if duplicate:
                    raise ValueError("An application with this name already exists")
                connection.execute(
                    """
                    UPDATE applications
                    SET name = ?, category = ?, cost = ?, licenses = ?, active = ?,
                        risk = ?, renewal = ?, annual = ?
                    WHERE name = ? COLLATE NOCASE
                    """,
                    (*(
                        app[key]
                        for key in ("name", "category", "cost", "licenses", "active", "risk", "renewal", "annual")
                    ), existing["name"]),
                )
                row = connection.execute(
                    """
                    SELECT name, category, cost, licenses, active, risk, renewal, annual
                    FROM applications WHERE name = ?
                    """,
                    (app["name"],),
                ).fetchone()
        return dict(row)

    def delete_app(self, name: str) -> bool:
        with closing(sqlite3.connect(self._database_path)) as connection:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM applications WHERE name = ? COLLATE NOCASE",
                    (name,),
                )
        return cursor.rowcount > 0

    def spend_history(self) -> list[dict]:
        months = "Nov Dec Jan Feb Mar Apr May Jun Jul Aug Sep Oct".split()
        vals = [22, 24, 26, 25, 28, 31, 33, 35, 37, 39, 41, 42.2]
        return [{"month": m, "lakh": v} for m, v in zip(months, vals)]

    def reclaim_license_seats(self, name: str) -> bool:
        with closing(sqlite3.connect(self._database_path)) as connection:
            with connection:
                app = connection.execute(
                    """
                    SELECT name, cost, licenses, active
                    FROM applications
                    WHERE name = ? COLLATE NOCASE
                    """,
                    (name,),
                ).fetchone()
                if app is None:
                    return False
                app_name, cost, licenses, active = app
                if licenses == active:
                    return False
                seat_cost = cost / licenses
                updated_cost = round(seat_cost * active)
                connection.execute(
                    """
                    UPDATE applications
                    SET cost = ?, licenses = ?, annual = ?
                    WHERE name = ?
                    """,
                    (updated_cost, active, round(seat_cost * active * 12), app_name),
                )
        return True

    def renewal_reviews(self) -> set[str]:
        with closing(sqlite3.connect(self._database_path)) as connection:
            rows = connection.execute(
                "SELECT name FROM applications WHERE renewal_reviewed = 1"
            ).fetchall()
        return {row[0].lower() for row in rows}

    def review_renewal(self, name: str) -> bool:
        with closing(sqlite3.connect(self._database_path)) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    UPDATE applications SET renewal_reviewed = 1
                    WHERE name = ? COLLATE NOCASE
                    """,
                    (name,),
                )
        return cursor.rowcount > 0

    def shadow_apps(self) -> list[dict]:
        return [dict(app) for app in self._shadow_apps]

    def update_shadow_status(self, app_id: str, status: str) -> bool:
        app = next((item for item in self._shadow_apps if item["id"] == app_id), None)
        if app is None:
            return False
        app["status"] = status
        return True

    def access_users(self) -> list[dict]:
        return [
            {**user, "assignments": [dict(assignment) for assignment in user["assignments"]]}
            for user in self._access_users
        ]

    def update_access_user(self, user_id: str, *, active: bool | None = None, reviewed: bool | None = None) -> bool:
        user = next((item for item in self._access_users if item["id"] == user_id), None)
        if user is None:
            return False
        if active is not None:
            user["active"] = active
        if reviewed is not None:
            user["reviewed"] = reviewed
        return True

    def security_findings(self) -> list[dict]:
        return [dict(finding) for finding in self._security_findings]

    def resolve_security_finding(self, finding_id: str) -> bool:
        finding = next((item for item in self._security_findings if item["id"] == finding_id), None)
        if finding is None:
            return False
        finding["status"] = "Resolved"
        return True
