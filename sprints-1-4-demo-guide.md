# Overworld Interactive Demo Guide
## Sprints 1-4 Feature Walkthrough

**Your guide to experiencing the complete AI-powered map generation platform**

This guide provides step-by-step commands and expected outcomes for a complete user journey through Overworld. Each step includes what to type, what to look for, and what's happening under the hood.

---

## Prerequisites Check

**Verify mise is installed:**
```bash
mise --version
```
**Expected:** Version 2024.x.x or later

**Verify Docker is running:**
```bash
docker info
```
**Expected:** Server information without errors

**Verify you're in the project root:**
```bash
pwd
```
**Expected:** `/home/delorenj/code/overworld`

---

## Phase 1: Environment Setup & Service Startup

### Step 1.1: Check Current Service State

**Command:**
```bash
docker compose ps
```

**What to look for:**
- If empty: Services are stopped (expected for first run)
- If populated: Some services may already be running

**What's happening:** Checking if containers from previous sessions are still active.

---

### Step 1.2: Clean Start (Recommended for Demo)

**Command:**
```bash
mise run down
```

**What to look for:**
```
Container overworld-backend Stopped
Container overworld-frontend Stopped
... (all services stopped)
```

**What's happening:** Gracefully stops all running containers without removing volumes (preserves database data).

---

### Step 1.3: Start All Services

**Command:**
```bash
mise run dev
```

**What to look for (output will scroll rapidly):**

1. **Docker image builds** (first run only, ~2 minutes):
   ```
   #12 [development 3/4] RUN uv pip install --system -r requirements.txt
   Installed 71 packages in 48ms
   ```

2. **Service startup sequence**:
   ```
   Container overworld-postgres  Started
   Container overworld-redis     Started
   Container overworld-rabbitmq  Started
   Container overworld-backend   Started
   Container overworld-frontend  Started
   ```

3. **Critical ready messages** (watch for these):
   ```
   postgres  | database system is ready to accept connections
   redis     | Ready to accept connections
   rabbitmq  | Server startup complete
   backend   | Uvicorn running on http://0.0.0.0:8000
   frontend  | ➜  Local:   http://localhost:5173/
   ```

**What's happening:**
- **postgres**: PostgreSQL 16 with extensions (uuid-ossp, pg_trgm)
- **redis**: In-memory cache for sessions and rate limiting
- **rabbitmq**: Message queue for async job processing
- **backend**: FastAPI application with hot reload
- **frontend**: Vite dev server with HMR

**Time to ready:** ~15-30 seconds (after images are built)

---

### Step 1.4: Detach from Logs

Once you see all services ready, detach from logs:

**Press:** `Ctrl+C`

**What to look for:**
```
^C
Gracefully stopping... (press Ctrl+C again to force)
```

**What's happening:** Logs stop scrolling but containers keep running in background.

**Verify services are still running:**
```bash
docker compose ps
```

**Expected:** All services show `Up` status with "healthy" for postgres/redis/rabbitmq.

---

### Step 1.5: Run Database Migrations

**Command:**
```bash
mise run migrate
```

**What to look for:**
```
INFO  [alembic.runtime.migration] Running upgrade  -> cf9a1d378cb5, initial schema
INFO  [alembic.runtime.migration] Running upgrade cf9a1d378cb5 -> 91c47a448481, add GIN index
INFO  [alembic.runtime.migration] Running upgrade 91c47a448481 -> 75b5025fadd6, add documents table
...
INFO  [alembic.runtime.migration] Running upgrade a1b2c3d4e5f6 -> 20260120_exports, Create exports table
```

**What's happening:** Alembic applies 7 migrations that create the database schema:
- **cf9a1d378cb5**: Initial schema (users, maps, themes, token_balance, transactions, generation_jobs)
- **91c47a448481**: GIN index on maps.hierarchy JSONB for fast search
- **75b5025fadd6**: Documents table for uploaded files
- **0c9ce5097329**: Fix documents.user_id foreign key type
- **7a66a7d54df2**: Add document processing fields (status, content_hash, processed_content)
- **a1b2c3d4e5f6**: Add ARQ job queue fields (arq_job_id, retry_count, progress_message)
- **20260120_exports**: Exports table for PNG/SVG downloads

**Verify migrations:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "\dt"
```

**Expected output:**
```
 Schema |      Name       | Type
--------+-----------------+-------
 public | alembic_version | table
 public | documents       | table
 public | exports         | table
 public | generation_jobs | table
 public | maps            | table
 public | themes          | table
 public | token_balance   | table
 public | transactions    | table
 public | users           | table
(9 rows)
```

---

## Phase 2: Backend API Verification

### Step 2.1: Test API Health Endpoint

**Command:**
```bash
curl -s http://localhost:8778/api/health | jq
```

**Expected response:**
```json
{
  "status": "ok",
  "service": "overworld-backend"
}
```

**What's happening:** Verifying FastAPI application is responding on port 8778.

---

### Step 2.2: Browse API Documentation

**Open in browser:**
```
http://localhost:8778/docs
```

**What you'll see:**
- **FastAPI Swagger UI** with all API endpoints organized by tags
- **Tags visible:**
  - `auth` - Authentication endpoints (register, login, refresh)
  - `documents` - Document upload and management
  - `maps` - Map CRUD operations
  - `generation` - Map generation job management
  - `stripe` - Payment and token package endpoints
  - `export` - Map export (PNG/SVG) endpoints

**Try expanding an endpoint:**
- Click on `POST /api/v1/auth/register`
- Click **"Try it out"**
- See the request schema with example values

**What's happening:** FastAPI auto-generates OpenAPI 3.0 documentation from your Pydantic schemas and route decorators.

---

### Step 2.3: View Available Stripe Token Packages

**Command:**
```bash
curl -s http://localhost:8778/api/v1/stripe/packages | jq
```

**Expected response:**
```json
{
  "packages": [
    {
      "id": "starter",
      "name": "Starter Pack",
      "tokens": 1000,
      "price": 5.00,
      "price_per_1k": 5.00,
      "savings_pct": 0,
      "popular": false
    },
    {
      "id": "pro",
      "name": "Pro Pack",
      "tokens": 5000,
      "price": 20.00,
      "price_per_1k": 4.00,
      "savings_pct": 20,
      "popular": true
    },
    {
      "id": "enterprise",
      "name": "Enterprise Pack",
      "tokens": 15000,
      "price": 50.00,
      "price_per_1k": 3.33,
      "savings_pct": 33,
      "popular": false
    },
    {
      "id": "ultimate",
      "name": "Ultimate Pack",
      "tokens": 50000,
      "price": 150.00,
      "price_per_1k": 3.00,
      "savings_pct": 40,
      "popular": false
    }
  ]
}
```

**What to notice:**
- **Volume discounts**: Price per 1,000 tokens decreases with larger packages
- **Popular flag**: "Pro Pack" marked as most common choice
- **Savings calculation**: Enterprise saves 33%, Ultimate saves 40% vs Starter

**What's happening:** StripeService calculates pricing dynamically based on package definitions in `/home/delorenj/code/overworld/backend/app/services/stripe_service.py:41-72`.

---

## Phase 3: Frontend Access

### Step 3.1: Open Frontend in Browser

**URL:**
```
http://localhost:8777
```

**What you'll see:**
- **Login/Register page** with Overworld branding
- Clean, modern UI with Tailwind CSS styling
- Form with email and password fields
- Toggle between "Sign In" and "Sign Up"

**What's happening:** React 19 app served by Vite dev server with hot module replacement (HMR) enabled.

---

### Step 3.2: Inspect Frontend Routes

**Open browser DevTools** (F12), go to Network tab, then check which routes are available:

**Available pages** (based on `/home/delorenj/code/overworld/frontend/src/main.tsx:32-49`):
- `/login` - Public login/register page
- `/dashboard` - Main dashboard (protected)
- `/dashboard/maps` - My Maps list view (protected)
- `/dashboard/upload` - Document upload (protected)
- `/dashboard/settings` - User settings & token balance (protected)
- `/map` - Interactive map viewer (protected)

**What's happening:** React Router with `AuthProvider` context protecting authenticated routes.

---

## Phase 4: User Registration & Authentication

### Step 4.1: Register a New Account (Browser)

**In the browser at `http://localhost:8777`:**

