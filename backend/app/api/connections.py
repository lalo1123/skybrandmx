"""API credential management — store encrypted third-party keys."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.deps import get_current_user
from ..models.base import User, ApiCredential
from ..core.security import encrypt_api_credential
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class ConnectionPayload(BaseModel):
    provider: str  # skydropx, facturapi, resend, shopify, meta
    api_key: str
    api_secret: Optional[str] = None


@router.post("/connect")
async def connect_integration(
    payload: ConnectionPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save an API key in the encrypted vault for a specific provider."""
    ws = current_user.workspace_id

    # Check if credential already exists for this provider
    existing = (
        db.query(ApiCredential)
        .filter(ApiCredential.workspace_id == ws, ApiCredential.provider == payload.provider)
        .first()
    )
    if existing:
        existing.encrypted_api_key = encrypt_api_credential(payload.api_key)
        if payload.api_secret:
            existing.encrypted_api_secret = encrypt_api_credential(payload.api_secret)
        db.commit()
        return {"status": "success", "message": f"Credenciales de {payload.provider} actualizadas."}

    new_cred = ApiCredential(
        workspace_id=ws,
        provider=payload.provider,
        encrypted_api_key=encrypt_api_credential(payload.api_key),
        encrypted_api_secret=encrypt_api_credential(payload.api_secret) if payload.api_secret else None,
    )
    db.add(new_cred)
    db.commit()
    return {"status": "success", "message": f"Conectado a {payload.provider} exitosamente."}
