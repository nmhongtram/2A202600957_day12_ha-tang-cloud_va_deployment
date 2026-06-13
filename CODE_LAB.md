#  Code Lab: Deploy Your AI Agent to Production

> **AICB-P1 · VinUniversity 2026**  
> Thời gian: 3-4 giờ | Độ khó: Intermediate

##  Mục Tiêu

Sau khi hoàn thành lab này, bạn sẽ:
- Hiểu sự khác biệt giữa development và production
- Containerize một AI agent với Docker
- Deploy agent lên cloud platform
- Bảo mật API với authentication và rate limiting
- Thiết kế hệ thống có khả năng scale và reliable

---

##  Yêu Cầu

```bash
 Python 3.11+
 Docker & Docker Compose
 Git
 Text editor (VS Code khuyến nghị)
 Terminal/Command line
```

**Không cần:**
-  OpenAI API key (dùng mock LLM)
-  Credit card
-  Kinh nghiệm DevOps trước đó

---

##  Lộ Trình Lab

| Phần | Thời gian | Nội dung |
|------|-----------|----------|
| **Part 1** | 30 phút | Localhost vs Production |
| **Part 2** | 45 phút | Docker Containerization |
| **Part 3** | 45 phút | Cloud Deployment |
| **Part 4** | 40 phút | API Security |
| **Part 5** | 40 phút | Scaling & Reliability |
| **Part 6** | 60 phút | Final Project |

---

## Part 1: Localhost vs Production (30 phút)

###  Concepts

**Vấn đề:** "It works on my machine" — code chạy tốt trên laptop nhưng fail khi deploy.

**Nguyên nhân:**
- Hardcoded secrets
- Khác biệt về environment (Python version, OS, dependencies)
- Không có health checks
- Config không linh hoạt

**Giải pháp:** 12-Factor App principles

###  Exercise 1.1: Phát hiện anti-patterns

```bash
cd 01-localhost-vs-production/develop
```

**Nhiệm vụ:** Đọc `app.py` và tìm ít nhất 5 vấn đề.

<details>
<summary> Gợi ý</summary>

Tìm:
- API key hardcode
- Port cố định
- Debug mode
- Không có health check
- Không xử lý shutdown

</details>

####  Nhận xét — 6 vấn đề tìm được trong `develop/app.py`

| # | Vấn đề | Vị trí | Tại sao nguy hiểm |
|---|--------|--------|--------------------|
| 1 | **Hardcode API key & DB URL** | `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`, `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"` | Push lên GitHub public là leak secret ngay lập tức; ai cũng dùng được key của bạn |
| 2 | **Không có config management** | `DEBUG = True`, `MAX_TOKENS = 500` cứng trong code | Muốn đổi giá trị giữa dev/staging/prod phải sửa code và build lại image |
| 3 | **`print()` thay vì logging, và log lộ secret** | `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` | Secret bị ghi ra log tập trung (Datadog/Loki...) — ai có quyền đọc log cũng đọc được key |
| 4 | **Không có health check endpoint** | Không có `/health` hoặc `/ready` | Cloud platform (Railway/Render/K8s) không biết agent còn sống để tự restart, hoặc sẵn sàng để route traffic |
| 5 | **Port & host cố định** | `host="localhost"`, `port=8000` | Trên container/cloud, app phải bind `0.0.0.0` và đọc `PORT` từ env do platform inject |
| 6 | **`reload=True` trong production** | `uvicorn.run(..., reload=True)` | Debug reload tốn tài nguyên, tự restart khi file thay đổi — không phù hợp production |

###  Exercise 1.2: Chạy basic version

```bash
pip install -r requirements.txt
python app.py
```

