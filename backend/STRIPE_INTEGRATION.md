# Stripe Integration + Anonymous Rate Limiting

## Overview

This document describes the complete Stripe payment integration and anonymous user rate limiting implementation for the Overworld platform (STORY-014).

## Features

### 1. Stripe Payment Integration
- **Token Packages**: Pre-defined token packages with volume discounts
- **Checkout Sessions**: Secure Stripe Checkout for payments
- **Webhook Processing**: Automatic token grants after successful payments
- **Idempotent Processing**: Duplicate webhook protection via `stripe_event_id`
- **Audit Trail**: All payments logged in transaction history

### 2. Anonymous Rate Limiting
- **IP-based Limiting**: Track anonymous users by IP address
- **Fingerprint Support**: Optional browser fingerprint for better tracking
- **Redis-backed**: Efficient storage with automatic TTL (24h)
- **Graceful Degradation**: Fails open if Redis is unavailable
- **Rate Limit Headers**: Standard `X-RateLimit-*` headers

## Architecture

### Components

```
app/
├── schemas/
│   └── stripe.py              # Pydantic models for Stripe API
├── services/
│   └── stripe_service.py      # Stripe integration logic
├── middleware/
│   └── rate_limit.py          # Anonymous rate limiting
├── api/v1/routers/
│   └── stripe.py              # Stripe API endpoints
└── core/
    └── config.py              # Stripe settings

tests/
└── test_stripe.py             # Comprehensive test suite
```

### Database Integration

Uses existing models:
- `TokenBalance`: User token balances
- `Transaction`: Immutable audit log with `stripe_event_id` for idempotency
- `TransactionType.PURCHASE`: Payment transactions

## Token Packages

Four pre-defined packages with volume discounts:

| Package ID | Name | Tokens | Price | Savings |
|------------|------|--------|-------|---------|
| `starter` | Starter Pack | 1,000 | $5.00 | 0% |
| `pro` | Pro Pack | 5,000 | $20.00 | 20% |
| `enterprise` | Enterprise Pack | 15,000 | $50.00 | 33% |
| `ultimate` | Ultimate Pack | 50,000 | $150.00 | 40% |

Base rate: ~$0.50 per 1,000 tokens

## API Endpoints

### Public Endpoints

#### `GET /api/v1/stripe/packages`
List all available token packages.

**Response:**
```json
{
  "packages": [
    {
      "id": "starter",
      "name": "Starter Pack",
      "tokens": 1000,
      "price_cents": 500,
      "currency": "usd",
      "popular": false,
      "savings_percent": 0
    }
  ],
  "currency": "usd"
}
```

#### `GET /api/v1/stripe/config`
Get public Stripe configuration (publishable key).

**Response:**
```json
{
  "publishable_key": "pk_live_..."
}
```

### Authenticated Endpoints

#### `POST /api/v1/stripe/checkout`
Create a checkout session for token purchase.

**Request:**
```json
{
  "package_id": "starter",
  "success_url": "https://example.com/payment/success",
  "cancel_url": "https://example.com/payment/cancel"
}
```

**Response:**
```json
{
  "session_id": "cs_test_123456789",
  "checkout_url": "https://checkout.stripe.com/c/pay/...",
  "expires_at": 1704067200
}
```

**Usage Flow:**
1. Frontend calls this endpoint to create checkout session
2. Redirect user to `checkout_url`
3. User completes payment on Stripe
4. Stripe redirects to `success_url` or `cancel_url`
5. Webhook grants tokens automatically

### Webhook Endpoint

#### `POST /api/v1/stripe/webhook`
Handle Stripe webhook events (signature verified).

**Important:** This endpoint is NOT authenticated (called by Stripe servers).
Security is provided by webhook signature verification.

**Supported Events:**
- `checkout.session.completed`: Grant tokens after successful payment
- `payment_intent.succeeded`: Log successful payment
- `payment_intent.payment_failed`: Log failed payment
- `charge.refunded`: Log refund (future: deduct tokens)

## Configuration

### Environment Variables

Add to `.env`:

