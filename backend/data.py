"""Data layer. Replace MockProvider with real API-backed providers later."""
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
_KEYS = ("name", "category", "cost", "licenses", "active", "risk", "renewal", "annual")

class Provider(Protocol):
    def apps(self) -> list[dict]: ...
    def spend_history(self) -> list[dict]: ...

class MockProvider:
    def __init__(self) -> None:
        self._apps = list(_APPS)
        self._renewal_reviews: set[str] = set()
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

    def apps(self) -> list[dict]:
        return [dict(zip(_KEYS, app)) for app in self._apps]

    def spend_history(self) -> list[dict]:
        months = "Nov Dec Jan Feb Mar Apr May Jun Jul Aug Sep Oct".split()
        vals = [22, 24, 26, 25, 28, 31, 33, 35, 37, 39, 41, 42.2]
        return [{"month": m, "lakh": v} for m, v in zip(months, vals)]

    def reclaim_license_seats(self, name: str) -> bool:
        app = next((item for item in self._apps if item[0].lower() == name.lower()), None)
        if app is None:
            return False
        name, category, cost, licenses, active, risk, renewal, _ = app
        if licenses == active:
            return False
        seat_cost = cost / licenses
        self._apps[self._apps.index(app)] = (
            name, category, round(seat_cost * active), active, active, risk, renewal, round(seat_cost * active * 12)
        )
        return True

    def renewal_reviews(self) -> set[str]:
        return set(self._renewal_reviews)

    def review_renewal(self, name: str) -> bool:
        if not any(app[0].lower() == name.lower() for app in self._apps):
            return False
        self._renewal_reviews.add(name.lower())
        return True

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
