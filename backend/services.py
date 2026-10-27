"""Business logic: utilization, renewals, and estimated savings."""
from datetime import date, datetime
from urllib.parse import quote

from tenant_migration import normalize_application_name

LOW_UTILIZATION_THRESHOLD = 75
DUE_SOON_DAYS = 30
URGENT_RENEWAL_DAYS = 14

def enrich(a: dict) -> dict:
    licenses = max(0, a["licenses"])
    active = min(max(0, a["active"]), licenses)
    cost = max(0, a["cost"])
    idle = licenses - active
    seat = round(cost / licenses) if licenses else 0
    return {
        **a,
        "idle": idle,
        "seat_cost": seat,
        "utilization": round(active / licenses * 100) if licenses else 0,
        "savings": min(cost, max(0, round(cost * idle / licenses))) if licenses else 0,
    }

def recommendation(a: dict) -> dict:
    if a["utilization"] >= LOW_UTILIZATION_THRESHOLD:
        return {"title": "Keep current plan", "text": "Utilization is healthy. No action needed this cycle."}
    return {"title": "Right-size before renewal",
            "text": f"Remove {a['idle']} idle seats and renew at {a['active']} seats before {a['renewal']}."}

WASTE = [{"name": n, "monthly": v} for n, v in [("Unused licenses", 320000), ("Duplicate tools", 210000), ("Upcoming renewals", 180000), ("Inactive users", 130000)]]

def savings(apps: list[dict]) -> list[dict]:
    opportunities = []
    for app in apps:
        enriched = enrich(app)
        if not enriched["idle"]:
            continue
        monthly = enriched["savings"]
        utilization = enriched["utilization"]
        opportunities.append({
            "type": "Low utilization" if utilization < LOW_UTILIZATION_THRESHOLD else "Unused licenses",
            "app": app["name"],
            "monthly": monthly,
            "estimated_monthly_savings": monthly,
            "annual": monthly * 12,
            "confidence": "Estimate",
            "why": (
                f"{enriched['idle']} of {enriched['licenses']} licenses are unused "
                f"({utilization}% utilization). Estimated at monthly application cost "
                f"divided by purchased licenses, multiplied by unused licenses "
                f"({app['cost']:,} ÷ {enriched['licenses']} × {enriched['idle']}). "
                "Potential only; no savings have been realized."
            ),
            "utilization": utilization,
            "active": enriched["active"],
            "licenses": enriched["licenses"],
            "unused": enriched["idle"],
            "seat_cost": enriched["seat_cost"],
        })
    return sorted(opportunities, key=lambda opportunity: (-opportunity["monthly"], opportunity["app"].lower()))


def savings_summary(apps: list[dict]) -> dict:
    opportunities = savings(apps)
    monthly = sum(opportunity["monthly"] for opportunity in opportunities)
    spend = sum(max(0, app["cost"]) for app in apps)
    return {
        "monthly": monthly,
        "estimated_monthly": monthly,
        "annual": monthly * 12,
        "spend": spend,
        "realized_monthly": 0,
        "waste": [{"name": "Unused license capacity", "monthly": monthly}] if monthly else [],
        "opportunities": opportunities,
        "estimate_basis": (
            "Estimated potential per application = min(monthly cost, round((monthly cost ÷ purchased "
            "licenses) × unused licenses)); unused licenses are max(purchased − active, 0). "
            "Zero-license applications estimate to ₹0. Estimates are potential, not realized savings."
        ),
    }

def overview(history, apps: list[dict] | None = None, today: date | None = None):
    apps = apps or []
    today = today or date.today()
    savings_data = savings_summary(apps)
    renewal_data = renewals(apps, set(), today)
    upcoming = [item for item in renewal_data["items"] if item["days_remaining"] is not None and item["days_remaining"] >= 0]
    breakdown = [
        {"name": app["name"], "lakh": max(0, app["cost"]) / 100000}
        for app in sorted(apps, key=lambda item: -max(0, item["cost"]))[:7]
    ]
    if len(apps) > 7:
        remainder = sorted(apps, key=lambda item: -max(0, item["cost"]))[7:]
        breakdown.append({"name": "Other", "lakh": sum(max(0, item["cost"]) for item in remainder) / 100000})
    spend_delta = 8.2
    if len(history) >= 2 and history[-2]["lakh"]:
        spend_delta = round((history[-1]["lakh"] - history[-2]["lakh"]) / history[-2]["lakh"] * 100, 1)
    alerts = []
    for renewal in renewal_data["items"]:
        if renewal["renewal_status"] == "Overdue":
            alerts.append({
                "level": "red",
                "text": f"{renewal['name']} renewal is overdue",
                "to": "/renewals",
            })
        elif renewal["renewal_status"] == "Due soon":
            alerts.append({
                "level": "yellow",
                "text": f"{renewal['name']} renewal in {renewal['days_remaining']} days",
                "to": "/renewals",
            })
    for opportunity in savings_data["opportunities"]:
        alerts.append({
            "level": "yellow",
            "text": f"{opportunity['unused']} unused licenses at {opportunity['app']}",
            "to": f"/apps/{quote(opportunity['app'])}",
        })
        if len(alerts) >= 4:
            break
    if not alerts:
        alerts.append({"level": "green", "text": "No upcoming renewal or unused-license alerts", "to": "/renewals"})
    return {
        "kpis": {
            "spend": savings_data["spend"],
            "spend_delta": spend_delta,
            "savings": savings_data["monthly"],
            "apps": len(apps),
            "renewals": sum(item["days_remaining"] >= 0 for item in upcoming),
            "next_renewal_days": min((item["days_remaining"] for item in upcoming), default=None),
        },
        "history": history,
        "breakdown": breakdown,
        "alerts": alerts[:4],
    }

