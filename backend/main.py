from datetime import date
import os
import uuid
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator
from data import DEFAULT_DATABASE_PATH, MockProvider
import assistant as assistant_service
import services as s
from auth import AuthenticatedUser, require_authenticated_user

app = FastAPI(title="SaaSSpend API")

development_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
]
configured_origins = os.getenv("SAASSPEND_CORS_ORIGINS")
allowed_origins = (
    [origin.strip().rstrip("/") for origin in configured_origins.split(",") if origin.strip()]
    if configured_origins
    else development_origins
)
if not allowed_origins or "*" in allowed_origins:
    raise RuntimeError("SAASSPEND_CORS_ORIGINS must contain explicit origins")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Organization-ID"],
)

_provider: MockProvider | None = None
router = APIRouter(prefix="/api", dependencies=[Depends(require_authenticated_user)])


@dataclass(frozen=True)
class TenantContext:
    user_id: str
    organization_id: str
    role: str
    provider: MockProvider


def get_provider() -> MockProvider:
    global _provider
    if _provider is None:
        database_path = os.getenv("SAASSPEND_DATABASE_PATH", str(DEFAULT_DATABASE_PATH))
        _provider = MockProvider(database_path)
    return _provider


def require_tenant(
    organization_id: str | None = Header(default=None, alias="X-Organization-ID"),
    user: AuthenticatedUser = Depends(require_authenticated_user),
    current_provider: MockProvider = Depends(get_provider),
) -> TenantContext:
    if not organization_id:
        raise HTTPException(status_code=400, detail="Organization selection required")
    try:
        organization_id = str(uuid.UUID(organization_id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid organization selection") from error
    role = current_provider.membership_role(organization_id, user.user_id.lower())
    if role is None:
        raise HTTPException(status_code=403, detail="Organization access denied")
    return TenantContext(user.user_id, organization_id, role, current_provider)


ROLE_LEVEL = {"viewer": 0, "editor": 1, "admin": 2, "owner": 3}


def require_role(required_role: str):
    def dependency(context: TenantContext = Depends(require_tenant)) -> TenantContext:
        if ROLE_LEVEL.get(context.role, -1) < ROLE_LEVEL[required_role]:
            raise HTTPException(status_code=403, detail="Insufficient organization role")
        return context

    return dependency


class ShadowStatus(BaseModel):
    status: Literal["Approved", "Dismissed"]


class OrganizationInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_required_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Organization name cannot be blank")
        return value


class AssistantMessage(BaseModel):
    message: str = Field(min_length=1, max_length=assistant_service.MAX_MESSAGE_LENGTH)

    @field_validator("message")
    @classmethod
    def require_nonblank_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value

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

@router.get("/organizations")
def organizations(
    user: AuthenticatedUser = Depends(require_authenticated_user),
    current_provider: MockProvider = Depends(get_provider),
):
    return current_provider.organizations_for_user(user.user_id.lower())


@router.post("/organizations", status_code=201)
def create_organization(
    organization: OrganizationInput,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    current_provider: MockProvider = Depends(get_provider),
):
    return current_provider.create_organization(organization.name, user.user_id.lower())


@router.get("/overview")
def overview(context: TenantContext = Depends(require_tenant)):
    return s.overview(
        context.provider.spend_history(context.organization_id),
        context.provider.apps(context.organization_id),
    )

@router.get("/apps")
def apps(context: TenantContext = Depends(require_tenant)):
    return [s.enrich(a) for a in context.provider.apps(context.organization_id)]

@router.post("/apps", status_code=201)
def create_app(
    application: ApplicationInput,
    context: TenantContext = Depends(require_role("editor")),
):
    try:
        return s.enrich(context.provider.create_app(context.organization_id, application.record()))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

@router.get("/apps/{name}")
def app_detail(name: str, context: TenantContext = Depends(require_tenant)):
    a = context.provider.app(context.organization_id, name)
    if not a: raise HTTPException(404, "Application not found")
    a = s.enrich(a)
    k = [.7, .72, .75, .8, .8, .84, .88, .9, .9, .95, .98, 1]
    hist = [
        {"month": month["month"], "cost": round(a["cost"] * factor)}
        for month, factor in zip(context.provider.spend_history(context.organization_id), k)
    ]
    return {**a, "history": hist, "recommendation": s.recommendation(a)}

@router.put("/apps/{name}")
def update_app(
    name: str,
    application: ApplicationInput,
    context: TenantContext = Depends(require_role("editor")),
):
    try:
        updated = context.provider.update_app(
            context.organization_id, name, application.record()
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if updated is None:
        raise HTTPException(404, "Application not found")
    return s.enrich(updated)

@router.delete("/apps/{name}", status_code=204)
def delete_app(name: str, context: TenantContext = Depends(require_role("editor"))):
    if not context.provider.delete_app(context.organization_id, name):
        raise HTTPException(404, "Application not found")

@router.get("/savings")
def savings(context: TenantContext = Depends(require_tenant)):
    return s.savings_summary(context.provider.apps(context.organization_id))

@router.get("/licenses")
def licenses(context: TenantContext = Depends(require_tenant)):
    return s.licenses(context.provider.apps(context.organization_id))

@router.post("/licenses/{name}/reclaim")
def reclaim_license_seats(name: str, context: TenantContext = Depends(require_role("editor"))):
    if not context.provider.reclaim_license_seats(context.organization_id, name):
        raise HTTPException(404, "Application not found or no unused seats remain")
    return s.licenses(context.provider.apps(context.organization_id))

@router.get("/renewals")
def renewals(context: TenantContext = Depends(require_tenant)):
    return s.renewals(
        context.provider.apps(context.organization_id),
        context.provider.renewal_reviews(context.organization_id),
    )

@router.post("/renewals/{name}/review")
def review_renewal(name: str, context: TenantContext = Depends(require_role("editor"))):
    if not context.provider.review_renewal(context.organization_id, name):
        raise HTTPException(404, "Application not found")
    return s.renewals(
        context.provider.apps(context.organization_id),
        context.provider.renewal_reviews(context.organization_id),
    )

@router.get("/shadow-it")
def shadow_it(context: TenantContext = Depends(require_tenant)):
    return s.shadow_it(context.provider.shadow_apps(context.organization_id))

@router.patch("/shadow-it/{app_id}")
def update_shadow_status(
    app_id: str,
    update: ShadowStatus,
    context: TenantContext = Depends(require_role("editor")),
):
    if not context.provider.update_shadow_status(
        context.organization_id, app_id, update.status
    ):
        raise HTTPException(404, "Discovered application not found")
    return s.shadow_it(context.provider.shadow_apps(context.organization_id))

@router.get("/access")
def access(context: TenantContext = Depends(require_tenant)):
    return s.access(context.provider.access_users(context.organization_id))

@router.post("/access/{user_id}/review")
def review_access(user_id: str, context: TenantContext = Depends(require_role("editor"))):
    if not context.provider.update_access_user(
        context.organization_id, user_id, reviewed=True
    ):
        raise HTTPException(404, "User not found")
    return s.access(context.provider.access_users(context.organization_id))

@router.post("/access/{user_id}/deactivate")
def deactivate_user(user_id: str, context: TenantContext = Depends(require_role("admin"))):
    if not context.provider.update_access_user(
        context.organization_id, user_id, active=False
    ):
        raise HTTPException(404, "User not found")
    return s.access(context.provider.access_users(context.organization_id))

@router.get("/security")
def security(context: TenantContext = Depends(require_tenant)):
    return s.security(context.provider.security_findings(context.organization_id))

@router.post("/assistant/chat")
def assistant_chat(
    request: AssistantMessage,
    context: TenantContext = Depends(require_tenant),
):
    return assistant_service.answer(
        request.message, context.provider, context.organization_id
    )

@router.post("/security/{finding_id}/resolve")
def resolve_security_finding(
    finding_id: str,
    context: TenantContext = Depends(require_role("editor")),
):
    if not context.provider.resolve_security_finding(
        context.organization_id, finding_id
    ):
        raise HTTPException(404, "Security finding not found")
    return s.security(context.provider.security_findings(context.organization_id))

@router.get("/auth/me")
def authenticated_user():
    return {"authenticated": True}

app.include_router(router)
