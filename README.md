# Stripe Webhook Payment Processor

A highly resilient, idempotent webhook processing endpoint built with FastAPI to handle incoming Stripe payment events with guaranteed exactly-once semantics.

## Architecture Overview

```
┌─────────────────────┐
│  Stripe API         │
│  (Payment Events)   │
└──────────┬──────────┘
           │ HTTP POST
           ▼
┌─────────────────────────────────────────┐
│  FastAPI Webhook Endpoint               │
│  (/webhooks/stripe/payment)             │
└──────────┬──────────────────────────────┘
           │
      ┌────┴────┐
      ▼         ▼
   Redis     PostgreSQL/SQLite
  (Token     (Event Records)
   Cache)
```

## Key Features

✅ **Idempotency**: Redis-backed event deduplication with 24-hour TTL  
✅ **Exactly-Once Semantics**: Prevents duplicate transaction processing  
✅ **Resilient Error Handling**: Separate exception handling for Redis and database failures  
✅ **HTTP Status Codes**:
- `201 Created`: Event successfully processed
- `200 OK`: Duplicate event (skipped)
- `503 Service Unavailable`: Infrastructure failure (Redis/DB)
- `422 Unprocessable Entity`: Invalid payload

✅ **Secure Logging**: PII-masked logging (event IDs partially redacted)  
✅ **Production-Ready**: Type hints, validation, structured logging, ORM usage  

## File Structure

```
.
├── main.py                 # FastAPI application and startup
├── webhook.py              # Core webhook endpoint logic
├── database.py             # SQLAlchemy ORM models and session
├── config.py               # Configuration management
├── payment.py              # Pydantic validation schemas
├── test_webhook.py         # Comprehensive test suite
├── requirements.txt        # Python dependencies
├── .env.example            # Environment configuration template
└── README.md               # This file
```

## Technical Specifications

### Redis Configuration
- **Purpose**: Event token caching for idempotency
- **Key Format**: `event:{event_id}`
- **TTL**: 24 hours (86400 seconds, configurable via `REDIS_EVENT_TTL`)
- **Data**: Simple flag value (`"1"`)

### Database Schema
```sql
CREATE TABLE payment_events (
    id INTEGER PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    amount FLOAT NOT NULL,
    currency VARCHAR(3) NOT NULL,
    status VARCHAR(50) DEFAULT 'processed',
    created_at DATETIME DEFAULT NOW(),
    processed_at DATETIME DEFAULT NOW()
);

CREATE INDEX idx_event_id ON payment_events(event_id);
CREATE INDEX idx_created_at ON payment_events(created_at);
```

### Payload Schema
```json
{
  "event_id": "evt_12345",
  "type": "payment.succeeded",
  "amount": 5000,
  "currency": "usd"
}
```

**Validation Rules:**
- `event_id`: 1-255 characters, alphanumeric + underscores
- `type`: One of `payment.succeeded`, `payment.failed`, `payment.pending`
- `amount`: Positive integer (in minor units: cents for USD)
- `currency`: 3-character ISO 4217 code, case-insensitive

### Response Schema
```json
{
  "status": "processed|skipped|error",
  "reason": "Optional explanation",
  "event_id": "evt_12345"
}
```

## Installation & Setup

### Prerequisites
- Python 3.11+
- Redis server
- PostgreSQL/SQLite (configurable)

### 1. Clone & Install Dependencies
```bash
git clone <repository>
cd cog-day-2

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your settings
# For development: SQLite + local Redis
# For production: PostgreSQL + managed Redis
```

### 3. Initialize Database
```bash
python -c "from database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### 4. Run Application
```bash
# Development
python main.py

# Production (with Gunicorn)
gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Usage Examples

### Example 1: First Payment Event
```bash
curl -X POST http://localhost:8000/webhooks/stripe/payment \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_12345",
    "type": "payment.succeeded",
    "amount": 5000,
    "currency": "usd"
  }'

# Response (201 Created)
{
  "status": "processed",
  "reason": "Payment event successfully processed",
  "event_id": "evt_12345"
}
```

### Example 2: Duplicate Event (Idempotency)
```bash
# Same request within 24 hours
curl -X POST http://localhost:8000/webhooks/stripe/payment \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_12345",
    "type": "payment.succeeded",
    "amount": 5000,
    "currency": "usd"
  }'

# Response (200 OK - already processed)
{
  "status": "skipped",
  "reason": "duplicate",
  "event_id": "evt_12345"
}
```

### Example 3: Redis Failure
```bash
# When Redis is unavailable

# Response (503 Service Unavailable)
{
  "detail": "Redis service unavailable"
}
```

## Error Handling

### Exception Hierarchy
```python
┌─ HTTPException (status=422)
│  └─ Pydantic ValidationError
│
┌─ HTTPException (status=503)
│  ├─ RedisError (caught separately)
│  └─ SQLAlchemyError (caught separately)
│
└─ Unexpected Exceptions → 503 Service Unavailable
```