```bash
# Stripe API Keys
STRIPE_SECRET_KEY=sk_test_...           # Stripe secret key (never expose!)
STRIPE_PUBLISHABLE_KEY=pk_test_...      # Stripe publishable key (safe for frontend)
STRIPE_WEBHOOK_SECRET=whsec_...         # Webhook signing secret

# Rate Limiting
ANONYMOUS_DAILY_LIMIT=3                 # Free map generations per day for anonymous users
```

### Stripe Dashboard Setup

1. **Create Product** (optional - we use dynamic pricing):
   - Go to Products → Create Product
   - Name: "Overworld Tokens"
   - Description: "Tokens for map generation"

2. **Set up Webhook**:
   - Go to Developers → Webhooks → Add endpoint
   - URL: `https://your-domain.com/api/v1/stripe/webhook`
   - Events to send:
     - `checkout.session.completed`
     - `payment_intent.succeeded`
     - `payment_intent.payment_failed`
     - `charge.refunded`
   - Copy webhook signing secret to `STRIPE_WEBHOOK_SECRET`

3. **Get API Keys**:
   - Go to Developers → API keys
   - Copy "Publishable key" to `STRIPE_PUBLISHABLE_KEY`
   - Copy "Secret key" to `STRIPE_SECRET_KEY`

## Rate Limiting

### Usage

#### In Routes (Dependency)

```python
from app.middleware.rate_limit import check_anonymous_rate_limit

@router.post("/generate")
async def generate_map(
    current_user: Optional[User] = Depends(get_optional_user),
    rate_limit: dict = Depends(check_anonymous_rate_limit),
):
    # Only rate-limited for anonymous users
    # Authenticated users bypass rate limiting
    ...
```

#### Manual Usage

```python
from app.middleware.rate_limit import AnonymousRateLimiter
from app.core.redis import get_redis

limiter = AnonymousRateLimiter(
    redis_client=await get_redis(),
    limit=3
)

# Check and increment
allowed, current, remaining = await limiter.check_rate_limit(request)
if allowed:
    new_count = await limiter.increment_usage(request)
```

### Rate Limit Response

When limit is exceeded:

**Status Code:** `429 Too Many Requests`

**Headers:**
```
Retry-After: 3600
X-RateLimit-Limit: 3
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1704067200
```

**Body:**
```json
{
  "detail": {
    "error": "rate_limit_exceeded",
    "message": "Anonymous users are limited to 3 map generations per 24h.",
    "limit": 3,
    "window": "24h",
    "retry_after": 3600
  }
}
```

## Testing

### Run Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run Stripe tests
pytest tests/test_stripe.py -v

# Run with coverage
pytest tests/test_stripe.py --cov=app.services.stripe_service --cov=app.middleware.rate_limit
```

### Test Coverage

The test suite covers:
- ✅ Token package definitions and lookup
- ✅ Checkout session creation
- ✅ Webhook signature verification
- ✅ Webhook event processing
- ✅ Idempotent payment handling
- ✅ Rate limit enforcement
- ✅ Client identifier generation
- ✅ Redis unavailability handling
- ✅ Error cases and edge cases

### Manual Testing

#### Test Checkout Flow

1. Start the server:
```bash
uvicorn app.main:app --reload
```

2. Create checkout session:
```bash
curl -X POST http://localhost:8000/api/v1/stripe/checkout \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "package_id": "starter",
    "success_url": "http://localhost:3000/success",
    "cancel_url": "http://localhost:3000/cancel"
  }'
```

3. Test webhook with Stripe CLI:
```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/api/v1/stripe/webhook

# Trigger test webhook
stripe trigger checkout.session.completed
```

#### Test Rate Limiting

```bash
# Make 4 requests to trigger rate limit
for i in {1..4}; do
  curl -X POST http://localhost:8000/api/v1/generation/start
