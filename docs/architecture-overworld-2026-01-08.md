# System Architecture: Overworld

**Date:** 2026-01-08
**Architect:** System Architect (BMAD Method v6)
**Version:** 1.0
**Project Type:** web-app
**Project Level:** 2
**Status:** Draft

---

## Document Overview

This document defines the system architecture for Overworld. It provides the technical blueprint for implementation, addressing all functional and non-functional requirements from the PRD.

**Related Documents:**
- Product Requirements Document: /home/delorenj/code/overworld/docs/prd-overworld-2026-01-05.md
- Product Brief: Not started (recommended)

---

## Executive Summary

Overworld transforms linear project documentation into interactive 8/16-bit era overworld maps through a multi-agent AI pipeline and game-like rendering engine. The architecture prioritizes two core differentiators: **AI-powered map generation with sub-30-second performance** and **60 FPS game-like interactivity** via PixiJS WebGL rendering.

The system follows a **modular monolith pattern** with clear separation between auth, tokenization, map management, and the multi-agent generation pipeline. Async job processing via RabbitMQ decouples long-running AI generation from API responsiveness. OpenRouter provides multi-model routing for cost optimization and resilience.

Key architectural decisions:
- **Backend:** FastAPI + Pydantic v2 (async-native, strict typing, OpenAPI auto-generation)
- **Frontend:** React 19 + PixiJS (SPA with embedded WebGL renderer)
- **AI:** OpenRouter for multi-provider LLM routing, Agno for agent orchestration
- **Data:** PostgreSQL (relational), Redis (cache/rate limits), Cloudflare R2 (object storage)
- **Infrastructure:** Docker Compose → Kubernetes with Traefik ingress

The architecture supports **freemium monetization** with token-based generation, Stripe payment processing, and hard cost controls for anonymous users via BYO API key escape hatch.

---

## Architectural Drivers

These requirements heavily influence architectural decisions:

### Critical Drivers (Highest Priority)

| Priority | NFR | Requirement | Architectural Impact |
|----------|-----|-------------|---------------------|
| **Critical** | NFR-001 | <30s map generation (95th percentile) | Queue-based async processing, progressive feedback |
| **Critical** | NFR-002 | 60 FPS rendering performance | 2D engine selection, WebGL optimization |
| **Critical** | NFR-006 | Cost control for anonymous users | Rate limiting, budget caps, BYO API key flow |

### High Priority Drivers

| Priority | NFR | Requirement | Architectural Impact |
|----------|-----|-------------|---------------------|
| **High** | NFR-003 | JWT/OAuth2 authentication | Auth service, token management |
| **High** | NFR-004 | PCI-DSS payment security | Stripe-only payment handling, no card storage |
| **High** | NFR-005 | 1,000 concurrent users | Horizontal scaling, connection pooling, CDN |

### Medium Priority Drivers

| Priority | NFR | Requirement | Architectural Impact |
|----------|-----|-------------|---------------------|
| **Medium** | NFR-007 | 99.5% uptime | Multi-AZ, health checks, automated failover |
| **Medium** | NFR-009 | 80%+ test coverage | CI/CD pipeline, testing strategy |

### Additional Drivers (from FRs)

| Driver | Source | Impact |
|--------|--------|--------|
| **Multi-Agent AI Pipeline** | FR-004, FR-005, FR-006, FR-007 | LLM orchestration, agent coordination |
| **Hierarchical Navigation (L0-L4)** | FR-023 | State management, nested rendering |
| **Token Economy** | FR-013, FR-014, FR-015 | Transaction management, balance tracking |
| **Theme System** | FR-017, FR-018 | Asset pipeline, dynamic theming |

**User Priority:** Multi-Agent Pipeline + Rendering prioritized as core differentiators.

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    React SPA + 2D Game Engine                        │    │
│  │         (Document Upload → Map Viewer → Interactive Canvas)          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │   Auth │ Rate Limiting │ Request Routing │ API Versioning           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌──────────────────────┐ ┌──────────────────┐ ┌──────────────────────────────┐
│    USER SERVICE      │ │  TOKEN SERVICE   │ │      MAP GENERATION          │
│  ─────────────────   │ │  ──────────────  │ │      ORCHESTRATOR            │
│  • Registration      │ │  • Balance mgmt  │ │  ────────────────────────    │
│  • Authentication    │ │  • Consumption   │ │  • Job queue (async)         │
│  • Profile mgmt      │ │  • Purchase      │ │  • Multi-agent pipeline      │
│  • OAuth providers   │ │  • Stripe webhook│ │  • Progressive feedback      │
└──────────────────────┘ └──────────────────┘ └──────────────────────────────┘
                                                          │
                                                          ▼
                              ┌────────────────────────────────────────────┐
                              │         MULTI-AGENT AI PIPELINE            │
                              │  ┌──────┐ ┌──────┐ ┌──────┐ ┌───────────┐  │
                              │  │Parser│→│Artist│→│ Road │→│Coordinator│  │
                              │  │Agent │ │Agent │ │Agent │ │  Agent    │  │
                              │  └──────┘ └──────┘ └──────┘ └───────────┘  │
                              └────────────────────────────────────────────┘
                                                          │
                                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌──────────────┐  │
│  │  PostgreSQL   │  │    Redis      │  │  Object Store │  │   Queue      │  │
│  │  (Users,Maps) │  │  (Cache,Rate) │  │  (Assets,PDF) │  │  (Jobs)      │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Architecture Diagram

Component interaction and data flow showing modular monolith with queue-based async processing pattern.

### Architectural Pattern

**Pattern:** Modular Monolith + Queue-Based AI Pipeline + REST + WebSocket

**Layer Breakdown:**

| Layer | Pattern | Rationale |
|-------|---------|-----------|
| **Backend Core** | Modular Monolith | Simple deployment for Level 2, clear module boundaries, easy to refactor later |
| **AI Pipeline** | Queue-Based + Agent Orchestration | Async processing for long-running generations, agent coordination |
| **API** | REST + WebSocket | REST for CRUD, WebSocket for real-time generation progress |
| **Frontend** | SPA + Game Engine | React for UI, embedded 2D engine for map rendering |

**Rationale:**

Modular monolith balances simplicity and scalability for a Level 2 project. Clear module boundaries (auth, tokens, maps, generation) enable future extraction to microservices if needed. Queue-based AI pipeline decouples API responsiveness from generation latency, critical for NFR-001 (30-second target). WebSocket real-time updates provide progressive feedback, reducing perceived wait time.

Trade-off: Monolith deployment is simpler than microservices but limits independent scaling. Acceptable for initial scale (1,000 concurrent users, NFR-005). Queue adds operational complexity but solves critical performance requirements.

---

## Technology Stack

### Frontend

**Choice:** React 19 + TypeScript + Vite

**Rationale:** User-preferred stack, strict typing via TypeScript prevents runtime errors, Vite provides fast dev server and optimal production builds. React 19 concurrent features support smooth UI updates during long-running generation.

**Trade-offs:**
- ✓ Gain: Strong typing, excellent ecosystem, team familiarity
- ✗ Lose: Bundle size larger than vanilla JS, but acceptable with code splitting

---

**Choice:** Tailwind CSS + shadcn/ui

**Rationale:** Rapid UI development with utility-first CSS, shadcn/ui provides pre-built accessible components. Consistent design system without custom CSS complexity.

**Trade-offs:**
- ✓ Gain: Fast iteration, accessibility built-in, maintainable
- ✗ Lose: HTML verbosity, but tooling mitigates

---

**Choice:** PixiJS (WebGL 2D Renderer)

**Rationale:** Lightweight WebGL renderer specifically optimized for 2D graphics. Hardware-accelerated sprite batching delivers 60 FPS performance (NFR-002) for 100+ element maps. Wide adoption, excellent documentation, active community.

**Alternatives Considered:**
- Phaser: Full game framework with physics, scenes, input handling. More features but heavier (300KB+ vs 150KB for PixiJS). Overkill for static map rendering.
- PlayCanvas: WebGL engine with editor. More 3D-focused, steeper learning curve. Not justified for 2D orthogonal maps.

**Trade-offs:**
- ✓ Gain: Best-in-class 2D WebGL performance, sprite batching, object pooling
- ✗ Lose: Less opinionated than Phaser, requires manual scene management

---

**Choice:** Zustand or React Context

**Rationale:** Lightweight state management sufficient for SPA complexity. Zustand if cross-component state needed (user session, token balance), React Context for localized state.