Test:
```bash
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

**Quan sát:** Nó chạy! Nhưng có production-ready không?

####  Nhận xét

Không. App **chạy được trên localhost** nhưng fail ngay khi đưa lên cloud:
- Không thể restart tự động khi crash (không có `/health`)
- Không thể đổi config theo môi trường mà không sửa code (secrets + flags hardcode)
- Log lộ secret ra ngoài
- `host="localhost"` khiến container không nhận được traffic từ bên ngoài (phải là `0.0.0.0`)
- `port=8000` cứng — trên Railway/Render, platform inject `PORT` ngẫu nhiên qua env var

→ Đây chính là khoảng cách "It works on my machine" vs "It works in production".

###  Exercise 1.3: So sánh với advanced version

```bash
cd ../production
cp .env.example .env
pip install -r requirements.txt
python app.py
```

**Nhiệm vụ:** So sánh 2 files `app.py`. Điền vào bảng:

| Feature | Basic | Advanced | Tại sao quan trọng? |
|---------|-------|----------|---------------------|
| Config | Hardcode (`OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG`, `MAX_TOKENS` cứng trong code) | `config.py` — `Settings` dataclass đọc tất cả từ env vars, có `.env.example` làm template, `validate()` fail-fast nếu thiếu config quan trọng ở production | Đổi config giữa dev/staging/prod mà không sửa code/build lại image; secrets không nằm trong git |
| Health check | Không có | `GET /health` (status, uptime, version, timestamp) + `GET /ready` (503 nếu chưa sẵn sàng) | Platform cần biết container "còn sống" để restart, và "sẵn sàng" để load balancer route traffic vào |
| Logging | `print()`, thậm chí in ra cả API key | `logging` + JSON format (`{"time":...,"level":...,"msg":...}`), không log secret | Log JSON dễ parse bởi log aggregator (Datadog/Loki); không leak credentials ra log tập trung |
| Shutdown | Đột ngột — `reload=True`, không có signal handler, `host="localhost"` | `lifespan()` (startup/shutdown) + `signal.signal(SIGTERM, handle_sigterm)`, `is_ready=False` khi shutdown, `host="0.0.0.0"` + `port` từ `PORT` env | Cho phép request đang xử lý hoàn thành trước khi container bị kill; bind đúng địa chỉ để platform route được traffic |

###  Checkpoint 1

- [x] Hiểu tại sao hardcode secrets là nguy hiểm — secret bị lộ khi push code/log, không đổi được giữa các môi trường
- [x] Biết cách dùng environment variables — `os.getenv(...)` + `Settings` dataclass trong `config.py`, nạp từ `.env`
- [x] Hiểu vai trò của health check endpoint — `/health` (liveness, platform restart khi fail) và `/ready` (readiness, load balancer ngừng route khi 503)
- [x] Biết graceful shutdown là gì — bắt `SIGTERM`, đặt `is_ready=False`, chờ request hiện tại xong rồi mới tắt process

---

## Part 2: Docker Containerization (45 phút)

###  Concepts

**Vấn đề:** "Works on my machine" part 2 — Python version khác, dependencies conflict.

**Giải pháp:** Docker — đóng gói app + dependencies vào container.

**Benefits:**
- Consistent environment
- Dễ deploy
- Isolation
- Reproducible builds

###  Exercise 2.1: Dockerfile cơ bản

```bash
cd ../../02-docker/develop
```

**Nhiệm vụ:** Đọc `Dockerfile` và trả lời:

1. Base image là gì?
2. Working directory là gì?
3. Tại sao COPY requirements.txt trước?
4. CMD vs ENTRYPOINT khác nhau thế nào?

####  Trả lời

1. **Base image:** `python:3.11` — bản full (không phải `-slim`), ~1 GB vì kèm nhiều build tools/libs không cần cho runtime.
2. **Working directory:** `/app` (đặt bằng `WORKDIR /app`).
3. **Tại sao COPY requirements.txt trước:** để tận dụng **Docker layer cache**. Layer `RUN pip install` chỉ bị rebuild khi `requirements.txt` thay đổi; nếu copy hết source code trước, mỗi lần sửa 1 dòng code sẽ làm cache layer pip install bị invalidate → phải cài lại toàn bộ dependencies, build chậm hơn rất nhiều.
4. **CMD vs ENTRYPOINT:**
   - `CMD ["python", "app.py"]` định nghĩa lệnh **mặc định**, có thể bị **override** khi chạy `docker run <image> <command-khác>`.
   - `ENTRYPOINT` định nghĩa lệnh **cố định luôn được chạy**; nếu có `CMD` đi kèm, `CMD` chỉ đóng vai trò là **argument** bổ sung cho `ENTRYPOINT` (không thay thế được executable, chỉ override args).
   - Dockerfile này chỉ dùng `CMD` → image linh hoạt, dễ debug bằng cách `docker run -it agent-develop sh`.

###  Exercise 2.2: Build và run

```bash
# Build image
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .

# Run container
docker run -p 8000:8000 my-agent:develop

# Test
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Docker?"}'
```

**Quan sát:** Image size là bao nhiêu? - 1.15GB

```bash
docker images my-agent:develop
```

####  Nhận xét

1.15 GB là rất lớn cho một app FastAPI nhỏ. Nguyên nhân:
- Base image `python:3.11` (full Debian, kèm build tools, compilers, docs...) thay vì `python:3.11-slim`
- Single-stage build → mọi thứ dùng để build (cache pip, apt) đều nằm lại trong image cuối
- Không có `.dockerignore` tối ưu để loại layer cache `__pycache__`, `.git`, `venv`...

→ Đây chính là động lực cho **Exercise 2.3: Multi-stage build**.

###  Exercise 2.3: Multi-stage build

```bash
cd ../production
```

**Nhiệm vụ:** Đọc `Dockerfile` và tìm:
- Stage 1 làm gì?
- Stage 2 làm gì?
- Tại sao image nhỏ hơn?

Build và so sánh:
```bash
docker build -t my-agent:advanced .
docker images | grep my-agent
```
```text
my-agent     advanced   210392061061   32 seconds ago   160MB
my-agent     develop    e9e999aa3cdb   16 minutes ago   1.15GB
```

####  Trả lời

- **Stage 1 (`builder`, `python:3.11-slim`):** cài `gcc`, `libpq-dev` (build tools cần để compile một số package), rồi `pip install --user -r requirements.txt`. Kết quả packages nằm ở `/root/.local`. Stage này **không** được copy vào image cuối.
- **Stage 2 (`runtime`, `python:3.11-slim`):** tạo non-root user (`appuser`), `COPY --from=builder /root/.local /home/appuser/.local` (chỉ lấy packages đã cài, không lấy gcc/build tools), copy source code, `HEALTHCHECK`, rồi chạy `uvicorn`.
- **Tại sao nhỏ hơn (160MB vs 1.15GB ≈ 7x):**
  1. Base `python:3.11-slim` thay vì `python:3.11` đầy đủ (~150MB vs ~1GB)
  2. Build tools (gcc, libpq-dev, apt cache) chỉ tồn tại ở stage builder, **không** nằm trong image runtime cuối
  3. Không có pip cache (`--no-cache-dir`)
  4. Chỉ copy đúng những gì cần để **chạy** (site-packages + code), không copy source/test/docs thừa

###  Exercise 2.4: Docker Compose stack

**Nhiệm vụ:** Đọc `docker-compose.yml` và vẽ architecture diagram.

```bash
docker compose up
```

Services nào được start? Chúng communicate thế nào?

Test:
```bash
# Health check
curl http://localhost/health

