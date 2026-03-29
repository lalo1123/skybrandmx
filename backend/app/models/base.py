from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

class Workspace(SQLModel, table=True):
    """
    Representa una empresa o cliente (Tenant). 
    Toda la data (pedidos, productos, credenciales) pertenece a un Workspace.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(unique=True, index=True) # Identificador único para la URL o subdominio
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relaciones
    users: List["User"] = Relationship(back_populates="workspace")
    credentials: List["ApiCredential"] = Relationship(back_populates="workspace")

class User(SQLModel, table=True):
    """
    Usuarios del sistema. Pertenecen a un Workspace.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str = Field(default="")
    full_name: Optional[str] = None
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Email verification
    email_verified: bool = Field(default=False)
    email_confirm_token: Optional[str] = Field(default=None)
    email_confirm_expires: Optional[datetime] = Field(default=None)

    # 2FA via email
    twofa_code: Optional[str] = Field(default=None)
    twofa_code_expires: Optional[datetime] = Field(default=None)

    # Multi-tenancy
    workspace_id: int = Field(foreign_key="workspace.id")
    workspace: Workspace = Relationship(back_populates="users")

class ApiCredential(SQLModel, table=True):
    """
    Bóveda encriptada para tokens de terceros. 
    Relacionada directamente al Workspace (Tenant).
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True) # 'skydropx', 'facturapi', 'shopify', 'meta'
    
    # Los tokens deben guardarse encriptados en la base de datos
    encrypted_api_key: str
    encrypted_api_secret: Optional[str] = None
    
    workspace_id: int = Field(foreign_key="workspace.id")
    workspace: Workspace = Relationship(back_populates="credentials")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