**Trade-offs:**
- ✓ Gain: Simple API, minimal boilerplate
- ✗ Lose: Not Redux-level time-travel debugging, acceptable for project scope

---

### Backend

**Choice:** FastAPI + Pydantic v2

**Rationale:** User-preferred stack. Async-native (critical for concurrent request handling, NFR-005). Pydantic v2 provides strict typing, request validation, and serialization. OpenAPI 3.0 spec auto-generated from route decorators (NFR-010).

**Trade-offs:**
- ✓ Gain: Async performance, strict typing, OpenAPI auto-docs, Python ecosystem
- ✗ Lose: Python GIL limits CPU-bound tasks, but AI generation offloaded to queue workers

---

**Choice:** FastAPI-Users + OAuth2

**Rationale:** Battle-tested auth library with JWT, OAuth2, password hashing built-in. Reduces custom auth code surface area (security best practice).

**Trade-offs:**
- ✓ Gain: Security audited, OAuth providers pre-integrated
- ✗ Lose: Opinionated structure, but aligns with requirements

---

**Choice:** RabbitMQ (Message Queue)

**Rationale:** User-preferred stack. Robust message broker for multi-agent orchestration. Supports priority queues (premium users first), dead-letter queues (failed jobs), and acknowledgments (at-least-once delivery).

**Alternatives Considered:**
- Redis Queue (RQ): Simpler, but lacks advanced routing and guarantees
- Celery: More opinionated, RabbitMQ backend anyway

**Trade-offs:**
- ✓ Gain: Robust guarantees, advanced routing, production-ready
- ✗ Lose: Operational complexity (monitoring, clustering), acceptable for requirements

---

### Database

**Choice:** PostgreSQL 15+

**Rationale:** User-preferred stack. Relational model fits user/token/map entities. JSONB support for hierarchical map data (L0-L4 navigation). ACID guarantees critical for token transactions. Advanced indexing (GIN for JSONB, B-tree for timestamps).

**Trade-offs:**
- ✓ Gain: ACID, relational integrity, JSONB flexibility, mature ecosystem
- ✗ Lose: Scaling writes harder than NoSQL, but read-heavy workload mitigates

---

**Choice:** Redis 7+

**Rationale:** In-memory cache for rate limiting (NFR-006), session storage, pub/sub for WebSocket progress updates. Sub-millisecond latency critical for rate limit checks on every request.

**Trade-offs:**
- ✓ Gain: Blazing fast, pub/sub built-in, simple data structures
- ✗ Lose: Volatile by default, but use RDB snapshots + AOF for persistence

---

**Choice:** Cloudflare R2 (S3-Compatible Object Storage)

**Rationale:** No egress fees (critical for map export downloads). S3-compatible API (drop-in replacement if migrating). Suitable for uploaded PDFs, generated map JSON, theme assets, export artifacts.

**Trade-offs:**
- ✓ Gain: Zero egress costs, S3 compatibility, Cloudflare CDN integration
- ✗ Lose: Vendor lock-in to Cloudflare ecosystem, acceptable for cost savings

---

### Infrastructure

**Choice:** Docker Compose → Kubernetes

**Rationale:** User-preferred stack. Docker Compose for local development (fast iteration). Kubernetes for production (horizontal scaling, health checks, rolling updates). Traefik as ingress controller (TLS termination, routing).

**Alternatives Considered:**
- Managed PaaS (Railway/Render): Faster initial deploy, less control, vendor lock-in
- VMs without containers: Slower deployments, harder dependency management

**Trade-offs:**
- ✓ Gain: Full control, portable, industry-standard
- ✗ Lose: K8s complexity, but managed K8s (EKS/GKE/AKS) mitigates

---

### Third-Party Services

| Service | Choice | Rationale |
|---------|--------|-----------|
| **Payments** | Stripe | PCI compliance handled, webhooks, subscription support (NFR-004) |
| **Email** | Resend or SendGrid | Transactional email for verification, receipts |
| **LLM** | OpenRouter | Multi-provider routing, cost optimization, fallback resilience |
| **Monitoring** | Grafana + Prometheus | Open-source observability, structured logging to Loki |

---

### Development & Deployment

| Tool | Purpose | Rationale |
|------|---------|-----------|
| **Version Control** | Git + GitHub | Industry standard, GitHub Actions for CI/CD |
| **Package Management** | uv (Python), bun (Node) | User preference, fast dependency resolution |
| **Task Runner** | mise tasks | User preference, project-local task definitions |
| **CI/CD** | GitHub Actions | Free for public repos, matrix builds, secrets management |
| **Secrets** | 1Password + mise | User preference, secure local dev secrets |
| **Testing** | pytest (backend), Vitest (frontend), Playwright (E2E) | Industry standard, async support |
| **Linting** | Ruff (Python), ESLint + Prettier (TypeScript) | Fast linters, auto-fix on commit |

---

## System Components

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │   Web App (SPA)  │  │  Map Renderer    │  │   Export Service         │   │
│  │   React + Vite   │  │  PixiJS Canvas   │  │   PNG/SVG Generation     │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API LAYER (FastAPI)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │ Auth Router  │ │ Token Router │ │  Map Router  │ │  Generation Router │  │
│  │ /api/v1/auth │ │/api/v1/tokens│ │ /api/v1/maps │ │  /api/v1/generate  │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────────────────┘  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │Theme Router  │ │Export Router │ │Share Router  │ │  WebSocket Handler │  │
│  │/api/v1/themes│ │/api/v1/export│ │/api/v1/share │ │  /ws/generation    │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BUSINESS LOGIC LAYER                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────────┐   │
│  │   Auth Service     │  │   Token Service    │  │   Map Service        │   │
│  │   ──────────────   │  │   ──────────────   │  │   ────────────       │   │
│  │   • Registration   │  │   • Balance CRUD   │  │   • Map CRUD         │   │
│  │   • OAuth flow     │  │   • Consumption    │  │   • Hierarchy store  │   │
│  │   • JWT mgmt       │  │   • Stripe hooks   │  │   • Share links      │   │
│  │   • Rate limiting  │  │   • Subscriptions  │  │   • Watermarking     │   │
│  └────────────────────┘  └────────────────────┘  └──────────────────────┘   │
│                                                                              │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────────┐   │
│  │  Document Parser   │  │  Theme Service     │  │  Export Service      │   │
│  │  ────────────────  │  │  ──────────────    │  │  ──────────────      │   │
│  │  • MD/PDF ingest   │  │  • Theme library   │  │  • PNG rendering     │   │
│  │  • Hierarchy ext.  │  │  • Asset mgmt      │  │  • SVG generation    │   │
│  │  • Obsidian syntax │  │  • Premium gating  │  │  • Resolution opts   │   │
│  │  • L0-L4 mapping   │  │  • Icon sets       │  │  • Watermark logic   │   │
│  └────────────────────┘  └────────────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GENERATION ORCHESTRATOR                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                    Job Queue (RabbitMQ)                             │     │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │     │
│  │  │ pending  │→ │ parsing  │→ │ styling  │→ │ rendering        │   │     │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                      │                                       │
│                                      ▼                                       │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                   Multi-Agent Pipeline                              │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │     │
│  │  │ Parser Agent │→ │ Artist Agent │→ │ Road Generator Agent     │ │     │
│  │  │ (structure)  │  │ (style opts) │  │ (spline + coordinates)   │ │     │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘ │     │
│  │                                             │                       │     │
│  │                                             ▼                       │     │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │     │
│  │  │Art Director  │← │Icon Placer   │← │ Coordinator Agent        │ │     │
│  │  │(validation)  │  │(milestones)  │  │ (orchestration)          │ │     │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘ │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             DATA LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────┐  ┌───────────────────┐  ┌────────────────────────┐   │
│  │    PostgreSQL     │  │      Redis        │  │   Cloudflare R2        │   │
│  │   ─────────────   │  │   ─────────────   │  │   ───────────────      │   │
│  │   • users         │  │   • rate limits   │  │   • uploaded docs      │   │
│  │   • tokens        │  │   • session cache │  │   • generated maps     │   │
│  │   • maps          │  │   • job progress  │  │   • theme assets       │   │
│  │   • transactions  │  │   • pub/sub       │  │   • icon libraries     │   │
│  │   • share_links   │  │   • BYO key cache │  │   • export artifacts   │   │
│  └───────────────────┘  └───────────────────┘  └────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Details

