# Sprint Plan: Overworld

**Date:** 2026-01-09
**Scrum Master:** BMAD Method v6
**Project Level:** 2 (Medium - 5-15 stories)
**Total Stories:** 17 stories (15 features + 2 infrastructure)
**Total Points:** 103 points
**Planned Sprints:** 3 sprints (6 weeks)
**Team:** 2-3 developers
**Sprint Length:** 2 weeks

---

## Executive Summary

This sprint plan delivers the Overworld MVP: an AI-powered platform that transforms linear project documentation into interactive 8/16-bit overworld maps. The MVP focuses on core differentiators (multi-agent map generation + 60 FPS PixiJS rendering) with basic auth, monetization, and export functionality.

**Key Metrics:**
- **Total Stories:** 17 stories
- **Total Points:** 103 points
- **Sprints:** 3 sprints (6 weeks estimated)
- **Team Capacity:** 35 points per sprint (2.5 devs, 6 productive hours/day)
- **Target Completion:** End of Week 6 (early March 2026)

**MVP Scope:**
- ✅ Document upload (MD/PDF) with hierarchy extraction
- ✅ Multi-agent AI pipeline (Parser → Artist → Road → Icon → Coordinator)
- ✅ PixiJS WebGL rendering with zoom/pan (60 FPS)
- ✅ User authentication (email + OAuth2)
- ✅ Token-based monetization with Stripe
- ✅ Map export (PNG/SVG with watermark)
- ⏸️ Deferred to Phase 2: L1-L4 interactive navigation, custom themes, shareable links

---

## Sprint Overview

| Sprint | Goal | Stories | Points | Dates |
|--------|------|---------|--------|-------|
| **Sprint 1** | Foundation & Core Pipeline | 6 | 36 / 35 | Weeks 1-2 |
| **Sprint 2** | Complete Generation + Auth | 5 | 34 / 35 | Weeks 3-4 |
| **Sprint 3** | Monetization + Launch Prep | 6 | 33 / 33 | Weeks 5-6 |

---

## Story Inventory

### Infrastructure Stories

#### STORY-000: Development Environment Setup

**Epic:** Infrastructure
**Priority:** Must Have (Prerequisite)
**Points:** 5

**User Story:**
As a developer, I want a containerized development environment so that I can iterate quickly with consistent dependencies

**Acceptance Criteria:**
- [ ] Docker Compose setup with FastAPI backend, React frontend, PostgreSQL, Redis, RabbitMQ
- [ ] Hot reload working for both frontend (Vite) and backend (uvicorn --reload)
- [ ] Database migrations via Alembic
- [ ] Environment variables via mise + 1Password integration
- [ ] README with setup instructions (`mise run dev` to start all services)
- [ ] Pre-commit hooks configured (ruff, eslint, prettier)

**Technical Notes:**
- Docker Compose per architecture: traefik as reverse proxy, separate networks for security
- mise tasks: `dev`, `test`, `migrate`, `seed`
- 1Password CLI integration for secrets (Stripe keys, OpenRouter key)

**Dependencies:** None

---

#### STORY-INF-001: Core Infrastructure & Database Schema

**Epic:** Infrastructure
**Priority:** Must Have (Prerequisite)
**Points:** 5

**User Story:**
As a developer, I want the database schema and message queue configured so that I can build features on solid foundations

**Acceptance Criteria:**
- [ ] PostgreSQL schema created via Alembic migration:
  - `users` (id, email, password_hash, oauth_provider, oauth_id, is_verified, created_at)
  - `token_balance` (user_id FK, free_tokens, purchased_tokens, last_reset_at)
  - `transactions` (id, user_id FK, type enum, tokens_delta, stripe_event_id, metadata JSONB)
  - `maps` (id, user_id FK, name, hierarchy JSONB, theme_id FK, watermarked, created_at)
  - `generation_jobs` (id, map_id FK, user_id FK, status enum, agent_state JSONB, progress_pct, error_msg)
  - `themes` (id, name, description, is_premium, asset_manifest JSONB)
- [ ] Indexes created (idx_users_email, idx_maps_user_created, idx_generation_jobs_status, idx_maps_hierarchy_gin)
- [ ] RabbitMQ exchanges and queues configured:
  - Exchange: `generation` (topic)
  - Queues: `generation.pending`, `generation.retry`, `generation.dlq`
  - Bindings configured with routing keys
- [ ] Redis connection pooling configured (redis-py, max connections: 50)
- [ ] Cloudflare R2 buckets created via CLI:
  - `overworld-uploads` (uploaded docs)
  - `overworld-maps` (generated map JSON)
  - `overworld-themes` (theme assets)
  - `overworld-exports` (PNG/SVG exports)

**Technical Notes:**
- SQLAlchemy models in `backend/app/models/`
- Alembic migration: `alembic revision --autogenerate -m "initial schema"`
- RabbitMQ topology via pika library, defined in `backend/app/core/queue.py`

**Dependencies:** STORY-000

---

### EPIC-001: Document Ingestion & Parsing

#### STORY-001: Document Upload & Storage

**Epic:** EPIC-001 (Document Ingestion)
**Priority:** Must Have
**Points:** 5

**User Story:**
As a user, I want to upload markdown or PDF documents so that I can generate maps from my project documentation

**Acceptance Criteria:**
- [ ] POST /api/v1/documents/upload endpoint:
  - Accepts multipart/form-data with file field
  - Validates file type via magic number (not just extension)
  - MD max 5MB, PDF max 10MB
  - Returns: `{document_id, filename, size_bytes, r2_url, uploaded_at}`
- [ ] File validation:
  - MD: Check for `text/markdown` or `text/plain` magic number
  - PDF: Check for `%PDF-` header
  - Reject other file types with 400 Bad Request
- [ ] Upload to Cloudflare R2:
  - Path: `/uploads/{user_id}/{timestamp}/{filename}`
  - boto3 client for S3-compatible API
  - Pre-signed URL generation for download (1-hour expiry)
- [ ] Frontend drag-and-drop upload component:
  - React dropzone library
  - Upload progress bar
  - Error display for invalid files
  - Success message with document preview link
- [ ] Error handling:
  - File too large → 413 Payload Too Large
  - Invalid format → 400 Bad Request with helpful message
  - R2 upload fails → Retry 3x, then 500 Internal Server Error

**Technical Notes:**
- FastAPI `UploadFile` for streaming uploads (memory-efficient)
- boto3 for R2: `s3_client.upload_fileobj()`
- React: `react-dropzone` library

**Dependencies:** STORY-INF-001