# Agent endpoint
curl http://localhost/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain microservices"}'
```

####  Trả lời — Architecture diagram

`02-docker/production/docker-compose.yml` khởi động **4 services** trên network `internal`:

```
                     ┌──────────────┐
   Client  ───────▶  │ nginx :80/443│   (port expose ra ngoài)
                     └──────┬───────┘
                            │ proxy_pass → agent_cluster:8000
                            ▼
                     ┌──────────────┐
                     │ agent (runtime│  build target "runtime"
                     │  stage image) │  không expose port — chỉ qua nginx
                     └──────┬───────┘
                ┌───────────┴────────────┐
                ▼                        ▼
        ┌──────────────┐         ┌──────────────────┐
        │ redis:7-alpine│         │ qdrant (vector DB)│
        │ (session/rate │         │ cho RAG, :6333    │
        │  limit cache) │         └──────────────────┘
        └──────────────┘
```

- **nginx**: reverse proxy / load balancer, là cổng vào duy nhất (port 80/443), forward request tới `agent_cluster` (upstream trỏ tới service `agent:8000`)
- **agent**: FastAPI app, build từ multi-stage Dockerfile (chỉ build stage `runtime`), kết nối tới `redis` (cache/rate limit) và `qdrant` (vector store)
- **redis**: lưu session/rate-limit counters, có healthcheck `redis-cli ping`
- **qdrant**: vector database cho RAG, healthcheck qua `/dev/tcp`
- Tất cả service (trừ nginx) **không expose port ra host** — chỉ giao tiếp qua `internal` network bằng DNS tên service (`redis`, `qdrant`, `agent`)
- `agent` chỉ start sau khi `redis` và `qdrant` healthy (`depends_on: condition: service_healthy`)

###  Checkpoint 2

- [x] Hiểu cấu trúc Dockerfile — base image, WORKDIR, COPY layer order, CMD
- [x] Biết lợi ích của multi-stage builds — image nhỏ hơn (~7x), không lẫn build tools, an toàn hơn
- [x] Hiểu Docker Compose orchestration — services, `depends_on` + healthcheck, internal network, volumes
- [x] Biết cách debug container (`docker logs`, `docker exec`) — `docker logs <container>` xem log, `docker exec -it <container> sh` vào shell để kiểm tra file/env/network

---

## Part 3: Cloud Deployment (45 phút)

###  Concepts

**Vấn đề:** Laptop không thể chạy 24/7, không có public IP.

**Giải pháp:** Cloud platforms — Railway, Render, GCP Cloud Run.

**So sánh:**

| Platform | Độ khó | Free tier | Best for |
|----------|--------|-----------|----------|
| Railway | ⭐ | $5 credit | Prototypes |
| Render | ⭐⭐ | 750h/month | Side projects |
| Cloud Run | ⭐⭐⭐ | 2M requests | Production |

###  Exercise 3.1: Deploy Railway (15 phút)

```bash
cd ../../03-cloud-deployment/railway
```

**Steps:**

1. Install Railway CLI:
```bash
npm i -g @railway/cli
```

2. Login:
```bash
railway login
```

3. Initialize project:
```bash
railway init
```

4. Set environment variables:
```bash
railway variables set PORT=8000
railway variables set AGENT_API_KEY=my-secret-key
```

5. Deploy:
```bash
railway up
```

6. Get public URL:
```bash
railway domain
```

**Nhiệm vụ:** Test public URL với curl hoặc Postman.

Test:
```bash
# Health check
curl http://student-agent-domain/health

# Agent endpoint
curl http://studen-agent-domain/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": ""}'
```

####  Nhận xét

> Lưu ý: 2 lệnh `curl` mẫu phía trên có lỗi đánh máy — domain phải **giống nhau**
> (`studen-agent-domain` thiếu chữ "t") và phải thay bằng domain thật do
> `railway domain` trả về (dạng `https://<tên-app>.up.railway.app`), ví dụ:
> ```bash
> curl https://<tên-app>.up.railway.app/health
> curl https://<tên-app>.up.railway.app/ask -X POST \
>   -H "Content-Type: application/json" \
>   -d '{"question": "Hello"}'
> ```
> Câu hỏi rỗng `{"question": ""}` sẽ bị validation reject (422) vì `AskRequest.question`
> yêu cầu `min_length=1` — đây là input validation đang hoạt động đúng.

`railway.toml` ở đây dùng `builder = "NIXPACKS"` (Railway tự detect Python + FastAPI,
không cần Dockerfile), `startCommand` đọc `$PORT` do Railway inject, và có
`healthcheckPath = "/health"` + `restartPolicyType = "ON_FAILURE"` để Railway tự
restart container khi crash.

###  Exercise 3.2: Deploy Render (15 phút)

```bash
cd ../render
```

**Steps:**

