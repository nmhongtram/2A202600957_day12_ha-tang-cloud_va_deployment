"""
Rate limiting — sliding window, lưu state trong Redis.

Dùng Redis sorted set thay vì in-memory deque: mọi instance phía sau
Nginx đều thấy cùng counter cho 1 user_id, nên giới hạn
"N req/min per user" đúng kể cả khi scale ra nhiều container/worker.
"""
import time

from fastapi import HTTPException

from app.config import settings
from app.redis_client import redis_client


def check_rate_limit(user_id: str) -> None:
    """Raise 429 nếu user_id vượt rate_limit_per_minute trong 60s gần nhất."""
    now = time.time()
    key = f"ratelimit:{user_id}"

    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(key, 0, now - 60)   # bỏ các request cũ hơn 60s
    pipe.zadd(key, {str(now): now})           # ghi request hiện tại
    pipe.zcard(key)                           # đếm số request trong window
    pipe.expire(key, 60)                      # tự dọn key nếu user ngừng gọi
    _, _, count, _ = pipe.execute()

    if count > settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} req/min per user",
            headers={"Retry-After": "60"},
        )
