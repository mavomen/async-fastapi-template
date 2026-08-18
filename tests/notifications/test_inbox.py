"""Tests for in-app notification inbox CRUD (real Postgres)."""

import httpx
import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.crud.notification import notification as notification_crud
from app.crud.user import user as crud_user
from app.main import app
from app.models.notification import Notification
from app.models.user import User
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def _make_user(db_session, email="inbox@example.com", username="inbox-user") -> User:
    user = User(email=email, username=username, hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_create_and_list_for_user(db_session):
    user = await _make_user(db_session)
    await notification_crud.create_for_user(
        db_session, user_id=user.id, event_type="user.created", title="Welcome", body="Hi"
    )
    await notification_crud.create_for_user(
        db_session, user_id=user.id, event_type="user.updated", title="Update", body=None
    )

    items = await notification_crud.list_for_user(db_session, user_id=user.id)
    assert len(items) == 2
    assert items[0].title == "Update"
    assert await notification_crud.count_for_user(db_session, user_id=user.id) == 2
    assert await notification_crud.count_unread(db_session, user_id=user.id) == 2


@pytest.mark.asyncio
async def test_list_filters_unread_and_paginates(db_session):
    user = await _make_user(db_session)
    for i in range(3):
        await notification_crud.create_for_user(
            db_session, user_id=user.id, event_type="e", title=f"n{i}", body=None
        )
    first = await notification_crud.list_for_user(db_session, user_id=user.id, limit=2)
    assert len(first) == 2
    unread = await notification_crud.list_for_user(db_session, user_id=user.id, unread_only=True)
    assert len(unread) == 3


@pytest.mark.asyncio
async def test_get_for_user_enforces_ownership(db_session):
    user_a = await _make_user(db_session, email="a@example.com", username="user-a")
    user_b = await _make_user(db_session, email="b@example.com", username="user-b")
    notification = await notification_crud.create_for_user(
        db_session, user_id=user_a.id, event_type="e", title="secret", body=None
    )

    assert (
        await notification_crud.get_for_user(
            db_session, notification_id=notification.id, user_id=user_a.id
        )
        is not None
    )
    assert (
        await notification_crud.get_for_user(
            db_session, notification_id=notification.id, user_id=user_b.id
        )
        is None
    )


@pytest.mark.asyncio
async def test_mark_read_sets_timestamps(db_session):
    user = await _make_user(db_session)
    notification = await notification_crud.create_for_user(
        db_session, user_id=user.id, event_type="e", title="n", body=None
    )

    marked = await notification_crud.mark_read(db_session, notification=notification)
    assert marked.is_read is True
    assert marked.read_at is not None
    assert await notification_crud.count_unread(db_session, user_id=user.id) == 0

    again = await notification_crud.mark_read(db_session, notification=marked)
    assert again.read_at == marked.read_at


@pytest.mark.asyncio
async def test_mark_all_read_updates_only_owned_unread(db_session):
    user_a = await _make_user(db_session, email="a@example.com", username="user-a")
    user_b = await _make_user(db_session, email="b@example.com", username="user-b")
    for i in range(2):
        await notification_crud.create_for_user(
            db_session, user_id=user_a.id, event_type="e", title=f"a{i}", body=None
        )
    await notification_crud.create_for_user(
        db_session, user_id=user_b.id, event_type="e", title="b", body=None
    )

    updated = await notification_crud.mark_all_read(db_session, user_id=user_a.id)
    assert updated == 2
    assert await notification_crud.count_unread(db_session, user_id=user_a.id) == 0
    assert await notification_crud.count_unread(db_session, user_id=user_b.id) == 1


@pytest.mark.asyncio
async def test_delete_removes_notification(db_session):
    user = await _make_user(db_session)
    notification = await notification_crud.create_for_user(
        db_session, user_id=user.id, event_type="e", title="n", body=None
    )

    await notification_crud.delete(db_session, id=notification.id)

    result = await db_session.execute(
        select(Notification).where(Notification.id == notification.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cursor_endpoint_returns_cursor_envelope(db_session):
    """GET /notifications via async_client returns cursor fields, not total."""
    user_in = UserCreate(
        email="cursor-endpoint@example.com", username="cursor-ep", password="Pass1!"
    )
    user = await crud_user.create(db_session, obj_in=user_in)
    token = create_access_token(subject=user.id)

    for i in range(3):
        await notification_crud.create_for_user(
            db_session, user_id=user.id, event_type="e", title=f"n{i}", body=None
        )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            "/api/v1/notifications",
            params={"size": 2},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "next_cursor" in body
    assert "has_more" in body
    assert "unread_count" in body
    assert "size" in body
    assert "total" not in body
    assert body["size"] == 2
    assert body["has_more"] is True
    assert body["next_cursor"] is not None

    # Walk to next page
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp2 = await client.get(
            "/api/v1/notifications",
            params={"size": 2, "cursor": body["next_cursor"]},
            headers={"Authorization": f"Bearer {token}"},
        )
    body2 = resp2.json()
    assert body2["size"] == 1
    assert body2["has_more"] is False
    assert body2["next_cursor"] is None
