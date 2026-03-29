import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.core.email import generate_2fa_code, send_2fa_code, send_confirmation_email
from app.core.deps import get_current_user, get_current_admin_user
from app.models.base import User, Workspace

router = APIRouter()


# --- Schemas ---

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    workspace_id: int
    user_id: int


class LoginResponse(BaseModel):
    requires_2fa: bool
    user_id: int
    message: str


class Verify2FARequest(BaseModel):
    user_id: int
    code: str


class ConfirmEmailRequest(BaseModel):
    token: str
    password: str


class AdminCreateUser(BaseModel):
    email: str
    full_name: Optional[str] = None


class UserProfile(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_admin: bool
    workspace_id: int
    email_verified: bool


# --- Endpoints ---

@router.post("/login", response_model=LoginResponse)
def login_step1(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """Step 1: Validate email+password, send 2FA code."""
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not user.hashed_password or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas.",
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="El usuario está inactivo.")

    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Debes confirmar tu email antes de iniciar sesión. Revisa tu bandeja de entrada.")

    # Generate and send 2FA code
    code = generate_2fa_code()
    user.twofa_code = code
    user.twofa_code_expires = datetime.utcnow() + timedelta(minutes=10)
    db.add(user)
    db.commit()

    try:
        send_2fa_code(user.email, code)
    except Exception:
        pass  # Don't block login if email fails, code is in DB

    return LoginResponse(
        requires_2fa=True,
        user_id=user.id,
        message="Código de verificación enviado a tu email.",
    )


@router.post("/verify-2fa", response_model=TokenResponse)
def verify_2fa(
    data: Verify2FARequest,
    db: Session = Depends(get_db),
):
    """Step 2: Verify 2FA code, return JWT."""
    user = db.query(User).filter(User.id == data.user_id).first()

    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado.")

    if not user.twofa_code or not user.twofa_code_expires:
        raise HTTPException(status_code=401, detail="No hay código pendiente. Inicia sesión de nuevo.")

    if datetime.utcnow() > user.twofa_code_expires:
        raise HTTPException(status_code=401, detail="El código ha expirado. Inicia sesión de nuevo.")

    if user.twofa_code != data.code:
        raise HTTPException(status_code=401, detail="Código incorrecto.")

    # Clear 2FA code
    user.twofa_code = None
    user.twofa_code_expires = None
    db.add(user)
    db.commit()

    # Generate JWT
    access_token = create_access_token(
        subject=user.id,
        workspace_id=user.workspace_id,
        is_admin=user.is_admin,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        workspace_id=user.workspace_id,
        user_id=user.id,
    )


@router.post("/confirm-email")
def confirm_email(
    data: ConfirmEmailRequest,
    db: Session = Depends(get_db),
):
    """User sets password from invitation link."""
    user = db.query(User).filter(User.email_confirm_token == data.token).first()

    if not user:
        raise HTTPException(status_code=400, detail="Token de confirmación inválido.")

    if user.email_confirm_expires and datetime.utcnow() > user.email_confirm_expires:
        raise HTTPException(status_code=400, detail="El enlace ha expirado. Pide a tu administrador que reenvíe la invitación.")

    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres.")

    user.hashed_password = get_password_hash(data.password)
    user.email_verified = True
    user.is_active = True
    user.email_confirm_token = None
    user.email_confirm_expires = None
    db.add(user)
    db.commit()

    return {"message": "Cuenta activada correctamente. Ya puedes iniciar sesión."}


@router.get("/me", response_model=UserProfile)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_admin=current_user.is_admin,
        workspace_id=current_user.workspace_id,
        email_verified=current_user.email_verified,
    )


@router.post("/register")
def admin_create_user(
    data: AdminCreateUser,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Admin creates a new user and sends invitation email."""
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con este email.")

    token = str(uuid.uuid4())
    new_user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password="",
        is_active=False,
        is_admin=False,
        email_verified=False,
        email_confirm_token=token,
        email_confirm_expires=datetime.utcnow() + timedelta(hours=48),
        workspace_id=admin.workspace_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    try:
        send_confirmation_email(data.email, data.full_name or data.email, token)
    except Exception as e:
        pass  # User created, email can be resent

    return {
        "message": f"Invitación enviada a {data.email}",
        "user_id": new_user.id,
    }
