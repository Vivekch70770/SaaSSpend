"""Deterministic, read-only answers grounded in current SaaSSpend data."""
from datetime import date
from typing import Protocol

import services

MAX_MESSAGE_LENGTH = 1000
TOP_APPLICATIONS = 5
TOP_LICENSES = 8
MAX_RENEWALS = 10


class AssistantProvider(Protocol):
    def apps(self, organization_id: str) -> list[dict]: ...
    def renewal_reviews(self, organization_id: str) -> set[str]: ...
    def security_findings(self, organization_id: str) -> list[dict]: ...
    def access_users(self, organization_id: str) -> list[dict]: ...


def answer(message: str, provider: AssistantProvider, organization_id: str) -> dict:
    question = message.strip().lower()
    apps = provider.apps(organization_id)
    if not apps:
        return {
            "intent": "no_data",
            "answer": "There are no application records available to analyze yet.",
            "items": [],
        }

    if any(word in question for word in ("security", "finding", "findings", "vulnerability", "vulnerabilities")):
        findings = services.security(provider.security_findings(organization_id))
        items = findings["items"]
        open_count = findings["summary"]["open"]
        high_count = findings["summary"]["high"]
        return {
            "intent": "security",
            "answer": (
                f"There are {open_count} open simulated security findings, including "
                f"{high_count} high-severity findings. These are prototype records, not live scans."
            ),
            "items": [
                {
                    "title": item["title"],
                    "application": item["application"],
                    "severity": item["severity"],
                    "status": item["status"],
                }
                for item in items
            ],
        }

    if any(word in question for word in ("access", "administrator", "admin", "inactive user", "users")):
        access = services.access(provider.access_users(organization_id))
        flagged = [item for item in access["items"] if not item["active"] or item["excessive_access"]]
        return {
            "intent": "access",
            "answer": (
                f"The current directory data contains {access['summary']['users']} users, "
                f"{access['summary']['inactive']} inactive accounts, and "
                f"{access['summary']['excessive']} users flagged for multiple administrator assignments. "
                "These are illustrative provider records, not a live identity-provider sync."
            ),
            "items": [
                {
                    "name": item["name"],
                    "active": item["active"],
                    "excessive_access": item["excessive_access"],
                    "assignments": item["assignment_count"],
                }
                for item in flagged
            ],
        }

    if any(word in question for word in ("saving", "savings", "save", "waste", "overpay")):
        summary = services.savings_summary(apps)
        opportunities = summary["opportunities"]
        answer_text = (
            f"Estimated potential savings are ₹{summary['estimated_monthly']:,} per month "
            f"(₹{summary['annual']:,} annualized). Realized savings tracked: "
            f"₹{summary['realized_monthly']:,} per month. Estimates use the current application records."
        )
        if len(opportunities) > TOP_LICENSES:
            answer_text += f" Showing the top {TOP_LICENSES} opportunities."
        items = [
            {
                "application": item["app"],
                "estimated_monthly_savings": item["estimated_monthly_savings"],
                "annual": item["annual"],
                "utilization": item["utilization"],
                "unused": item["unused"],
                "licenses": item["licenses"],
                "reason": item["why"],
            }
            for item in opportunities[:TOP_LICENSES]
        ]
        return {
            "intent": "savings",
            "answer": answer_text,
            "items": items,
        }

    if any(word in question for word in ("renewal", "renewals", "renew", "due", "overdue")):
        renewal_data = services.renewals(apps, provider.renewal_reviews(organization_id))
        overdue_only = "overdue" in question or "past due" in question
        due_soon_only = "due soon" in question or "due-soon" in question
        if overdue_only:
            selected = [item for item in renewal_data["items"] if item["renewal_status"] == "Overdue"]
            intent = "overdue_renewals"
            heading = f"There are {len(selected)} overdue renewals."
        elif due_soon_only:
            selected = [item for item in renewal_data["items"] if item["renewal_status"] == "Due soon"]
            intent = "due_soon_renewals"
            heading = f"There are {len(selected)} renewals due within {services.DUE_SOON_DAYS} days."
        else:
            selected = [
                item for item in renewal_data["items"]
                if item["renewal_status"] in ("Upcoming", "Due soon")
            ]
            intent = "renewals"
            heading = (
                f"There are {len(selected)} upcoming renewals, including "
                f"{renewal_data['summary']['due_soon']} due within {services.DUE_SOON_DAYS} days."
            )
        items = [
            {
                "application": item["name"],
                "renewal_date": item["renewal_date"],
                "days_remaining": item["days_remaining"],
                "status": item["renewal_status"],
                "monthly_cost": item["monthly_cost"],
            }
            for item in selected[:MAX_RENEWALS]
        ]
        if len(selected) > MAX_RENEWALS:
            heading += f" Showing the first {MAX_RENEWALS} by urgency."
        if not selected:
            heading += " No matching dated renewal records were found."
        return {"intent": intent, "answer": heading, "items": items}

    if any(word in question for word in ("license", "licenses", "seat", "seats", "utilization", "underutilized", "unused")):
        ranked = sorted(
            (services.enrich(app) for app in apps),
            key=lambda app: (-app["idle"], app["utilization"], app["name"].lower()),
        )
        unused_apps = [app for app in ranked if app["idle"] > 0]
        items = [
            {
                "application": app["name"],
                "active": app["active"],
                "licenses": app["licenses"],
                "unused": app["idle"],
                "utilization": app["utilization"],
                "estimated_monthly_savings": app["savings"],
            }
            for app in unused_apps[:TOP_LICENSES]
        ]
        if not items:
            text = "All recorded application licenses are fully utilized."
        else:
            text = (
                f"{len(unused_apps)} applications have unused licenses. "
                f"Estimates are based on the saved license and cost records; showing up to {TOP_LICENSES}."
            )
        return {"intent": "license_utilization", "answer": text, "items": items}

    if any(word in question for word in ("spend", "cost", "expensive", "highest", "most", "application", "applications")):
        ranked = sorted(apps, key=lambda app: (-max(0, app["cost"]), app["name"].lower()))
        items = [
            {
                "application": app["name"],
                "monthly_cost": max(0, app["cost"]),
                "category": app["category"],
            }
            for app in ranked[:TOP_APPLICATIONS]
        ]
        return {
            "intent": "highest_spend",
            "answer": f"Here are the {len(items)} highest monthly application costs from the saved records.",
            "items": items,
        }

    if any(word in question for word in ("summary", "summarize", "overall", "portfolio", "workspace")):
        savings = services.savings_summary(apps)
        renewals = services.renewals(
            apps, provider.renewal_reviews(organization_id), today=date.today()
        )
        licenses = services.licenses(apps)
        return {
            "intent": "summary",
            "answer": (
                f"The saved portfolio has {len(apps)} applications and ₹{savings['spend']:,} in monthly "
                f"subscription cost. Estimated potential savings are ₹{savings['estimated_monthly']:,} per month; "
                f"{licenses['summary']['unused']} licenses are unused. "
                f"There are {renewals['summary']['upcoming']} upcoming and "
                f"{renewals['summary']['overdue']} overdue renewals."
            ),
            "items": [],
        }

    return {
        "intent": "unsupported",
        "answer": (
            "I can answer questions about application spend, license utilization, renewals, potential savings, "
            "access summaries, and the prototype security findings using available SaaSSpend data."
        ),
        "items": [],
    }
