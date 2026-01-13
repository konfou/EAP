import json
import time
from typing import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import text

from eap.logging import configure_logging

from .crud import quarantine
from .db import SessionLocal, engine
from .routers import alerts, dq, ingest, metrics
from .settings import settings
from .telemetry import record_request, snapshot

logger = configure_logging(settings.log_level)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_latency_seconds",
    "HTTP request latency in seconds",
    ["path"],
)

app = FastAPI(title="Enterprise Analytics Platform")

app.include_router(ingest.router)
app.include_router(metrics.router)
app.include_router(dq.router)
app.include_router(alerts.router)


@app.middleware("http")
async def telemetry_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    start = time.perf_counter()
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        record_request(status_code, duration_ms)
        REQUEST_COUNT.labels(
            method=request.method, path=request.url.path, status=str(status_code)
        ).inc()
        REQUEST_LATENCY.labels(path=request.url.path).observe(duration_ms / 1000)
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=status_code,
            duration_ms=round(duration_ms, 2),
        )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    body = None
    try:
        raw_body = await request.body()
        if raw_body:
            body = json.loads(raw_body.decode("utf-8"))
    except Exception:
        body = {"raw": "unparseable"}

    payload = {
        "path": request.url.path,
        "errors": jsonable_encoder(exc.errors()),
        "body": body,
    }
    db = None
    try:
        db = SessionLocal()
        with db.begin():
            quarantine(db, reason="validation_error", payload=payload)
    except Exception as error:
        logger.error("quarantine_failed", error=str(error))
    finally:
        if db is not None:
            db.close()

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/ready")
def ready() -> dict[str, bool]:
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:
        logger.error("readiness_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not ready",
        )


@app.get("/metrics", response_model=None)
def metrics_snapshot(request: Request) -> Response | dict[str, float]:
    accept_header = request.headers.get("accept", "")
    if "text/plain" in accept_header:
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    data = snapshot()
    return {
        "total_requests": data.total_requests,
        "total_errors": data.total_errors,
        "avg_latency_ms": round(data.avg_latency_ms, 2),
    }


@app.get("/metrics/prometheus")
def metrics_prometheus() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
