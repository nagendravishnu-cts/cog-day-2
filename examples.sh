#!/bin/bash
# Example webhook requests using curl

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

API_URL="http://localhost:8000"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Stripe Webhook API Examples${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Health check
echo -e "${YELLOW}1. Health Check${NC}"
echo -e "   ${GREEN}GET${NC} $API_URL/health"
curl -s "$API_URL/health" | jq .
echo ""

# Successful payment event
echo -e "${YELLOW}2. Process New Payment Event (HTTP 201)${NC}"
echo -e "   ${GREEN}POST${NC} $API_URL/webhooks/stripe/payment"
curl -s -X POST "$API_URL/webhooks/stripe/payment" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_success_2024_001",
    "type": "payment.succeeded",
    "amount": 5000,
    "currency": "usd"
  }' | jq .
echo ""

# Duplicate event
echo -e "${YELLOW}3. Process Duplicate Event (HTTP 200 - Skipped)${NC}"
echo -e "   ${GREEN}POST${NC} $API_URL/webhooks/stripe/payment"
echo "   (Same event_id as above)"
curl -s -X POST "$API_URL/webhooks/stripe/payment" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_success_2024_001",
    "type": "payment.succeeded",
    "amount": 5000,
    "currency": "usd"
  }' | jq .
echo ""

# Different currencies
echo -e "${YELLOW}4. Payment in EUR (HTTP 201)${NC}"
echo -e "   ${GREEN}POST${NC} $API_URL/webhooks/stripe/payment"
curl -s -X POST "$API_URL/webhooks/stripe/payment" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_eur_2024_001",
    "type": "payment.succeeded",
    "amount": 15000,
    "currency": "EUR"
  }' | jq .
echo ""

# Failed payment
echo -e "${YELLOW}5. Failed Payment Event (HTTP 201)${NC}"
echo -e "   ${GREEN}POST${NC} $API_URL/webhooks/stripe/payment"
curl -s -X POST "$API_URL/webhooks/stripe/payment" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_failed_2024_001",
    "type": "payment.failed",
    "amount": 2500,
    "currency": "usd"
  }' | jq .
echo ""

# Pending payment
echo -e "${YELLOW}6. Pending Payment Event (HTTP 201)${NC}"
echo -e "   ${GREEN}POST${NC} $API_URL/webhooks/stripe/payment"
curl -s -X POST "$API_URL/webhooks/stripe/payment" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_pending_2024_001",
    "type": "payment.pending",
    "amount": 10000,
    "currency": "gbp"
  }' | jq .
echo ""

# Invalid payload (missing fields)
echo -e "${YELLOW}7. Invalid Payload - Missing Fields (HTTP 422)${NC}"
echo -e "   ${GREEN}POST${NC} $API_URL/webhooks/stripe/payment"
curl -s -X POST "$API_URL/webhooks/stripe/payment" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_invalid_001"
  }' | jq .
echo ""

# Invalid event type
echo -e "${YELLOW}8. Invalid Event Type (HTTP 422)${NC}"
echo -e "   ${GREEN}POST${NC} $API_URL/webhooks/stripe/payment"
curl -s -X POST "$API_URL/webhooks/stripe/payment" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_invalid_002",
    "type": "invalid.event",
    "amount": 5000,
    "currency": "usd"
  }' | jq .
echo ""

# Invalid amount (negative)
echo -e "${YELLOW}9. Invalid Amount - Negative Value (HTTP 422)${NC}"
echo -e "   ${GREEN}POST${NC} $API_URL/webhooks/stripe/payment"
curl -s -X POST "$API_URL/webhooks/stripe/payment" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_invalid_003",
    "type": "payment.succeeded",
    "amount": -5000,
    "currency": "usd"
  }' | jq .
echo ""

# Invalid currency (wrong length)
echo -e "${YELLOW}10. Invalid Currency Code (HTTP 422)${NC}"
echo -e "   ${GREEN}POST${NC} $API_URL/webhooks/stripe/payment"
curl -s -X POST "$API_URL/webhooks/stripe/payment" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "evt_invalid_004",
    "type": "payment.succeeded",
    "amount": 5000,
    "currency": "usdt"
  }' | jq .
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "📝 Notes:"
echo "  • Successful processing returns 201 Created"
echo "  • Duplicate events return 200 OK with status: skipped"
echo "  • Invalid payloads return 422 Unprocessable Entity"
echo "  • Infrastructure errors return 503 Service Unavailable"
echo ""
echo "📚 API Documentation:"
echo "  • OpenAPI Docs: $API_URL/docs"
echo "  • ReDoc: $API_URL/redoc"
echo ""
