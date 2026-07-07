"""Test suite for Stripe webhook endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from main import app
from database import Base, get_db, PaymentEvent
from payment import StripePaymentEventRequest

# Create in-memory SQLite database for testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestWebhookEndpoint:
    """Test cases for the Stripe webhook endpoint."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Clean database before each test."""
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @patch("webhook.get_redis_client")
    def test_process_new_payment_event(self, mock_redis):
        """Test processing a new payment event."""
        mock_client = MagicMock()
        mock_client.exists.return_value = False
        mock_redis.return_value = mock_client

        payload = {
            "event_id": "evt_12345",
            "type": "payment.succeeded",
            "amount": 5000,
            "currency": "usd"
        }

        response = client.post("/webhooks/stripe/payment", json=payload)
        
        assert response.status_code == 201
        assert response.json()["status"] == "processed"
        assert response.json()["event_id"] == "evt_12345"
        
        # Verify Redis storage was called
        mock_client.setex.assert_called_once()

    @patch("webhook.get_redis_client")
    def test_duplicate_event_returns_200(self, mock_redis):
        """Test that duplicate events return 200 with skip reason."""
        mock_client = MagicMock()
        mock_client.exists.return_value = True  # Event already processed
        mock_redis.return_value = mock_client

        payload = {
            "event_id": "evt_12345",
            "type": "payment.succeeded",
            "amount": 5000,
            "currency": "usd"
        }

        response = client.post("/webhooks/stripe/payment", json=payload)
        
        assert response.status_code == 200
        assert response.json()["status"] == "skipped"
        assert response.json()["reason"] == "duplicate"

    @patch("webhook.get_redis_client")
    def test_redis_failure_returns_503(self, mock_redis):
        """Test that Redis failures return 503."""
        from redis import RedisError
        
        mock_client = MagicMock()
        mock_client.exists.side_effect = RedisError("Connection failed")
        mock_redis.return_value = mock_client

        payload = {
            "event_id": "evt_12345",
            "type": "payment.succeeded",
            "amount": 5000,
            "currency": "usd"
        }

        response = client.post("/webhooks/stripe/payment", json=payload)
        
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()

    @patch("webhook.get_redis_client")
    def test_invalid_payload_returns_422(self, mock_redis):
        """Test that invalid payloads return 422."""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        # Missing required fields
        payload = {
            "event_id": "evt_12345"
            # Missing: type, amount, currency
        }

        response = client.post("/webhooks/stripe/payment", json=payload)
        
        assert response.status_code == 422

    @patch("webhook.get_redis_client")
    def test_currency_lowercase_conversion(self, mock_redis):
        """Test that currency is converted to lowercase."""
        mock_client = MagicMock()
        mock_client.exists.return_value = False
        mock_redis.return_value = mock_client

        payload = {
            "event_id": "evt_12345",
            "type": "payment.succeeded",
            "amount": 5000,
            "currency": "USD"  # Uppercase
        }

        response = client.post("/webhooks/stripe/payment", json=payload)
        
        assert response.status_code == 201
        
        # Check database
        db = TestingSessionLocal()
        event = db.query(PaymentEvent).filter(
            PaymentEvent.event_id == "evt_12345"
        ).first()
        db.close()
        
        assert event is not None
        assert event.currency == "usd"

    @patch("webhook.get_redis_client")
    def test_amount_conversion_from_minor_units(self, mock_redis):
        """Test that amount is converted from minor units (cents) to major units."""
        mock_client = MagicMock()
        mock_client.exists.return_value = False
        mock_redis.return_value = mock_client

        payload = {
            "event_id": "evt_12345",
            "type": "payment.succeeded",
            "amount": 5000,  # 5000 cents = $50.00
            "currency": "usd"
        }

        response = client.post("/webhooks/stripe/payment", json=payload)
        
        assert response.status_code == 201
        
        # Check database
        db = TestingSessionLocal()
        event = db.query(PaymentEvent).filter(
            PaymentEvent.event_id == "evt_12345"
        ).first()
        db.close()
        
        assert event is not None
        assert event.amount == 50.0  # Converted from cents

    @patch("webhook.get_redis_client")
    def test_payment_event_stored_in_database(self, mock_redis):
        """Test that payment events are properly stored in database."""
        mock_client = MagicMock()
        mock_client.exists.return_value = False
        mock_redis.return_value = mock_client

        payload = {
            "event_id": "evt_test123",
            "type": "payment.succeeded",
            "amount": 10000,
            "currency": "eur"
        }

        response = client.post("/webhooks/stripe/payment", json=payload)
        assert response.status_code == 201

        # Query database
        db = TestingSessionLocal()
        event = db.query(PaymentEvent).filter(
            PaymentEvent.event_id == "evt_test123"
        ).first()
        db.close()

        assert event is not None
        assert event.event_type == "payment.succeeded"
        assert event.amount == 100.0
        assert event.currency == "eur"
        assert event.status == "processed"

    @patch("webhook.get_redis_client")
    def test_idempotency_with_multiple_requests(self, mock_redis):
        """Test idempotency with multiple identical requests."""
        mock_client = MagicMock()
        
        # First request: event doesn't exist
        # Subsequent requests: event exists
        mock_client.exists.side_effect = [False, True, True]
        mock_redis.return_value = mock_client

        payload = {
            "event_id": "evt_idempotent",
            "type": "payment.succeeded",
            "amount": 7500,
            "currency": "gbp"
        }

        # First request should process
        response1 = client.post("/webhooks/stripe/payment", json=payload)
        assert response1.status_code == 201
        assert response1.json()["status"] == "processed"

        # Second request should skip (duplicate)
        response2 = client.post("/webhooks/stripe/payment", json=payload)
        assert response2.status_code == 200
        assert response2.json()["status"] == "skipped"

        # Third request should also skip
        response3 = client.post("/webhooks/stripe/payment", json=payload)
        assert response3.status_code == 200
        assert response3.json()["status"] == "skipped"

        # Only one record should exist in database
        db = TestingSessionLocal()
        events = db.query(PaymentEvent).filter(
            PaymentEvent.event_id == "evt_idempotent"
        ).all()
        db.close()
        
        assert len(events) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