1. Push code lên GitHub (nếu chưa có)
2. Vào [render.com](https://render.com) → Sign up
3. New → Blueprint
4. Connect GitHub repo
5. Render tự động đọc `render.yaml`
6. Set environment variables trong dashboard
7. Deploy!

**Nhiệm vụ:** So sánh `render.yaml` với `railway.toml`. Khác nhau gì?

####  Trả lời

| | `railway.toml` | `render.yaml` |
|--|----------------|----------------|
| Format | TOML, `[build]` / `[deploy]` sections cho **1 service** | YAML "Blueprint" — có thể khai báo **nhiều services** (web, redis, database...) trong cùng 1 file |
| Builder | `builder = "NIXPACKS"` — Railway tự detect Python và build | `runtime: python` + khai báo rõ `buildCommand`/`startCommand` |
| Start command | `startCommand = "uvicorn app:app --host 0.0.0.0 --port $PORT"` | `startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT` (tương tự) |
| Health check | `healthcheckPath = "/health"`, `healthcheckTimeout = 30` | `healthCheckPath: /health` |
| Restart policy | `restartPolicyType = "ON_FAILURE"`, `restartPolicyMaxRetries = 3` | Không khai báo trong file — Render quản lý mặc định |
| Secrets | Set qua `railway variables set ...` (CLI/dashboard), **không** nằm trong `railway.toml` | Khai báo ngay trong `envVars`, dùng `sync: false` (set tay trên dashboard) hoặc `generateValue: true` (Render tự sinh secret) |
| Auto deploy | Theo cấu hình project trên dashboard | `autoDeploy: true` ngay trong file |

**Tóm lại:** `railway.toml` là config build/deploy cho **một service**, còn `render.yaml`
là **Infrastructure-as-Code** cho cả stack — commit vào git để Render tự đồng bộ
toàn bộ infrastructure (kể cả cách sinh/khai báo secrets).

###  Exercise 3.3: (Optional) GCP Cloud Run (15 phút)

```bash
cd ../production-cloud-run
```

**Yêu cầu:** GCP account (có free tier).

**Nhiệm vụ:** Đọc `cloudbuild.yaml` và `service.yaml`. Hiểu CI/CD pipeline.

####  Trả lời — CI/CD Pipeline

`cloudbuild.yaml` định nghĩa 4 bước chạy tuần tự (mỗi step `waitFor` step trước):

1. **`test`** — cài deps + chạy `pytest tests/` (fail sớm nếu test fail, không build/deploy)
2. **`build`** — `docker build` image, tag bằng `$COMMIT_SHA` và `latest`, dùng
   `--cache-from latest` để tái sử dụng layer cache → build nhanh hơn
3. **`push`** — push cả 2 tag lên Container Registry (`gcr.io/$PROJECT_ID/ai-agent`)
4. **`deploy`** — `gcloud run deploy` với:
   - `--allow-unauthenticated` (public endpoint)
   - `--min-instances=1` (giữ ấm, tránh cold start) / `--max-instances=10` (giới hạn chi phí)
   - `--set-secrets=OPENAI_API_KEY=openai-key:latest` — secret lấy từ **Secret Manager**, không hardcode

`service.yaml` là bản khai báo IaC tương đương (deploy bằng
`gcloud run services replace`), thêm:
- `autoscaling.knative.dev/minScale|maxScale` + `containerConcurrency: 80` — auto-scale theo số request đồng thời mỗi instance
- `livenessProbe: /health` và `startupProbe: /ready` — Cloud Run dùng 2 probe này tương tự Kubernetes
- `env[].valueFrom.secretKeyRef` — inject secret từ Secret Manager vào container, không qua biến môi trường thường

→ Đây là pipeline "push to main → test → build → push image → deploy" hoàn toàn tự động,
khác với Railway/Render (build trực tiếp từ source mỗi lần deploy).

###  Checkpoint 3

- [x] Hiểu cách set environment variables trên cloud — Railway: `railway variables set KEY=value`; Render: `envVars` trong `render.yaml` hoặc dashboard; Cloud Run: `--set-env-vars` / `--set-secrets` (Secret Manager)
- [x] Biết cách xem logs — Railway: `railway logs`; Render: tab "Logs" trên dashboard; Cloud Run: `gcloud run services logs read` hoặc Cloud Logging
- [ ] Deploy thành công lên ít nhất 1 platform *(cần thực hiện với account Railway/Render thật của bạn — xem lệnh ở Exercise 3.1/3.2)*
- [ ] Có public URL hoạt động *(sau khi deploy, verify bằng `curl <url>/health`)*

---

## Part 4: API Security (40 phút)

###  Concepts

**Vấn đề:** Public URL = ai cũng gọi được = hết tiền OpenAI.

**Giải pháp:**
1. **Authentication** — Chỉ user hợp lệ mới gọi được
2. **Rate Limiting** — Giới hạn số request/phút
3. **Cost Guard** — Dừng khi vượt budget

###  Exercise 4.1: API Key authentication

```bash
cd ../../04-api-gateway/develop
```

**Nhiệm vụ:** Đọc `app.py` và tìm:
- API key được check ở đâu?
- Điều gì xảy ra nếu sai key?
- Làm sao rotate key?

Test:
```bash
python app.py

#  Không có key
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'

#  Có key
curl http://localhost:8000/ask -X POST \
  -H "X-API-Key: secret-key-123" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

####  Trả lời

- **API key được check ở đâu?** Trong dependency `verify_api_key()` (`04-api-gateway/develop/app.py`), inject vào endpoint qua `Depends(verify_api_key)`. Key được đọc từ header `X-API-Key` bằng `APIKeyHeader(name="X-API-Key", auto_error=False)`, so sánh với `AGENT_API_KEY` lấy từ env (`os.getenv("AGENT_API_KEY", "demo-key-change-in-production")`).
- **Điều gì xảy ra nếu sai key?**
  - Thiếu header `X-API-Key` → `401 Unauthorized` ("Missing API key...")
  - Có header nhưng giá trị sai → `403 Forbidden` ("Invalid API key.")
- **Làm sao rotate key?** Đổi giá trị env var `AGENT_API_KEY` (trên Railway/Render: `railway variables set AGENT_API_KEY=...` hoặc dashboard) rồi restart service — không cần sửa code, vì key được đọc từ env mỗi lần app khởi động (12-factor config).

###  Exercise 4.2: JWT authentication (Advanced)

```bash
cd ../production
```

**Nhiệm vụ:** 
1. Đọc `auth.py` — hiểu JWT flow
2. Lấy token:
```bash
python app.py

curl http://localhost:8000/token -X POST \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'
```

3. Dùng token để gọi API:
```bash
TOKEN="<token_từ_bước_2>"
curl http://localhost:8000/ask -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain JWT"}'
```

####  Trả lời

> Lưu ý: endpoint thật trong `production/app.py` là **`POST /auth/token`** (không phải
> `/token`), và demo users là `student/demo123` (role `user`) và `teacher/teach456`
> (role `admin`) — không phải `admin/secret`.
> ```bash
> curl -X POST http://localhost:8000/auth/token \
>   -H "Content-Type: application/json" \
>   -d '{"username": "student", "password": "demo123"}'
> ```

**JWT flow (`auth.py`):**
1. `POST /auth/token` với `username`/`password` → `authenticate_user()` kiểm tra trong `DEMO_USERS` (in-memory)
2. Nếu hợp lệ → `create_token()` ký JWT bằng `jwt.encode(payload, SECRET_KEY, algorithm="HS256")`. Payload gồm `sub` (username), `role`, `iat`, `exp` (hết hạn sau 60 phút — `ACCESS_TOKEN_EXPIRE_MINUTES`)
3. Client gửi `Authorization: Bearer <token>` ở các request sau
4. `verify_token()` (dependency `Security(HTTPBearer(auto_error=False))`) decode + verify signature bằng `jwt.decode(...)`. Nếu hết hạn → `401 "Token expired"`; nếu sai chữ ký/format → `403 "Invalid token"`. Token hợp lệ → trả về `{"username":..., "role":...}` để dùng cho rate limit/cost guard theo role.

→ JWT là **stateless**: server không cần lưu session, mọi thông tin (user, role, expiry) đã nằm trong token, chỉ cần verify chữ ký bằng `JWT_SECRET`.

###  Exercise 4.3: Rate limiting

**Nhiệm vụ:** Đọc `rate_limiter.py` và trả lời:
- Algorithm nào được dùng? (Token bucket? Sliding window?)
- Limit là bao nhiêu requests/minute?
- Làm sao bypass limit cho admin?

Test:
```bash
# Gọi liên tục 20 lần
for i in {1..20}; do
  curl http://localhost:8000/ask -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"question": "Test '$i'"}'
  echo ""
done
```

Quan sát response khi hit limit.

####  Trả lời

- **Algorithm:** Sliding Window Counter — mỗi user có 1 `deque` chứa timestamps các request gần đây; mỗi lần check, các timestamp cũ hơn `window_seconds` (60s) bị loại khỏi đầu deque (`while window and window[0] < now - window_seconds: popleft()`).
- **Limit:** `rate_limiter_user = RateLimiter(max_requests=10, window_seconds=60)` → **10 req/phút** cho role `user`; `rate_limiter_admin = RateLimiter(max_requests=100, window_seconds=60)` → **100 req/phút** cho role `admin`.
- **Bypass cho admin:** trong `app.py`, dòng `limiter = rate_limiter_admin if role == "admin" else rate_limiter_user` — chọn limiter theo `role` lấy từ JWT payload. Login bằng `teacher/teach456` (role `admin`) sẽ có quota 100 req/phút thay vì 10.

**Quan sát khi hit limit:** request thứ 11+ (trong vòng 60s, với role `user`) trả về
`429 Too Many Requests` kèm body `{"error": "Rate limit exceeded", "limit": 10, "window_seconds": 60, "retry_after_seconds": ...}` và headers `X-RateLimit-Remaining: 0`, `Retry-After: <giây>`.

###  Exercise 4.4: Cost guard

**Nhiệm vụ:** Đọc `cost_guard.py` và implement logic:

```python
def check_budget(user_id: str, estimated_cost: float) -> bool:
    """
    Return True nếu còn budget, False nếu vượt.
    
    Logic:
    - Mỗi user có budget $10/tháng
    - Track spending trong Redis
    - Reset đầu tháng
    """
    # TODO: Implement
    pass
```

<details>
<summary> Solution</summary>

```python
import redis
from datetime import datetime

r = redis.Redis()

def check_budget(user_id: str, estimated_cost: float) -> bool:
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"
    
    current = float(r.get(key) or 0)
    if current + estimated_cost > 10:
        return False
    
    r.incrbyfloat(key, estimated_cost)
    r.expire(key, 32 * 24 * 3600)  # 32 days
    return True
```

</details>

####  Nhận xét

`cost_guard.py` thực tế trong `production/` **không** dùng Redis như gợi ý ở trên —
nó dùng class `CostGuard` **in-memory**:
- `check_budget(user_id)` — kiểm tra **trước** khi gọi LLM: nếu global cost ≥
  `global_daily_budget_usd` ($10/ngày) → `503`; nếu cost của user ≥
  `daily_budget_usd` ($1/ngày) → `402 Payment Required`; nếu ≥ 80% → log warning.
- `record_usage(user_id, input_tokens, output_tokens)` — gọi **sau** khi có response,
  cộng dồn cost (`PRICE_PER_1K_INPUT_TOKENS=0.00015`, `PRICE_PER_1K_OUTPUT_TOKENS=0.0006`,
  giá GPT-4o-mini) vào `UsageRecord` của user và vào `_global_cost`.
- Reset theo ngày: `_get_record()` so sánh `record.day` với `time.strftime("%Y-%m-%d")`,
  tạo `UsageRecord` mới nếu sang ngày khác.

**Hạn chế:** vì lưu trong biến Python (`self._records`, `self._global_cost`), dữ liệu
**mất khi restart** và **không chia sẻ được giữa nhiều instance** khi scale ngang.
Bản Redis ở gợi ý (`check_budget`/`incrbyfloat`/`expire`) giải quyết đúng vấn đề này —
đây chính là yêu cầu "Stateless design (state trong Redis)" ở **Part 6**.

###  Checkpoint 4

- [x] Implement API key authentication — `verify_api_key()` với `APIKeyHeader`, so khớp `AGENT_API_KEY` từ env
- [x] Hiểu JWT flow — `/auth/token` cấp token (HS256, exp 60'), `verify_token()` decode + lấy `username`/`role`
- [x] Implement rate limiting — sliding window theo `deque`, 10 req/phút (user) / 100 req/phút (admin)
- [x] Implement cost guard với Redis — hiểu solution Redis (`incrbyfloat` + `expire` theo tháng); bản hiện tại trong `production/` là in-memory, cần chuyển sang Redis để stateless (làm ở Part 6)

---

## Part 5: Scaling & Reliability (40 phút)

###  Concepts

**Vấn đề:** 1 instance không đủ khi có nhiều users.

**Giải pháp:**
1. **Stateless design** — Không lưu state trong memory
2. **Health checks** — Platform biết khi nào restart
3. **Graceful shutdown** — Hoàn thành requests trước khi tắt
4. **Load balancing** — Phân tán traffic

###  Exercise 5.1: Health checks

```bash
cd ../../05-scaling-reliability/develop
```

**Nhiệm vụ:** Implement 2 endpoints:

```python
@app.get("/health")
def health():
    """Liveness probe — container còn sống không?"""
    # TODO: Return 200 nếu process OK
    pass

@app.get("/ready")
def ready():
    """Readiness probe — sẵn sàng nhận traffic không?"""
    # TODO: Check database connection, Redis, etc.
    # Return 200 nếu OK, 503 nếu chưa ready
    pass
```

<details>
<summary> Solution</summary>

```python
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    try:
        # Check Redis
        r.ping()
        # Check database
        db.execute("SELECT 1")
        return {"status": "ready"}
    except:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready"}
        )