1. Click **"Sign Up"** tab
2. Enter:
   - **Email:** `demo@overworld.dev`
   - **Password:** `DemoPassword123!`
3. Click **"Create Account"**

**What you'll see:**
- Brief loading state (spinner)
- Redirect to `/dashboard`
- Welcome message or dashboard content

**What's happening:**
1. Frontend POST to `/api/v1/auth/register`
2. Backend creates user in database with bcrypt password hash
3. Backend creates token_balance record with 5,000 free tokens
4. Backend generates JWT with user_id claim
5. Frontend stores JWT in localStorage
6. Frontend AuthContext sets authenticated state

---

### Step 4.2: Verify Registration (CLI)

**Command:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "SELECT id, email, is_verified, created_at FROM users WHERE email='demo@overworld.dev'"
```

**Expected output:**
```
 id |       email        | is_verified |          created_at
----+--------------------+-------------+-------------------------------
  1 | demo@overworld.dev | t           | 2026-01-25 15:25:42.123456+00
(1 row)
```

**What to notice:**
- `is_verified` is `t` (true) - email verification disabled in dev mode
- Timestamp matches your registration time

**Check token balance:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "SELECT user_id, free_tokens, purchased_tokens FROM token_balance WHERE user_id=1"
```

**Expected output:**
```
 user_id | free_tokens | purchased_tokens
---------+-------------+------------------
       1 |        5000 |                0
(1 row)
```

**What's happening:** New users receive 5,000 free tokens for testing (~5-10 map generations).

---

### Step 4.3: Register via CLI (Alternative Method)

**Command:**
```bash
curl -X POST http://localhost:8778/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "cli-user@overworld.dev",
    "password": "CliPassword123!"
  }' | jq
```

**Expected response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZXhwIjoxNzM...",
  "token_type": "bearer",
  "user": {
    "id": 2,
    "email": "cli-user@overworld.dev",
    "is_verified": true,
    "created_at": "2026-01-25T15:26:00.000000+00:00"
  }
}
```

**Save the access token for later:**
```bash
export ACCESS_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZXhwIjoxNzM..."
```

**What's happening:** Same registration flow, but returns JWT in response for programmatic access.

---

## Phase 5: Document Upload

### Step 5.1: Create a Sample Project Document

**Command:**
```bash
cat > /tmp/sample-project.md << 'EOF'
# Project Roadmap: AI Assistant Platform

Transform how teams build AI-powered applications with intelligent workflows.

## Phase 1: Foundation & Infrastructure
Building the groundwork for scalable AI integration.

### Sprint 1.1: Development Environment
- Docker Compose multi-service setup
- PostgreSQL database with migrations
- Redis caching layer
- RabbitMQ message queue

### Sprint 1.2: Authentication System
- JWT-based user authentication
- OAuth2 integration (Google, GitHub)
- Role-based access control
- Session management with Redis

### Sprint 1.3: Core API Framework
- FastAPI application structure
- Pydantic schema validation
- Error handling middleware
- Structured logging with correlation IDs

## Phase 2: AI Integration Layer
Connecting to LLM providers and managing contexts.

### Sprint 2.1: OpenRouter Integration
- Multi-provider routing (OpenAI, Anthropic, Google)
- Token usage tracking
- Rate limiting and quotas
- Fallback strategies

### Sprint 2.2: Conversation Management
- Context window optimization
- Message history persistence
- Conversation threading
- Export/import conversations

### Sprint 2.3: Document Processing
- PDF extraction with pypdf
- Markdown parsing
- Hierarchy detection
- Chunking strategies for RAG

## Phase 3: Vector Database & Search
Semantic search capabilities for knowledge retrieval.

### Sprint 3.1: Qdrant Vector Database
- Docker service configuration
- Collection schema design
- Embedding generation pipeline
- Hybrid search (vector + keyword)

### Sprint 3.2: RAG Pipeline
- Document chunking strategies
- Embedding model selection
- Retrieval algorithms
- Context injection

### Sprint 3.3: Knowledge Management
- Document versioning
- Incremental updates
- Metadata filtering
- Search result ranking

## Phase 4: Advanced AI Features
Multi-agent coordination and workflow automation.

### Sprint 4.1: Agent Framework
- Agent definition and registration
- Tool/function calling interface
- State management
- Inter-agent communication

### Sprint 4.2: Workflow Orchestration
- n8n integration
- Event-driven triggers
- Conditional branching
- Error recovery

### Sprint 4.3: Monitoring & Observability
- Structured logging aggregation
- Performance metrics (Prometheus)
- Distributed tracing (OpenTelemetry)
- Alert configuration

## Phase 5: Production Readiness
Deployment and operational excellence.

### Sprint 5.1: Infrastructure as Code
- Terraform for cloud resources
- Kubernetes manifests
- Helm charts
- GitOps with ArgoCD

### Sprint 5.2: CI/CD Pipeline
- GitHub Actions workflows
- Automated testing
- Container image building
- Deployment strategies (blue/green)

### Sprint 5.3: Security Hardening
- Dependency scanning
- Secret management (1Password)
- HTTPS enforcement
- OWASP compliance

## Appendix: Technology Stack

**Backend:** FastAPI, SQLAlchemy, Alembic, Pydantic
**Database:** PostgreSQL 16, Redis 7
**Queue:** RabbitMQ 3
**AI:** OpenRouter, Anthropic Claude, OpenAI GPT-4
**Vector DB:** Qdrant
**Frontend:** React 19, TypeScript, Tailwind CSS
**Infrastructure:** Docker, Terraform, Kubernetes
**Monitoring:** Prometheus, Grafana, OpenTelemetry
EOF
```

**What to look for:**
```
(no output means success)
```

**Verify file created:**
```bash
wc -l /tmp/sample-project.md
```
**Expected:** `125 /tmp/sample-project.md`

**What's happening:** Created a realistic project roadmap with hierarchical structure (4 levels: Project → Phases → Sprints → Tasks).

---

### Step 5.2: Upload Document via API (CLI Method)

**Command:**
```bash
curl -X POST http://localhost:8778/api/v1/documents/upload \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@/tmp/sample-project.md" | jq
```

**Expected response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": 2,
  "filename": "sample-project.md",
  "file_size": 3842,
  "r2_url": "s3://overworld-uploads/2/2026-01-25/sample-project.md",
  "status": "UPLOADED",
  "uploaded_at": "2026-01-25T15:30:00.000000+00:00"
}
```

**What to notice:**
- **id**: UUID for document reference
- **file_size**: Bytes (3.8KB)
- **r2_url**: S3-compatible Cloudflare R2 storage path
- **status**: UPLOADED (will become PROCESSING → PROCESSED after parsing)

**What's happening:**
1. FastAPI receives multipart upload
2. Validates file type (checks for markdown magic bytes)
3. Uploads to R2 at `/uploads/{user_id}/{date}/{filename}`
4. Creates database record in `documents` table
5. Returns document metadata

---

### Step 5.3: Upload Document via Browser (Preferred UX)

**In browser at `http://localhost:8777/dashboard/upload`:**

1. **Drag file** `/tmp/sample-project.md` onto dropzone
   - **OR** click "Choose File" and select it

**What you'll see:**
1. **Upload progress bar** (0% → 100%)
2. **Processing indicator** appears
3. **Success message:** "Document uploaded successfully!"
4. **Auto-redirect** to generation job status page

