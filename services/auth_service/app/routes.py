from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .jwt_utils import create_access_token, verify_password
from .models import User
from .schemas import LoginRequest, TokenResponse, UserOut

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    token, expires_in = create_access_token(
        subject=str(user.id),
        extra={"email": user.email, "role": user.role, "name": user.name},
    )
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserOut)
def me(x_user_id: str = Header(...), db: Session = Depends(get_db)) -> UserOut:
    user = db.get(User, x_user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return UserOut(id=str(user.id), email=user.email, name=user.name, role=user.role)


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "auth"}
