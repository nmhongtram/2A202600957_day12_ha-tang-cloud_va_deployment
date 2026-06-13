"""
Production AI Agent — Kết hợp tất cả Day 12 concepts

Checklist:
  ✅ Config từ environment (12-factor)
  ✅ Structured JSON logging
  ✅ API Key authentication
  ✅ Rate limiting (Redis, 10 req/min per user)
  ✅ Cost guard (Redis, $10/month per user)
  ✅ Conversation history (Redis, stateless)
  ✅ Input validation (Pydantic)
  ✅ Health check + Readiness probe (kiểm tra Redis)
  ✅ Graceful shutdown
  ✅ Security headers
  ✅ CORS
  ✅ Error handling
"""
import os
import time
import signal
import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget, record_usage, get_usage
from app.history import append_message, get_history, clear_history
from app.redis_client import redis_client

# Mock LLM (thay bằng OpenAI/Anthropic khi có API key)
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
# Docker đặt HOSTNAME = container ID — dùng để xem request được Nginx
# load-balance tới instance nào (chứng minh app stateless + scale-out).
INSTANCE_ID = os.getenv("HOSTNAME", "local")
_is_ready = False
_request_count = 0
_error_count = 0

# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "instance": INSTANCE_ID,
    }))
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))

    yield

    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))

# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers.pop("server", None)
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception:
        _error_count += 1
        raise

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000,
                          description="Your question for the agent")
    user_id: str = Field(default="anonymous", min_length=1, max_length=100,
                          description="Dùng để tách rate limit / budget / history theo user")

class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    user_id: str
    timestamp: str
    served_by: str

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "history": "GET /history/{user_id} (requires X-API-Key)",
            "usage": "GET /usage/{user_id} (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    _key: str = Depends(verify_api_key),
):
    """
    Send a question to the AI agent.

    **Authentication:** Include header `X-API-Key: <your-key>`

    State (rate limit, budget, conversation history) sống trong Redis
    theo `user_id` — request có thể được Nginx route tới bất kỳ
    instance nào mà vẫn ra cùng kết quả.
    """
    # Rate limit + budget — theo user_id, dùng chung Redis cho mọi instance
    check_rate_limit(body.user_id)
    check_budget(body.user_id)

    logger.info(json.dumps({
        "event": "agent_call",
        "user_id": body.user_id,
        "q_len": len(body.question),
        "instance": INSTANCE_ID,
    }))

    answer = llm_ask(body.question)

    # Ghi nhận chi phí + lưu lịch sử hội thoại
    input_tokens = len(body.question.split()) * 2
    output_tokens = len(answer.split()) * 2
    record_usage(body.user_id, input_tokens, output_tokens)

    append_message(body.user_id, "user", body.question)
    append_message(body.user_id, "assistant", answer)

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        user_id=body.user_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        served_by=INSTANCE_ID,
    )


@app.get("/history/{user_id}", tags=["Agent"])
def get_conversation_history(user_id: str, _key: str = Depends(verify_api_key)):
    """Đọc lịch sử hội thoại của user_id từ Redis."""
    return {"user_id": user_id, "messages": get_history(user_id)}


@app.delete("/history/{user_id}", tags=["Agent"])
def delete_conversation_history(user_id: str, _key: str = Depends(verify_api_key)):
    """Xoá lịch sử hội thoại của user_id."""
    clear_history(user_id)
    return {"user_id": user_id, "deleted": True}


@app.get("/usage/{user_id}", tags=["Agent"])
def usage(user_id: str, _key: str = Depends(verify_api_key)):
    """Xem chi phí đã dùng trong tháng + budget còn lại của user_id."""
    return get_usage(user_id)


@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe. Platform restarts container if this fails."""
    try:
        redis_client.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "unreachable"

    return {
        "status": "ok" if redis_status == "ok" else "degraded",
        "version": settings.app_version,
        "environment": settings.environment,
        "instance": INSTANCE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": {
            "llm": "mock" if not settings.openai_api_key else "openai",
            "redis": redis_status,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe. Load balancer stops routing here if not ready."""
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    try:
        redis_client.ping()
    except Exception:
        raise HTTPException(503, "Redis not available")
    return {"ready": True, "instance": INSTANCE_ID}


@app.get("/metrics", tags=["Operations"])
def metrics(_key: str = Depends(verify_api_key)):
    """Basic metrics (protected)."""
    return {
        "instance": INSTANCE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
    }


# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum}))

signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    logger.info(f"API Key: {settings.agent_api_key[:4]}****")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