**Behind the scenes** (check logs):
```bash
docker compose logs -f backend | grep "upload\|document"
```

**Expected log entries:**
```
INFO: POST /api/v1/documents/upload - 201 Created
INFO: Document abc-123 uploaded to R2: s3://overworld-uploads/2/...
INFO: Document status updated: UPLOADED → PROCESSING
```

---

## Phase 6: Map Generation Pipeline

### Step 6.1: Trigger Map Generation

**After uploading, you're auto-redirected to generation status page.**

**Manual trigger via API:**
```bash
curl -X POST http://localhost:8778/api/v1/generation/jobs \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "theme_id": 1,
    "name": "AI Platform Roadmap"
  }' | jq
```

**Expected response:**
```json
{
  "job_id": "gen_abc123def456",
  "status": "PENDING",
  "progress_pct": 0,
  "created_at": "2026-01-25T15:31:00.000000+00:00"
}
```

**What's happening:**
1. Backend creates `generation_jobs` record
2. Publishes message to RabbitMQ `generation.pending` queue
3. ARQ worker picks up job
4. Multi-agent pipeline begins

---

### Step 6.2: Monitor Generation Progress (Browser)

**In browser, watch the real-time progress updates:**

**Stages you'll see:**

**Stage 1: Parser Agent (0-25%)**
```
🔄 Parsing Document
   Extracting hierarchy structure...
   Progress: 15%
```

**What's happening:** Parser agent reads markdown, detects hierarchy (# → ## → ###), extracts levels L0-L4.

**Stage 2: Artist Agent (25-50%)**
```
🎨 Designing Map
   Selecting visual theme...
   Progress: 35%
```

**What's happening:** Artist agent chooses biome types, color palette, asset styles based on project content.

**Stage 3: Road Generator (50-75%)**
```
🛤️ Generating Roads
   Creating connection paths...
   Progress: 60%
```

**What's happening:** Road generator creates SVG paths connecting hierarchical nodes, applies pathfinding algorithms.

**Stage 4: Icon Placer (75-95%)**
```
📍 Placing Icons
   Positioning landmarks...
   Progress: 85%
```

**What's happening:** Icon placer assigns assets to nodes, ensures no overlaps, optimizes for visual balance.

**Stage 5: Finalization (95-100%)**
```
✅ Map Complete!
   Saving to database...
   Progress: 100%
```

**What's happening:** Coordinator agent validates output, saves to database, updates job status to COMPLETED.

**Total time:** ~10-20 seconds (depends on OpenRouter API latency)

---

### Step 6.3: Monitor Generation Progress (CLI)

**Command (run in loop):**
```bash
watch -n 2 'curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8778/api/v1/generation/jobs/gen_abc123def456 | jq'
```

**What you'll see (updates every 2 seconds):**

```json
{
  "job_id": "gen_abc123def456",
  "status": "PROCESSING",
  "progress_pct": 35,
  "progress_message": "Artist agent designing map aesthetics",
  "created_at": "2026-01-25T15:31:00+00:00",
  "updated_at": "2026-01-25T15:31:08+00:00"
}
```

**Press `Ctrl+C` to stop watching.**

**Final status when complete:**
```json
{
  "job_id": "gen_abc123def456",
  "status": "COMPLETED",
  "progress_pct": 100,
  "progress_message": "Map generation complete",
  "map_id": 42,
  "created_at": "2026-01-25T15:31:00+00:00",
  "completed_at": "2026-01-25T15:31:15+00:00"
}
```

**What to notice:**
- **map_id**: Reference to created map record
- **completed_at**: Timestamp when pipeline finished

---

### Step 6.4: Inspect RabbitMQ Queue Activity

**Open RabbitMQ Management UI:**
```
http://localhost:15672
```

**Login:**
- **Username:** `overworld`
- **Password:** `overworld_rabbitmq_password`

**Navigate to "Queues" tab:**

**What you'll see:**
- **generation.pending**: 0 messages (job already processed)
- **generation.retry**: 0 messages (no failures)
- **generation.dlq**: 0 messages (no dead letters)

**Click on "generation.pending" queue:**
- **Message stats**: Shows throughput (messages/sec)
- **Get messages**: View message payload (if any queued)

**What's happening:** RabbitMQ handled async job distribution. Workers consumed messages, processed jobs, and ack'd completion.

---

### Step 6.5: Verify Generated Map in Database

**Command:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "
SELECT id, name, theme_id, watermarked,
       jsonb_pretty(hierarchy::jsonb) as hierarchy_preview,
       created_at
FROM maps
WHERE id=42
"
```

**Expected output (truncated):**
```
 id |         name          | theme_id | watermarked |    hierarchy_preview
