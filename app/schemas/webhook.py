"""Pydantic schemas for outgoing webhooks."""

from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class WebhookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: AnyHttpUrl = Field(..., description="Target URL receiving the signed POST payload")
    event_types: list[str] | None = Field(
        None,
        description="Event types to subscribe to. Omit or pass null/[] to receive all events.",
    )


class WebhookUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    url: AnyHttpUrl | None = None
    event_types: list[str] | None = Field(
        None,
        description="Event types to subscribe to. Pass null/[] to receive all events.",
    )
    is_active: bool | None = None


class WebhookResponse(BaseModel):
    id: int
    name: str
    url: str
    event_types: list[str] | None
    is_active: bool
    last_delivery_at: datetime | None
    last_status: str | None
    failure_count: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class WebhookCreated(WebhookResponse):
    secret: str = Field(
        ...,
        description="HMAC signing secret. Shown only once at creation — store it safely.",
    )


class WebhookDeliveryResponse(BaseModel):
    id: int
    webhook_id: int
    event_id: str
    event_type: str
    attempt: int
    max_attempts: int
    status: str
    response_status: int | None
    response_body: str | None
    error: str | None
    next_retry_at: datetime | None
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
