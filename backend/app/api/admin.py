import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db
from app.core.deps import get_current_admin_user
from app.core.email import send_confirmation_email
from app.models.base import User

router = APIRouter()


class UserListItem(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    email_verified: bool
    created_at: Optional[datetime]


@router.get("/users", response_model=List[UserListItem])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    users = db.query(User).filter(User.workspace_id == admin.workspace_id).all()
    return [
        UserListItem(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            is_admin=u.is_admin,
            email_verified=u.email_verified,
            created_at=u.created_at if hasattr(u, "created_at") else None,
        )
        for u in users
    ]


@router.delete("/users/{user_id}")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    user = db.query(User).filter(
        User.id == user_id,
        User.workspace_id == admin.workspace_id,
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes desactivarte a ti mismo.")

    user.is_active = False
    db.add(user)
    db.commit()

    return {"message": f"Usuario {user.email} desactivado."}


@router.post("/users/{user_id}/resend-invite")
def resend_invite(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    user = db.query(User).filter(
        User.id == user_id,
        User.workspace_id == admin.workspace_id,
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if user.email_verified:
        raise HTTPException(status_code=400, detail="El usuario ya confirmó su email.")

    token = str(uuid.uuid4())
    user.email_confirm_token = token
    user.email_confirm_expires = datetime.utcnow() + timedelta(hours=48)
    db.add(user)
    db.commit()

    try:
        send_confirmation_email(user.email, user.full_name or user.email, token)
    except Exception:
        raise HTTPException(status_code=500, detail="Error al enviar el email.")

    return {"message": f"Invitación reenviada a {user.email}"}