| Component | Purpose | FRs Addressed | Effort |
|-----------|---------|---------------|--------|
| **Auth Service** | User registration, OAuth, JWT, rate limiting | FR-011, FR-016 | M |
| **Token Service** | Balance management, consumption, Stripe webhooks | FR-013, FR-014, FR-015 | M |
| **Document Parser** | MD/PDF ingestion, Obsidian syntax, L0-L4 hierarchy | FR-001, FR-002, FR-003 | M-L |
| **Map Service** | Map CRUD, share links, metadata | FR-012, FR-021 | S-M |
| **Theme Service** | Theme library, assets, premium gating | FR-017, FR-018 | S-M |
| **Generation Orchestrator** | Job queue, agent coordination, progress tracking | FR-004, FR-005, FR-006, FR-007 | L |
| **Multi-Agent Pipeline** | Parser→Artist→Road→Coordinator→Art Director | Core differentiator | XL |
| **Export Service** | PNG/SVG generation, watermarking, resolution options | FR-020 | M |
| **WebSocket Handler** | Real-time generation progress | NFR-001 | S |

---

## Data Architecture

### Data Model

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            PostgreSQL Schema                              │
└──────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│     users       │         │   token_balance  │         │  subscriptions  │
├─────────────────┤         ├──────────────────┤         ├─────────────────┤
│ id (UUID) PK    │────────<│ user_id (FK)     │    ┌───<│ user_id (FK)    │
│ email           │         │ free_tokens      │    │    │ stripe_sub_id   │
│ password_hash   │         │ purchased_tokens │    │    │ status          │
│ oauth_provider  │         │ last_reset_at    │    │    │ plan_tier       │
│ oauth_id        │         │ created_at       │    │    │ started_at      │
│ is_verified     │         │ updated_at       │    │    │ ends_at         │
│ created_at      │         └──────────────────┘    │    └─────────────────┘
│ updated_at      │                                 │
└─────────────────┘                                 │
        │                                           │
        │                                           │
        │          ┌──────────────────┐            │
        └─────────>│  transactions    │<───────────┘
                   ├──────────────────┤
                   │ id (UUID) PK     │
                   │ user_id (FK)     │
                   │ type (enum)      │  // 'generation', 'purchase', 'refund'
                   │ tokens_delta     │
                   │ stripe_event_id  │
                   │ metadata (JSONB) │
                   │ created_at       │
                   └──────────────────┘

┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│      maps       │         │  generation_jobs │         │   share_links   │
├─────────────────┤         ├──────────────────┤         ├─────────────────┤
│ id (UUID) PK    │────────<│ map_id (FK)      │    ┌───<│ map_id (FK)     │
│ user_id (FK)    │         │ user_id (FK)     │    │    │ slug            │
│ name            │         │ status (enum)    │    │    │ password_hash   │
│ hierarchy (JSONB)│        │ queue_position   │    │    │ view_count      │
│ theme_id (FK)   │         │ agent_state (JSONB)│   │    │ expires_at      │
│ watermarked     │         │ progress_pct     │    │    │ created_at      │
│ created_at      │         │ started_at       │    │    │ last_viewed_at  │
│ updated_at      │         │ completed_at     │    │    └─────────────────┘
└─────────────────┘         │ error_msg        │
        │                   │ created_at       │
        │                   └──────────────────┘
        │
        │          ┌──────────────────┐
        └─────────>│   map_exports    │
                   ├──────────────────┤
                   │ id (UUID) PK     │
                   │ map_id (FK)      │
                   │ format (enum)    │  // 'png', 'svg'
                   │ resolution       │
                   │ r2_path          │
                   │ file_size_bytes  │
                   │ created_at       │
                   └──────────────────┘

┌─────────────────┐
│     themes      │
├─────────────────┤
│ id (UUID) PK    │
│ name            │
│ description     │
│ is_premium      │
│ asset_manifest (JSONB) │
│ created_at      │
└─────────────────┘
```

### Database Design

**Entity Relationships:**

| Entity | Cardinality | Notes |
|--------|-------------|-------|
| `users` → `token_balance` | 1:1 | Separate table for high-update isolation |
| `users` → `maps` | 1:N | User owns many maps |
| `users` → `transactions` | 1:N | Immutable audit log |
| `maps` → `generation_jobs` | 1:N | Track all generation attempts |
| `maps` → `share_links` | 1:N | Multiple share links per map |
| `maps` → `map_exports` | 1:N | Cache export artifacts |
| `themes` → `maps` | 1:N | Theme reference |

**Indexes:**

```sql
-- Performance critical
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_oauth ON users(oauth_provider, oauth_id);
CREATE INDEX idx_maps_user_created ON maps(user_id, created_at DESC);
CREATE INDEX idx_generation_jobs_status ON generation_jobs(status, created_at);
CREATE INDEX idx_share_links_slug ON share_links(slug);
CREATE INDEX idx_transactions_user_created ON transactions(user_id, created_at DESC);

-- JSONB indexing for hierarchy navigation
CREATE INDEX idx_maps_hierarchy_gin ON maps USING GIN(hierarchy);
```

**Redis Data Structures:**

| Key Pattern | Type | Purpose | TTL |
|-------------|------|---------|-----|
| `rate_limit:ip:{ip}` | STRING | Anonymous rate limit counter | 24h |
| `rate_limit:user:{user_id}` | STRING | User rate limit counter | 1h |
| `session:{token}` | HASH | JWT session data | 24h |
| `generation:{job_id}:progress` | PUBSUB | Real-time progress updates | N/A |
| `byo_key:{user_id}` | STRING | User-provided OpenRouter key (encrypted) | 30d |
| `daily_budget:anonymous` | STRING | Anonymous daily spend tracker | 24h |

**R2 Object Storage Structure:**

```
/uploads/{user_id}/{timestamp}/{filename}             // Uploaded PDFs/MDs
/maps/{map_id}/generated/{timestamp}.json              // Generated map data
/maps/{map_id}/exports/{format}-{resolution}.{ext}     // Cached exports
/themes/{theme_id}/assets/{asset_name}                 // Theme assets
/icons/{theme_id}/{icon_name}.svg                      // Icon libraries
```

### Data Flow

**Write Path (Map Generation):**
```
Client Upload → R2 → generation_jobs (pending) → RabbitMQ → Multi-Agent Pipeline
→ Redis (progress pubsub) → generation_jobs (completed) → maps (hierarchy JSONB)
→ R2 (generated map data) → WebSocket (notify client)
```

**Read Path (Map Viewing):**
```
Client Request → PostgreSQL (maps table) → R2 (fetch generated data)
→ Redis (cache hierarchy) → Client (PixiJS renders)
```

**Token Consumption:**
```
Generation Request → token_balance (check) → transactions (debit)
→ generation_jobs (create) → [on error] → transactions (refund)
```

---

## API Design

### API Architecture

**Protocol:** REST + WebSocket hybrid
**Versioning:** URL-based (`/api/v1/`)
**Format:** JSON (request/response)
**Auth:** JWT (24h expiry) + OAuth2 (Google, GitHub)
**Spec:** OpenAPI 3.0 auto-generated via FastAPI

### Endpoints

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Auth & User Management                          │
└─────────────────────────────────────────────────────────────────────────┘
POST   /api/v1/auth/register              Register new user
POST   /api/v1/auth/login                 Login (email/password)
POST   /api/v1/auth/refresh               Refresh access token
POST   /api/v1/auth/logout                Invalidate tokens
GET    /api/v1/auth/oauth/{provider}      OAuth2 initiation
GET    /api/v1/auth/oauth/{provider}/callback  OAuth2 callback
POST   /api/v1/auth/verify-email          Verify email token
POST   /api/v1/auth/reset-password        Request password reset
PUT    /api/v1/users/me                   Update profile
GET    /api/v1/users/me                   Get current user
DELETE /api/v1/users/me                   Delete account

┌─────────────────────────────────────────────────────────────────────────┐
│                          Token & Monetization                            │
└─────────────────────────────────────────────────────────────────────────┘
GET    /api/v1/tokens/balance             Get token balance
GET    /api/v1/tokens/transactions        List transactions (paginated)
POST   /api/v1/tokens/purchase            Create Stripe checkout session
GET    /api/v1/tokens/purchase/{session_id}/status  Check purchase status
POST   /api/v1/subscriptions              Create subscription
GET    /api/v1/subscriptions/me           Get subscription status
PUT    /api/v1/subscriptions/me/cancel    Cancel subscription
POST   /api/v1/webhooks/stripe            Stripe webhook handler

┌─────────────────────────────────────────────────────────────────────────┐
│                          Map Generation & Management                     │
└─────────────────────────────────────────────────────────────────────────┘
POST   /api/v1/maps/generate              Initiate map generation
GET    /api/v1/maps                       List user maps (paginated)
GET    /api/v1/maps/{map_id}              Get map details
PUT    /api/v1/maps/{map_id}              Update map (name, metadata)
DELETE /api/v1/maps/{map_id}              Delete map
GET    /api/v1/maps/{map_id}/hierarchy    Get map hierarchy (JSONB)
GET    /api/v1/maps/{map_id}/preview      Get map preview data

┌─────────────────────────────────────────────────────────────────────────┐
│                          Generation Jobs & Progress                      │
└─────────────────────────────────────────────────────────────────────────┘
GET    /api/v1/jobs/{job_id}              Get job status
GET    /api/v1/jobs/{job_id}/progress     Get detailed progress
POST   /api/v1/jobs/{job_id}/cancel       Cancel pending job
WS     /ws/generation/{job_id}            Real-time progress stream

┌─────────────────────────────────────────────────────────────────────────┐
│                          Themes & Customization                          │
└─────────────────────────────────────────────────────────────────────────┘
GET    /api/v1/themes                     List available themes
GET    /api/v1/themes/{theme_id}          Get theme details
GET    /api/v1/themes/{theme_id}/preview  Get theme preview image

┌─────────────────────────────────────────────────────────────────────────┐
│                          Export & Sharing                                │
└─────────────────────────────────────────────────────────────────────────┘
POST   /api/v1/maps/{map_id}/export       Generate export (PNG/SVG)
GET    /api/v1/maps/{map_id}/exports      List cached exports
GET    /api/v1/maps/{map_id}/exports/{export_id}/download  Download export

POST   /api/v1/maps/{map_id}/share        Create share link
GET    /api/v1/maps/{map_id}/shares       List share links
DELETE /api/v1/shares/{share_id}          Revoke share link
GET    /api/v1/s/{slug}                   View shared map (public)
```