---

#### STORY-002: Hierarchy Extraction from Documents

**Epic:** EPIC-001 (Document Ingestion)
**Priority:** Must Have
**Points:** 5

**User Story:**
As a user, I want the system to extract hierarchical structure from my markdown documents so that my milestones are properly mapped

**Acceptance Criteria:**
- [ ] Parse markdown headers (H1-H4) as hierarchy levels:
  - H1 → L0 (Product name)
  - H2 → L1 (Milestones/Phases)
  - H3 → L2 (Epics/Features)
  - H4 → L3 (Tasks)
- [ ] Extract Obsidian Tasks syntax:
  - `- [ ]` → Incomplete task
  - `- [x]` → Completed task
  - `📅 YYYY-MM-DD` → Due date extraction
  - `#tag` → Tag extraction
- [ ] Map to L0-L4 structure:
  - L0: Entire product (single root)
  - L1: Milestones (disconnected islands for MVP, sequential for Phase 2)
  - L2: Epics on roads
  - L3: Tasks as landmarks
  - L4: Sub-tasks (not rendered in MVP, stored for Phase 2)
- [ ] Output structured JSON:
  ```json
  {
    "L0": {"title": "Product Name", "id": "root"},
    "L1": [
      {"id": "m1", "title": "Milestone 1", "children": [...]}
    ]
  }
  ```
- [ ] Handle nested lists up to 4 levels deep
- [ ] Store hierarchy in `maps.hierarchy` JSONB column with GIN index
- [ ] PDF parsing (optional for MVP, defer if complex):
  - Extract text via pypdf
  - Basic header detection (larger font = higher level)

**Technical Notes:**
- Python libraries: `markdown`, `re` (regex for Obsidian syntax)
- Recursive tree building algorithm
- JSONB storage in PostgreSQL with `USING GIN (hierarchy)` index

**Dependencies:** STORY-001

---

### EPIC-002: Core Map Generation Pipeline

#### STORY-003: Generation Orchestrator & Job Queue

**Epic:** EPIC-002 (Map Generation)
**Priority:** Must Have
**Points:** 8

**User Story:**
As a user, I want my map generation to process asynchronously so that I don't have to wait for the API to respond

**Acceptance Criteria:**
- [ ] POST /api/v1/maps/generate endpoint:
  - Accepts: `{document_id, theme_id (optional, defaults to smb3), options: {scatter_threshold}}`
  - Creates `generation_jobs` record with status='pending'
  - Publishes job to RabbitMQ `generation.pending` queue
  - Returns 202 Accepted: `{job_id, status: 'pending', queue_position, estimated_wait_seconds}`
- [ ] RabbitMQ worker process:
  - Consumes jobs from `generation.pending` queue
  - Updates job status to 'processing'
  - Executes multi-agent pipeline (STORY-004)
  - On success: status='completed', map_id populated
  - On failure: status='failed', error_msg populated, publish to `generation.dlq`
- [ ] Job state machine:
  - States: pending → processing → completed/failed
  - Transitions logged to structured logs
  - Invalid transitions rejected
- [ ] Failed jobs handling:
  - Transient failures (timeout, API error) → Retry queue (max 3 attempts)
  - Permanent failures (invalid document) → Dead-letter queue
  - All failures: Refund tokens automatically
- [ ] 120-second timeout per job:
  - Worker process enforces timeout via asyncio.wait_for()
  - Timeout triggers status='failed', error='Generation timeout exceeded'
  - Tokens refunded, user notified
- [ ] GET /api/v1/jobs/{job_id} endpoint:
  - Returns job status, progress, error details

**Technical Notes:**
- Pydantic models: `GenerationJobCreate`, `GenerationJobResponse`
- RabbitMQ: pika library, confirm mode enabled (at-least-once delivery)
- Worker: Background process in `backend/app/workers/generation_worker.py`
- asyncio for timeout enforcement

**Dependencies:** STORY-INF-001, STORY-002

---

#### STORY-004: Multi-Agent Pipeline Foundation

**Epic:** EPIC-002 (Map Generation)
**Priority:** Must Have
**Points:** 8

**User Story:**
As a system, I want a coordinated multi-agent pipeline so that map generation proceeds through well-defined stages

**Acceptance Criteria:**
- [ ] Agent base class: `BaseAgent` with `execute(context: JobContext) -> AgentResult` interface
- [ ] JobContext dataclass:
  - `job_id`, `user_id`, `document_url`, `hierarchy`, `theme`, `options`
  - `agent_state: dict` (checkpointing)
- [ ] AgentResult dataclass:
  - `success: bool`, `data: dict`, `error: Optional[str]`
- [ ] OpenRouter client integration:
  - SDK: `openrouter-py` library
  - API key from environment (1Password via mise)
  - Model selection: Fast model for Parser (gpt-3.5-turbo), quality model for Artist (gpt-4)
  - Cost tracking: Log tokens used per request
- [ ] Agent state persistence:
  - After each agent completes, save result to `generation_jobs.agent_state` JSONB
  - On retry/resume, load previous state and skip completed agents
- [ ] Checkpoint/resume support:
  - If job fails mid-pipeline, can resume from last completed agent
  - Example: Parser complete, Artist failed → Resume at Artist stage
- [ ] Structured logging:
  - Log format: `{"timestamp": "...", "job_id": "...", "agent": "Parser", "stage": "starting", "elapsed_ms": 0}`
  - Correlation ID: job_id used throughout pipeline
  - Logs sent to stdout (captured by Docker logs)
- [ ] Error handling with retry logic:
  - OpenRouter API errors: Retry 3x with exponential backoff (1s, 2s, 4s)
  - Rate limit (429): Exponential backoff up to 60s
  - Permanent errors (4xx except 429): No retry, fail immediately

**Technical Notes:**
- Agno framework for agent orchestration OR custom implementation
- OpenRouter SDK: `openrouter` package, async client
- Redis for agent state caching (faster than DB reads)
- Python `structlog` library for structured logging

**Dependencies:** STORY-003

---

#### STORY-005: Parser & Artist Agents

**Epic:** EPIC-002 (Map Generation)
**Priority:** Must Have
**Points:** 5

**User Story:**
As a generation pipeline, I want the Parser agent to validate hierarchy and the Artist agent to select the default SMB3 theme

**Acceptance Criteria:**
- [ ] **Parser Agent:**
  - Input: Hierarchy JSON from STORY-002
  - Validation: Check for at least 1 L1 milestone, max 50 milestones (MVP limit)
  - Counts: Total milestones, levels detected
  - Output: `{valid: true, milestone_count: N, levels: [0,1,2,3]}`
  - Execution time: <5s target