```

</details>

####  Nhận xét

`05-scaling-reliability/develop/app.py` đã implement đầy đủ và **chi tiết hơn** bản
solution mẫu:
- `GET /health` — trả `status`, `uptime_seconds`, `version`, `environment`, và một
  `checks.memory` (dùng `psutil` để đo `% RAM` sử dụng; nếu `>90%` → `status: "degraded"`)
- `GET /ready` — trả `503` nếu `_is_ready == False` (chưa qua giai đoạn startup
  trong `lifespan()`), ngược lại trả `{"ready": true, "in_flight_requests": N}`

Kết quả thực tế khi gọi (xem `05-scaling-reliability/README.md`):
```json
{
  "status": "ok",
  "uptime_seconds": 76.4,
  "version": "1.0.0",
  "environment": "development",
  "timestamp": "2026-06-10T07:20:39.887711+00:00",
  "checks": {"memory": {"status": "ok", "used_percent": 76.5}}
}
```

###  Exercise 5.2: Graceful shutdown

**Nhiệm vụ:** Implement signal handler:

```python
import signal
import sys

def shutdown_handler(signum, frame):
    """Handle SIGTERM from container orchestrator"""
    # TODO:
    # 1. Stop accepting new requests
    # 2. Finish current requests
    # 3. Close connections
    # 4. Exit
    pass

