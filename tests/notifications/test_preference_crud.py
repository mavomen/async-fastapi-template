"""Tests for notification preference CRUD (real Postgres)."""

import pytest
from sqlalchemy import func, select

from app.crud.notification import notification_preference as pref_crud
from app.identity.models.user import User
from app.models.notification_preference import NotificationPreference
from app.schemas.notification import NotificationPreferenceUpdate


@pytest.mark.asyncio
async def test_get_for_user_returns_none_when_missing(db_session):
    assert await pref_crud.get_for_user(db_session, user_id=1) is None


@pytest.mark.asyncio
async def test_get_or_create_creates_defaults_enabled(db_session):
    user = User(
        email="prefs@example.com",
        username="prefs-user",
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.commit()

    pref = await pref_crud.get_or_create(db_session, user_id=user.id)
    assert pref.user_id == user.id
    assert pref.email_enabled is True
    assert pref.in_app_enabled is True
    assert pref.webhook_enabled is True

    again = await pref_crud.get_for_user(db_session, user_id=user.id)
    assert again is not None
    assert again.id == pref.id


@pytest.mark.asyncio
async def test_update_for_user_upserts_and_updates(db_session):
    user = User(
        email="prefs2@example.com",
        username="prefs-user-2",
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.commit()

    pref = await pref_crud.update_for_user(
        db_session,
        user_id=user.id,
        obj_in=NotificationPreferenceUpdate(email_enabled=False),
    )
    assert pref.email_enabled is False
    assert pref.in_app_enabled is True

    pref = await pref_crud.update_for_user(
        db_session,
        user_id=user.id,
        obj_in=NotificationPreferenceUpdate(webhook_enabled=False),
    )
    assert pref.webhook_enabled is False
    assert pref.email_enabled is False


@pytest.mark.asyncio
async def test_update_for_user_empty_payload_is_noop(db_session):
    user = User(
        email="prefs3@example.com",
        username="prefs-user-3",
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.commit()

    pref = await pref_crud.update_for_user(
        db_session, user_id=user.id, obj_in=NotificationPreferenceUpdate()
    )
    assert pref.email_enabled is True

    result = await db_session.execute(select(func.count()).select_from(NotificationPreference))
    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_single_preference_per_user(db_session):
    user = User(
        email="prefs4@example.com",
        username="prefs-user-4",
        hashed_password="hashed",
    )
    db_session.add(user)
    await db_session.commit()

    await pref_crud.get_or_create(db_session, user_id=user.id)
    await pref_crud.get_or_create(db_session, user_id=user.id)

    result = await db_session.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    assert len(result.scalars().all()) == 1
