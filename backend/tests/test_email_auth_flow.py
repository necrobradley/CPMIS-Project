from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.auth import accept_invitation, login, reset_password, verify_email
from app.core.security import get_password_hash, verify_password
from app.db.database import Base
from app.models.user import User, UserRole
from app.schemas.schemas import EmailTokenRequest, LoginRequest, PasswordTokenRequest
from app.services.email_auth import ACCEPT_INVITATION, RESET_PASSWORD, VERIFY_EMAIL, issue_email_token


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_unverified_required_account_cannot_login_until_email_is_verified():
    db = build_database()
    user = User(
        name="First Owner",
        email="owner@example.com",
        password_hash=get_password_hash("OwnerPassword123"),
        role=UserRole.ADMIN,
        is_active=True,
        email_verification_required=True,
        email_verified_at=None,
    )
    db.add(user)
    db.flush()
    issued = issue_email_token(db, user, VERIFY_EMAIL, ttl=timedelta(hours=24))
    db.commit()

    with pytest.raises(HTTPException) as exc:
        login(LoginRequest(email=user.email, password="OwnerPassword123"), db)
    assert exc.value.status_code == 403

    result = verify_email(EmailTokenRequest(token=issued.token), db)
    assert result["success"] is True
    tokens = login(LoginRequest(email=user.email, password="OwnerPassword123"), db)
    assert tokens.access_token

    with pytest.raises(HTTPException) as reused:
        verify_email(EmailTokenRequest(token=issued.token), db)
    assert reused.value.status_code == 400


def test_invitation_sets_private_password_and_verifies_email_once():
    db = build_database()
    user = User(
        name="Invited Staff",
        email="staff@example.com",
        password_hash=get_password_hash("unusable-random-value"),
        role=UserRole.STAFF,
        is_active=True,
        email_verification_required=True,
        must_set_password=True,
    )
    db.add(user)
    db.flush()
    issued = issue_email_token(db, user, ACCEPT_INVITATION, ttl=timedelta(hours=72))
    db.commit()

    result = accept_invitation(
        PasswordTokenRequest(token=issued.token, password="PrivatePass123"), db,
    )
    db.refresh(user)
    assert result["success"] is True
    assert user.email_verified_at is not None
    assert user.must_set_password is False
    assert verify_password("PrivatePass123", user.password_hash)

    with pytest.raises(HTTPException):
        accept_invitation(PasswordTokenRequest(token=issued.token, password="AnotherPass123"), db)


def test_password_reset_invalidates_auth_version_and_is_single_use():
    db = build_database()
    user = User(
        name="Verified Manager",
        email="manager@example.com",
        password_hash=get_password_hash("OldPassword123"),
        role=UserRole.MANAGER,
        is_active=True,
        email_verification_required=True,
        email_verified_at=datetime.utcnow(),
        auth_version=3,
    )
    db.add(user)
    db.flush()
    issued = issue_email_token(db, user, RESET_PASSWORD, ttl=timedelta(minutes=60))
    db.commit()

    reset_password(PasswordTokenRequest(token=issued.token, password="NewPassword123"), db)
    db.refresh(user)
    assert user.auth_version == 4
    assert verify_password("NewPassword123", user.password_hash)

    with pytest.raises(HTTPException):
        reset_password(PasswordTokenRequest(token=issued.token, password="OtherPassword123"), db)