signal.signal(signal.SIGTERM, shutdown_handler)
```

Test:
```bash
python app.py &
PID=$!

# Gửi request
curl http://localhost:8000/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Long task"}' &

# Ngay lập tức kill
kill -TERM $PID

# Quan sát: Request có hoàn thành không?
```

####  Nhận xét

`develop/app.py` xử lý graceful shutdown qua **3 lớp phối hợp**:

1. `signal.signal(signal.SIGTERM, handle_sigterm)` + `signal.signal(signal.SIGINT, handle_sigterm)` — chỉ **log** signal nhận được, vì `uvicorn` đã tự bắt SIGTERM và trigger lifespan shutdown.
2. `lifespan()` shutdown block: đặt `_is_ready = False` ngay (→ `/ready` trả `503`, load balancer ngừng route traffic mới), rồi `while _in_flight_requests > 0 and elapsed < 30: sleep(1)` — chờ tối đa 30s cho các request đang xử lý hoàn thành.
3. `track_requests` middleware: tăng/giảm `_in_flight_requests` quanh mỗi request — đây là số liệu mà lifespan shutdown dùng để biết "đã xong chưa".
4. `uvicorn.run(..., timeout_graceful_shutdown=30)` — giới hạn tổng thời gian uvicorn chờ trước khi force-kill.

**Kết quả mong đợi** (đã verify, xem `05-scaling-reliability/README.md`): cả 2 request
gửi song song trước khi `kill -TERM` đều trả về `200 OK` đầy đủ — **không bị cắt giữa
đường** — trước khi process thực sự exit.

###  Exercise 5.3: Stateless design

```bash
cd ../production
```

**Nhiệm vụ:** Refactor code để stateless.

**Anti-pattern:**
```python
#  State trong memory
conversation_history = {}

@app.post("/ask")
def ask(user_id: str, question: str):
    history = conversation_history.get(user_id, [])
    # ...
```

**Correct:**
```python
#  State trong Redis
@app.post("/ask")
def ask(user_id: str, question: str):
    history = r.lrange(f"history:{user_id}", 0, -1)
    # ...