def licenses(apps: list[dict]) -> dict:
    items = [
        {**enrich(app), "purchased": app["licenses"], "assigned": app["active"], "unused": app["licenses"] - app["active"]}
        for app in apps
    ]
    return {
        "summary": {
            "purchased": sum(item["purchased"] for item in items),
            "assigned": sum(item["assigned"] for item in items),
            "unused": sum(item["unused"] for item in items),
            "utilization": round(
                sum(item["assigned"] for item in items) / sum(item["purchased"] for item in items) * 100
            ) if items else 0,
        },
        "items": items,
    }

def renewals(apps: list[dict], reviewed: set[str], today: date | None = None) -> dict:
    today = today or date.today()
    items = []
    for app in apps:
        renewal_value = app.get("renewal")
        try:
            if not renewal_value:
                raise ValueError("Renewal date is missing")
            renewal_date = date.fromisoformat(renewal_value)
        except (ValueError, TypeError):
            # Compatibility for providers that still supply a recurring month/day.
            renewal_date = None
            if renewal_value:
                try:
                    month, day = renewal_value.split()
                    parsed = datetime.strptime(f"{month} {day} 2000", "%b %d %Y").date()
                    year = today.year
                    while renewal_date is None:
                        try:
                            candidate = date(year, parsed.month, parsed.day)
                        except ValueError:
                            year += 1
                            continue
                        if candidate >= today:
                            renewal_date = candidate
                        else:
                            year += 1
                except (ValueError, TypeError):
                    renewal_date = None
        days_remaining = (renewal_date - today).days if renewal_date else None
        urgency = "Unknown" if days_remaining is None else (
            "Overdue" if days_remaining < 0
            else "High" if days_remaining <= URGENT_RENEWAL_DAYS
            else "Medium" if days_remaining <= DUE_SOON_DAYS
            else "Low"
        )
        renewal_status = (
            "Unknown" if days_remaining is None
            else "Overdue" if days_remaining < 0
            else "Due soon" if days_remaining <= DUE_SOON_DAYS
            else "Upcoming"
        )
        items.append({
            "name": app["name"], "category": app["category"],
            "renewal_date": renewal_date.isoformat() if renewal_date else None,
            "days_remaining": days_remaining, "monthly_cost": app["cost"], "annual_cost": app["annual"],
            "risk": app["risk"], "urgency": urgency,
            "renewal_status": renewal_status,
            "status": (
                "Reviewed"
                if normalize_application_name(app["name"]) in reviewed
                else "Needs review"
            ),
        })
    items.sort(key=lambda item: (
        item["days_remaining"] is None,
        item["days_remaining"] if item["days_remaining"] is not None else 0,
        item["name"].lower(),
    ))
    return {
        "summary": {
            "upcoming": sum(item["days_remaining"] is not None and item["days_remaining"] >= 0 for item in items),
            "due_soon": sum(item["renewal_status"] == "Due soon" for item in items),
            "overdue": sum(item["renewal_status"] == "Overdue" for item in items),
            "annual_cost": sum(item["annual_cost"] for item in items),
        },
        "items": items,
    }

def shadow_it(apps: list[dict]) -> dict:
    return {
        "summary": {
            "discovered": len(apps),
            "pending": sum(app["status"] == "Pending review" for app in apps),
            "monthly_spend": sum(app["monthly_cost"] for app in apps),
        },
        "items": apps,
    }

def access(users: list[dict]) -> dict:
    for user in users:
        user["assignment_count"] = len(user["assignments"])
        user["excessive_access"] = sum(assignment["role"] == "Admin" for assignment in user["assignments"]) > 1
    return {
        "summary": {
            "users": len(users), "inactive": sum(not user["active"] for user in users),
            "excessive": sum(user["excessive_access"] for user in users),
        },
        "items": users,
    }

def security(findings: list[dict]) -> dict:
    return {
        "summary": {
            "open": sum(finding["status"] == "Open" for finding in findings),
            "high": sum(finding["severity"] == "High" and finding["status"] == "Open" for finding in findings),
        },
        "items": findings,
        "simulated": True,
    }
