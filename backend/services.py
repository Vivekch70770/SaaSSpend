"""Business logic: utilization, waste, savings. Pure functions over provider data."""
from datetime import date, datetime

OPPORTUNITIES = [  # (type, app, monthly saving, confidence, explanation); None = computed
    ("Unused licenses", "Figma", None, "High", "{idle} of {lic} licenses had no activity in 60 days. ₹{seat:,}/seat × {idle} seats."),
    ("Duplicate software", "Zoom + Meet", 92000, "Medium", "Google Meet, already in Workspace, covers most Zoom meetings. Idle Zoom seats with a 15% buffer."),
    ("Inactive users", "Slack", 64000, "High", "18 accounts inactive for 45+ days at roughly ₹3,467/seat."),
    ("Unused seats", "Notion", 48000, "High", "48 seats unused. 27 reclaimable after keeping a 20-seat buffer."),
]

def enrich(a: dict) -> dict:
    idle = a["licenses"] - a["active"]
    seat = round(a["cost"] / a["licenses"])
    return {**a, "idle": idle, "seat_cost": seat, "utilization": round(a["active"] / a["licenses"] * 100), "savings": idle * seat}

def recommendation(a: dict) -> dict:
    if a["utilization"] >= 75:
        return {"title": "Keep current plan", "text": "Utilization is healthy. No action needed this cycle."}
    return {"title": "Right-size before renewal",
            "text": f"Remove {a['idle']} idle seats and renew at {a['active']} seats before {a['renewal']}."}

WASTE = [{"name": n, "monthly": v} for n, v in [("Unused licenses", 320000), ("Duplicate tools", 210000), ("Upcoming renewals", 180000), ("Inactive users", 130000)]]

def savings(apps: list[dict]) -> list[dict]:
    by = {a["name"]: enrich(a) for a in apps}
    out = []
    for kind, name, amt, conf, why in OPPORTUNITIES:
        a = by[name.split(" + ")[0]]
        amt = amt if amt is not None else a["savings"]
        out.append({"type": kind, "app": name, "monthly": amt, "annual": amt * 12, "confidence": conf,
                    "why": why.format(idle=a["idle"], lic=a["licenses"], seat=a["seat_cost"]),
                    "utilization": a["utilization"], "active": a["active"], "licenses": a["licenses"]})
    return sorted(out, key=lambda o: -o["monthly"])

def overview(history):
    return {
        "kpis": {"spend": 4218400, "spend_delta": 8.2, "savings": 842600, "apps": 34, "renewals": 7, "next_renewal_days": 14},
        "history": history,
        "breakdown": [{"name": n, "lakh": v} for n, v in [("AWS", 8.4), ("Slack", 5.2), ("Microsoft 365", 4.8), ("GitHub", 4.1), ("Figma", 3.2), ("Notion", 2.1), ("Zoom", 1.4), ("Other", 12.6)]],
        "alerts": [
            {"level": "red", "text": "14 unused Figma licenses detected", "to": "/apps/Figma"},
            {"level": "yellow", "text": "Zoom renewal in 14 days", "to": "/apps/Zoom"},
            {"level": "yellow", "text": "New SaaS application detected: Linear", "to": "/savings"},
            {"level": "green", "text": "GitHub license utilization improved by 12%", "to": "/apps/GitHub"}],
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
            "utilization": round(sum(item["assigned"] for item in items) / sum(item["purchased"] for item in items) * 100),
        },
        "items": items,
    }

def renewals(apps: list[dict], reviewed: set[str]) -> dict:
    today = date.today()
    items = []
    for app in apps:
        month, day = app["renewal"].split()
        renewal_date = datetime.strptime(f"{month} {day} {today.year}", "%b %d %Y").date()
        if renewal_date < today:
            renewal_date = renewal_date.replace(year=today.year + 1)
        days_remaining = (renewal_date - today).days
        urgency = "High" if days_remaining <= 14 else "Medium" if days_remaining <= 30 else "Low"
        items.append({
            "name": app["name"], "category": app["category"], "renewal_date": renewal_date.isoformat(),
            "days_remaining": days_remaining, "monthly_cost": app["cost"], "annual_cost": app["annual"],
            "risk": app["risk"], "urgency": urgency,
            "status": "Reviewed" if app["name"].lower() in reviewed else "Needs review",
        })
    items.sort(key=lambda item: item["days_remaining"])
    return {
        "summary": {
            "upcoming": len(items), "due_soon": sum(item["days_remaining"] <= 30 for item in items),
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
