"""
Conversation history — lưu trong Redis (list per user_id).

Stateless: bất kỳ instance nào sau Nginx cũng đọc được history của
user, vì state không nằm trong process memory của 1 container cụ thể.
"""
import json
import time

from app.redis_client import redis_client

MAX_MESSAGES = 20    # giữ 10 lượt hỏi-đáp gần nhất
TTL_SECONDS = 3600   # hội thoại "nguội" sau 1h thì tự xoá


def _key(user_id: str) -> str:
    return f"history:{user_id}"


def append_message(user_id: str, role: str, content: str) -> None:
    key = _key(user_id)
    entry = json.dumps({"role": role, "content": content, "ts": time.time()})
    redis_client.rpush(key, entry)
    redis_client.ltrim(key, -MAX_MESSAGES, -1)
    redis_client.expire(key, TTL_SECONDS)


def get_history(user_id: str) -> list[dict]:
    return [json.loads(m) for m in redis_client.lrange(_key(user_id), 0, -1)]


def clear_history(user_id: str) -> None:
    redis_client.delete(_key(user_id))
