import os
from datetime import datetime, timedelta
from typing import Optional, Any, Union
from cryptography.fernet import Fernet
import bcrypt
from jose import jwt

# Configuraciones de Seguridad (Deberían estar en .env en Producción)
MASTER_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secreto-cambiar-en-produccion")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 días de sesión

# --- Hashing de Contraseñas (bcrypt directo) ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña en texto plano coincide con el hash almacenado."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def get_password_hash(password: str) -> str:
    """Genera el hash bcrypt de una contraseña."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# --- Bóveda de Encriptación Simétrica (Fernet) ---
def encrypt_api_credential(plain_text: str) -> str:
    """
    Encripta llaves de API (Skydropx, Facturapi, Meta) usando AES-256 (Fernet).
    Nunca deben guardarse en la DB en texto plano.
    """
    f = Fernet(MASTER_KEY.encode())
    return f.encrypt(plain_text.encode()).decode()

def decrypt_api_credential(encrypted_text: str) -> str:
    """Desencripta la llave guardada en la bóveda al momento de usarla."""
    f = Fernet(MASTER_KEY.encode())
    return f.decrypt(encrypted_text.encode()).decode()


# --- Motor de Autenticación (JWT) ---
def create_access_token(
    subject: Union[str, Any],
    workspace_id: int,
    is_admin: bool = False,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Crea el JSON Web Token (JWT).
    REGLA MULTI-TENANT: Inyecta el workspace_id directamente en el payload.
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),       # User ID
        "workspace_id": workspace_id, # Token atado a este espacio de trabajo
        "is_admin": is_admin
    }
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