**Rate Limiting:**

| Endpoint Pattern | Tier | Limit |
|------------------|------|-------|
| `/api/v1/auth/*` | All | 10 req/min per IP |
| `/api/v1/maps/generate` | Anonymous | 3 req/day per IP |
| `/api/v1/maps/generate` | Free | 10 req/month (token-based) |
| `/api/v1/maps/generate` | Premium | Unlimited |
| `/api/v1/maps/*` (read) | All | 100 req/min per user |
| `/api/v1/tokens/*` | All | 30 req/min per user |

### Authentication & Authorization

**JWT Token Lifecycle:**
```
POST /api/v1/auth/register → email verification → Login
POST /api/v1/auth/login → {access_token (24h), refresh_token (30d)}
→ Authorization: Bearer {access_token}
→ POST /api/v1/auth/refresh → new access_token

GET /api/v1/auth/oauth/google → OAuth2 redirect → callback → JWT tokens
```

**JWT Payload:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "is_premium": false,
  "exp": 1704067200,
  "iat": 1703980800
}
```

**OAuth2 Flow:**
- Providers: Google, GitHub
- PKCE flow for security
- State parameter: Random 32-byte string, Redis-backed, 5-minute TTL

---

## Non-Functional Requirements Coverage

### NFR-001: Map Generation Speed

**Requirement:** 95th percentile generation time < 30 seconds for 50-milestone documents

**Architecture Solution:**
- Queue-based async processing: RabbitMQ decouples API from generation, prevents blocking
- Progressive agent pipeline: Parser → Artist → Road → Coordinator runs in stages, checkpoints allow recovery
- OpenRouter model selection: Route to fastest models for non-critical agents (Parser uses fast model, Artist uses quality model)
- Parallel agent execution: Icon placement and spline generation run concurrently where dependencies allow
- WebSocket progress updates: Client receives real-time feedback every 5 seconds, reduces perceived wait time
- Timeout handling: 120-second hard timeout kills job, refunds tokens, logs for analysis

**Implementation Notes:**
- Instrument each agent with timing metrics (structured logging to Grafana)
- Background job monitoring dashboard tracks p50/p95/p99 latencies
- Agent optimization targets: Parser <5s, Artist <10s, Road <8s, Coordinator <7s

**Validation:**
- Load testing: 100 concurrent generations, measure p95 latency
- Production monitoring: Alert if p95 > 35s for 5 minutes

---

### NFR-002: Rendering Performance

**Requirement:** 60 FPS during zoom/pan/animations for 100+ element maps

**Architecture Solution:**
- PixiJS WebGL renderer: Hardware-accelerated 2D rendering, sprite batching, efficient draw calls
- Object pooling: Reuse sprite instances for milestones/icons, minimize GC pressure
- Level-of-detail (LOD): Reduce icon complexity at low zoom levels, skip non-visible elements
- Viewport culling: Only render sprites within visible canvas bounds + margin
- Debounced pan/zoom: Throttle mouse events to 16ms (60 FPS), batch transform updates
- Lazy loading hierarchy: L1-L4 navigation loads child levels on-demand, not upfront

**Implementation Notes:**
- PixiJS `PIXI.Application` with `antialias: true, resolution: window.devicePixelRatio`
- Use `PIXI.Container` grouping for hierarchical transforms
- Monitor frame time with `stats.js` during development

**Validation:**
- Chrome DevTools Performance profiling: No frames > 16.67ms
- Automated Lighthouse performance audit in CI: Score > 90

---

### NFR-003: Authentication & Authorization

**Requirement:** JWT tokens, OAuth2, bcrypt password hashing, CSRF protection

**Architecture Solution:**
- FastAPI-Users library: Pre-built JWT auth, OAuth2 integration, password hashing
- bcrypt cost factor 12: Balance security vs performance (< 200ms hash time)
- JWT tokens: 24h access token, 30d refresh token, stored in Redis with user_id index
- OAuth2 providers: Google + GitHub via `python-social-auth`, PKCE flow for security
- CSRF protection: Double-submit cookie pattern for state-changing endpoints
- Rate limiting: 10 login attempts per 15 minutes per IP, Redis-backed counter

**Implementation Notes:**
- Refresh token rotation: Issue new refresh token on each refresh, invalidate old
- OAuth state parameter: Random 32-byte string, Redis-backed, 5-minute TTL

**Validation:**
- Penetration testing: Attempt brute force, token replay, CSRF attacks
- OWASP ZAP automated security scanning in CI

---

### NFR-004: Payment Security

**Requirement:** PCI-DSS compliance via Stripe, no credit card storage

**Architecture Solution:**
- Stripe Checkout: Client-side redirect to Stripe-hosted payment page, no card data touches our servers
- Webhook signature verification: Validate `Stripe-Signature` header with signing secret
- TLS 1.3 enforced: Traefik config: `minVersion: VersionTLS13`
- Stripe API keys in environment: Never committed to repo, loaded from 1Password via `mise`
- Idempotency: Webhook handler checks `stripe_event_id` in transactions table, prevents duplicate processing

**Implementation Notes:**
- Webhook endpoint: `/api/v1/webhooks/stripe` (public, signature-verified)
- Handle events: `checkout.session.completed`, `invoice.paid`, `customer.subscription.deleted`
- Retry logic: Stripe retries failed webhooks exponentially up to 3 days

**Validation:**
- Stripe CLI webhook forwarding for local testing
- Production monitoring: Alert on webhook processing failures

---

### NFR-005: Concurrent Users

**Requirement:** 1,000 concurrent users without degradation

**Architecture Solution:**
- Horizontal scaling: Docker Compose → K8s deployment with HPA (Horizontal Pod Autoscaler)
- Stateless API layer: No in-memory session state, all state in Redis/PostgreSQL
- Connection pooling: SQLAlchemy pool size 20, max overflow 40 per API instance
- Redis cluster: Sentinel mode with 3 nodes, automatic failover
- CDN caching: Cloudflare for static assets (themes, icons, exported maps), 1-year cache
- Queue concurrency: RabbitMQ worker pool scales independently from API layer

**Implementation Notes:**
- K8s HPA target: 70% CPU utilization, min 2 replicas, max 10 replicas
- Database read replicas for heavy read endpoints (`GET /api/v1/maps`)
- Traefik load balancer: Round-robin algorithm, health checks every 10s

**Validation:**
- Load testing with k6: Ramp to 1,000 concurrent users over 5 minutes, sustain for 10 minutes
- Monitor: Error rate < 1%, p95 latency < 500ms, no connection pool exhaustion

---

### NFR-006: Cost Control for Anonymous Users

**Requirement:** Hard daily budget cap, BYO API key escape hatch

**Architecture Solution:**
- Redis-backed daily budget: `daily_budget:anonymous` counter, resets at UTC midnight
- IP-based rate limiting: 3 generations/day per IP, rolling 24h window
- Cookie fingerprinting: Secondary soft limit, track browser fingerprint
- BYO API key flow: User provides OpenRouter key, stored encrypted in Redis (30d TTL), bypasses budget
- Admin dashboard: Real-time anonymous spend monitoring, manual budget adjustment
- Hard cutoff: When budget reached, return `429 Too Many Requests`, show signup CTA

**Implementation Notes:**
- Budget cap: $50/day default, configurable via environment variable
- Encryption: `cryptography.fernet` with key from environment, symmetric encryption
- Cost tracking: Log LLM token usage per generation, calculate cost via OpenRouter pricing

**Validation:**
- Test BYO key flow: User-provided key used instead of platform key
- Automated budget exhaustion test: Trigger cutoff, verify refusal + error message

---

### NFR-007: Uptime

**Requirement:** 99.5% monthly uptime (3.6 hours downtime/month)

**Architecture Solution:**
- Multi-region deployment: Primary region + failover region (manual promotion initially)
- Health check endpoints: `/health` (liveness), `/ready` (readiness with dependency checks)
- Automated alerting: PagerDuty integration, escalation to on-call engineer after 5 minutes
- Database backups: Daily automated backups to R2, point-in-time recovery (PITR) enabled
- Graceful degradation: If RabbitMQ down, queue generation requests in PostgreSQL fallback table

**Implementation Notes:**
- Health check response time: < 100ms, checks Redis, PostgreSQL, RabbitMQ connectivity
- Uptime monitoring: UptimeRobot pings `/health` every 60 seconds from 5 global locations
- Incident response SLA: Acknowledge within 15 minutes, resolve within 4 hours

**Validation:**
- Chaos engineering: Simulate database failure, RabbitMQ crash, test recovery
- Monthly uptime reports: Track actual uptime vs 99.5% target

---

### NFR-008: Browser Support

**Requirement:** Chrome 120+, Firefox 120+, Safari 17+, Edge 120+

**Architecture Solution:**
- Transpilation: Vite + `@vitejs/plugin-react` with Babel targets `> 0.5%, last 2 versions`
- Polyfills: Minimal polyfills for WebGL, WebSocket, fetch (modern browsers have native support)
- Feature detection: Check for WebGL support, show fallback message if unavailable
- Progressive enhancement: Core functionality works without JavaScript, maps require JS
- Automated testing: Playwright E2E tests run on Chrome, Firefox, Safari (WebKit)

**Implementation Notes:**
- Unsupported browser message: "Overworld requires a modern browser. Please upgrade."
- Mobile support: Touch gestures for zoom/pan via `PIXI.InteractionManager`

**Validation:**
- BrowserStack cross-browser testing for visual regression
- Lighthouse audit on all supported browsers

---

### NFR-009: Code Quality

**Requirement:** 80%+ unit test coverage, TypeScript strict mode, linting

**Architecture Solution:**
- Testing: pytest (backend), Vitest (frontend), Playwright (E2E)
- Coverage: codecov integration, fail CI if coverage drops below 80%
- TypeScript strict mode: `strict: true`, no `any` types without explicit override
- Linting: Ruff (Python), ESLint + Prettier (TypeScript), pre-commit hooks
- CI pipeline: GitHub Actions, all tests + lint + type-check + coverage on PR
- Code review: Required PR approval, automated reviewers check for common issues

**Implementation Notes:**
- Pre-commit hook: `ruff check`, `eslint --fix`, `prettier --write`
- CI test parallelization: Run backend and frontend tests concurrently

**Validation:**
- PR merge criteria: All tests pass, coverage ≥ 80%, no lint errors
- Monthly code quality reports: Track test coverage trends

---

### NFR-010: API Design

**Requirement:** RESTful API with OpenAPI 3.0 spec

**Architecture Solution:**
- FastAPI auto-generation: OpenAPI 3.0 spec generated from route decorators + Pydantic models
- API versioning: `/api/v1/` prefix, future versions at `/api/v2/`
- Consistent response format: `{success: bool, data: {...}, errors: [...]}`
- CORS: Configured allowlist for web clients, credentials support
- Rate limiting: Per-endpoint limits, documented in OpenAPI spec
- API documentation: Swagger UI at `/docs`, ReDoc at `/redoc`

**Implementation Notes:**
- Pydantic models for all request/response schemas, auto-validated
- Error responses follow RFC 7807 (Problem Details)

**Validation:**
- OpenAPI spec validation: `openapi-spec-validator`
- API contract testing: Ensure frontend matches spec

---

## Security Architecture

### Authentication

**Method:** JWT + OAuth2

**JWT Tokens:**
- Access token: 24h expiry, claims: `{user_id, email, is_premium, exp, iat}`
- Refresh token: 30d expiry, single-use rotation (new refresh token on each refresh)
- Storage: Redis with user_id index for fast revocation

**OAuth2 Providers:**
- Google, GitHub
- PKCE flow for additional security
- State parameter validation (Redis-backed, 5-minute TTL)

**Password Hashing:**
- bcrypt cost factor 12
- Hash time: < 200ms on modern hardware

### Authorization

**RBAC Model:**
- Roles: `anonymous`, `free`, `premium`
- Permissions: Checked at service layer, not middleware
- Premium features gated via `is_premium` JWT claim

**API Authorization:**
- JWT required for all `/api/v1/*` except `/auth/*`, `/webhooks/*`, `/s/{slug}` (public shares)
- Rate limits enforced based on role

### Data Encryption

**At Rest:**
- PostgreSQL: Transparent Data Encryption (TDE) if supported by managed service
- R2: Server-side encryption (SSE) enabled by default

**In Transit:**
- TLS 1.3 enforced on all endpoints
- Traefik TLS termination with automatic cert renewal (Let's Encrypt)

**Key Management:**
- Application secrets: Environment variables, loaded via `mise` + 1Password
- Production secrets: Kubernetes Secrets, rotated quarterly
- Encryption keys: Fernet symmetric encryption for BYO API keys

### Security Best Practices

**Input Validation:**
- Pydantic validators on all API inputs
- SQL injection prevented via SQLAlchemy ORM (no raw SQL)
- File upload validation: Magic number check, max size limits

**Security Headers:**
```
Strict-Transport-Security: max-age=31536000
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'
```

**CSRF Protection:**
- Double-submit cookie pattern for state-changing endpoints
- SameSite cookie attribute: `Strict`

**XSS Prevention:**
- Markdown sanitization: Strip script tags if rendering user content
- React's built-in XSS protection via JSX escaping

---

## Scalability & Performance

### Scaling Strategy

**Horizontal Scaling:**
- Stateless API pods: Scale independently based on CPU/memory metrics
- K8s HPA: Min 2 replicas, max 10, target 70% CPU utilization
- RabbitMQ workers: Separate deployment, scale based on queue depth

**Vertical Scaling:**
- PostgreSQL: Managed service auto-scales storage
- Redis: Cluster mode with 3 nodes, manual vertical scaling if needed

**Database Scaling:**
- Read replicas for dashboard queries, heavy read endpoints
- Connection pooling: SQLAlchemy pool size 20, max overflow 40 per pod
- Partitioning: `transactions` table partitioned by month

### Performance Optimization

**Query Optimization:**
- JSONB indexing on `maps.hierarchy` for fast L0-L4 navigation
- Eager loading for joined queries (avoid N+1)
- Query monitoring: pg_stat_statements enabled

**Agent Pipeline Optimization:**
- Agent result caching: If same document re-generated, skip Parser agent
- Model selection: Fast models for deterministic tasks, quality models for creative tasks
- Batch processing: Group multiple jobs if queue depth > 10

### Caching Strategy

```
L1: Browser cache (theme assets, static JS/CSS) - 1 year
L2: Cloudflare CDN (exported maps, icons) - 1 month
L3: Redis (user sessions, rate limits, hierarchy JSON) - 1 hour to 24 hours
L4: PostgreSQL query cache - automatic
```

**Cache Invalidation:**
- User sessions: On logout or password change
- Map hierarchy: On map update
- Exported maps: On map regeneration

### Load Balancing

**Traefik Ingress:**
- Algorithm: Round-robin
- Health checks: HTTP GET `/health` every 10s
- Sticky sessions: Not required (stateless API)

**Database Load Balancing:**
- Write traffic: Primary only
- Read traffic: Round-robin across read replicas
- Failover: Automatic promotion of read replica if primary fails

---

## Reliability & Availability

### High Availability Design

**Multi-AZ Deployment:**
- K8s cluster: 3 availability zones
- Database: Multi-AZ managed PostgreSQL (automatic failover)
- Redis: Sentinel mode with 3 nodes (automatic failover)

**Redundancy:**
- No single points of failure for critical path (API, DB, cache)
- RabbitMQ: Clustered with mirrored queues

**Circuit Breakers:**
- OpenRouter API calls: Circuit breaker pattern, fallback to cached responses if available
- Stripe API: Retry with exponential backoff, alert on sustained failures

### Disaster Recovery

**RPO (Recovery Point Objective):** 1 hour
**RTO (Recovery Time Objective):** 4 hours

**Backup Strategy:**
- PostgreSQL: Daily automated backups to R2, point-in-time recovery (PITR) enabled
- Redis: RDB snapshots every 6 hours + AOF for write-ahead logging
- R2: Versioning enabled, 30-day retention

**Restore Procedures:**
1. PostgreSQL: Restore from latest backup, replay WAL logs to desired point
2. Redis: Restore from RDB snapshot, accept data loss up to 6 hours
3. R2: Restore from version history

### Backup Strategy

| Component | Frequency | Retention | Location |
|-----------|-----------|-----------|----------|
| PostgreSQL | Daily | 30 days | Cloudflare R2 |
| Redis | Every 6 hours (RDB) | 7 days | Cloudflare R2 |
| R2 Objects | Versioning | 30 days | Built-in versioning |

### Monitoring & Alerting

**Metrics (Prometheus + Grafana):**
- API latency (p50, p95, p99)
- Queue depth and processing rate
- Database connection pool utilization
- Redis hit/miss ratio
- Generation success rate
- Error rate by endpoint

**Logging (Structured JSON → Loki):**
- Request ID tracing across services
- Agent execution traces
- Error stack traces with context
- Audit logs for sensitive operations (token purchases, account deletions)

**Alerting (PagerDuty):**
- Critical: p95 latency > 1s for 5 minutes
- Critical: Error rate > 5% for 2 minutes
- Warning: Queue depth > 100 for 10 minutes
- Warning: Database connection pool > 80% for 5 minutes

---

## Integration Architecture

### External Integrations

| Service | Integration Type | Purpose | Failure Mode |
|---------|------------------|---------|--------------|
| **OpenRouter** | REST API | LLM provider routing | Circuit breaker, cached responses |
| **Stripe** | REST API + Webhooks | Payment processing | Retry with backoff, manual reconciliation |
| **Cloudflare R2** | S3-compatible API | Object storage | Retry 3x, fallback to local disk |
| **SendGrid/Resend** | REST API | Transactional email | Queue for retry, alert on sustained failures |

### Internal Integrations

**API ↔ RabbitMQ:**
- Protocol: AMQP 0-9-1
- Connection: Persistent connection with heartbeat
- Publish: Confirm mode enabled (at-least-once delivery)

**API ↔ PostgreSQL:**
- Protocol: PostgreSQL wire protocol
- Connection: SQLAlchemy connection pooling
- Transactions: ACID guarantees for critical operations

**API ↔ Redis:**
- Protocol: Redis protocol
- Connection: Connection pooling via `redis-py`
- Persistence: RDB snapshots + AOF

### Message/Event Architecture (if applicable)

**RabbitMQ Queue Design:**

| Queue | Purpose | Priority | DLQ |
|-------|---------|----------|-----|
| `generation.pending` | New generation jobs | Yes (premium first) | `generation.dlq` |
| `generation.retry` | Failed jobs for retry | No | `generation.dlq` |
| `webhook.stripe` | Stripe webhook events | No | `webhook.dlq` |

**Message Format:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "document_url": "https://r2.../uploads/...",
  "theme_id": "smb3-default",
  "priority": 5,
  "created_at": "2026-01-08T12:00:00Z"
}
```

---

## Development Architecture

### Code Organization

```
/overworld
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routers
│   │   ├── models/        # SQLAlchemy models
│   │   ├── services/      # Business logic layer
│   │   ├── agents/        # Multi-agent pipeline
│   │   └── core/          # Config, auth, dependencies
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── lib/           # Utilities, API client
│   │   ├── renderers/     # PixiJS rendering logic
│   │   └── App.tsx
│   ├── tests/
│   └── package.json
├── infra/
│   ├── docker-compose.yml
│   ├── traefik.yml
│   └── k8s/               # Kubernetes manifests
└── docs/
```

### Module Structure

**Backend Modules:**
```
app/
├── api/
│   ├── v1/
│   │   ├── auth.py        # Auth endpoints
│   │   ├── tokens.py      # Token endpoints
│   │   ├── maps.py        # Map endpoints
│   │   └── generation.py  # Generation endpoints
├── services/
│   ├── auth_service.py
│   ├── token_service.py
│   ├── map_service.py
│   └── generation_service.py
├── agents/
│   ├── parser.py
│   ├── artist.py
│   ├── road.py
│   └── coordinator.py
└── models/
    ├── user.py
    ├── token.py
    └── map.py
```

**Frontend Modules:**
```
src/
├── components/
│   ├── auth/
│   ├── dashboard/
│   ├── map-viewer/
│   └── shared/
├── lib/
│   ├── api-client.ts
│   ├── auth.ts
│   └── utils.ts
└── renderers/
    ├── pixi-renderer.ts
    ├── map-renderer.ts
    └── hierarchy-navigator.ts
```

### Testing Strategy

**Backend Testing:**
- **Unit tests (pytest):** Service layer, agent logic, 80%+ coverage
- **Integration tests (pytest):** API endpoints, database operations
- **Contract tests:** Pydantic schema validation

**Frontend Testing:**
- **Unit tests (Vitest):** Components, utilities, 80%+ coverage
- **Integration tests (Vitest):** API client, state management
- **Visual regression:** Percy or Chromatic for UI changes

**E2E Testing:**
- **Playwright:** Critical user flows (signup, generation, export)
- **Browsers:** Chrome, Firefox, Safari (WebKit)
- **Frequency:** On every PR

**Performance Testing:**
- **k6:** Load testing for API endpoints
- **Lighthouse:** Frontend performance audit

### CI/CD Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                       GitHub Actions                             │
└─────────────────────────────────────────────────────────────────┘

PR Opened → Lint (ruff, eslint) → Type Check (mypy, tsc) → Test (pytest, vitest)
→ Coverage Check (≥ 80%) → E2E (Playwright) → Build (Docker) → Security Scan
→ PR Approval Required → Merge to main

main branch → Build Production Images → Push to Registry → Deploy to Staging
→ Smoke Tests → Manual Approval → Deploy to Production (rolling update)
```

**CI Stages:**
1. **Lint & Format:** ruff, eslint, prettier (auto-fix on commit)
2. **Type Check:** mypy (backend), tsc (frontend)
3. **Unit Tests:** pytest, vitest (parallel execution)
4. **Integration Tests:** pytest with test database
5. **E2E Tests:** Playwright on staging environment
6. **Coverage:** codecov, fail if < 80%
7. **Security Scan:** OWASP ZAP, Trivy (container scanning)
8. **Build:** Docker multi-stage builds, layer caching

---

## Deployment Architecture

### Environments

| Environment | Purpose | Deployment | Database |
|-------------|---------|------------|----------|
| **Local** | Development | Docker Compose | Local PostgreSQL |
| **Staging** | Pre-production testing | K8s cluster | Staging DB (restore from prod backup) |
| **Production** | Live | K8s cluster (multi-AZ) | Managed PostgreSQL (HA) |

**Environment Parity:**
- Staging mirrors production configuration
- Staging uses prod-like data (anonymized)
- Staging runs smoke tests before prod deployment

### Deployment Strategy

**Rolling Update:**
- Update 25% of pods at a time
- Health check before proceeding to next batch
- Rollback: Automated if error rate > 5% for 2 minutes

**Database Migrations:**
- Alembic for schema versioning
- Backward-compatible migrations only (two-phase deployment)
- Migrations run before deployment, verify success

**Zero-Downtime Strategy:**
1. Deploy new version alongside old (both running)
2. Health check new version
3. Gradually shift traffic (25%, 50%, 75%, 100%)
4. Monitor error rates at each step
5. Rollback if error rate spikes

### Infrastructure as Code

**Terraform/OpenTofu:**
- Provision K8s cluster, managed PostgreSQL, Redis
- State stored in R2 with locking

**K8s Manifests:**
- Kustomize overlays for staging/production
- Helm charts for complex applications (RabbitMQ)

**Configuration Management:**
- ConfigMaps for application config
- Secrets for sensitive data (Stripe keys, DB credentials)
- `mise` for local environment setup

---

## Requirements Traceability

### Functional Requirements Coverage

| FR ID | FR Name | Components | Implementation Notes |
|-------|---------|------------|---------------------|
| FR-001 | Document Upload | API Gateway, Map Service, R2 Storage | File validation, magic number check |
| FR-002 | Hierarchical Structure Extraction | Document Parser, Parser Agent | Obsidian Tasks syntax, L0-L4 mapping |
| FR-003 | Document Preview | Map Service, Frontend | Tree view with expand/collapse |
| FR-004 | Artist Agent - Style Selection | Artist Agent, Theme Service | 3-5 style variations, Art Director approval |
| FR-005 | Road/Path Generator | Road Generator Agent | Bezier/spline-based curves |
| FR-006 | Coordinate Spline Mapping | Road Generator Agent | Arc-length parameterization |
| FR-007 | Milestone Icon Placement (MVP) | Icon Placer Agent | Numbered circles, evenly spaced |
| FR-008 | Custom Icon Placement (Post-MVP) | Icon Placer Agent, Theme Service | Keyword→icon mapping |
| FR-009 | 2D Rendering Engine | PixiJS Renderer | WebGL, sprite batching, 60 FPS |
| FR-010 | Interactive Map Navigation | PixiJS Renderer, Frontend | Zoom/pan, click for details |
| FR-011 | User Registration & Authentication | Auth Service, FastAPI-Users | Email/password, OAuth2, email verification |
| FR-012 | User Dashboard | Frontend, Map Service | Map list, token balance, usage history |
| FR-013 | Token Allocation | Token Service | 10 tokens/month, monthly reset |
| FR-014 | Token Consumption | Token Service, Generation Orchestrator | 1 token (basic), 5 tokens (custom theme) |
| FR-015 | Token Purchase & Subscription | Token Service, Stripe | One-time packs, subscriptions |
| FR-016 | Anonymous Rate Limiting | Auth Service, Redis | IP-based, BYO API key escape hatch |
| FR-017 | Default Theme (SMB3) | Theme Service | 8/16-bit aesthetic, free tier |
| FR-018 | Custom Theme Library | Theme Service | Premium themes, 5-token cost |
| FR-019 | User-Uploaded Themes (Post-MVP) | Theme Service | Theme editor, validation |
| FR-020 | Image Export | Export Service | PNG/SVG, watermarked (free) |
| FR-021 | Shareable Links | Map Service, Share Links | Public view-only, password protection |
| FR-022 | Embed Code | Map Service | Premium-only, iframe embed |
| FR-023 | Multi-Level Interactive Navigation | PixiJS Renderer, Frontend | L0-L4 hierarchy, click-through |

### Non-Functional Requirements Coverage

| NFR ID | NFR Name | Solution | Validation |
|--------|----------|----------|------------|
| NFR-001 | <30s generation (p95) | Queue-based async, progressive agents, WebSocket progress | Load testing, p95 monitoring |
| NFR-002 | 60 FPS rendering | PixiJS WebGL, object pooling, viewport culling | Chrome DevTools, Lighthouse |
| NFR-003 | JWT/OAuth2 auth | FastAPI-Users, bcrypt, CSRF protection | Penetration testing, OWASP ZAP |
| NFR-004 | PCI-DSS payment | Stripe Checkout, webhook verification, TLS 1.3 | Stripe CLI testing, monitoring |
| NFR-005 | 1,000 concurrent users | Horizontal scaling, connection pooling, CDN | k6 load testing |
| NFR-006 | Cost control anonymous | Redis budget cap, IP rate limit, BYO API key | Budget exhaustion testing |
| NFR-007 | 99.5% uptime | Multi-AZ, health checks, automated failover | Chaos engineering, uptime reports |
| NFR-008 | Modern browser support | Vite transpilation, Playwright testing | BrowserStack, Lighthouse |
| NFR-009 | 80%+ test coverage | pytest, Vitest, Playwright, codecov | CI coverage checks |
| NFR-010 | OpenAPI 3.0 REST | FastAPI auto-generation, Swagger UI | OpenAPI spec validation |

---

## Trade-offs & Decision Log

### Decision 1: Modular Monolith vs Microservices

**Decision:** Modular Monolith

**Trade-off:**
- ✓ Gain: Simpler deployment, faster development for Level 2 scope, single codebase
- ✗ Lose: Cannot scale individual modules independently, future extraction requires refactoring

**Rationale:** Project scope (Level 2, 5-15 stories) does not justify microservices complexity. Clear module boundaries enable future extraction if needed. Acceptable for initial scale (1,000 concurrent users).

---

### Decision 2: PixiJS vs Phaser vs PlayCanvas

**Decision:** PixiJS

**Trade-off:**
- ✓ Gain: Lightweight (150KB), best 2D WebGL performance, sprite batching, object pooling
- ✗ Lose: Less opinionated than Phaser, no built-in physics/scenes (not needed for static maps)

**Rationale:** 60 FPS rendering (NFR-002) requires hardware-accelerated 2D renderer. PixiJS is purpose-built for 2D sprites without game engine overhead.

---

### Decision 3: OpenRouter vs Single LLM Provider

**Decision:** OpenRouter

**Trade-off:**
- ✓ Gain: Multi-provider routing, cost optimization, fallback resilience, unified API
- ✗ Lose: Additional abstraction layer, dependency on OpenRouter uptime

**Rationale:** Multi-provider fallback critical for reliability. Cost optimization via model selection (fast models for deterministic tasks). BYO API key flow provides escape hatch for anonymous users.

---

### Decision 4: Queue-Based vs Synchronous Generation

**Decision:** Queue-Based (RabbitMQ)

**Trade-off:**
- ✓ Gain: Async processing, API responsiveness, priority queues, dead-letter handling
- ✗ Lose: Operational complexity, eventual consistency, monitoring overhead

**Rationale:** 30-second generation target (NFR-001) requires decoupling API from long-running AI tasks. WebSocket progress updates provide real-time feedback. Queue enables independent scaling of generation workers.

---

### Decision 5: PostgreSQL JSONB vs Separate Tables for Hierarchy

**Decision:** PostgreSQL JSONB

**Trade-off:**
- ✓ Gain: Flexible schema, fast traversal with GIN indexing, single query for full hierarchy
- ✗ Lose: Harder to query individual hierarchy levels, no relational integrity

**Rationale:** L0-L4 hierarchy structure varies per map (dynamic depth). JSONB enables flexible storage with fast GIN indexing for navigation. Relational model would require recursive CTEs (complex, slower).

---

## Open Issues & Risks

### Open Issues

| Issue | Impact | Mitigation |
|-------|--------|------------|
| **OpenRouter rate limits** | Generation failures during high traffic | Circuit breaker, exponential backoff, multi-provider fallback |
| **JSONB hierarchy query performance at scale** | Slow L0-L4 navigation for large maps | GIN indexing, caching in Redis, pagination for deep hierarchies |
| **WebSocket scaling across K8s pods** | Inconsistent progress updates if user switches pods | Redis pub/sub for cross-pod messaging |
| **Stripe webhook replay attacks** | Duplicate token grants | Idempotency via `stripe_event_id` check in transactions table |

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **LLM cost spikes** | Medium | High | Hard budget cap, BYO API key escape hatch, cost monitoring |
| **PixiJS performance on low-end devices** | Medium | Medium | LOD rendering, viewport culling, performance profiling |
| **Agent pipeline timeout failures** | High | Medium | 120s hard timeout, refund tokens, retry queue |
| **PostgreSQL connection pool exhaustion** | Medium | High | Connection pooling, read replicas, K8s HPA scaling |
| **Stripe webhook delivery failures** | Low | High | Retry logic, manual reconciliation dashboard |

---

## Assumptions & Constraints

### Assumptions (from PRD)

1. Users have structured documents: We assume users provide documents already organized hierarchically. We do not restructure unorganized content.
2. Target audience has gaming context: Users understand 8/16-bit gaming aesthetics (nostalgia factor critical for engagement).
3. LLM costs remain stable: Monetization model assumes current LLM API pricing. Significant price increases would require model adjustment.
4. Modern browser adoption: 95%+ of users on Chrome/Firefox/Safari last 2 versions. Legacy browser support not prioritized.
5. Stripe availability: Stripe services available in target markets (US, EU initially).

### Additional Assumptions

6. OpenRouter uptime: 99.9% uptime for LLM provider routing. Fallback to cached responses if unavailable.
7. Cloudflare R2 reliability: S3-compatible API maintains compatibility. Migration path to AWS S3 if needed.
8. K8s managed service: EKS/GKE/AKS handles cluster management, auto-scaling, upgrades.

### Constraints

1. Budget: Initial launch budget limits infrastructure to single region deployment.
2. Team size: Small team (1-3 developers) limits operational complexity. Modular monolith chosen over microservices.
3. Time to market: 3-month MVP target requires prioritization (numbered circles over custom icons).
4. Legal: GDPR compliance required for EU users (data export, deletion, consent).

---

## Future Considerations

### Phase 2 Enhancements (Post-MVP)

1. **Custom Icons (FR-008):** Keyword→icon mapping, themed icon libraries
2. **L1-L4 Interactive Navigation (FR-023):** Full hierarchy with click-through exploration
3. **User-Uploaded Themes (FR-019):** Theme editor, validation, marketplace
4. **Embed Code (FR-022):** White-label iframe embedding for premium users

### Phase 3 Enhancements (6-12 months)

1. **Mobile Apps:** Native iOS/Android apps for map viewing and editing
2. **Real-Time Collaboration:** Multiple users editing same map simultaneously
3. **Gantt Chart Integration:** Traditional project management views alongside maps
4. **PM Tool Integrations:** Jira, Asana, Monday.com sync via API webhooks
5. **AI Content Suggestions:** LLM-powered task breakdown, milestone naming

### Scalability Considerations

1. **Microservices Extraction:** If scale exceeds 10,000 concurrent users, extract auth, tokens, generation into separate services
2. **Multi-Region Deployment:** Expand to 3+ regions for global latency reduction
3. **Read Replica Scaling:** PostgreSQL read replicas per region for dashboard queries
4. **Agent Pipeline Sharding:** Partition generation queue by theme or complexity for specialized workers

### Technical Debt

1. **Agent Result Caching:** Cache Parser output for identical documents to reduce generation time
2. **Frontend Code Splitting:** Split PixiJS renderer into separate bundle, lazy-load for non-map pages
3. **Database Partitioning:** Partition `transactions` table by month to maintain query performance
4. **Observability Improvements:** Distributed tracing across agents with OpenTelemetry

---

## Approval & Sign-off

**Review Status:**
- [ ] Technical Lead
- [ ] Product Owner
- [ ] Security Architect (if applicable)
- [ ] DevOps Lead

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-08 | System Architect (BMAD Method v6) | Initial architecture |

---

## Next Steps

### Phase 4: Sprint Planning & Implementation

Run `/sprint-planning` to:
- Break epics into detailed user stories
- Estimate story complexity
- Plan sprint iterations
- Begin implementation following this architectural blueprint

**Key Implementation Principles:**
1. Follow component boundaries defined in this document
2. Implement NFR solutions as specified
3. Use technology stack as defined
4. Follow API contracts exactly
5. Adhere to security and performance guidelines

---

**This document was created using BMAD Method v6 - Phase 3 (Solutioning)**

*To continue: Run `/workflow-status` to see your progress and next recommended workflow.*

---

## Appendix A: Technology Evaluation Matrix

| Category | Option 1 | Option 2 | Option 3 | Decision | Rationale |
|----------|----------|----------|----------|----------|-----------|
| **2D Renderer** | PixiJS (150KB) | Phaser (300KB+) | PlayCanvas (3D-focused) | PixiJS | Best 2D WebGL performance, lightweight |
| **LLM Provider** | OpenRouter | OpenAI Direct | Claude Direct | OpenRouter | Multi-provider routing, cost optimization |
| **Queue** | RabbitMQ | Redis Queue | Celery (RabbitMQ backend) | RabbitMQ | Robust guarantees, advanced routing |
| **Database** | PostgreSQL | MongoDB | Firebase | PostgreSQL | ACID, JSONB flexibility, user preference |
| **Object Storage** | Cloudflare R2 | AWS S3 | Backblaze B2 | R2 | Zero egress costs, S3 compatibility |
| **Infra** | Docker Compose → K8s | Managed PaaS | VMs | Docker/K8s | Full control, user preference |

---

## Appendix B: Capacity Planning

### Expected Load (Month 1)

| Metric | Value | Assumption |
|--------|-------|------------|
| **Active Users** | 500 | Gradual ramp-up post-launch |
| **Maps Generated/Day** | 200 | 40% of users generate 1 map/day |
| **Concurrent Users (Peak)** | 50 | 10% of active users online at peak |
| **API Requests/Second** | 10 | Average across all endpoints |

### Expected Load (Month 6)

| Metric | Value | Assumption |
|--------|-------|------------|
| **Active Users** | 5,000 | Viral growth (ProductHunt, social) |
| **Maps Generated/Day** | 2,000 | Increased engagement |
| **Concurrent Users (Peak)** | 500 | 10% of active users online at peak |
| **API Requests/Second** | 100 | Increased dashboard traffic |

### Infrastructure Sizing

| Component | Month 1 | Month 6 | Scaling Trigger |
|-----------|---------|---------|-----------------|
| **API Pods** | 2 | 6 | CPU > 70% for 5 min |
| **RabbitMQ Workers** | 2 | 10 | Queue depth > 50 |
| **PostgreSQL** | db.t3.small | db.t3.large | CPU > 60%, connections > 80% |
| **Redis** | cache.t3.micro | cache.t3.small | Memory > 70% |

---

## Appendix C: Cost Estimation

### Monthly Costs (Month 1, 500 users)

| Component | Cost | Notes |
|-----------|------|-------|
| **Compute (K8s)** | $50 | 2 API pods, 2 workers (t3.small equivalent) |
| **Database (PostgreSQL)** | $25 | Managed service, db.t3.small |
| **Cache (Redis)** | $15 | cache.t3.micro |
| **Object Storage (R2)** | $5 | 100GB storage, zero egress |
| **LLM Costs (OpenRouter)** | $100 | 200 generations/day × $0.50/generation (estimated) |
| **Stripe Fees** | $10 | 2.9% + $0.30 per transaction (low initial volume) |
| **Monitoring (Grafana Cloud)** | $20 | Free tier likely sufficient, budgeted conservatively |
| **Total** | **$225/month** | |

### Monthly Costs (Month 6, 5,000 users)

| Component | Cost | Notes |
|-----------|------|-------|
| **Compute (K8s)** | $300 | 6 API pods, 10 workers (auto-scaling) |
| **Database (PostgreSQL)** | $150 | db.t3.large + read replica |
| **Cache (Redis)** | $50 | cache.t3.small |
| **Object Storage (R2)** | $50 | 1TB storage, zero egress |
| **LLM Costs (OpenRouter)** | $1,000 | 2,000 generations/day × $0.50/generation |
| **Stripe Fees** | $200 | Increased transaction volume |
| **Monitoring (Grafana Cloud)** | $50 | Pro tier for advanced features |
| **Total** | **$1,800/month** | |

### Revenue Assumptions (Month 6)

| Source | Monthly Revenue | Notes |
|--------|-----------------|-------|
| **Free Tier** | $0 | 10 tokens/month free |
| **Token Purchases** | $500 | 50 users × $10 avg purchase |
| **Subscriptions** | $1,000 | 50 users × $20/month subscription |
| **Total** | **$1,500/month** | |

**Break-even:** Month 8-10 (estimated), assuming 10% conversion to paid.

**Note:** LLM costs are the primary variable. BYO API key adoption and anonymous budget caps critical for cost control.