- [ ] **Artist Agent:**
  - Input: Milestone count, theme preference (defaults to 'smb3')
  - MVP: Hardcoded SMB3 theme (skip LLM generation for speed)
  - Output: Theme configuration JSON:
    ```json
    {
      "theme_id": "smb3",
      "colors": {"road": "#D2691E", "bg": "#6B8CFF", "milestone": "#FFD700"},
      "textures": {"road": "pixelated-brown", "milestone": "numbered-circle"},
      "icon_set": "8bit-sprites"
    }
    ```
  - Execution time: <10s target (mostly hardcoded, minimal LLM use)
- [ ] Both agents log execution time to structured logs
- [ ] Agent outputs stored in `generation_jobs.agent_state` JSONB:
  - `agent_state.parser = {...}`
  - `agent_state.artist = {...}`

**Technical Notes:**
- Parser: Python logic, no LLM needed (just validation)
- Artist: MVP hardcoded theme, Phase 2 adds LLM-generated style variations
- OpenRouter fast model if LLM needed (gpt-3.5-turbo for speed)

**Dependencies:** STORY-004

---

#### STORY-006: Road Generator Agent (Spline Math)

**Epic:** EPIC-002 (Map Generation)
**Priority:** Must Have
**Points:** 8

**User Story:**
As a generation pipeline, I want the Road Generator to create a curved, stylized path so that milestones can be placed along a visually appealing route

**Acceptance Criteria:**
- [ ] Generate Bezier/spline curve:
  - No straight lines (enforced via control point constraints)
  - Organic, curvy aesthetic (similar to Super Mario World overworld maps)
  - Use scipy.interpolate for spline generation (B-spline or Bezier)
- [ ] Arc-length parameterization:
  - Even spacing of milestones along curve (not Euclidean spacing)
  - Parameterize spline from 0.0 (start) to 1.0 (end)
  - Sample N points where N = milestone_count from Parser
- [ ] Output ordered coordinate points:
  - JSON array: `[{t: 0.0, x: 100, y: 200}, {t: 0.1, x: 150, y: 220}, ...]`
  - Coordinates in pixel space (canvas size: 1920x1080 default)
- [ ] Canvas bounds checking:
  - All coordinates stay within canvas with 100px margin
  - If curve exits bounds, regenerate with adjusted control points
- [ ] Scatter threshold:
  - Offset milestones from exact spline path by random offset within threshold
  - Threshold from options.scatter_threshold (default: 20px)
  - Adds organic "hand-placed" feel vs. perfectly aligned
- [ ] Road texture metadata:
  - Texture type from Artist theme (e.g., "pixelated-brown")
  - Texture width: 40px (8-bit style)
- [ ] Generation time: <8s target
  - LLM generates control points (4-6 points), Python computes spline

**Technical Notes:**
- scipy.interpolate.splprep for spline fitting
- NumPy for coordinate math and arc-length computation
- LLM prompt: "Generate 5 control points for a curvy Bezier path that resembles a Super Mario World overworld map. Points should create an organic, winding route."
- Deterministic spline computation (no randomness except scatter)

**Dependencies:** STORY-005

---

#### STORY-007: Icon Placer Agent & Coordinator

**Epic:** EPIC-002 (Map Generation)
**Priority:** Must Have
**Points:** 5

**User Story:**
As a generation pipeline, I want milestones placed along the road as numbered circles so that users can see their project progression

**Acceptance Criteria:**
- [ ] **Icon Placer Agent:**
  - Input: Spline coordinates from Road Generator, milestone list from Parser
  - For each milestone:
    - Assign coordinate from spline (in document order)
    - Assign number (1, 2, 3, ...) matching sequence
    - Label from hierarchy (milestone title)
  - Output: Milestones array:
    ```json
    [
      {"number": 1, "pos": {"x": 100, "y": 200}, "label": "Project Setup"},
      {"number": 2, "pos": {"x": 150, "y": 220}, "label": "Backend API"},
      ...
    ]
    ```
  - Numbering sequence matches document order (L1 milestones top-to-bottom)
  - Circles evenly spaced along spline (no overlapping)
  - MVP: Numbered circles only (custom icons deferred to Phase 2)
- [ ] **Coordinator Agent:**
  - Orchestrates full pipeline: Parser → Artist → Road → Icon
  - Sequential execution (each waits for previous)
  - Validates each stage before proceeding:
    - Parser: Check `valid: true`
    - Artist: Check theme_id exists
    - Road: Check coordinate count matches milestone count
    - Icon: Check no overlapping positions
  - Collects all outputs into final map data structure:
    ```json
    {
      "theme": {...},
      "road": {"spline": [...], "texture": "..."},
      "milestones": [...],
      "metadata": {"milestone_count": 10, "generation_time_ms": 25000}
    }
    ```
- [ ] Final map data saved to Cloudflare R2:
  - Path: `/maps/{map_id}/generated/{timestamp}.json`
  - URL stored in `maps` table
- [ ] Total pipeline time: <30s (p95 target)
  - Parser: <5s
  - Artist: <10s
  - Road: <8s
  - Icon: <2s
  - Overhead: <5s

**Technical Notes:**
- Coordinator pattern: Sequential async execution with validation gates
- Icon placement: Simple array mapping (no complex collision detection for MVP)
- Final JSON written to R2, map record updated with r2_url

**Dependencies:** STORY-006

---

#### STORY-008: PixiJS Map Renderer

**Epic:** EPIC-002 (Map Generation)
**Priority:** Must Have
**Points:** 8

**User Story:**
As a user, I want to view my generated map with smooth zoom/pan interactions so that I can explore my project roadmap

**Acceptance Criteria:**
- [ ] PixiJS Application initialized:
  - WebGL renderer (fallback to Canvas if WebGL unavailable)
  - Canvas size: 1920x1080 (responsive scaling to fit container)
  - Antialiasing enabled: `antialias: true`
  - HiDPI support: `resolution: window.devicePixelRatio`
- [ ] Load map JSON from R2:
  - Fetch from map.r2_url
  - Parse JSON: theme, road, milestones
- [ ] Render road as textured sprite:
  - Draw spline path using PIXI.Graphics (or pre-rendered sprite)
  - Apply texture from theme (pixelated brown for SMB3)
  - Line width: 40px
