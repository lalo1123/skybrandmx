from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.session import get_db # Placeholder, assuming it exists or creating it
from ..models.models import User, CredentialVault, IntegrationProvider
from ..schemas.schemas import ConnectionPayload, GenericResponse
from ..core.security import encrypt_key

router = APIRouter()

@router.post("/connect", response_model=GenericResponse)
async def connect_integration(
    payload: ConnectionPayload,
    current_user_id: int = 1, # TODO: Use real Auth
    db: Session = Depends(get_db)
):
    """
    Saves an API Key in the encrypted vault for a specific provider (SAT, DHL, Meta).
    The Orquestador will use these credentials in background tasks.
    """
    # 1. Verify provider exists in catalog
    provider = db.query(IntegrationProvider).filter(IntegrationProvider.slug == payload.provider_slug).first()
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider {payload.provider_slug} not supported.")
    
    # 2. Encrypt sensitive data
    encrypted_key = encrypt_key(payload.api_key)
    encrypted_secret = encrypt_key(payload.api_secret) if payload.api_secret else None
    
    # 3. Store in the Vault
    new_vault_entry = CredentialVault(
        user_id=current_user_id,
        provider_id=provider.id,
        encrypted_key=encrypted_key,
        encrypted_secret=encrypted_secret,
        is_valid=True
    )
    
    db.add(new_vault_entry)
    db.commit()
    
    return {
        "status": "success",
        "message": f"Successfully connected to {provider.name}. Your credentials are encrypted and secure."
    }