### Logging Examples
```
INFO - Event token stored in Redis with TTL 86400s: evt1****5
INFO - Payment event processed: evt1****5 | type=payment.succeeded | amount=5000usd
ERROR - Redis check failed for event evt1****5: Connection refused
ERROR - Database error processing event evt1****5: Integrity constraint violated
```

**Masked Logging Strategy:**
- Event IDs: Show first 4 + last 4 characters (`evt_12****6789`)
- Other PII: Customer emails, tokens → Never logged
- Sensitive data: Database credentials → Never logged

## Testing

### Run Test Suite
```bash
# All tests
pytest test_webhook.py -v

# Specific test
pytest test_webhook.py::TestWebhookEndpoint::test_idempotency_with_multiple_requests -v

# With coverage
pytest test_webhook.py --cov=webhook --cov=database
```

### Test Coverage
- ✅ Successful payment processing (201)
- ✅ Duplicate event handling (200)
- ✅ Redis failure scenarios (503)
- ✅ Invalid payload validation (422)
- ✅ Idempotency with multiple requests
- ✅ Data type conversions (currency lowercase, amount units)
- ✅ Database persistence
- ✅ Health check endpoint

## Production Deployment

### Environment Variables
```bash
# Production configuration
DATABASE_URL=postgresql://prod_user:secure_pwd@db.prod.example.com/stripe_webhooks
REDIS_URL=redis://:secure_pwd@redis.prod.example.com:6379/0
REDIS_EVENT_TTL=86400
DEBUG=false
LOG_LEVEL=WARNING
```

### Infrastructure Requirements
1. **Database**: PostgreSQL 13+ or SQLite (for low-traffic)
2. **Redis**: Redis 6.0+ with persistence enabled
3. **Load Balancer**: Handle multiple replicas
4. **Monitoring**: Application logs, error tracking (Sentry, CloudWatch)

### Deployment Checklist
- [ ] Database migrations executed
- [ ] Redis persistence enabled
- [ ] Environment variables configured
- [ ] SSL/TLS certificates in place
- [ ] Health check endpoint monitored
- [ ] Error tracking (Sentry/DataDog) integrated
- [ ] Database backups configured
- [ ] Redis backup strategy in place
- [ ] Rate limiting implemented (optional)
- [ ] API authentication/signing verified (Stripe webhook signature)

### Scaling Considerations
- **Stateless**: Multiple instances can run in parallel
- **Redis**: Use Redis Cluster for HA, or managed Redis service
- **Database**: Connection pooling configured via SQLAlchemy
- **Load Balancer**: Route webhook requests to available instances

## Monitoring & Observability

### Key Metrics to Track
1. **Request Rate**: Webhooks received per minute
2. **Processing Latency**: P50, P95, P99 response times
3. **Error Rate**: 503, 422 responses
4. **Duplicate Rate**: Percentage of skipped (duplicate) events
5. **Redis Health**: Connection pool size, latency
6. **Database Health**: Query latency, connection pool usage

### Log Aggregation
```bash
# Example with structured logging
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "webhook",
  "event": "payment_processed",
  "event_id_masked": "evt1****5",
  "type": "payment.succeeded",
  "amount": 5000,
  "currency": "usd"
}
```

## Security Considerations

1. **Webhook Verification** (Add if needed):
   - Implement Stripe signature verification
   - Use webhook signing secrets

2. **Rate Limiting** (Optional):
   - Add per-IP rate limiting
   - Implement backoff strategies

3. **Data Protection**:
   - Never log PII (emails, card numbers)
   - Use environment variables for secrets
   - Enable database encryption at rest

4. **Network**:
   - Deploy behind VPN/firewall
   - Use HTTPS only
   - Restrict webhook source IPs if possible

## Troubleshooting

### Issue: "Redis service unavailable"
**Solution**: Check Redis connection
```bash
redis-cli ping  # Should return PONG
redis-cli INFO  # Check server status
```

### Issue: "Database service unavailable"
**Solution**: Verify database connection
```bash
# Test connection string
sqlalchemy_echo=True python -c "from database import engine; engine.connect()"
```

### Issue: Duplicate events not being skipped
**Solution**: Check Redis TTL
```bash
redis-cli TTL event:evt_12345  # Should show seconds remaining
redis-cli SCAN 0 MATCH "event:*"  # List all event keys
```

### Issue: High error rate
**Solution**: Check logs
```bash
# View recent errors
grep ERROR application.log | tail -20
```

## Contributing

1. Run tests before submitting PRs
2. Maintain test coverage > 85%
3. Follow PEP 8 style guide
4. Document new features/changes
5. Update README if necessary

## License

MIT License - See LICENSE file for details