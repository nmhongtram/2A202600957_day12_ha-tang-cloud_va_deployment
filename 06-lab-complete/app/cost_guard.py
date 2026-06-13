"""
Cost guard — budget $/tháng cho mỗi user, lưu trong Redis.

Key đổi theo tháng (budget:<user_id>:<YYYY-MM>) nên tự "reset" vào đầu
tháng mới mà không cần job dọn dữ liệu riêng.
"""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import redis_client

# Giá token tham khảo (GPT-4o-mini)
PRICE_PER_1K_INPUT_TOKENS = 0.00015   # $0.15 / 1M input tokens
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006   # $0.60 / 1M output tokens


def _budget_key(user_id: str) -> str:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    return f"budget:{user_id}:{month}"


def check_budget(user_id: str) -> None:
    """Raise 402 nếu user đã dùng hết budget tháng này."""
    spent = float(redis_client.get(_budget_key(user_id)) or 0)
    if spent >= settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "spent_usd": round(spent, 4),
                "budget_usd": settings.monthly_budget_usd,
                "resets_at": "1st of next month (UTC)",
            },
        )


def record_usage(user_id: str, input_tokens: int, output_tokens: int) -> float:
    """Ghi nhận chi phí sau khi gọi LLM, trả về tổng đã dùng trong tháng."""
    cost = (input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS \
        + (output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS

    key = _budget_key(user_id)
    total = redis_client.incrbyfloat(key, cost)
    redis_client.expire(key, 32 * 24 * 3600)  # key sống hết tháng rồi tự hết hạn
    return float(total)


def get_usage(user_id: str) -> dict:
    spent = float(redis_client.get(_budget_key(user_id)) or 0)
    return {
        "user_id": user_id,
        "month": datetime.now(timezone.utc).strftime("%Y-%m"),
        "spent_usd": round(spent, 4),
        "budget_usd": settings.monthly_budget_usd,
        "remaining_usd": round(max(0.0, settings.monthly_budget_usd - spent), 4),
    }
