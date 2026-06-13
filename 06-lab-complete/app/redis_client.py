"""
Shared Redis client — một connection pool cho toàn app.

Mọi state cần chia sẻ giữa các instance (rate limit counters, cost
guard, conversation history) đi qua client này, KHÔNG lưu trong biến
Python toàn cục → app stateless, có thể scale ngang sau Nginx.
"""
import redis

from app.config import settings

redis_client = redis.from_url(settings.redis_url, decode_responses=True)