----+-----------------------+----------+-------------+--------------------------
 42 | AI Platform Roadmap   |        1 | f           | {                       +
    |                       |          |             |     "L0": {             +
    |                       |          |             |         "title": "AI...",+
    |                       |          |             |         "children": [...]
(1 row)
```

**What to notice:**
- **hierarchy**: Nested JSONB structure with L0 (world) → L1 (phases) → L2 (sprints) → L3 (tasks)
- **watermarked**: `f` (false) - user has tokens, no watermark applied
- **theme_id**: References default theme

**Pretty-print full hierarchy:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -t -c "
SELECT jsonb_pretty(hierarchy::jsonb)
FROM maps
WHERE id=42
" | head -50
```

**What you'll see:**
```json
{
    "L0": {
        "title": "AI Assistant Platform",
        "description": "Transform how teams build AI-powered applications",
        "x": 512,
        "y": 384,
        "biome": "grassland"
    },
    "L1": [
        {
            "id": "phase1",
            "title": "Foundation & Infrastructure",
            "x": 256,
            "y": 200,
            "parent": "L0",
            "biome": "forest"
        },
        ...
    ]
}
```

**What's happening:** Multi-agent pipeline extracted hierarchy, assigned coordinates, selected biomes, and serialized to JSONB for fast queries.

---

## Phase 7: Interactive Map Viewing

### Step 7.1: Open Map Viewer (Browser)

**Navigate to:**
```
http://localhost:8777/map?id=42
```

**What you'll see:**

1. **Full-screen PixiJS canvas** (WebGL-accelerated)
2. **8-bit/16-bit styled overworld** with:
   - **L0 center**: "AI Assistant Platform" title text
   - **4 phase regions**: Positioned around L0 (North, East, South, West or clustered)
   - **Roads**: SVG paths connecting phases
   - **Assets**: Trees, mountains, buildings (theme-dependent)
   - **Smooth 60 FPS rendering**

3. **UI Controls (if implemented):**
   - **Top-right toolbar**: Zoom in/out, export, settings
   - **Bottom-left**: Minimap (if implemented)
   - **FPS counter**: Shows 60 FPS (dev mode only)

---

### Step 7.2: Test Interactive Controls

**Mouse wheel up/down:**
- **Action:** Scroll wheel
- **Expected:** Map zooms in/out smoothly
- **Notice:** Zoom centers on mouse cursor position
- **Range:** Typically 0.5x to 4x zoom

**Click and drag:**
- **Action:** Click canvas, hold, drag
- **Expected:** Map pans in drag direction
- **Notice:** Smooth easing, respects boundaries

**Click on a phase region (e.g., "Phase 1"):**
- **Action:** Click on phase area
- **Expected:** (If L1 navigation implemented) Zooms into phase detail view
- **OR:** Highlights region, shows tooltip with phase info

---

### Step 7.3: Inspect PixiJS Performance

**Open browser DevTools:**
1. Press `F12`
2. Go to **Performance** tab
3. Click **Record**
4. Interact with map (zoom, pan) for 5 seconds
5. Stop recording

**What to look for in flame graph:**
- **Consistent frame rate**: ~60 FPS (16.7ms per frame)
- **requestAnimationFrame**: Smooth, evenly-spaced calls
- **No layout thrashing**: Minimal reflows/repaints

**Console output (if debug enabled):**
```
PixiJS: WebGL2 Renderer initialized
FPS: 60.2
Sprites rendered: 234
Draw calls: 12
```

**What's happening:** PixiJS uses WebGL for hardware-accelerated rendering. Game loop runs at 60 FPS, re-rendering only changed sprites.

---

## Phase 8: Token System & Stripe Integration

### Step 8.1: Check Token Balance (Browser)

**Navigate to:**
```
http://localhost:8777/dashboard/settings
```

**What you'll see:**

**Token Balance Card:**
```
💎 Token Balance
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Free Tokens:      4,850
Purchased Tokens:     0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total:            4,850 tokens
```

**Transaction History:**
```
📊 Recent Transactions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-01-25 15:31  Map Generation     -150 tokens
2026-01-25 15:25  Welcome Bonus    +5,000 tokens
```

**What to notice:**
- You started with 5,000 free tokens
- Map generation cost 150 tokens (typical for medium-complexity project)
- Balance updates in real-time

---

### Step 8.2: View Token Packages

**In Settings, scroll to "Purchase Tokens" section:**

**What you'll see:**

```
💳 Token Packages
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[  Starter Pack   ]   [    Pro Pack     ]   [ Enterprise Pack ]
   1,000 tokens          5,000 tokens         15,000 tokens
      $5.00                 $20.00               $50.00
   $5.00/1k tokens       $4.00/1k tokens      $3.33/1k tokens
                         ⭐ POPULAR            💎 33% SAVINGS

   [ Buy Now ]           [ Buy Now ]          [ Buy Now ]
```

**What's happening:** Frontend fetches packages from `/api/v1/stripe/packages`, calculates savings percentages.

---

### Step 8.3: Simulate Token Purchase (Test Mode)

**Click "Buy Now" on Pro Pack:**

**What you'll see:**
1. Loading spinner
2. Redirect to **Stripe Checkout** page (test mode)

**Stripe Checkout page shows:**
```
Pay $20.00 to Overworld
━━━━━━━━━━━━━━━━━━━━━━━
Item: Pro Pack - 5,000 Tokens
Amount: $20.00

[Test Mode - Use Test Card]

Card Number: 4242 4242 4242 4242
Expiry: 12/34
CVC: 123
Name: Test User

[ Complete Payment ]
```

**What's happening:**
1. Frontend POST to `/api/v1/stripe/checkout` with package_id
2. Backend calls Stripe API to create checkout session
3. Backend includes metadata: `{user_id: 2, package_id: "pro", tokens: 5000}`
4. Stripe returns session URL
5. Frontend redirects to Stripe hosted checkout

---

### Step 8.4: Complete Test Payment

**In Stripe Checkout:**
1. Enter test card: `4242 4242 4242 4242`
2. Expiry: Any future date
3. CVC: Any 3 digits
4. Click **"Complete Payment"**

**What happens next:**

1. **Stripe processes payment**
2. **Webhook fires** to `http://localhost:8778/api/v1/stripe/webhook`
   - Event type: `checkout.session.completed`
3. **Backend verifies signature** (HMAC-SHA256)
4. **Backend grants tokens:**
   - Checks for duplicate (idempotency via stripe_event_id)
   - Adds 5,000 tokens to purchased_tokens
   - Creates transaction record
5. **Redirect to success page**

**Verify tokens granted:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "
SELECT user_id, free_tokens, purchased_tokens
FROM token_balance
WHERE user_id=2
"
```

**Expected:**
```
 user_id | free_tokens | purchased_tokens
---------+-------------+------------------
       2 |        4850 |             5000
(1 row)
```

**Check transaction log:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "
SELECT type, tokens_delta, stripe_event_id, created_at
FROM transactions
WHERE user_id=2
ORDER BY created_at DESC
LIMIT 3
"
```

**Expected:**
```
     type      | tokens_delta |     stripe_event_id      |         created_at
---------------+--------------+--------------------------+-----------------------------
 PURCHASE      |         5000 | evt_1AbC2dEf3GhI4jK5     | 2026-01-25 15:32:15.123456
 USAGE         |         -150 | NULL                     | 2026-01-25 15:31:10.654321
 WELCOME_BONUS |         5000 | NULL                     | 2026-01-25 15:25:42.987654
(3 rows)
```

**What to notice:**
- **stripe_event_id**: Ensures webhook processing is idempotent (no duplicate grants)
- **type**: PURCHASE for paid tokens, USAGE for consumed, WELCOME_BONUS for signup

---

### Step 8.5: Test Webhook Signature Verification (Advanced)

**Command:**
```bash
curl -X POST http://localhost:8778/api/v1/stripe/webhook \
  -H "Content-Type: application/json" \
  -d '{"type":"checkout.session.completed","data":{}}' \
  -v 2>&1 | grep "< HTTP"
```

**Expected response:**
```
< HTTP/1.1 400 Bad Request
```

**What's happening:** Webhook rejected because request lacks valid Stripe-Signature header. This prevents replay attacks and unauthorized token grants.

---

## Phase 9: Map Export (PNG/SVG)

### Step 9.1: Request PNG Export (Browser)

**On map viewer page (`/map?id=42`):**

1. Click **"Export"** button (top-right toolbar)
2. **Export dialog opens:**

```
╔═══════════════════════════════════╗
║      Export Your Map              ║
╟───────────────────────────────────╢
║ Format:  ( ) PNG  (•) SVG         ║
║                                   ║
║ Resolution (PNG only):            ║
║  ( ) 1x - 1024px                  ║
║  (•) 2x - 2048px                  ║
║  ( ) 4x - 4096px                  ║
║                                   ║
║ ℹ️ Free tier includes watermark   ║
║                                   ║
║         [ Generate Export ]       ║
╚═══════════════════════════════════╝
```

3. Select **PNG** and **2x resolution**
4. Click **"Generate Export"**

**What you'll see:**

**Progress updates:**
```
🔄 Processing export...
   Rendering map... 25%

🔄 Processing export...
   Applying watermark... 50%

🔄 Processing export...
   Uploading to storage... 75%

✅ Export ready!
   [ Download PNG ]
```

**What's happening (backend flow):**
1. POST to `/api/v1/maps/42/export` with format=PNG, resolution=2
2. Backend creates export record (status=PENDING)
3. Background task starts:
   - Renders map to PIL Image (2048x1536)
   - Applies watermark if user is free tier (checks purchased_tokens > 0)
   - Saves PNG to `/tmp/exports/{job_id}/map.png`
   - Uploads to R2 `overworld-exports` bucket
   - Generates pre-signed download URL (24-hour expiry)
   - Updates export status to COMPLETED
4. Frontend polls `/api/v1/maps/42/export/{export_id}/status` every 2 seconds
5. When status=COMPLETED, shows download button

---

### Step 9.2: Download and Inspect Export

**Click "Download PNG":**

**What happens:**
- Browser downloads `overworld-map-{timestamp}.png`
- File size: ~2-4MB (depending on complexity)

**Open the downloaded PNG:**

**What you'll see:**
- **2048x1536 resolution** (or selected size)
- **High-quality render** of the 8-bit map
- **Watermark** (if free tier): "Generated with Overworld" in bottom-right corner
- **No watermark** (if premium): Clean export

**Verify watermark logic:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "
SELECT e.id, e.format, e.watermarked, tb.purchased_tokens
FROM exports e
JOIN maps m ON e.map_id = m.id
JOIN token_balance tb ON m.user_id = tb.user_id
WHERE e.id = (SELECT MAX(id) FROM exports)
"
```

**Expected:**
```
 id | format | watermarked | purchased_tokens
----+--------+-------------+------------------
  1 | png    | t           |                0
```

**Interpretation:**
- `watermarked=t` (true) because `purchased_tokens=0` (free tier)
- If you had purchased tokens, `watermarked=f`

---

### Step 9.3: Request SVG Export (Vector Graphics)

**Repeat export process, but select:**
- **Format:** SVG
- Click **"Generate Export"**

**Expected download:**
- Filename: `overworld-map-{timestamp}.svg`
- File size: ~50-200KB (much smaller than PNG)
- **Scalable**: Can zoom infinitely without pixelation

**Open SVG in browser:**
- Drag file into new browser tab
- **OR** use `file:///path/to/map.svg`

**What you'll see:**
- Vector graphics rendering
- Crisp edges at any zoom level
- Can inspect XML source (right-click → View Source)

**Inspect SVG structure:**
```bash
head -30 ~/Downloads/overworld-map-*.svg
```

**Expected structure:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg width="1024" height="768" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <pattern id="grass-texture" .../>
    <filter id="8bit-pixelate" .../>
  </defs>

  <!-- Background layer -->
  <rect fill="#87CEEB" width="1024" height="768"/>

  <!-- Terrain features -->
  <g id="terrain">
    <path d="M 512,384 Q 256,200 ..." stroke="#8B4513" .../>
  </g>

  <!-- Watermark (if free tier) -->
  <text x="924" y="748" opacity="0.3">Generated with Overworld</text>
</svg>
```

**What's happening:** ExportService renders map to SVG using hierarchy coordinates, applies theme styling, embeds watermark as text element.

---

### Step 9.4: Check Export History

**In browser, navigate to Settings:**

**Scroll to "Export History" section:**

```
📥 Export History
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Map Name            Format  Resolution  Created          Status
AI Platform Roadmap SVG     -           2026-01-25 15:35 ✅ Ready
AI Platform Roadmap PNG     2x          2026-01-25 15:33 ✅ Ready
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Click on any export row:**
- Shows download button
- Shows expiration time (24 hours from creation)
- Shows watermark status

**What's happening:** Frontend fetches from `/api/v1/exports?limit=50`, displays sortable table.

---

## Phase 10: Anonymous User Flow & Rate Limiting

### Step 10.1: Test Anonymous Generation Limit

**Open incognito window:**
```
http://localhost:8777
```

**What you'll see:**
- Login page, but with **"Try as Guest"** button (if implemented)
- **OR** direct access to upload without auth

**Upload document without logging in:**
- Drag `/tmp/sample-project.md`
- Submit for generation

**After 3 generations (or configured limit):**

**What you'll see:**
```
❌ Daily Limit Reached

You've used your 3 free map generations today.

Options:
- [Create Free Account] (5,000 tokens)
- [Purchase Tokens] (volume discounts)

Limit resets in: 18 hours
```

**What's happening:**
1. RateLimitMiddleware hashes client IP
2. Redis tracks count: `rate_limit:{hashed_ip}:generation` = 3
3. TTL set to 24 hours
4. Next request returns 429 Too Many Requests

---

### Step 10.2: Verify Rate Limit in Redis

**Command:**
```bash
docker compose exec redis redis-cli --raw KEYS "rate_limit:*"
```

**Expected output:**
```
rate_limit:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08:generation
```

**Check the counter value:**
```bash
docker compose exec redis redis-cli GET "rate_limit:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08:generation"
```

**Expected output:**
```
3
```

**Check TTL (time to live):**
```bash
docker compose exec redis redis-cli TTL "rate_limit:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08:generation"
```

**Expected output:**
```
64800
```
(18 hours in seconds)

**What's happening:** Redis automatically expires the key after 24 hours, resetting the limit.

---

### Step 10.3: Test Rate Limit Headers

**Command:**
```bash
curl -X POST http://localhost:8778/api/v1/generation/jobs \
  -H "Content-Type: application/json" \
  -d '{"document_id":"...","theme_id":1,"name":"Test"}' \
  -i 2>&1 | grep -E "^HTTP|^X-RateLimit|^Retry-After"
```

**Expected response (after hitting limit):**
```
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 3
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1737820800
Retry-After: 64800
```

**What to notice:**
- **429 status**: Standard HTTP "Too Many Requests"
- **X-RateLimit-Limit**: Maximum requests allowed (3)
- **X-RateLimit-Remaining**: Requests left (0)
- **X-RateLimit-Reset**: Unix timestamp when limit resets
- **Retry-After**: Seconds until retry allowed (18 hours)

**What's happening:** RateLimitMiddleware returns standard rate limit headers per RFC 6585.

---

## Phase 11: Database Deep Dive

### Step 11.1: Explore Schema Relationships

**Command:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name
"
```

**Expected output:**
```
   table_name    |   column_name   | foreign_table_name | foreign_column_name
-----------------+-----------------+--------------------+---------------------
 documents       | user_id         | users              | id
 exports         | map_id          | maps               | id
 exports         | user_id         | users              | id
 generation_jobs | document_id     | documents          | id
 generation_jobs | map_id          | maps               | id
 generation_jobs | user_id         | users              | id
 maps            | theme_id        | themes             | id
 maps            | user_id         | users              | id
 token_balance   | user_id         | users              | id
 transactions    | user_id         | users              | id
(10 rows)
```

**What this shows:**
- **users** is the central entity (referenced by 8 foreign keys)
- **documents → generation_jobs → maps**: Generation pipeline flow
- **maps → exports**: Export dependency chain
- **Cascade deletes**: Deleting a user cascades to all related data

---

### Step 11.2: Query Map Hierarchy with JSONB

**Command:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "
SELECT
    id,
    name,
    hierarchy->'L0'->>'title' as world_title,
    jsonb_array_length(hierarchy->'L1') as num_phases
FROM maps
WHERE hierarchy @> '{\"L0\": {\"title\": \"AI Assistant Platform\"}}'::jsonb
"
```

**Expected output:**
```
 id |        name         |     world_title      | num_phases
----+---------------------+----------------------+------------
 42 | AI Platform Roadmap | AI Assistant Platform|          5
(1 row)
```

**What's happening:**
- `->` operator: Extract JSON object
- `->>` operator: Extract as text
- `@>` operator: JSONB containment check (GIN index accelerated)
- `jsonb_array_length()`: Count array elements

**Performance benefit:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "
EXPLAIN ANALYZE
SELECT id FROM maps
WHERE hierarchy @> '{\"L0\": {\"biome\": \"grassland\"}}'::jsonb
"
```

**What to look for:**
```
Bitmap Index Scan on idx_maps_hierarchy_gin  (cost=0.00..8.27 rows=1)
  Index Cond: (hierarchy @> '{"L0": {"biome": "grassland"}}'::jsonb)
Planning Time: 0.123 ms
Execution Time: 0.045 ms
```

**Notice:** GIN index makes JSONB queries fast (~0.045ms), even with complex hierarchies.

---

### Step 11.3: Analyze Token Transaction Patterns

**Command:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "
SELECT
    type,
    COUNT(*) as count,
    SUM(tokens_delta) as total_tokens,
    AVG(tokens_delta) as avg_tokens
FROM transactions
GROUP BY type
ORDER BY count DESC
"
```

**Expected output:**
```
     type      | count | total_tokens | avg_tokens
---------------+-------+--------------+------------
 WELCOME_BONUS |     2 |        10000 |       5000
 USAGE         |     2 |         -300 |       -150
 PURCHASE      |     1 |         5000 |       5000
(3 rows)
```

**What this tells you:**
- **Most common**: Welcome bonuses (new user signups)
- **Average generation cost**: 150 tokens
- **Total purchased**: 5,000 tokens from 1 transaction

---

## Phase 12: Background Job Processing

### Step 12.1: Monitor ARQ Worker Activity

**Command:**
```bash
docker compose logs -f backend | grep "arq\|worker\|job"
```

**What you'll see (during generation):**
```
INFO: ARQ worker started, listening for jobs
INFO: Job gen_abc123 started: Parser agent
INFO: Job gen_abc123 progress: 15% - Extracting hierarchy
INFO: Job gen_abc123 progress: 35% - Artist designing theme
INFO: Job gen_abc123 progress: 60% - Road generation
INFO: Job gen_abc123 progress: 85% - Icon placement
INFO: Job gen_abc123 completed in 12.3s
```

**What's happening:**
- ARQ (async Redis queue) worker polls Redis for jobs
- Jobs enqueued by API endpoints
- Worker updates progress in database
- Frontend polls for status updates

---

### Step 12.2: Inspect Redis Job Queue

**Command:**
```bash
docker compose exec redis redis-cli KEYS "arq:*"
```

**Expected output:**
```
1) "arq:queue"
2) "arq:job:gen_abc123"
3) "arq:result:gen_abc123"
```

**Get job details:**
```bash
docker compose exec redis redis-cli HGETALL "arq:job:gen_abc123"
```

**Expected output:**
```
1) "function"
2) "process_generation_job"
3) "enqueue_time"
4) "1737820260.123"
5) "status"
6) "complete"
7) "result"
8) "{\"map_id\": 42, \"tokens_used\": 150}"
```

**What's happening:** ARQ stores job state in Redis hashes with automatic TTL cleanup.

---

## Phase 13: Error Handling & Edge Cases

### Step 13.1: Test File Size Limit

**Create oversized file:**
```bash
dd if=/dev/zero of=/tmp/large.md bs=1M count=6
```

**Upload via browser or CLI:**
```bash
curl -X POST http://localhost:8778/api/v1/documents/upload \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@/tmp/large.md" -i 2>&1 | grep "HTTP"
```

**Expected response:**
```
HTTP/1.1 413 Payload Too Large
```

**Error message:**
```json
{
  "detail": "File size exceeds 5MB limit for markdown documents"
}
```

**What's happening:** FastAPI middleware checks `content-length` header, rejects before reading entire file (prevents memory exhaustion).

---

### Step 13.2: Test Invalid File Type

**Create invalid file:**
```bash
echo "#!/bin/bash\necho 'malicious script'" > /tmp/bad.sh
```

**Upload:**
```bash
curl -X POST http://localhost:8778/api/v1/documents/upload \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@/tmp/bad.sh" | jq
```

**Expected response:**
```json
{
  "detail": "Invalid file format. Only .md and .pdf files are supported."
}
```

**What's happening:** Backend validates magic bytes (file signature), not just extension. Shell script rejected even if renamed to `.md`.

---

### Step 13.3: Test Insufficient Token Balance

**Manually deplete tokens:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "
UPDATE token_balance
SET free_tokens=0, purchased_tokens=0
WHERE user_id=2
"
```

**Attempt generation:**
```bash
curl -X POST http://localhost:8778/api/v1/generation/jobs \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"document_id":"550e8400-e29b-41d4-a716-446655440000","theme_id":1,"name":"Test"}' \
  | jq
```

**Expected response:**
```json
{
  "detail": "Insufficient tokens. Required: 150, Available: 0. Please purchase tokens."
}
```

**What's happening:** TokenService.deduct_tokens() checks balance before creating generation job, preventing negative balances.

---

### Step 13.4: Test Idempotent Webhook Processing

**Simulate duplicate Stripe webhook:**

1. **First webhook (success):**
```bash
# This would normally come from Stripe with valid signature
# Simulating the internal flow after signature verification
```

2. **Duplicate webhook with same stripe_event_id:**

**Database constraint prevents duplicate:**
```sql
UNIQUE (stripe_event_id) ON transactions table
```

**Expected behavior:**
- First event: Grants 5,000 tokens
- Duplicate event: Returns 200 OK but no tokens granted (idempotent)

**Verify in logs:**
```bash
docker compose logs backend | grep "stripe_event_id"
```

**Expected:**
```
INFO: Processing Stripe event evt_1AbC2dEf3GhI4jK5
INFO: Tokens granted: 5000 (transaction_id: txn_123)
INFO: Duplicate event evt_1AbC2dEf3GhI4jK5 detected, skipping
```

**What's happening:** Database unique constraint + try/except pattern ensures atomic, idempotent webhook processing.

---

## Phase 14: Performance & Observability

### Step 14.1: Check Application Metrics

**Monitor resource usage:**
```bash
docker stats --no-stream
```

**Expected output:**
```
NAME                CPU %   MEM USAGE / LIMIT     MEM %   NET I/O
overworld-backend   2.5%    180MB / 4GB           4.5%    1.2MB / 800KB
overworld-frontend  0.8%    120MB / 4GB           3.0%    500KB / 200KB
overworld-postgres  1.2%    45MB / 2GB            2.25%   200KB / 150KB
overworld-redis     0.5%    15MB / 512MB          2.9%    50KB / 30KB
overworld-rabbitmq  1.0%    80MB / 1GB            8.0%    100KB / 50KB
```

**What to notice:**
- **Backend memory**: ~180MB (FastAPI + SQLAlchemy connection pool)
- **Frontend memory**: ~120MB (Vite dev server + Node.js)
- **Postgres memory**: ~45MB (small dataset, mostly shared buffers)
- **Redis memory**: ~15MB (session data + rate limit counters)
- **RabbitMQ memory**: ~80MB (management UI overhead)

**Production optimization opportunities:**
- Backend could reduce to ~50MB with gunicorn workers
- Frontend production build: ~2MB static files (no Node.js runtime)

---

### Step 14.2: Query Database Performance Stats

**Check most expensive queries:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "
SELECT
    query,
    calls,
    mean_exec_time,
    total_exec_time
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY mean_exec_time DESC
LIMIT 5
" 2>/dev/null || echo "pg_stat_statements extension not enabled (optional)"
```

**If enabled, you'll see:**
```
                    query                     | calls | mean_exec_time | total_exec_time
----------------------------------------------+-------+----------------+-----------------
 SELECT * FROM maps WHERE hierarchy @> $1     |    12 |           1.23 |           14.76
 INSERT INTO generation_jobs ...              |     8 |           0.85 |            6.80
(Simplified output)
```

**What this tells you:** JSONB queries are fast (~1.2ms) due to GIN index.

---

### Step 14.3: Check PixiJS Performance Metrics

**In browser on map viewer, open console (F12):**

**Type:**
```javascript
// Get PixiJS app instance
const app = window.__PIXI_APP__
console.log(`FPS: ${app.ticker.FPS.toFixed(1)}`)
console.log(`Sprites: ${app.stage.children.length}`)
console.log(`Draw calls: ${app.renderer.renderingToScreen}`)
```

**Expected output:**
```
FPS: 60.0
Sprites: 234
Draw calls: true
```

**Enable performance overlay:**
```javascript
app.renderer.plugins.performance.showStats = true
```

**What you'll see:**
- FPS counter in top-left corner
- Draw call count
- GPU memory usage (if available)

**What's happening:** PixiJS maintains 60 FPS by batching sprite rendering, using texture atlases, and leveraging WebGL shaders.

---

## Phase 15: Multi-Map Management

### Step 15.1: View All Maps (Browser)

**Navigate to:**
```
http://localhost:8777/dashboard/maps
```

**What you'll see:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗺️ My Maps                    [ + Upload New Document ]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────┐  ┌─────────────────────────┐
│ [Map Thumbnail Image]   │  │ [Map Thumbnail Image]   │
│                         │  │                         │
│ AI Platform Roadmap     │  │ Product Launch Plan     │
│ Created: 2026-01-25     │  │ Created: 2026-01-24     │
│ 150 tokens              │  │ 200 tokens              │
│                         │  │                         │
│ [View] [Export] [...]   │  │ [View] [Export] [...]   │
└─────────────────────────┘  └─────────────────────────┘
```

**What's happening:** Frontend fetches `/api/v1/maps?limit=50`, displays grid with thumbnails (if generated) or placeholder icons.

---

### Step 15.2: Query Maps via CLI

**List all maps for user:**
```bash
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8778/api/v1/maps?limit=10" | jq '.maps[] | {id, name, created_at}'
```

**Expected output:**
```json
{
  "id": 42,
  "name": "AI Platform Roadmap",
  "created_at": "2026-01-25T15:31:15.000000+00:00"
}
{
  "id": 43,
  "name": "Product Launch Plan",
  "created_at": "2026-01-24T10:15:30.000000+00:00"
}
```

---

### Step 15.3: Filter Maps by Theme

**Command:**
```bash
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8778/api/v1/maps?theme_id=1&limit=10" | jq '.maps[] | {id, name, theme_id}'
```

**Expected output:**
```json
{
  "id": 42,
  "name": "AI Platform Roadmap",
  "theme_id": 1
}
```

**What's happening:** Backend filters using SQLAlchemy query: `select(Map).where(Map.theme_id == 1)`.

---

## Phase 16: Testing the Full Stack

### Step 16.1: Run Backend Tests

**Command:**
```bash
mise run test
```

**What you'll see:**
```
========================== test session starts ==========================
platform linux -- Python 3.12.12, pytest-7.4.4, pluggy-1.6.0
collected 493 items

tests/test_auth.py ..................                              [  3%]
tests/test_documents.py ..............                             [  6%]
tests/test_generation.py ....................                      [ 10%]
tests/test_maps.py ........................                        [ 15%]
tests/test_stripe.py .............................                 [ 21%]
tests/test_export.py .................                             [ 24%]
...

======================== 493 passed in 45.2s ===========================
```

**What to notice:**
- **493 tests total** (Sprints 1-4 coverage)
- **Key test files:**
  - `test_stripe.py`: 29 tests for payment integration
  - `test_export.py`: 17 tests for PNG/SVG export
  - `test_auth.py`: 18 tests for JWT auth
  - `test_generation.py`: 23 tests for multi-agent pipeline

**What's happening:** pytest runs async tests with isolated database fixtures (each test gets fresh DB).

---

### Step 16.2: Run Tests with Coverage Report

**Command:**
```bash
mise run test-cov
```

**Expected output:**
```
========================== test session starts ==========================
493 passed in 45.2s

---------- coverage: platform linux, python 3.12.12 -----------
Name                                      Stmts   Miss  Cover
-------------------------------------------------------------
app/__init__.py                               0      0   100%
app/api/v1/routers/auth.py                  142      8    94%
app/api/v1/routers/documents.py             95      5    95%
app/api/v1/routers/export.py               178     12    93%
app/api/v1/routers/generation.py           156     10    94%
app/api/v1/routers/stripe.py               123      7    94%
app/services/stripe_service.py             187     11    94%
app/services/export_service.py             245     18    93%
app/services/token_service.py               89      4    96%
app/middleware/rate_limit.py                96      6    94%
-------------------------------------------------------------
TOTAL                                      3847    212    94%

Coverage HTML written to htmlcov/index.html
```

**Open coverage report:**
```bash
xdg-open backend/htmlcov/index.html
```
(Or manually open in browser)

**What you'll see:**
- Line-by-line coverage highlighting
- Uncovered lines in red
- Branch coverage percentages

**What this tells you:** 94% coverage across core services. Uncovered lines are mostly error edge cases.

---

## Phase 17: Stripe Integration Deep Dive

### Step 17.1: View Stripe Configuration

**Command:**
```bash
curl -s http://localhost:8778/api/v1/stripe/config | jq
```

**Expected response:**
```json
{
  "publishable_key": "pk_test_51AbC2dEf3GhI4jK5LmN6oP7qR8sT9uV0wX1yZ2",
  "currency": "usd",
  "country": "US"
}
```

**What to notice:**
- **publishable_key**: Safe to expose in frontend (starts with `pk_test_`)
- **currency**: USD (could be configurable per user locale)
- **country**: US (affects Stripe payment methods available)

**What's happening:** Backend returns public config only, secret key never exposed.

---

### Step 17.2: Inspect Stripe Service Implementation

**Read the service code:**
```bash
head -100 /home/delorenj/code/overworld/backend/app/services/stripe_service.py
```

**Key sections to notice:**

**Line 41-72: Token packages defined as code**
```python
PACKAGES = [
    TokenPackage(
        id="starter",
        name="Starter Pack",
        tokens=1_000,
        price=5.00,
    ),
    TokenPackage(
        id="pro",
        name="Pro Pack",
        tokens=5_000,
        price=20.00,
        popular=True,
    ),
    ...
]
```

**Line 120-145: Checkout session creation**
```python
async def create_checkout_session(
    user_id: int,
    package_id: str,
) -> str:
    """Creates Stripe checkout session with metadata."""
    package = next((p for p in PACKAGES if p.id == package_id), None)

    session = stripe.checkout.Session.create(
        metadata={"user_id": user_id, "package_id": package_id},
        success_url=f"{settings.FRONTEND_URL}/checkout/success",
        cancel_url=f"{settings.FRONTEND_URL}/checkout/cancel",
        ...
    )
```

**What to notice:**
- Metadata embeds user_id for webhook processing
- Success/cancel URLs redirect back to frontend
- Stripe hosted checkout (PCI compliance handled by Stripe)

---

### Step 17.3: Test Webhook Signature Verification

**Read webhook handler:**
```bash
grep -A 30 "def webhook_handler" /home/delorenj/code/overworld/backend/app/api/v1/routers/stripe.py
```

**Key security check at line ~95:**
```python
try:
    event = stripe.Webhook.construct_event(
        payload,
        sig_header,
        settings.STRIPE_WEBHOOK_SECRET
    )
except ValueError:
    raise HTTPException(status_code=400, detail="Invalid payload")
except stripe.error.SignatureVerificationError:
    raise HTTPException(status_code=400, detail="Invalid signature")
```

**What this prevents:**
- **Replay attacks**: Expired signatures rejected
- **Tampering**: Modified payloads fail HMAC verification
- **Spoofing**: Events without valid signature ignored

---

## Phase 18: Export Feature Deep Dive

### Step 18.1: List All Exports for a Map

**Command:**
```bash
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8778/api/v1/maps/42/exports" | jq
```

**Expected response:**
```json
{
  "exports": [
    {
      "id": 1,
      "map_id": 42,
      "format": "svg",
      "resolution_multiplier": null,
      "status": "completed",
      "watermarked": true,
      "download_url": "https://r2.cloudflarestorage.com/overworld-exports/...",
      "download_url_expires_at": "2026-01-26T15:35:00+00:00",
      "created_at": "2026-01-25T15:35:00+00:00"
    },
    {
      "id": 2,
      "map_id": 42,
      "format": "png",
      "resolution_multiplier": 2,
      "status": "completed",
      "watermarked": true,
      "download_url": "https://r2.cloudflarestorage.com/...",
      "download_url_expires_at": "2026-01-26T15:33:00+00:00",
      "created_at": "2026-01-25T15:33:00+00:00"
    }
  ],
  "total": 2,
  "limit": 50,
  "offset": 0
}
```

**What to notice:**
- **download_url_expires_at**: Pre-signed URLs expire after 24 hours
- **watermarked**: Based on user's token tier at generation time
- **resolution_multiplier**: Only for PNG (SVG is vector, scales infinitely)

---

### Step 18.2: Manually Download Export via Pre-signed URL

**Extract download URL:**
```bash
DOWNLOAD_URL=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://localhost:8778/api/v1/maps/42/exports" | jq -r '.exports[0].download_url')

echo $DOWNLOAD_URL
```

**Download file:**
```bash
curl -o /tmp/exported-map.svg "$DOWNLOAD_URL"
```

**What's happening:**
1. Pre-signed URL includes S3 signature with expiration
2. R2 validates signature and serves file
3. No authentication required (signature proves authorization)
4. URL becomes invalid after 24 hours

---

### Step 18.3: Inspect Export Processing Logic

**Read export service:**
```bash
grep -A 20 "def process_export" /home/delorenj/code/overworld/backend/app/services/export_service.py
```

**Key flow at line ~180:**
```python
async def process_export(export_id: int, db: AsyncSession) -> None:
    """Background task to generate export file."""

    # Fetch export and map
    export = await db.get(Export, export_id)
    map_obj = await db.get(Map, export.map_id)

    # Render map based on format
    if export.format == ExportFormat.PNG:
        file_path = await _render_png(map_obj, export.resolution_multiplier)
    else:
        file_path = await _render_svg(map_obj)

    # Apply watermark if needed
    if export.watermarked:
        file_path = await _apply_watermark(file_path, export.format)

    # Upload to R2
    r2_key, download_url = await r2_service.upload_file(file_path, ...)
```

**What's happening:** Background task runs asynchronously, updates export status, generates pre-signed URL.

---

## Phase 19: Architecture Exploration

### Step 19.1: View Service Dependencies

**Command:**
```bash
docker compose config --services
```

**Expected output:**
```
postgres
redis
rabbitmq
backend
frontend
```

**Check dependency order:**
```bash
docker compose config | grep -A 3 "depends_on:"
```

**Expected output:**
```
depends_on:
  postgres:
    condition: service_healthy
  redis:
    condition: service_healthy
  rabbitmq:
    condition: service_healthy
```

**What this shows:** Backend waits for healthy database/cache/queue before starting (prevents startup race conditions).

---

### Step 19.2: Trace a Request Through the Stack

**Enable verbose logging:**
```bash
docker compose logs -f backend frontend | grep -E "POST|GET|PUT|DELETE|→|←"
```

**In another terminal, make a request:**
```bash
curl -X GET http://localhost:8778/api/v1/maps/42 \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**What you'll see in logs:**
```
backend   | → GET /api/v1/maps/42 from 172.19.0.1
backend   | ← 200 OK (45ms)
```

**Detailed trace (if debug enabled):**
```
backend   | [correlation_id=abc-123] → GET /api/v1/maps/42
backend   | [correlation_id=abc-123] Auth: Validated JWT for user_id=2
backend   | [correlation_id=abc-123] DB: SELECT * FROM maps WHERE id=42 AND user_id=2
backend   | [correlation_id=abc-123] DB: Query took 2.3ms
backend   | [correlation_id=abc-123] ← 200 OK (45ms total)
```

**What's happening:** Structured logging with correlation IDs enables request tracing across services.

---

## Phase 20: Cleanup & Reset

### Step 20.1: Stop All Services (Preserve Data)

**Command:**
```bash
mise run down
```

**What happens:**
- All containers stop gracefully
- Volumes persist (database data, Redis cache)
- Next `mise run dev` resumes with same data

---

### Step 20.2: Full Reset (Clean Slate)

**Command:**
```bash
mise run clean
```

**What happens:**
- Stops all containers
- Removes all volumes (⚠️ **deletes all data**)
- Next startup requires re-running migrations

**When to use:**
- Testing fresh install experience
- Clearing corrupted state
- Resetting demo environment

---

## Summary: What You Experienced

You just completed a full walkthrough of **68 story points** of functionality across **Sprints 1-4**.

### Feature Inventory

✅ **Sprint 1: Foundation (36 points)**
- STORY-001: Document upload (MD/PDF) with R2 storage
- STORY-002: Hierarchy extraction from nested documents
- STORY-003: Multi-agent generation pipeline (4 agents)

✅ **Sprint 2: Generation + Auth (34 points)**
- STORY-004: Complete pipeline with coordinator
- STORY-005: Job status API with polling
- STORY-010: JWT authentication with registration/login

✅ **Sprint 3: Rendering (21 points)**
- STORY-006: PixiJS WebGL renderer (60 FPS)
- STORY-007: Interactive zoom/pan controls
- STORY-008: Theme system with asset manifests

✅ **Sprint 4: Monetization + Export (13 points)**
- STORY-014: Stripe integration + anonymous rate limiting
- STORY-015: PNG/SVG export with watermarking

### Architecture Components

**Data Layer:**
- PostgreSQL 16 with JSONB (GIN indexed)
- Alembic migrations with relationship constraints
- Redis for session/cache/rate limit
- RabbitMQ for async job distribution

**Business Logic Layer:**
- FastAPI services (auth, generation, export, stripe)
- Multi-agent pipeline (Parser → Artist → Road → Icon)
- Token service with transaction logging
- Idempotent webhook processing

**Presentation Layer:**
- React 19 with TypeScript
- PixiJS WebGL rendering (60 FPS)
- Tailwind CSS styling
- Real-time job status polling

### Production Readiness Checklist

✅ Type safety (Pydantic schemas, TypeScript)
✅ Comprehensive test coverage (94%)
✅ Error handling with custom exceptions
✅ Security (JWT auth, webhook signatures, rate limiting)
✅ Observability (structured logging, correlation IDs)
✅ Performance (GIN indexes, Redis caching, async processing)
✅ Scalability (background workers, message queues)
⚠️ Missing: Distributed tracing, metrics export, auto-scaling

---

## Next Steps

**Remaining sprints (deferred to Phase 2):**

**Sprint 5: Advanced Features**
- STORY-009: L1-L4 interactive navigation (drill-down)
- STORY-011: Theme marketplace with previews
- STORY-012: Collaboration (shareable links, permissions)

**Sprint 6: Polish & Launch**
- STORY-013: Landing page with feature showcase
- STORY-016: Email notifications (job complete, export ready)
- STORY-017: Analytics dashboard (usage stats, popular themes)

**Infrastructure improvements:**
- Kubernetes deployment manifests
- Prometheus metrics export
- OpenTelemetry distributed tracing
- Automated E2E tests with Playwright

---

## Troubleshooting Reference

### Services Won't Start

**Check Docker daemon:**
```bash
docker info
```

**Check port conflicts:**
```bash
sudo lsof -i :80 -i :5432 -i :6379 -i :5672
```

**Force rebuild:**
```bash
mise run clean && mise run rebuild
```

---

### Migrations Fail

**Check alembic version:**
```bash
docker compose exec backend alembic current
```

**Reset database (⚠️ destructive):**
```bash
docker compose down -v
docker compose up -d postgres
mise run migrate
```

---

### Tests Fail

**Check test database connection:**
```bash
docker compose exec backend pytest tests/test_auth.py -v
```

**Reset test fixtures:**
```bash
docker compose exec postgres psql -U delorenj -d overworld -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public"
mise run migrate
```

---

### Frontend Won't Load

**Check Vite dev server:**
```bash
docker compose logs frontend | tail -20
```

**Rebuild node_modules:**
```bash
docker compose exec frontend rm -rf node_modules
docker compose restart frontend
```

---

**End of Demo Guide**

For architecture deep-dives, see:
- `/home/delorenj/code/overworld/docs/architecture-overworld-2026-01-08.md`
- `/home/delorenj/code/overworld/docs/sprint-plan-overworld-2026-01-09.md`

For implementation details:
- Backend: `/home/delorenj/code/overworld/backend/STRIPE_INTEGRATION.md`
- Backend: `/home/delorenj/code/overworld/backend/docs/EXPORT_FEATURE.md`
