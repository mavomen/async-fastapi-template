"""Pydantic schemas for notification preferences and the in-app inbox."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool | None = Field(None, description="Opt in/out of notification emails")
    in_app_enabled: bool | None = Field(
        None, description="Opt in/out of in-app inbox notifications"
    )
    webhook_enabled: bool | None = Field(
        None, description="Opt in/out of webhook deliveries triggered by this user"
    )


class NotificationPreferenceResponse(BaseModel):
    id: int
    user_id: int
    email_enabled: bool
    in_app_enabled: bool
    webhook_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationResponse(BaseModel):
    id: int
    event_type: str
    title: str
    body: str | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int


class NotificationTestRequest(BaseModel):
    title: str = Field("Test notification", min_length=1, max_length=200)
    body: str | None = Field(None, max_length=2000)


class NotificationCreate(BaseModel):
    user_id: int
    event_type: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    body: str | None = Field(None, max_length=2000)
    is_read: bool = False


class NotificationUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    body: str | None = Field(None, max_length=2000)
    is_read: bool | None = None
