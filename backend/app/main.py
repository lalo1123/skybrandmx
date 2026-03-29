import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import webhooks, inventory, auth, admin, automations, demo

app = FastAPI(
    title="SkyBrandMX SaaS API",
    description="Backend logic for unified CRM, Inventory, and Invoicing.",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4010",
        "http://localhost:4321",
        "https://skybrandmx.com",
        "http://skybrandmx.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(webhooks.router, prefix="/api/v1", tags=["Webhooks"])
app.include_router(inventory.router, prefix="/api/v1", tags=["Inventory"])
app.include_router(automations.router, prefix="/api/v1/automations", tags=["Automations"])
app.include_router(demo.router, prefix="/api/v1/demo", tags=["Demo"])

@app.on_event("startup")
async def startup_event():
    from app.core.database import engine, SessionLocal
    from app.models.base import User, Workspace, ApiCredential
    from app.models.automation import AutomationRule, AutomationLog, AutomationStepLog  # noqa: F401
    from sqlmodel import SQLModel
    # Import actions to register them
    import app.engine.actions  # noqa: F401
    from app.core.security import get_password_hash

    # Create tables
    SQLModel.metadata.create_all(engine)

    db = SessionLocal()
    try:
        workspace = db.query(Workspace).filter(Workspace.slug == "default").first()
        if not workspace:
            workspace = Workspace(name="Default Workspace", slug="default")
            db.add(workspace)
            db.commit()
            db.refresh(workspace)

        admin_email = os.environ.get("ADMIN_EMAIL", "serratos@skybrandmx.com")
        admin_password = os.environ.get("ADMIN_PASSWORD", "skybrandmx")
        admin_user = db.query(User).filter(User.email == admin_email).first()
        if not admin_user:
            admin_user = User(
                email=admin_email,
                hashed_password=get_password_hash(admin_password),
                full_name="Admin SkyBrandMX",
                is_admin=True,
                is_active=True,
                email_verified=True,
                workspace_id=workspace.id,
            )
            db.add(admin_user)
            db.commit()
            print(f"Admin user created: {admin_email}")
    finally:
        db.close()

@app.get("/")
async def root():
    return {
        "app": "SkyBrandMX SaaS API",
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs"
    }
