# Lab 12 — Complete Production Agent

Kết hợp TẤT CẢ những gì đã học trong 1 project hoàn chỉnh.

## Checklist Deliverable

- [x] Dockerfile (multi-stage, < 500 MB)
- [x] docker-compose.yml (agent + redis + nginx, scale agent ra nhiều replica)
- [x] .dockerignore
- [x] Health check endpoint (`GET /health`, kiểm tra Redis)
- [x] Readiness endpoint (`GET /ready`, kiểm tra Redis)
- [x] API Key authentication
- [x] Rate limiting — 10 req/min per user (Redis sliding window)
- [x] Cost guard — $10/month per user (Redis, theo `user_id`)
- [x] Conversation history per user (Redis)
- [x] Config từ environment variables
- [x] Structured logging (JSON)
- [x] Graceful shutdown
- [x] Stateless — scale ngang được vì state nằm trong Redis
- [x] Public URL ready (Railway / Render config)

---

## Cấu Trúc

```
06-lab-complete/
├── app/
│   ├── main.py         # Entry point — endpoints /ask, /history, /usage, /health, /ready
│   ├── config.py       # 12-factor config
│   ├── auth.py         # API Key auth
│   ├── rate_limiter.py # Rate limiting (Redis sliding window, 10 req/min/user)
│   ├── cost_guard.py   # Budget protection (Redis, $10/month/user)
│   ├── history.py      # Conversation history (Redis list/user)
│   └── redis_client.py # Shared Redis connection
├── utils/
│   └── mock_llm.py     # Mock LLM (không cần API key thật)
├── Dockerfile          # Multi-stage, non-root, HEALTHCHECK
├── docker-compose.yml  # agent (x3) + redis + nginx (LB)
├── nginx.conf           # Reverse proxy / round-robin
├── railway.toml        # Deploy Railway
├── render.yaml         # Deploy Render
├── .env.example        # Template
├── .dockerignore
└── requirements.txt
```

---

## Chạy Local

```bash
# 1. Setup
cp .env.example .env

# 2. Chạy với Docker Compose (3 instance agent phía sau Nginx)
docker compose up --build --scale agent=3

# 3. Test
curl http://localhost/health
curl http://localhost/ready

# 4. Lấy API key từ .env, test endpoint
API_KEY=$(grep AGENT_API_KEY .env | cut -d= -f2)
curl -H "X-API-Key: $API_KEY" \
     -X POST http://localhost/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "What is deployment?", "user_id": "user1"}'

# 5. Xem lịch sử hội thoại + usage của user1
curl -H "X-API-Key: $API_KEY" http://localhost/history/user1
curl -H "X-API-Key: $API_KEY" http://localhost/usage/user1
```

---

## Deploy Railway (< 5 phút)

```bash
# Cài Railway CLI
npm i -g @railway/cli

# Login và deploy
railway login
railway init
railway variables set OPENAI_API_KEY=sk-...
railway variables set AGENT_API_KEY=your-secret-key
railway up

# Nhận public URL!
railway domain
```

---

## Deploy Render

1. Push repo lên GitHub
2. Render Dashboard → New → Blueprint
3. Connect repo → Render đọc `render.yaml`
4. Set secrets: `OPENAI_API_KEY`, `AGENT_API_KEY`
5. Deploy → Nhận URL!

---

## Kiểm Tra Production Readiness

```bash
python check_production_ready.py
```

Script này kiểm tra tất cả items trong checklist và báo cáo những gì còn thiếu.
