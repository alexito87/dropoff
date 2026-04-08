
from datetime import datetime, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User
from app.schemas.auth import LoginRequest, MessageResponse, SignupRequest, TokenResponse
from app.services.email_service import send_verification_email

router = APIRouter()


@router.post("/signup", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> MessageResponse:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email.lower(),
        hashed_password=get_password_hash(payload.password),
    )
    db.add(user)
    db.flush()

    token = EmailVerificationToken(
        user_id=user.id,
        token=uuid.uuid4().hex + uuid.uuid4().hex,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(token)
    db.commit()

    send_verification_email(to_email=user.email, token=token.token)
    return MessageResponse(message="Account created. Check Mailpit for the verification email.")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access_token = create_access_token(user.id)
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/verify-email", response_model=MessageResponse)
def verify_email(token: str = Query(...), db: Session = Depends(get_db)) -> MessageResponse:
    record = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.token == token)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Verification token not found")
    if record.used_at is not None:
        raise HTTPException(status_code=400, detail="Verification token already used")
    if record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification token expired")

    user = db.get(User, record.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.email_verified = True
    record.used_at = datetime.now(timezone.utc)
    db.commit()
    return MessageResponse(message="Email successfully verified")


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    if current_user.email_verified:
        return MessageResponse(message="Email is already verified")

    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == current_user.id,
        EmailVerificationToken.used_at.is_(None)
    ).delete()

    token = EmailVerificationToken(
        user_id=current_user.id,
        token=uuid.uuid4().hex + uuid.uuid4().hex,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(token)
    db.commit()
    send_verification_email(to_email=current_user.email, token=token.token)
    return MessageResponse(message="Verification email sent")