done
```

## Security Considerations

### Webhook Signature Verification

All webhooks are verified using Stripe's signature verification:

```python
event = stripe.Webhook.construct_event(
    payload, signature, webhook_secret
)
```

This prevents:
- ✅ Replay attacks
- ✅ Man-in-the-middle attacks
- ✅ Forged webhook events

### Idempotency

Payment processing is idempotent via `stripe_event_id`:

1. Store `stripe_event_id` in Transaction table (unique constraint)
2. If duplicate event received, database constraint prevents double-grant
3. Return success status (Stripe considers it processed)

### Rate Limit Privacy

Client identifiers are hashed for privacy:

```python
hashed = hashlib.sha256(f"{ip}:{fingerprint}".encode()).hexdigest()
```

Raw IP addresses are never stored in Redis.

## Monitoring and Logging

### Logging

All payment events are logged:

```python
logger.info(f"Checkout session created: {session_id} for user {user_id}")
logger.info(f"Granted {tokens} tokens to user {user_id}. New balance: {balance}")
logger.warning(f"Payment failed: {error}")
```

### Metrics to Monitor

- **Checkout Sessions Created**: Track conversion funnel
- **Webhook Processing Time**: Ensure under 5 seconds
- **Failed Webhooks**: Stripe retries failed webhooks
- **Rate Limit Hits**: Monitor anonymous user abuse
- **Token Grant Failures**: Alert on processing errors

### Stripe Dashboard

Monitor in Stripe Dashboard:
- Payments → Recent payments
- Developers → Webhooks → View logs
- Developers → Events → Filter by type

## Error Handling

### Service Errors

All errors inherit from `StripeServiceError`:

```python
InvalidPackageError         # Invalid package_id
WebhookVerificationError    # Signature verification failed
PaymentProcessingError      # Token grant failed
StripeServiceError          # General Stripe API errors
```

### HTTP Status Codes

- `200 OK`: Success
- `201 Created`: Checkout session created
- `400 Bad Request`: Invalid package or signature
- `404 Not Found`: Package not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Webhook processing failed
- `503 Service Unavailable`: Stripe unavailable

## Future Enhancements

### Phase 2 (Post-MVP)

1. **Subscription Plans**
   - Monthly/yearly token subscriptions
   - Auto-renewal with recurring payments
   - Subscription management UI

2. **Refund Handling**
   - Automatic token deduction on refund
   - Partial refund support
   - Refund reason tracking

3. **Payment Methods**
   - Support for Apple Pay, Google Pay
   - Bank transfers (ACH)
   - Cryptocurrency (if needed)

4. **Advanced Rate Limiting**
   - Per-user rate limits (authenticated users)
   - Dynamic limits based on account age
   - IP reputation scoring
   - CAPTCHA integration for suspicious IPs

5. **Analytics**
   - Revenue analytics dashboard
   - Conversion funnel tracking
   - A/B testing for pricing
   - Customer lifetime value (CLV)

## Troubleshooting

### Webhook Not Receiving Events

1. Check webhook URL is correct in Stripe Dashboard
2. Verify `STRIPE_WEBHOOK_SECRET` is set correctly
3. Check server logs for signature verification errors
4. Use Stripe CLI to test locally: `stripe listen --forward-to ...`

### Tokens Not Granted

1. Check Transaction table for duplicate `stripe_event_id`
2. Verify `payment_status` is "paid" in webhook event
3. Check logs for errors in `process_checkout_completed`
4. Verify user_id and package_id in session metadata

### Rate Limit Not Working

1. Verify Redis is running: `redis-cli ping`
2. Check `REDIS_URL` in settings
3. Verify rate limiter is applied to route
4. Check Redis keys: `redis-cli keys "ratelimit:*"`

### Test Mode vs Production

**Test Mode:**
- Use test API keys (sk_test_... and pk_test_...)
- Test cards: 4242 4242 4242 4242
- No real charges

**Production:**
- Use live API keys (sk_live_... and pk_live_...)
- Real credit cards
- Real charges (be careful!)

## Support

For issues or questions:
1. Check Stripe Dashboard logs
2. Review application logs
3. Test with Stripe CLI
4. Consult Stripe documentation: https://stripe.com/docs

---

**Implementation Date:** January 2025
**Story:** STORY-014
**Version:** 1.0.0
