# Lyftr AI Webhook Service

A production-grade FastAPI webhook service that ingests WhatsApp-like messages with HMAC signature verification, stores them in SQLite, and provides REST APIs for listing, filtering, and analytics.

## Features

- **POST /webhook**: Ingest messages with HMAC-SHA256 signature verification
- **GET /messages**: List and filter messages with pagination
- **GET /stats**: Analytics endpoint with message statistics
- **Health Probes**: `/health/live` and `/health/ready` endpoints
- **Prometheus Metrics**: `/metrics` endpoint for monitoring
- **Structured JSON Logging**: All requests logged in JSON format
- **Simple Home Page**: HTML home page at `/` linking to `/docs`
- **Dockerized (Optional)**: Fully containerized with Docker Compose

## Quick Start

1. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate      # Windows PowerShell: venv\Scripts\Activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create `.env` in the project root and set required variables:**
   ```env
   WEBHOOK_SECRET=your-secret-key-here
   DATABASE_URL=sqlite:///./data/app.db
   LOG_LEVEL=INFO
   ```

4. **Start the service locally with Uvicorn:**
   ```bash
   uvicorn main:app --reload
   ```

5. **Access the service:**
   - Home: http://localhost:8000/
   - API Docs (Swagger UI): http://localhost:8000/docs
   - Health (liveness): http://localhost:8000/health/live
   - Health (readiness): http://localhost:8000/health/ready
   - Metrics: http://localhost:8000/metrics

6. **(Optional) Run via Docker Compose:**
   Requires Docker Desktop.
   ```bash
   docker compose up -d --build
   ```

## API Endpoints

### POST /webhook

Ingest a message with HMAC signature verification.

**Headers:**
- `X-Signature`: HMAC-SHA256 signature of the request body

**Request Body:**
```json
{
  "message_id": "msg_123",
  "from": "+919876543210",
  "to": "+919876543211",
  "ts": "2025-01-15T10:00:00Z",
  "text": "Hello, world!"
}
```

**Response:**
```json
{
  "status": "ok"
}
```

**Example with curl:**
```bash
# Calculate HMAC signature
SECRET="your-secret-key-here"
BODY='{"message_id":"msg_123","from":"+919876543210","to":"+919876543211","ts":"2025-01-15T10:00:00Z","text":"Hello"}'
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

# Send request
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIGNATURE" \
  -d "$BODY"
```

**Status Codes:**
- `200`: Message accepted (created or duplicate)
- `401`: Invalid or missing signature
- `422`: Validation error

### GET /messages

List and filter messages with pagination.

**Query Parameters:**
- `limit` (default: 50, min: 1, max: 100): Number of messages to return
- `offset` (default: 0, min: 0): Pagination offset
- `from` (optional): Filter by sender MSISDN (exact match)
- `since` (optional): Filter by timestamp (ISO-8601 UTC, ts >= since)
- `q` (optional): Case-insensitive substring search in text

**Response:**
```json
{
  "data": [
    {
      "message_id": "msg_123",
      "from": "+919876543210",
      "to": "+919876543211",
      "ts": "2025-01-15T10:00:00Z",
      "text": "Hello, world!"
    }
  ],
  "total": 123,
  "limit": 50,
  "offset": 0
}
```

**Examples:**
```bash
# Get first 10 messages
curl "http://localhost:8000/messages?limit=10"

# Filter by sender
curl "http://localhost:8000/messages?from=%2B919876543210"

# Search in text
curl "http://localhost:8000/messages?q=hello"

# Messages since timestamp
curl "http://localhost:8000/messages?since=2025-01-15T00:00:00Z"

# Combined filters with pagination
curl "http://localhost:8000/messages?from=%2B919876543210&limit=20&offset=40"
```

### GET /stats

Get message statistics and analytics.

**Response:**
```json
{
  "total_messages": 123,
  "senders_count": 10,
  "messages_per_sender": [
    {
      "from": "+919876543210",
      "count": 50
    }
  ],
  "first_message_ts": "2025-01-10T09:00:00Z",
  "last_message_ts": "2025-01-15T10:00:00Z"
}
```

**Example:**
```bash
curl http://localhost:8000/stats
```

### GET /health/live

Liveness probe - always returns 200 when the service is running.

**Response:**
```json
{
  "status": "ok"
}
```

