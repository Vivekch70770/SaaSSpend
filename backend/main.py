from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator
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

class ApplicationInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=100)
    cost: int = Field(ge=0)
    licenses: int = Field(gt=0)
    active: int = Field(ge=0)
    risk: Literal["Low", "Medium", "High"]
    renewal: date

    @field_validator("name", "category")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value

    @model_validator(mode="after")
    def active_seats_within_licenses(self) -> "ApplicationInput":
        if self.active > self.licenses:
            raise ValueError("Active seats cannot exceed purchased licenses")
        return self

    def record(self) -> dict:
        values = self.model_dump()
        values["renewal"] = self.renewal.isoformat()
        values["annual"] = self.cost * 12
        return values

@app.get("/api/overview")
def overview(): return s.overview(provider.spend_history(), provider.apps())

@app.get("/api/apps")
def apps(): return [s.enrich(a) for a in provider.apps()]

@app.post("/api/apps", status_code=201)
def create_app(application: ApplicationInput):
    try:
        return s.enrich(provider.create_app(application.record()))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

@app.get("/api/apps/{name}")
def app_detail(name: str):
    a = provider.app(name)
    if not a: raise HTTPException(404, "Application not found")
    a = s.enrich(a)
    k = [.7, .72, .75, .8, .8, .84, .88, .9, .9, .95, .98, 1]
    hist = [{"month": m["month"], "cost": round(a["cost"] * f)} for m, f in zip(provider.spend_history(), k)]
    return {**a, "history": hist, "recommendation": s.recommendation(a)}

@app.put("/api/apps/{name}")
def update_app(name: str, application: ApplicationInput):
    try:
        updated = provider.update_app(name, application.record())
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if updated is None:
        raise HTTPException(404, "Application not found")
    return s.enrich(updated)

@app.delete("/api/apps/{name}", status_code=204)
def delete_app(name: str):
    if not provider.delete_app(name):
        raise HTTPException(404, "Application not found")

@app.get("/api/savings")
def savings(): return s.savings_summary(provider.apps())

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
