import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints.auth import register
from app.db.database import Base
from app.models.user import User


def build_database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


@pytest.mark.asyncio
async def test_public_register_is_closed_for_staff():
    db = build_database()

    with pytest.raises(HTTPException) as exc:
        await register()

    assert exc.value.status_code == 403
    assert "Aplikasi tertutup" in exc.value.detail


@pytest.mark.asyncio
async def test_public_register_rejects_director_role():
    db = build_database()

    with pytest.raises(HTTPException) as exc:
        await register()

    assert exc.value.status_code == 403
    assert "admin aplikasi" in exc.value.detail
    assert db.query(User).filter(User.email == "director-candidate@example.com").first() is None
