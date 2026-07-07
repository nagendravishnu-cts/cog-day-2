"""Pydantic schemas for payment event validation."""

from typing import Optional, Literal

from pydantic import BaseModel, Field, validator


class StripePaymentEventRequest(BaseModel):
    """Stripe payment event webhook payload schema."""

    event_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique event identifier (e.g., evt_12345)"
    )
    type: Literal["payment.succeeded", "payment.failed", "payment.pending"] = Field(
        ...,
        description="Event type"
    )
    amount: int = Field(
        ...,
        gt=0,
        description="Amount in minor units (e.g., cents for USD)"
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code (e.g., usd)"
    )

    @validator("currency")
    def validate_currency(cls, v):
        """Ensure currency is lowercase."""
        return v.lower()

    class Config:
        schema_extra = {
            "example": {
                "event_id": "evt_12345",
                "type": "payment.succeeded",
                "amount": 5000,
                "currency": "usd"
            }
        }


class WebhookResponse(BaseModel):
    """Webhook processing response schema."""

    status: Literal["processed", "skipped", "error"]
    reason: Optional[str] = None
    event_id: Optional[str] = None

    class Config:
        schema_extra = {
            "examples": [
                {
                    "status": "processed",
                    "reason": "Payment event successfully processed",
                    "event_id": "evt_12345"
                },
                {
                    "status": "skipped",
                    "reason": "duplicate",
                    "event_id": "evt_12345"
                },
                {
                    "status": "error",
                    "reason": "Database connection failed"
                }
            ]
        }