```

Tại sao? Vì khi scale ra nhiều instances, mỗi instance có memory riêng.

####  Nhận xét

`production/app.py` đã refactor theo đúng pattern "Correct": các hàm
`save_session()` / `load_session()` / `append_to_history()` đọc/viết session vào
**Redis** (`_redis.setex("session:<id>", ttl, json)` / `_redis.get(...)`), thay vì
một dict toàn cục.

Điểm hay: code có **fallback** sang `_memory_store: dict = {}` (chính là
anti-pattern) khi không kết nối được Redis — kèm `print("⚠️ Redis not available —
using in-memory store (not scalable!)")`. Fallback này hữu ích để dev nhanh không
cần Redis, nhưng **không dùng được khi scale > 1 instance** vì mỗi instance có
`_memory_store` riêng — đúng như câu hỏi "Tại sao?" ở trên: mỗi instance có memory
riêng, instance B sẽ không thấy session do instance A tạo.

###  Exercise 5.4: Load balancing

**Nhiệm vụ:** Chạy stack với Nginx load balancer:

```bash
docker compose up --scale agent=3
```

Quan sát:
- 3 agent instances được start
- Nginx phân tán requests
- Nếu 1 instance die, traffic chuyển sang instances khác

Test:
```bash
# Gọi 10 requests
for i in {1..10}; do
  curl http://localhost/ask -X POST \
    -H "Content-Type: application/json" \
    -d '{"question": "Request '$i'"}'
done

# Check logs — requests được phân tán
docker compose logs agent
```

####  Nhận xét

`production/docker-compose.yml` đã định nghĩa `agent` với `deploy.replicas: 3` và
một service `nginx` (image `nginx:alpine`) expose port `8080:80`. `nginx.conf` định
nghĩa `upstream agent_cluster { server agent:8000; }` — Docker Compose's embedded DNS
(`127.0.0.11`) resolve tên service `agent` ra **nhiều IP** (1 cho mỗi replica) và tự
round-robin giữa chúng, nên 1 dòng `server agent:8000;` là đủ để load-balance.

> Lưu ý: `deploy.replicas` trong file chỉ thật sự được Docker Compose áp dụng khi
> chạy `docker compose up --scale agent=3` (hoặc với Swarm). Nếu chỉ `docker compose
> up` (không `--scale`), Compose vẫn chỉ chạy 1 instance `agent` — đúng như lệnh được
> hướng dẫn ở trên.

Khi gọi 10 requests tới `http://localhost:8080` (qua nginx), header
`X-Served-By: $upstream_addr` (thêm bởi `add_header` trong `nginx.conf`) và
`docker compose logs agent` cho thấy các container `agent` khác nhau xử lý các
request khác nhau — chứng minh traffic được phân tán.

###  Exercise 5.5: Test stateless

```bash
python test_stateless.py
```

Script này:
1. Gọi API để tạo conversation
2. Kill random instance
3. Gọi tiếp — conversation vẫn còn không?

####  Nhận xét

`test_stateless.py` (bản hiện tại) làm cụ thể như sau, gọi qua `http://localhost:8080`:
1. Gửi 5 câu hỏi liên tiếp tới `POST /chat`, lần đầu không có `session_id` (server tự
   tạo bằng `uuid.uuid4()`), các lần sau gửi kèm `session_id` nhận được để tiếp tục
   cùng conversation
2. In ra `served_by` (instance ID) của mỗi response → thu thập vào `instances_seen`
3. Cuối cùng `GET /chat/{session_id}/history` để lấy lại **toàn bộ lịch sử hội thoại**
   và in ra — nếu `len(instances_seen) > 1` mà history vẫn đầy đủ → chứng minh session
   **không bị mất** dù mỗi request có thể được route tới container `agent` khác nhau,
   vì state nằm trong Redis (shared), không nằm trong memory của từng instance.

###  Checkpoint 5

- [x] Implement health và readiness checks — `/health` (liveness + memory check), `/ready` (readiness, dựa vào `_is_ready` + in-flight requests)
- [x] Implement graceful shutdown — `SIGTERM` handler + `lifespan` shutdown chờ `_in_flight_requests == 0` (tối đa 30s) + `timeout_graceful_shutdown=30`
- [x] Refactor code thành stateless — session/conversation history lưu trong Redis (`save_session`/`load_session`/`append_to_history`), có fallback in-memory cho dev
- [x] Hiểu load balancing với Nginx — `upstream agent_cluster { server agent:8000; }`, Docker DNS round-robin giữa các replica, `add_header X-Served-By`
- [x] Test stateless design — `test_stateless.py` xác nhận `served_by` thay đổi giữa các request nhưng `session history` vẫn đầy đủ qua Redis

---

## Part 6: Final Project (60 phút)

###  Objective

Build một production-ready AI agent từ đầu, kết hợp TẤT CẢ concepts đã học.

###  Requirements

**Functional:**
- [ ] Agent trả lời câu hỏi qua REST API
- [ ] Support conversation history
- [ ] Streaming responses (optional)

**Non-functional:**
- [ ] Dockerized với multi-stage build
- [ ] Config từ environment variables
- [ ] API key authentication
- [ ] Rate limiting (10 req/min per user)
- [ ] Cost guard ($10/month per user)
- [ ] Health check endpoint
- [ ] Readiness check endpoint
- [ ] Graceful shutdown
- [ ] Stateless design (state trong Redis)
- [ ] Structured JSON logging
- [ ] Deploy lên Railway hoặc Render
- [ ] Public URL hoạt động

### 🏗 Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Nginx (LB)     │
└──────┬──────────┘
       │
       ├─────────┬─────────┐
       ▼         ▼         ▼
   ┌──────┐  ┌──────┐  ┌──────┐
   │Agent1│  │Agent2│  │Agent3│
   └───┬──┘  └───┬──┘  └───┬──┘
       │         │         │
       └─────────┴─────────┘
                 │
                 ▼
           ┌──────────┐
           │  Redis   │
           └──────────┘
```

###  Step-by-step

#### Step 1: Project setup (5 phút)

```bash
mkdir my-production-agent
cd my-production-agent

# Tạo structure
mkdir -p app
touch app/__init__.py
touch app/main.py
touch app/config.py
touch app/auth.py
touch app/rate_limiter.py
touch app/cost_guard.py
touch Dockerfile
touch docker-compose.yml
touch requirements.txt
touch .env.example
touch .dockerignore
```

#### Step 2: Config management (10 phút)

**File:** `app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # TODO: Define all config
    # - PORT
    # - REDIS_URL
    # - AGENT_API_KEY
    # - LOG_LEVEL
    # - RATE_LIMIT_PER_MINUTE
    # - MONTHLY_BUDGET_USD
    pass

settings = Settings()
```

#### Step 3: Main application (15 phút)

**File:** `app/main.py`

```python
from fastapi import FastAPI, Depends, HTTPException
from .config import settings
from .auth import verify_api_key
from .rate_limiter import check_rate_limit
from .cost_guard import check_budget

app = FastAPI()

@app.get("/health")
def health():
    # TODO
    pass

@app.get("/ready")
def ready():
    # TODO: Check Redis connection
    pass

@app.post("/ask")
def ask(
    question: str,
    user_id: str = Depends(verify_api_key),
    _rate_limit: None = Depends(check_rate_limit),
    _budget: None = Depends(check_budget)
):
    # TODO: 
    # 1. Get conversation history from Redis
    # 2. Call LLM
    # 3. Save to Redis
    # 4. Return response
    pass
```

#### Step 4: Authentication (5 phút)

**File:** `app/auth.py`

```python
from fastapi import Header, HTTPException

def verify_api_key(x_api_key: str = Header(...)):
    # TODO: Verify against settings.AGENT_API_KEY
    # Return user_id if valid
    # Raise HTTPException(401) if invalid
    pass
```

#### Step 5: Rate limiting (10 phút)

**File:** `app/rate_limiter.py`

```python
import redis
from fastapi import HTTPException

r = redis.from_url(settings.REDIS_URL)

def check_rate_limit(user_id: str):
    # TODO: Implement sliding window
    # Raise HTTPException(429) if exceeded
    pass
```

#### Step 6: Cost guard (10 phút)

**File:** `app/cost_guard.py`

```python
def check_budget(user_id: str):
    # TODO: Check monthly spending
    # Raise HTTPException(402) if exceeded
    pass
```

#### Step 7: Dockerfile (5 phút)

```dockerfile
# TODO: Multi-stage build
# Stage 1: Builder
# Stage 2: Runtime
```

#### Step 8: Docker Compose (5 phút)

```yaml
# TODO: Define services
# - agent (scale to 3)
# - redis
# - nginx (load balancer)
```

#### Step 9: Test locally (5 phút)

```bash
docker compose up --scale agent=3

# Test all endpoints
curl http://localhost/health
curl http://localhost/ready
curl -H "X-API-Key: secret" http://localhost/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello", "user_id": "user1"}'
```

#### Step 10: Deploy (10 phút)

```bash
# Railway
railway init
railway variables set REDIS_URL=...
railway variables set AGENT_API_KEY=...
railway up

# Hoặc Render
# Push lên GitHub → Connect Render → Deploy
```

###  Validation

Chạy script kiểm tra:

```bash
cd 06-lab-complete
python check_production_ready.py
```

Script sẽ kiểm tra:
-  Dockerfile exists và valid
-  Multi-stage build
-  .dockerignore exists
-  Health endpoint returns 200
-  Readiness endpoint returns 200
-  Auth required (401 without key)
-  Rate limiting works (429 after limit)
-  Cost guard works (402 when exceeded)
-  Graceful shutdown (SIGTERM handled)
-  Stateless (state trong Redis, không trong memory)
-  Structured logging (JSON format)

###  Grading Rubric

| Criteria | Points | Description |
|----------|--------|-------------|
| **Functionality** | 20 | Agent hoạt động đúng |
| **Docker** | 15 | Multi-stage, optimized |
| **Security** | 20 | Auth + rate limit + cost guard |
| **Reliability** | 20 | Health checks + graceful shutdown |
| **Scalability** | 15 | Stateless + load balanced |
| **Deployment** | 10 | Public URL hoạt động |
| **Total** | 100 | |

---

##  Hoàn Thành!

Bạn đã:
-  Hiểu sự khác biệt dev vs production
-  Containerize app với Docker
-  Deploy lên cloud platform
-  Bảo mật API
-  Thiết kế hệ thống scalable và reliable

###  Next Steps

1. **Monitoring:** Thêm Prometheus + Grafana
2. **CI/CD:** GitHub Actions auto-deploy
3. **Advanced scaling:** Kubernetes
4. **Observability:** Distributed tracing với OpenTelemetry
5. **Cost optimization:** Spot instances, auto-scaling

###  Resources

- [12-Factor App](https://12factor.net/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Railway Docs](https://docs.railway.app/)
- [Render Docs](https://render.com/docs)

---

##  Q&A

**Q: Tôi không có credit card, có thể deploy không?**  
A: Có! Railway cho $5 credit, Render có 750h free tier.

**Q: Mock LLM khác gì với OpenAI thật?**  
A: Mock trả về canned responses, không gọi API. Để dùng OpenAI thật, set `OPENAI_API_KEY` trong env.

**Q: Làm sao debug khi container fail?**  
A: `docker logs <container_id>` hoặc `docker exec -it <container_id> /bin/sh`

**Q: Redis data mất khi restart?**  
A: Dùng volume: `volumes: - redis-data:/data` trong docker-compose.

**Q: Làm sao scale trên Railway/Render?**  
A: Railway: `railway scale <replicas>`. Render: Dashboard → Settings → Instances.

---

**Happy Deploying! **