### GET /health/ready

Readiness probe - returns 200 if database is reachable and WEBHOOK_SECRET is set, otherwise 503.

**Response:**
```json
{
  "status": "ok"
}
```

### GET /metrics

Prometheus metrics endpoint.

**Example:**
```bash
curl http://localhost:8000/metrics
```

## Design Decisions

### HMAC Signature Verification

The service uses HMAC-SHA256 for webhook signature verification. The signature is computed as:
```
HMAC-SHA256(secret, request_body)
```

The signature is compared using `hmac.compare_digest()` to prevent timing attacks. The raw request body is read before JSON parsing to ensure accurate signature verification.

### Pagination Approach

The `/messages` endpoint uses offset-based pagination with a total count. This approach:
- Provides predictable results with consistent ordering (ts ASC, message_id ASC)
- Allows clients to calculate total pages
- Works well with SQLite's LIMIT/OFFSET
- Returns total count for UI pagination controls

### Stats Computation Strategy

Statistics are computed on-demand using SQL aggregations:
- Total messages: `COUNT(*)`
- Unique senders: `COUNT(DISTINCT from_msisdn)`
- Top 10 senders: `GROUP BY` with `ORDER BY count DESC LIMIT 10`
- First/last timestamps: `MIN(ts)` and `MAX(ts)`

For production with large datasets, consider caching or materialized views.

### Metrics Design

Prometheus metrics include:
- `http_requests_total{path, status}`: Total HTTP requests by path and status
- `webhook_requests_total{result}`: Webhook requests by result (created, duplicate, invalid_signature, validation_error)
- `http_request_latency_seconds{path, method}`: Request latency histogram with standard buckets

Metrics are exposed in Prometheus text format at `/metrics`.

### Database Schema

SQLite is used with the following schema:
```sql
CREATE TABLE messages (
  message_id TEXT PRIMARY KEY,
  from_msisdn TEXT NOT NULL,
  to_msisdn TEXT NOT NULL,
  ts TEXT NOT NULL,
  text TEXT,
  created_at TEXT NOT NULL
);
```

Indexes are created on `ts` and `from_msisdn` for efficient filtering and sorting.

### Idempotency

The webhook endpoint is idempotent - duplicate `message_id` values return 200 but don't create new rows. This is handled using SQLite's PRIMARY KEY constraint with graceful error handling.

### Structured Logging

All logs are emitted as JSON with the following fields:
- `ts`: ISO-8601 UTC timestamp
- `level`: Log level (INFO, ERROR, etc.)
- `request_id`: Unique UUID for each request
- `method`: HTTP method
- `path`: Request path
- `status`: HTTP status code
- `latency_ms`: Request latency in milliseconds
- `message_id`: Message ID (for webhook requests)
- `dup`: Whether message was duplicate (for webhook requests)
- `result`: Request result (for webhook requests)

## Environment Variables

- `DATABASE_URL`: SQLite database URL (default: `sqlite:///data/app.db`)
- `LOG_LEVEL`: Logging level (default: `INFO`)
- `WEBHOOK_SECRET`: Secret key for HMAC signature verification (required)

## Project Structure

```
main.py           # FastAPI app, middleware, routes
models.py         # SQLite initialization
storage.py        # Database operations
logging_utils.py  # JSON logger setup
metrics.py        # Prometheus metrics helpers
config.py         # Environment configuration
data/             # SQLite database files
tests/            # Pytest test suite
  test_webhook.py
  test_messages.py
  test_stats.py
Dockerfile        # Multi-stage Docker build
docker-compose.yml# Docker Compose configuration
Makefile          # Build and run commands
README.md         # This file
.env              # Environment variables (not committed)
requirements.txt  # Python dependencies
```

## Testing

Run tests with:
```bash
make test
```

Or manually:
```bash
python -m pytest tests/ -v
```

## Development Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export WEBHOOK_SECRET=your-secret-key
   export DATABASE_URL=sqlite:///./data/app.db
   export LOG_LEVEL=INFO
   ```

3. **Run locally:**
   ```bash
   uvicorn main:app --reload
   ```

## Setup Used

This project was developed using:
- **VSCode** - Code editor
- **Copilot** - AI pair programming assistant
- **ChatGPT** - AI assistance for design and implementation

## License

This project is part of the Lyftr AI backend assignment.

