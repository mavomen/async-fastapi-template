"""Tests for notification CRUD keyset cursor pagination."""

import pytest

from app.crud.notification import notification as notification_crud
from app.models.user import User


@pytest.mark.asyncio
async def _make_user(db_session, email="ncrud@example.com", username="ncrud-user") -> User:
    user = User(email=email, username=username, hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_cursor_returns_all_newest_first(db_session):
    user = await _make_user(db_session)
    ids = []
    for i in range(5):
        n = await notification_crud.create_for_user(
            db_session, user_id=user.id, event_type="e", title=f"n{i}", body=None
        )
        ids.append(n.id)

    items = await notification_crud.list_for_user_cursor(db_session, user_id=user.id, size=10)
    assert len(items) == 5
    assert [i.id for i in items] == ids[::-1]


@pytest.mark.asyncio
async def test_cursor_walks_pages(db_session):
    user = await _make_user(db_session, email="walk@example.com", username="walk")
    ids = []
    for i in range(3):
        n = await notification_crud.create_for_user(
            db_session, user_id=user.id, event_type="e", title=f"n{i}", body=None
        )
        ids.append(n.id)

    page1 = await notification_crud.list_for_user_cursor(db_session, user_id=user.id, size=2)
    assert len(page1) == 3  # 2 + lookahead
    assert page1[0].id == ids[2]
    assert page1[1].id == ids[1]

    cursor = ids[1]  # last item on page1
    page2 = await notification_crud.list_for_user_cursor(
        db_session, user_id=user.id, cursor=cursor, size=2
    )
    assert len(page2) == 1  # remaining item only
    assert page2[0].id == ids[0]


@pytest.mark.asyncio
async def test_cursor_unread_only(db_session):
    user = await _make_user(db_session, email="unread@example.com", username="unread")
    n1 = await notification_crud.create_for_user(
        db_session, user_id=user.id, event_type="e", title="read", body=None
    )
    n2 = await notification_crud.create_for_user(
        db_session, user_id=user.id, event_type="e", title="unread", body=None
    )
    await notification_crud.mark_read(db_session, notification=n1)

    items = await notification_crud.list_for_user_cursor(
        db_session, user_id=user.id, unread_only=True, size=10
    )
    assert len(items) == 1
    assert items[0].id == n2.id


@pytest.mark.asyncio
async def test_cursor_empty_result(db_session):
    user = await _make_user(db_session, email="empty@example.com", username="empty")
    items = await notification_crud.list_for_user_cursor(db_session, user_id=user.id, size=10)
    assert items == []


@pytest.mark.asyncio
async def test_cursor_scoped_to_user(db_session):
    user_a = await _make_user(db_session, email="a@example.com", username="user-a")
    user_b = await _make_user(db_session, email="b@example.com", username="user-b")
    for uid in (user_a.id, user_b.id):
        await notification_crud.create_for_user(
            db_session, user_id=uid, event_type="e", title="n", body=None
        )
    items_a = await notification_crud.list_for_user_cursor(db_session, user_id=user_a.id, size=10)
    assert len(items_a) == 1