- [ ] Render milestone circles with numbers:
  - PIXI.Graphics circle at each milestone.pos
  - Fill color: Gold (#FFD700 for SMB3)
  - Stroke: Black, 2px
  - Number text: PIXI.Text with 8-bit font (e.g., "Press Start 2P")
  - Numbers centered on circles
- [ ] Zoom interactions:
  - Mouse wheel: Zoom in/out (0.5x to 3x scale)
  - Pinch gesture: Mobile zoom (touch events)
  - Clamp zoom to min/max
- [ ] Pan interactions:
  - Click-drag: Pan canvas (mouse)
  - Touch-drag: Pan canvas (mobile)
  - Bounds checking: Prevent panning beyond map edges
- [ ] Performance: 60 FPS sustained
  - Monitor via `stats.js` during dev
  - No frame drops during zoom/pan
  - Sprite batching enabled (PixiJS default)
- [ ] Viewport culling:
  - Only render sprites within visible viewport + 200px margin
  - Essential for large maps (100+ milestones, Phase 2)
- [ ] Retina/HiDPI support:
  - Detect `devicePixelRatio`
  - Scale canvas appropriately (no blurry sprites)

**Technical Notes:**
- PixiJS v7+ for latest WebGL features
- React integration: `useRef` for canvas container, `useEffect` for PixiJS setup/teardown
- PIXI.Container for hierarchical transforms (zoom/pan applied to root container)
- Object pooling for milestones (reuse PIXI.Graphics instances)
- 8-bit font: Load "Press Start 2P" from Google Fonts

**Dependencies:** STORY-007

---

#### STORY-009: WebSocket Real-Time Progress

**Epic:** EPIC-002 (Map Generation)
**Priority:** Should Have
**Points:** 5

**User Story:**
As a user, I want to see real-time progress updates during generation so that I know the system is working

**Acceptance Criteria:**
- [ ] WebSocket endpoint: `/ws/generation/{job_id}`
  - FastAPI WebSocket route
  - Authenticate via JWT token (query param: ?token={access_token})
  - Connection established on generation start
- [ ] Agent progress published to Redis pub/sub:
  - Each agent publishes progress messages to channel: `generation:{job_id}:progress`
  - Message format:
    ```json
    {
      "stage": "parsing",
      "progress_pct": 0.25,
      "message": "Extracting hierarchy from document..."
    }
    ```
  - Stages: "parsing" (0-25%), "styling" (25-50%), "roads" (50-75%), "icons" (75-90%), "finalizing" (90-100%)
- [ ] WebSocket broadcasts progress messages:
  - FastAPI WebSocket subscribes to Redis channel
  - Broadcasts each message to connected client
  - Client receives updates every 2-5 seconds (agent checkpoints)
- [ ] Frontend progress bar:
  - React component with progress bar (0-100%)
  - Stage name displayed above bar
  - Message displayed below bar
  - Updates in real-time as WebSocket receives messages
- [ ] Completion message:
  - Final message: `{stage: "complete", progress_pct: 100, map_id: "...", map_url: "/maps/{map_id}"}`
  - Frontend redirects to map viewer automatically
- [ ] Error messages:
  - Error message: `{stage: "error", error: "Parsing failed: invalid markdown structure", details: {...}}`
  - Frontend displays error with "Retry" button
  - Tokens refunded automatically (handled in STORY-003)
- [ ] Connection resilience:
  - Auto-reconnect on disconnect (exponential backoff: 1s, 2s, 4s, max 10s)
  - Display "Reconnecting..." indicator during reconnect attempts

**Technical Notes:**
- FastAPI WebSocket: async def websocket_endpoint(websocket: WebSocket)
- Redis pub/sub: `redis-py` async client, subscribe to pattern `generation:*:progress`
- React WebSocket: `useWebSocket` custom hook or `react-use-websocket` library
- Progress bar: HTML5 `<progress>` element or custom CSS animation

**Dependencies:** STORY-007, STORY-008

---

### EPIC-004: User Management & Authentication

#### STORY-010: User Authentication (Registration + Login)

**Epic:** EPIC-004 (User Management)
**Priority:** Must Have
**Points:** 8

**User Story:**
As a user, I want to create an account and log in so that I can save my generated maps

**Acceptance Criteria:**
- [ ] **POST /api/v1/auth/register:**
  - Input: `{email, password, confirm_password}`
  - Validation: Email format, password strength (8+ chars, 1 uppercase, 1 number), passwords match
  - Create user record with `is_verified=false`
  - Hash password with bcrypt (cost factor 12)
  - Generate email verification token (random UUID, 24h expiry)
  - Send verification email via SendGrid/Resend
  - Return 201 Created: `{user_id, email, message: "Verification email sent"}`
- [ ] **Email verification flow:**
  - Email contains link: `/verify-email?token={verification_token}`
  - GET /api/v1/auth/verify-email?token={token}
  - Validate token (check expiry, check user exists)
  - Set `is_verified=true`
  - Return 200 OK: `{message: "Email verified, you can now log in"}`
- [ ] **POST /api/v1/auth/login:**
  - Input: `{email, password}`
  - Validate: User exists, password matches (bcrypt.verify), is_verified=true
  - Generate JWT access token (24h expiry): `{user_id, email, is_premium, exp, iat}`
  - Generate JWT refresh token (30d expiry): `{user_id, exp, iat}`
  - Store refresh token in Redis: key=`refresh:{user_id}`, value=token_hash, TTL=30d
  - Return 200 OK: `{access_token, refresh_token, user: {id, email, is_premium}}`
- [ ] **POST /api/v1/auth/refresh:**
  - Input: `{refresh_token}`
  - Validate refresh token (signature, expiry, exists in Redis)
  - Generate new access token (24h expiry)
  - Generate new refresh token (rotation: invalidate old, store new)
  - Return 200 OK: `{access_token, refresh_token}`
- [ ] **JWT token structure:**
  - Algorithm: HS256 (symmetric, secret from environment)
  - Access token claims: `{user_id, email, is_premium, exp, iat}`
  - Refresh token claims: `{user_id, exp, iat}`
- [ ] **Rate limiting:**
  - Login endpoint: 10 attempts per 15 minutes per IP
  - Redis counter: key=`rate_limit:login:{ip}`, increment on each attempt, TTL=15min
  - After 10 attempts: Return 429 Too Many Requests
- [ ] **Frontend:**
  - Registration form: Email, Password, Confirm Password, Submit
  - Login form: Email, Password, Submit
  - Token storage: localStorage for access_token, httpOnly cookie for refresh_token (if possible)
  - Auto-redirect to dashboard on successful login

**Technical Notes:**
- FastAPI-Users library for auth scaffolding (optional, can build custom)
- bcrypt library: `bcrypt.hashpw()` with rounds=12
- JWT library: `pyjwt` or FastAPI built-in OAuth2PasswordBearer
- Redis for rate limiting and refresh token storage
- Email service: SendGrid or Resend API

**Dependencies:** STORY-INF-001

---

#### STORY-011: OAuth2 Providers (Google + GitHub)

**Epic:** EPIC-004 (User Management)
**Priority:** Should Have
**Points:** 5

**User Story:**
As a user, I want to sign in with Google or GitHub so that I don't have to create another password

**Acceptance Criteria:**
- [ ] **GET /api/v1/auth/oauth/{provider}:** (provider = google | github)
  - Redirect to OAuth provider's consent screen
  - Include PKCE challenge (code_challenge, code_challenge_method=S256)
  - Include state parameter (random UUID, stored in Redis with 5-min TTL)
  - Scopes: Google (email, profile), GitHub (user:email)
- [ ] **GET /api/v1/auth/oauth/{provider}/callback:**
  - Receive: `code`, `state` from OAuth provider
  - Validate state parameter (check exists in Redis, then delete)
  - Exchange code for access_token (with PKCE verifier)
  - Fetch user profile from provider (email, name, avatar)
  - Check if user exists by `oauth_provider` + `oauth_id`:
    - If exists: Log in user (generate JWT tokens)
    - If not exists: Create user with `oauth_provider`, `oauth_id`, `is_verified=true` (OAuth email is pre-verified)
  - If email matches existing non-OAuth user: Link OAuth account to existing user
  - Return JWT tokens (same as login)
- [ ] **PKCE flow security:**
  - Generate code_verifier (random 43-128 char string)
  - Compute code_challenge = base64url(sha256(code_verifier))
  - Store code_verifier in session/Redis for callback
- [ ] **State parameter validation:**
  - Generate random UUID on initiation
  - Store in Redis: key=`oauth_state:{state}`, TTL=5min
  - On callback: Check state exists in Redis, then delete (prevent replay)
- [ ] **Account linking:**
  - If OAuth email matches existing email user:
    - Prompt: "Link {provider} account to existing account?"
    - If yes: Update user record with oauth_provider, oauth_id
    - If no: Create separate OAuth account
- [ ] **Frontend:**
  - Google login button: Redirects to /api/v1/auth/oauth/google
  - GitHub login button: Redirects to /api/v1/auth/oauth/github
  - Callback handler: Parse tokens from redirect, store in localStorage, redirect to dashboard

**Technical Notes:**
- python-social-auth library or custom OAuth2 client
- OAuth2 client credentials stored in environment (Google: client_id, client_secret; GitHub: client_id, client_secret)
- PKCE: `secrets.token_urlsafe(64)` for code_verifier
- State: `uuid.uuid4()` for state parameter

**Dependencies:** STORY-010

---

#### STORY-012: User Dashboard

**Epic:** EPIC-004 (User Management)
**Priority:** Must Have
**Points:** 5

**User Story:**
As a user, I want a dashboard showing my generated maps and token balance so that I can manage my account

**Acceptance Criteria:**
- [ ] **GET /api/v1/users/me:**
  - Requires JWT authentication (Authorization: Bearer {access_token})
  - Returns: `{id, email, is_premium, token_balance: {free_tokens, purchased_tokens}, created_at}`
- [ ] **GET /api/v1/maps:**
  - Requires JWT authentication
  - Returns user's maps (filtered by user_id)
  - Pagination: `?page=1&page_size=20` (default page_size=20)
  - Response:
    ```json
    {
      "maps": [
        {
          "id": "...",
          "name": "My Project Roadmap",
          "thumbnail_url": "https://r2.../thumb.png",
          "created_at": "2026-01-05T12:00:00Z",
          "status": "completed"
        }
      ],
      "total": 42,
      "page": 1,
      "page_size": 20
    }
    ```
  - Sort by: created_at DESC (newest first)
- [ ] **Map metadata:**
  - Each map includes thumbnail (generated during export or placeholder)
  - name (user-editable via PUT /api/v1/maps/{map_id})
  - created_at timestamp
  - status: 'pending', 'processing', 'completed', 'failed'
- [ ] **Frontend dashboard layout:**
  - Header: User email, token balance prominently displayed
  - Token balance: "10 free tokens | 50 purchased tokens | Total: 60"
  - Quick action: "Generate New Map" button (redirects to upload page)
  - Map grid: 3-column card grid (responsive: 2 cols on tablet, 1 col on mobile)
  - Each card: Thumbnail image, map name, created date, status badge
  - Click card → Navigate to map viewer (/maps/{map_id})
  - Pagination controls: Previous, Next, Page X of Y
- [ ] **Token balance display:**
  - Color-coded: Green if >5 tokens, Orange if 1-5 tokens, Red if 0 tokens
  - Tooltip on hover: "Free tokens reset on 1st of each month"
  - "Buy More Tokens" button if balance low

**Technical Notes:**
- React dashboard component with grid layout (CSS Grid or Tailwind)
- Pagination: React state for current page, API call on page change
- Thumbnail generation: Deferred to export story (STORY-015), use placeholder for MVP

**Dependencies:** STORY-010, STORY-008

---

### EPIC-005: Monetization & Token System

#### STORY-013: Token System (Balance + Consumption)

**Epic:** EPIC-005 (Monetization)
**Priority:** Must Have
**Points:** 5

**User Story:**
As a user, I want a token balance that resets monthly so that I can generate maps for free up to my limit

**Acceptance Criteria:**
- [ ] **New user token grant:**
  - On user registration (STORY-010), create `token_balance` record:
    - `user_id`, `free_tokens=10`, `purchased_tokens=0`, `last_reset_at=NOW()`
- [ ] **Monthly token reset:**
  - Cron job runs daily at 00:00 UTC (via `apscheduler` or K8s CronJob)
  - For each user where `last_reset_at < first day of current month`:
    - Set `free_tokens=10`
    - Set `last_reset_at=NOW()`
  - Purchased tokens never reset (persist across months)
- [ ] **GET /api/v1/tokens/balance:**
  - Requires JWT authentication
  - Returns: `{free_tokens, purchased_tokens, total: free_tokens + purchased_tokens, next_reset_date: "2026-02-01"}`
- [ ] **Token consumption (map generation):**
  - Pre-flight check in POST /api/v1/maps/generate:
    - Calculate cost: 1 token (basic theme), 5 tokens (custom theme - Phase 2)
    - Check: `total_tokens >= cost`
    - If insufficient: Return 429 Too Many Requests: `{error: "Insufficient tokens", balance: {...}, cost: 1}`
  - On generation start:
    - Debit tokens: Prefer free_tokens first, then purchased_tokens
    - Create `transactions` record:
      - `type='generation'`, `tokens_delta=-1`, `metadata={map_id, theme_id}`
    - Update `token_balance` accordingly
- [ ] **Token refund on failure:**
  - If generation fails (STORY-003):
    - Create refund transaction: `type='refund'`, `tokens_delta=+1`, `metadata={original_transaction_id}`
    - Credit tokens back to balance (reverse of debit)
- [ ] **GET /api/v1/tokens/transactions:**
  - Requires JWT authentication
  - Returns paginated transaction history: `?page=1&page_size=20`
  - Response:
    ```json
    {
      "transactions": [
        {"id": "...", "type": "generation", "tokens_delta": -1, "created_at": "...", "metadata": {...}},
        {"id": "...", "type": "purchase", "tokens_delta": +50, "created_at": "...", "metadata": {...}}
      ],
      "total": 42,
      "page": 1
    }
    ```
  - Sort by: created_at DESC

**Technical Notes:**
- Cron job: `apscheduler` library (Python) or Kubernetes CronJob
- Token debit: Atomic transaction (BEGIN, UPDATE token_balance, INSERT transaction, COMMIT)
- Immutable audit log: `transactions` table is append-only (never UPDATE/DELETE)

**Dependencies:** STORY-010, STORY-003

---

#### STORY-014: Stripe Integration + Anonymous Limits

**Epic:** EPIC-005 (Monetization)
**Priority:** Must Have
**Points:** 8

**User Story:**
As a user, I want to purchase token packs with Stripe so that I can generate more maps beyond my free limit

**Acceptance Criteria:**
- [ ] **POST /api/v1/tokens/purchase:**
  - Requires JWT authentication
  - Input: `{product_id: "50_tokens" | "150_tokens"}`
  - Products defined:
    - `50_tokens`: 50 tokens for $9.99
    - `150_tokens`: 150 tokens for $24.99
  - Create Stripe Checkout session via Stripe SDK
  - Return redirect URL: `{checkout_url: "https://checkout.stripe.com/..."}`
  - Frontend redirects to Stripe-hosted checkout page
- [ ] **Stripe Checkout session config:**
  - Mode: `payment` (one-time purchase)
  - Success URL: `https://overworld.com/payment/success?session_id={CHECKOUT_SESSION_ID}`
  - Cancel URL: `https://overworld.com/dashboard`
  - Metadata: `{user_id, product_id, token_amount}`
- [ ] **GET /api/v1/tokens/purchase/{session_id}/status:**
  - Check Stripe session status
  - If paid: Return `{status: 'complete', tokens_added: 50}`
  - If pending: Return `{status: 'pending'}`
- [ ] **POST /api/v1/webhooks/stripe:**
  - Public endpoint (no auth, but signature-verified)
  - Handle Stripe events:
    - `checkout.session.completed`: Payment successful
    - `checkout.session.expired`: Session expired without payment
  - Signature verification:
    - Read `Stripe-Signature` header
    - Verify with Stripe webhook signing secret (from environment)
    - Reject if signature invalid (403 Forbidden)
  - Idempotency check:
    - Check if `stripe_event_id` exists in `transactions` table
    - If exists: Return 200 OK (already processed, ignore duplicate)
    - If not exists: Process event
- [ ] **Webhook event processing (`checkout.session.completed`):**
  - Extract: `user_id`, `product_id`, `token_amount` from session metadata
  - Create transaction: `type='purchase'`, `tokens_delta=+token_amount`, `stripe_event_id`, `metadata={session_id}`
  - Update `token_balance.purchased_tokens += token_amount`
  - Send confirmation email: "You purchased 50 tokens for $9.99"
- [ ] **Retry logic:**
  - Stripe retries failed webhooks exponentially up to 3 days
  - Idempotency ensures duplicate events are ignored
- [ ] **Anonymous rate limiting:**
  - Redis counter: `daily_budget:anonymous` (tracks total spend for all anonymous users)
  - IP-based rate limiting: `rate_limit:ip:{ip}` (max 3 generations per day per IP)
  - On anonymous generation request (no JWT):
    - Check IP limit: If `rate_limit:ip:{ip} >= 3`: Return 429 Too Many Requests
    - Increment IP counter: `INCR rate_limit:ip:{ip}`, `EXPIRE 86400` (24h TTL)
    - Check daily budget: If `daily_budget:anonymous >= 50.00`: Return 429 (budget exhausted)
    - Increment budget: `INCRBYFLOAT daily_budget:anonymous 0.50` (assume $0.50 per generation)
    - Reset budget daily: Cron job at 00:00 UTC: `SET daily_budget:anonymous 0`
- [ ] **BYO API key flow:**
  - User provides OpenRouter API key
  - POST /api/v1/users/me/api-key: `{api_key: "sk-..."}`
  - Encrypt with Fernet: `cryptography.fernet.Fernet(key_from_env).encrypt(api_key.encode())`
  - Store in Redis: `byo_key:{user_id}`, TTL=30 days
  - On generation: If `byo_key:{user_id}` exists, use user's key instead of platform key
  - Bypasses anonymous budget (user pays their own LLM costs)
- [ ] **Frontend:**
  - "Buy Tokens" button on dashboard
  - Token purchase modal: Select product (50 or 150 tokens), Checkout button
  - Redirect to Stripe Checkout
  - Success page: Display confirmation, redirect to dashboard after 3 seconds

**Technical Notes:**
- Stripe SDK: `stripe-python` library
- Stripe products created manually in Stripe Dashboard (or via API on first deploy)
- Webhook endpoint must be HTTPS in production (ngrok for local testing)
- Fernet encryption: `cryptography` library, key stored in environment

**Dependencies:** STORY-013

---

### EPIC-007: Export & Sharing

#### STORY-015: Map Export (PNG/SVG with Watermark)

**Epic:** EPIC-007 (Export)
**Priority:** Must Have
**Points:** 5

**User Story:**
As a user, I want to export my map as PNG or SVG so that I can share it in presentations or documentation

**Acceptance Criteria:**
- [ ] **POST /api/v1/maps/{map_id}/export:**
  - Requires JWT authentication
  - Input: `{format: "png" | "svg", resolution: "1080p" | "4k"}`
  - Formats supported:
    - PNG: Raster image (1920x1080 for 1080p, 3840x2160 for 4k)
    - SVG: Vector image (resolution-independent)
  - Generate export asynchronously (if slow) or synchronously (if fast)
  - Return export_id: `{export_id, status: 'generating'}`
- [ ] **Export generation:**
  - PNG: Use Playwright to screenshot PixiJS canvas
    - Launch headless browser
    - Navigate to map viewer with map_id
    - Wait for map to render
    - Screenshot canvas at specified resolution
    - Apply watermark if free tier (see below)
    - Save to R2: `/maps/{map_id}/exports/png-{resolution}-{timestamp}.png`
  - SVG: Export PixiJS scene to SVG
    - Use svg-export library or custom SVG generation
    - Convert PIXI.Graphics paths to SVG <path> elements
    - Apply watermark if free tier
    - Save to R2: `/maps/{map_id}/exports/svg-{timestamp}.svg`
- [ ] **Watermark logic:**
  - Free tier (`is_premium=false`): Add watermark
    - Text: "Generated by Overworld"
    - Position: Bottom-right corner, 20px margin
    - Style: Semi-transparent gray (opacity 0.5), small font (12px)
  - Premium tier (`is_premium=true`): No watermark
- [ ] **Export caching:**
  - Store export in `map_exports` table:
    - `map_id`, `format`, `resolution`, `r2_path`, `file_size_bytes`, `created_at`
  - If same format/resolution requested again: Return cached export (skip regeneration)
- [ ] **GET /api/v1/maps/{map_id}/exports/{export_id}/download:**
  - Returns pre-signed R2 URL (1-hour expiry)
  - Browser triggers download (Content-Disposition: attachment)
- [ ] **GET /api/v1/maps/{map_id}/exports:**
  - List all cached exports for map
  - Returns: `{exports: [{id, format, resolution, created_at, file_size_bytes}]}`
- [ ] **Frontend:**
  - Export button on map viewer page
  - Export modal: Select format (PNG/SVG), resolution (1080p/4k for PNG)
  - "Export" button triggers POST /api/v1/maps/{map_id}/export
  - Progress indicator (if async)
  - Download triggers automatically when ready

**Technical Notes:**
- Playwright for PNG screenshots: `playwright-python` library, headless Chromium
- SVG export: Custom logic or `pixi-svg` plugin (if available)
- Watermark: Canvas overlay (PNG) or SVG <text> element (SVG)
- R2 pre-signed URLs: boto3 `generate_presigned_url()`

**Dependencies:** STORY-008, STORY-013

---

## Epic Traceability

| Epic ID | Epic Name | Stories | Total Points | Sprints |
|---------|-----------|---------|--------------|---------|
| **Infrastructure** | Development & Database Setup | STORY-000, STORY-INF-001 | 10 | Sprint 1 |
| **EPIC-001** | Document Ingestion & Parsing | STORY-001, STORY-002 | 10 | Sprint 1 |
| **EPIC-002** | Core Map Generation Pipeline | STORY-003, STORY-004, STORY-005, STORY-006, STORY-007, STORY-008, STORY-009 | 47 | Sprint 1-3 |
| **EPIC-004** | User Management & Authentication | STORY-010, STORY-011, STORY-012 | 18 | Sprint 2-3 |
| **EPIC-005** | Monetization & Token System | STORY-013, STORY-014 | 13 | Sprint 3 |
| **EPIC-007** | Export & Sharing | STORY-015 | 5 | Sprint 3 |

---

## Functional Requirements Coverage

| FR ID | FR Name | Story | Sprint |
|-------|---------|-------|--------|
| FR-001 | Document Upload | STORY-001 | 1 |
| FR-002 | Hierarchical Structure Extraction | STORY-002 | 1 |
| FR-003 | Document Preview | Deferred to Phase 2 | - |
| FR-004 | Artist Agent - Style Selection | STORY-005 | 2 |
| FR-005 | Road/Path Generator | STORY-006 | 2 |
| FR-006 | Coordinate Spline Mapping | STORY-006 | 2 |
| FR-007 | Milestone Icon Placement (MVP) | STORY-007 | 2 |
| FR-008 | Custom Icon Placement | Deferred to Phase 2 | - |
| FR-009 | 2D Rendering Engine | STORY-008 | 2 |
| FR-010 | Interactive Map Navigation | STORY-008 | 2 |
| FR-011 | User Registration & Authentication | STORY-010, STORY-011 | 2-3 |
| FR-012 | User Dashboard | STORY-012 | 3 |
| FR-013 | Token Allocation | STORY-013 | 3 |
| FR-014 | Token Consumption | STORY-013 | 3 |
| FR-015 | Token Purchase & Subscription | STORY-014 | 3 |
| FR-016 | Anonymous Rate Limiting | STORY-014 | 3 |
| FR-017 | Default Theme (SMB3) | STORY-005 | 2 |
| FR-018 | Custom Theme Library | Deferred to Phase 2 | - |
| FR-019 | User-Uploaded Themes | Deferred to Phase 2 | - |
| FR-020 | Image Export | STORY-015 | 3 |
| FR-021 | Shareable Links | Deferred to Phase 2 | - |
| FR-022 | Embed Code | Deferred to Phase 2 | - |
| FR-023 | Multi-Level Interactive Navigation | Deferred to Phase 2 | - |

**MVP Coverage:** 15/23 FRs (65%)
**Phase 2 Coverage:** 8/23 FRs (35%)

---

## Risks and Mitigation

### High-Priority Risks

**1. OpenRouter Rate Limiting During High-Traffic Testing**
- **Probability:** Medium
- **Impact:** High (map generation fails, user frustration)
- **Mitigation:**
  - Circuit breaker pattern in STORY-004
  - Exponential backoff (1s, 2s, 4s, 8s, max 60s)
  - Multi-provider fallback via OpenRouter's routing
  - BYO API key escape hatch (STORY-014)

**2. Spline Math Aesthetic Quality**
- **Probability:** High (subjective visual quality)
- **Impact:** Medium (maps look "off", need refinement)
- **Mitigation:**
  - Iterative tuning in STORY-006
  - Time-box aesthetic refinement to 1 day
  - LLM generates control points with aesthetic constraints in prompt
  - Accept "good enough" for MVP, refine in Phase 2

**3. Multi-Agent Pipeline Timeout Failures**
- **Probability:** High (complex pipeline, LLM latency)
- **Impact:** Medium (generation fails, tokens refunded)
- **Mitigation:**
  - 120s hard timeout enforced in STORY-003
  - Automatic token refund on timeout
  - Retry queue for transient failures (max 3 attempts)
  - Monitoring: Alert if timeout rate > 10%

### Medium-Priority Risks

**4. PixiJS 60 FPS Performance on Low-End Devices**
- **Probability:** Medium
- **Impact:** Medium (poor UX on mobile/low-end laptops)
- **Mitigation:**
  - LOD rendering (reduce detail at low zoom)
  - Viewport culling (only render visible sprites)
  - Performance profiling during STORY-008
  - Mobile testing deferred to Phase 2 (desktop-first for MVP)

**5. Stripe Webhook Delivery Failures**
- **Probability:** Low (Stripe is reliable)
- **Impact:** High (tokens not credited, payment issues)
- **Mitigation:**
  - Retry logic (Stripe auto-retries failed webhooks)
  - Idempotency checks prevent duplicate processing
  - Manual reconciliation dashboard (admin-only, Phase 2)
  - Monitoring: Alert on webhook processing failures

### Sprint-Specific Risks

**Sprint 1:**
- **RabbitMQ Clustering Complexity in Docker Compose**
  - Mitigation: Start with single-node RabbitMQ, scale to cluster later if needed
- **PostgreSQL Migration Conflicts if Schema Changes Mid-Sprint**
  - Mitigation: Alembic backward-compatible migrations only, no breaking changes

**Sprint 2:**
- **Road Generator Spline Tuning Takes Longer Than Estimated**
  - Mitigation: Time-box to 1 day, accept "good enough" aesthetic for MVP
- **PixiJS Learning Curve Steeper Than Expected**
  - Mitigation: Allocate 1 day for PixiJS tutorial/prototyping before STORY-008 starts

**Sprint 3:**
- **Stripe Test Mode Webhook Testing Requires ngrok or Similar**
  - Mitigation: Stripe CLI for local webhook forwarding (documented in architecture)

---

## Dependencies

### External Dependencies

| Dependency | Provider | Impact if Unavailable | Mitigation |
|------------|----------|------------------------|------------|
| **OpenRouter API** | OpenRouter | Map generation fails | Circuit breaker, cached responses for repeated docs, BYO API key escape hatch |
| **Stripe API** | Stripe | Payment processing fails | Retry logic, queue failed webhooks, manual reconciliation |
| **Cloudflare R2** | Cloudflare | File uploads/downloads fail | Retry 3x, fallback to local disk temp storage, alert on sustained failures |
| **Email Service** | SendGrid/Resend | Email verification fails | Queue for retry, alert on sustained failures, provide manual verification endpoint |

### Team Dependencies

**Design Assets:**
- SMB3 theme sprites, icons, textures (8-bit pixelated style)
- **Status:** Can start with placeholders, refine in Sprint 2
- **Owner:** TBD (AI-generated via DALL-E/Midjourney if no designer available)

**Domain & SSL Certificate:**
- Domain: overworld.com (or similar)
- **Status:** Needed before Sprint 3 for Stripe production webhooks (dev can use ngrok)
- **Owner:** Product owner (Jarad)

**Production Infrastructure:**
- Kubernetes cluster or managed hosting (Vercel/Railway/Fly.io)
- **Status:** Needed after Sprint 3 for MVP deployment
- **Owner:** DevOps (Jarad if solo)

---

## Definition of Done

For a story to be considered complete:

- [ ] **Code Implemented:** All acceptance criteria met, code committed to main branch
- [ ] **Unit Tests Written:** ≥80% coverage for business logic (pytest for backend, Vitest for frontend)
- [ ] **Integration Tests Passing:** API endpoints tested with test database, critical flows validated
- [ ] **Code Reviewed:** PR approved by at least 1 team member (or self-review if solo, with checklist)
- [ ] **Documentation Updated:** API endpoints documented in OpenAPI spec, README updated if needed
- [ ] **Deployed to Staging:** Code deployed to staging environment, smoke tests passed
- [ ] **Acceptance Criteria Validated:** Manual testing or automated E2E tests confirm all criteria met

---

## Next Steps

### Immediate: Begin Sprint 1

**Sprint 1 starts now!**

Run `/dev-story STORY-000` to begin implementing the development environment setup.

**Recommended story order for Sprint 1:**
1. **STORY-000:** Development Environment Setup (foundational, blocks all other work)
2. **STORY-INF-001:** Core Infrastructure & Database Schema (parallel with STORY-000 if 2+ devs)
3. **STORY-001:** Document Upload & Storage (requires INF-001 complete)
4. **STORY-002:** Hierarchy Extraction (requires STORY-001 complete)
5. **STORY-003:** Generation Orchestrator & Job Queue (requires INF-001 complete, can parallel with STORY-001/002)
6. **STORY-004:** Multi-Agent Pipeline Foundation (requires STORY-003 complete)

**Team Split Strategy (if 2-3 devs):**
- **Dev 1:** STORY-000 → STORY-INF-001 → STORY-003 → STORY-004 (infrastructure & backend pipeline)
- **Dev 2:** Wait for INF-001 → STORY-001 → STORY-002 (document ingestion)
- **Dev 3 (if available):** Frontend setup in STORY-000, then support backend or start early frontend work

---

### Sprint Cadence

**Sprint Structure:**
- **Sprint Length:** 2 weeks (10 workdays)
- **Sprint Planning:** Monday Week 1 (2 hours)
- **Daily Standups:** Every morning (15 minutes)
- **Sprint Review:** Friday Week 2 (1 hour demo)
- **Sprint Retrospective:** Friday Week 2 (1 hour)

**Sprint 1 Milestones:**
- **End of Week 1:** Infrastructure complete (STORY-000, STORY-INF-001), document upload working (STORY-001)
- **End of Week 2:** Generation orchestrator + multi-agent foundation complete (STORY-003, STORY-004), hierarchy extraction working (STORY-002)

**Sprint 2 Milestones:**
- **End of Week 3:** AI agents complete (STORY-005, STORY-006, STORY-007), first end-to-end map generated
- **End of Week 4:** PixiJS renderer working (STORY-008), user authentication live (STORY-010)

**Sprint 3 Milestones:**
- **End of Week 5:** Token system + Stripe integration complete (STORY-013, STORY-014), WebSocket progress live (STORY-009)
- **End of Week 6:** OAuth2 + dashboard + export complete (STORY-011, STORY-012, STORY-015), **MVP LAUNCH READY**

---

**This plan was created using BMAD Method v6 - Phase 4 (Implementation Planning)**

*To continue: Run `/workflow-status` to see your progress or `/dev-story STORY-000` to begin implementation.*
