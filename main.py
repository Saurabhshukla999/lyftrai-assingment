"""FastAPI application with webhook, messages, stats, and health endpoints."""
import hmac
import hashlib
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, Response, Header, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field, field_validator
import logging

from config import settings
from models import init_db
from storage import Storage
from logging_utils import setup_logging
from metrics import record_http_request, record_webhook_request, get_metrics
import os

# Validate webhook secret at startup (fail fast) - skip in test mode
if not os.getenv("TESTING"):
    settings.validate_webhook_secret()

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# Initialize database
init_db(settings.database_url)
storage = Storage(settings.database_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    logger.info("Starting application")
    yield
    # Shutdown
    logger.info("Shutting down application")


app = FastAPI(
    title="Lyftr AI Webhook Service",
    description="Production-grade webhook service for WhatsApp-like messages",
    lifespan=lifespan,
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to each request."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Logging and metrics middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log requests and record metrics."""
    start_time = time.time()
    # Ensure request_id exists even if previous middleware didn't set it
    try:
        request_id = request.state.request_id
    except AttributeError:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
    
    # Process request
    response = await call_next(request)
    
    # Calculate latency
    latency_ms = (time.time() - start_time) * 1000
    
    # Log request
    log_record = logging.LogRecord(
        name=logger.name,
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    )
    log_record.request_id = request_id
    log_record.method = request.method
    log_record.path = request.url.path
    log_record.status = response.status_code
    log_record.latency_ms = round(latency_ms, 2)
    
    logger.handle(log_record)
    
    # Record metrics
    record_http_request(
        path=request.url.path,
        status=response.status_code,
        method=request.method,
        latency=time.time() - start_time,
    )
    
    return response


# Pydantic models
class WebhookMessage(BaseModel):
    """Webhook message model."""
    message_id: str = Field(..., min_length=1)
    from_msisdn: str
    to_msisdn: str
    ts: str
    text: Optional[str] = Field(None, max_length=4096)
    
    @field_validator("from_msisdn", "to_msisdn")
    @classmethod
    def validate_msisdn(cls, v: str) -> str:
        """Validate E.164 format."""
        if not v.startswith("+"):
            raise ValueError("must start with +")
        if not v[1:].isdigit():
            raise ValueError("must contain only digits after +")
        return v
    
    @field_validator("ts")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Validate ISO-8601 UTC timestamp with Z suffix."""
        if not v.endswith("Z"):
            raise ValueError("must end with Z")
        try:
            from datetime import datetime
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("must be valid ISO-8601 UTC timestamp")
        return v


class WebhookResponse(BaseModel):
    """Webhook response model."""
    status: str = "ok"


class MessagesResponse(BaseModel):
    """Messages list response model."""
    data: list
    total: int
    limit: int
    offset: int


# HMAC signature verification
def verify_signature(secret: str, body_bytes: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = hmac.new(
        secret.encode(),
        body_bytes,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# Routes
@app.get("/", response_class=HTMLResponse)
async def root():
    return """<!DOCTYPE html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>Lyftr AI Webhook Service</title>
  </head>
  <body>
    <h1>Lyftr AI Webhook Service</h1>
    <p>Backend service is running.</p>
    <p>Explore the API docs at <a href=\"/docs\">/docs</a>.</p>
  </body>
</html>"""


@app.post("/webhook", response_model=WebhookResponse)
async def webhook(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
):
    """Ingest webhook messages with HMAC verification."""
    request_id = request.state.request_id
    
    # Get raw body for signature verification (must read before parsing)
    body_bytes = await request.body()
    
    # Verify signature first
    if not x_signature:
        record_webhook_request("invalid_signature")
        log_record = logging.LogRecord(
            name=logger.name,
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="",
            args=(),
            exc_info=None,
        )
        log_record.request_id = request_id
        log_record.method = request.method
        log_record.path = request.url.path
        log_record.status = 401
        log_record.latency_ms = 0
        log_record.result = "invalid_signature"
        logger.handle(log_record)
        
        raise HTTPException(status_code=401, detail="invalid signature")
    
    if not verify_signature(settings.webhook_secret, body_bytes, x_signature):
        record_webhook_request("invalid_signature")
        log_record = logging.LogRecord(
            name=logger.name,
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="",
            args=(),
            exc_info=None,
        )
        log_record.request_id = request_id
        log_record.method = request.method
        log_record.path = request.url.path
        log_record.status = 401
        log_record.latency_ms = 0
        log_record.result = "invalid_signature"
        logger.handle(log_record)
        
        raise HTTPException(status_code=401, detail="invalid signature")
    
    # Parse JSON body
    import json
    try:
        body_dict = json.loads(body_bytes.decode("utf-8"))
        message = WebhookMessage(**body_dict)
    except (json.JSONDecodeError, ValueError) as e:
        record_webhook_request("validation_error")
        log_record = logging.LogRecord(
            name=logger.name,
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="",
            args=(),
            exc_info=None,
        )
        log_record.request_id = request_id
        log_record.method = request.method
        log_record.path = request.url.path
        log_record.status = 422
        log_record.latency_ms = 0
        log_record.result = "validation_error"
        logger.handle(log_record)
        
        raise HTTPException(status_code=422, detail=str(e))
    
    # Insert message (idempotent)
    inserted = storage.insert_message(
        message_id=message.message_id,
        from_msisdn=message.from_msisdn,
        to_msisdn=message.to_msisdn,
        ts=message.ts,
        text=message.text,
    )
    
    result = "created" if inserted else "duplicate"
    record_webhook_request(result)
    
    # Log webhook request
    log_record = logging.LogRecord(
        name=logger.name,
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    )
    log_record.request_id = request_id
    log_record.method = request.method
    log_record.path = request.url.path
    log_record.status = 200
    log_record.latency_ms = 0
    log_record.message_id = message.message_id
    log_record.dup = not inserted
    log_record.result = result
    logger.handle(log_record)
    
    return WebhookResponse(status="ok")


@app.get("/messages", response_model=MessagesResponse)
async def get_messages(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    from_msisdn: Optional[str] = Query(None, alias="from"),
    since: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
):
    """List and filter messages."""
    messages, total = storage.get_messages(
        limit=limit,
        offset=offset,
        from_msisdn=from_msisdn,
        since=since,
        q=q,
    )
    
    return MessagesResponse(
        data=messages,
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/stats")
async def get_stats():
    """Get message statistics."""
    stats = storage.get_stats()
    return stats


@app.get("/health/live")
async def health_live():
    """Liveness probe - always returns 200 when running."""
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    """Readiness probe - returns 200 if DB is reachable and WEBHOOK_SECRET is set."""
    # Check database
    if not storage.check_health():
        return Response(status_code=503, content="Database not ready")
    
    # Check WEBHOOK_SECRET
    if not settings.webhook_secret:
        return Response(status_code=503, content="WEBHOOK_SECRET not set")
    
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=get_metrics(), media_type="text/plain")

