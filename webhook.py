"""FastAPI webhook endpoint for processing Stripe payment events."""

import logging
from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from redis import Redis, RedisError

from config import settings
from database import get_db, PaymentEvent
from payment import StripePaymentEventRequest, WebhookResponse

# Configure structured logging
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

# Create router
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Redis connection pool (initialized once at startup)
_redis_client: Redis = None


def get_redis_client() -> Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def mask_sensitive_data(event_id: str) -> str:
    """Mask sensitive event ID for logging (show first 4 and last 4 chars)."""
    if len(event_id) <= 8:
        return "****"
    return f"{event_id[:4]}****{event_id[-4:]}"


def check_event_idempotency(redis_client: Redis, event_id: str) -> bool:
    """
    Check if event has been processed before.
    
    Args:
        redis_client: Redis client instance
        event_id: Event ID to check
        
    Returns:
        True if event already processed, False otherwise
        
    Raises:
        RedisError: If Redis operation fails
    """
    try:
        exists = redis_client.exists(f"event:{event_id}")
        return bool(exists)
    except RedisError as e:
        logger.error(
            f"Redis check failed for event {mask_sensitive_data(event_id)}: {str(e)}"
        )
        raise


def store_event_token(
    redis_client: Redis,
    event_id: str,
    ttl: int = settings.REDIS_EVENT_TTL
) -> None:
    """
    Store event token in Redis with 24-hour TTL.
    
    Args:
        redis_client: Redis client instance
        event_id: Event ID to store
        ttl: Time-to-live in seconds (default: 24 hours)
        
    Raises:
        RedisError: If Redis operation fails
    """
    try:
        redis_client.setex(
            f"event:{event_id}",
            ttl,
            "1"
        )
        logger.info(
            f"Event token stored in Redis with TTL {ttl}s: {mask_sensitive_data(event_id)}"
        )
    except RedisError as e:
        logger.error(
            f"Failed to store event token for {mask_sensitive_data(event_id)}: {str(e)}"
        )
        raise


def process_payment_event(
    db: Session,
    payload: StripePaymentEventRequest
) -> PaymentEvent:
    """
    Process and persist payment event to database.
    
    Args:
        db: SQLAlchemy database session
        payload: Validated payment event payload
        
    Returns:
        Created PaymentEvent instance
        
    Raises:
        SQLAlchemyError: If database operation fails
    """
    try:
        # Create new payment event record
        payment_event = PaymentEvent(
            event_id=payload.event_id,
            event_type=payload.type,
            amount=payload.amount / 100,  # Convert from minor units to major units
            currency=payload.currency,
            status="processed"
        )
        
        db.add(payment_event)
        db.commit()
        db.refresh(payment_event)
        
        logger.info(
            f"Payment event processed: {mask_sensitive_data(payload.event_id)} "
            f"| type={payload.type} | amount={payload.amount}{payload.currency.upper()}"
        )
        
        return payment_event
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Database error processing event {mask_sensitive_data(payload.event_id)}: {str(e)}"
        )
        raise


@router.post(
    "/stripe/payment",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Process Stripe Payment Webhook",
    description="Idempotent endpoint for processing Stripe payment events with Redis deduplication."
)
async def process_stripe_webhook(
    payload: StripePaymentEventRequest,
    db: Session = Depends(get_db),
) -> Tuple[WebhookResponse, int]:
    """
    Process incoming Stripe payment event webhook.
    
    Implements idempotency through Redis event token tracking with 24-hour TTL.
    Returns 200 for duplicate events, 201 for newly processed events.
    Returns 503 on infrastructure failures (Redis or DB).
    
    Args:
        payload: Validated Stripe payment event payload
        db: Database session
        
    Returns:
        WebhookResponse with status and metadata
        
    Raises:
        HTTPException: 503 on Redis/DB errors, 422 on validation failures
    """
    masked_event_id = mask_sensitive_data(payload.event_id)
    
    try:
        # Initialize Redis client
        redis_client = get_redis_client()
        
        # Check for duplicate event (idempotency check)
        try:
            is_duplicate = check_event_idempotency(redis_client, payload.event_id)
            
            if is_duplicate:
                logger.info(
                    f"Duplicate event detected (skipped): {masked_event_id}"
                )
                return (
                    WebhookResponse(
                        status="skipped",
                        reason="duplicate",
                        event_id=payload.event_id
                    ),
                    status.HTTP_200_OK
                )
                
        except RedisError as e:
            logger.error(
                f"Redis infrastructure failure: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis service unavailable"
            )
        
        # Process payment event in database
        try:
            payment_event = process_payment_event(db, payload)
            
        except SQLAlchemyError as e:
            logger.error(
                f"Database infrastructure failure: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable"
            )
        
        # Store event token in Redis (after successful DB write)
        try:
            store_event_token(redis_client, payload.event_id)
            
        except RedisError as e:
            logger.error(
                f"Failed to store event token (non-blocking): {str(e)}"
            )
            # Note: We continue processing even if Redis storage fails,
            # but log the issue for monitoring
        
        # Success response
        return (
            WebhookResponse(
                status="processed",
                reason="Payment event successfully processed",
                event_id=payload.event_id
            ),
            status.HTTP_201_CREATED
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error processing event {masked_event_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal server error"
        )


@router.get("/health", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}
