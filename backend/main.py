from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from data import MockProvider
import services as s

app = FastAPI(title="SaaSSpend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

provider = MockProvider()  # swap for real providers here

class ShadowStatus(BaseModel):
    status: Literal["Approved", "Dismissed"]

@app.get("/api/overview")
def overview(): return s.overview(provider.spend_history())

@app.get("/api/apps")
def apps(): return [s.enrich(a) for a in provider.apps()]

@app.get("/api/apps/{name}")
def app_detail(name: str):
    a = next((x for x in provider.apps() if x["name"].lower() == name.lower()), None)
    if not a: raise HTTPException(404, "Application not found")
    a = s.enrich(a)
    k = [.7, .72, .75, .8, .8, .84, .88, .9, .9, .95, .98, 1]
    hist = [{"month": m["month"], "cost": round(a["cost"] * f)} for m, f in zip(provider.spend_history(), k)]
    return {**a, "history": hist, "recommendation": s.recommendation(a)}

@app.get("/api/savings")
def savings(): return {"monthly": 842600, "annual": 10111200, "spend": 4218400,
                        "waste": s.WASTE, "opportunities": s.savings(provider.apps())}

@app.get("/api/licenses")
def licenses():
    return s.licenses(provider.apps())

@app.post("/api/licenses/{name}/reclaim")
def reclaim_license_seats(name: str):
    if not provider.reclaim_license_seats(name):
        raise HTTPException(404, "Application not found or no unused seats remain")
    return s.licenses(provider.apps())

@app.get("/api/renewals")
def renewals():
    return s.renewals(provider.apps(), provider.renewal_reviews())

@app.post("/api/renewals/{name}/review")
def review_renewal(name: str):
    if not provider.review_renewal(name):
        raise HTTPException(404, "Application not found")
    return s.renewals(provider.apps(), provider.renewal_reviews())

@app.get("/api/shadow-it")
def shadow_it():
    return s.shadow_it(provider.shadow_apps())

@app.patch("/api/shadow-it/{app_id}")
def update_shadow_status(app_id: str, update: ShadowStatus):
    if not provider.update_shadow_status(app_id, update.status):
        raise HTTPException(404, "Discovered application not found")
    return s.shadow_it(provider.shadow_apps())

@app.get("/api/access")
def access():
    return s.access(provider.access_users())

@app.post("/api/access/{user_id}/review")
def review_access(user_id: str):
    if not provider.update_access_user(user_id, reviewed=True):
        raise HTTPException(404, "User not found")
    return s.access(provider.access_users())

@app.post("/api/access/{user_id}/deactivate")
def deactivate_user(user_id: str):
    if not provider.update_access_user(user_id, active=False):
        raise HTTPException(404, "User not found")
    return s.access(provider.access_users())

@app.get("/api/security")
def security():
    return s.security(provider.security_findings())

@app.post("/api/security/{finding_id}/resolve")
def resolve_security_finding(finding_id: str):
    if not provider.resolve_security_finding(finding_id):
        raise HTTPException(404, "Security finding not found")
    return s.security(provider.security_findings())
