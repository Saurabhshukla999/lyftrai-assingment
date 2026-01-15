"""Prometheus metrics helpers."""
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from typing import Optional

# HTTP request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["path", "status"]
)

# Webhook-specific metrics
webhook_requests_total = Counter(
    "webhook_requests_total",
    "Total number of webhook requests",
    ["result"]  # created, duplicate, invalid_signature, validation_error
)

# Request latency histogram
http_request_latency = Histogram(
    "http_request_latency_seconds",
    "HTTP request latency in seconds",
    ["path", "method"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)


def record_http_request(path: str, status: int, method: str, latency: float) -> None:
    """Record HTTP request metrics."""
    http_requests_total.labels(path=path, status=str(status)).inc()
    http_request_latency.labels(path=path, method=method).observe(latency)


def record_webhook_request(result: str) -> None:
    """Record webhook request result."""
    webhook_requests_total.labels(result=result).inc()


def get_metrics() -> bytes:
    """Get Prometheus metrics in text format."""
    return generate_latest()

