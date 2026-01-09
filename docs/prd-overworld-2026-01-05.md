# Product Requirements Document (PRD)
## Overworld - Interactive Project Visualization Platform

**Document Version:** 1.0
**Date:** 2026-01-05
**Author:** Product Manager (BMAD Method v6)
**Project:** Overworld
**Project Level:** 2 (Medium - 5-15 stories)

---

## Executive Summary

**Overworld** transforms linear project documentation (roadmaps, implementation plans, hierarchical task lists) into visually engaging, interactive 8/16-bit era overworld maps. By leveraging multi-agent AI architecture and game-inspired aesthetics, Overworld makes project planning intuitive, accessible, and fun.

**Core Value Proposition:**
- **For Product Managers:** Transform boring roadmap documents into visually compelling stakeholder presentations
- **For Development Teams:** Track progress through familiar gaming metaphors (worlds, levels, milestones)
- **For Executives:** Understand complex projects at-a-glance without parsing dense documentation

**Business Model:** Freemium with fair, accessible monetization
- Free tier: 10 tokens/month, SMB3 theme only
- Premium tier: Unlimited generations, custom themes, watermark-free exports
- Anonymous tier: Rate-limited trial access with BYO API key option for cost control

---

## Business Objectives

1. **Create Engaging Visualization Tool** that transforms linear documents into visually compelling 8/16-bit maps
2. **Reduce Friction in Project Comprehension** via familiar gaming metaphors and interactive exploration
3. **Build Modular Multi-Agent Architecture** for maintainability, extensibility, and clear separation of concerns
4. **Establish Sustainable, Fair Monetization** that keeps the tool accessible while generating revenue

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| User Acquisition | 1,000 users in 3 months | User registrations |
| Conversion Rate | 10% free → paid | Payment transactions / Total users |
| Map Generation Success | >95% successful generations | Successful outputs / Total attempts |
| User Engagement | 3+ maps generated per user | Avg generations per user |
| Performance | <30s generation time (95th percentile) | Server-side monitoring |
| Cost Per Anonymous User | <$0.50/generation | LLM API costs + infra |

---

## User Personas

### 1. Product Manager Paula
- **Role:** Mid-level product manager at SaaS company
- **Goals:** Make roadmaps more engaging for stakeholders, reduce time explaining plans
- **Pain Points:** Linear documents are boring, executives don't read detailed specs
- **Usage:** Weekly roadmap reviews, quarterly planning presentations

### 2. Indie Dev Ian
- **Role:** Solo developer building side projects
- **Goals:** Visual progress tracking that feels motivating and fun
- **Pain Points:** Project management tools feel corporate and joyless
- **Usage:** Personal project tracking, progress sharing on social media

### 3. Team Lead Tamara
- **Role:** Engineering team lead at mid-size company
- **Goals:** Clear milestone visualization for non-technical executives
- **Pain Points:** Executives need visual dashboards, not Jira tickets
- **Usage:** Sprint planning visualization, executive status reports

---

## Functional Requirements

### Area 1: Document Ingestion & Parsing

#### FR-001: Document Upload
**Priority:** Must Have

**Description:**
System accepts markdown and PDF documents as input for map generation.

**Acceptance Criteria:**
- [ ] Accepts .md files up to 5MB
- [ ] Accepts .pdf files up to 10MB
- [ ] Validates file format before processing (magic number verification)
- [ ] Returns clear error messages for unsupported formats
- [ ] Drag-and-drop upload interface
- [ ] Progress indicator during upload

**Dependencies:** None

---

#### FR-002: Hierarchical Structure Extraction
**Priority:** Must Have

**Description:**
System parses document to extract hierarchical task structure following Obsidian Tasks syntax conventions.

**Acceptance Criteria:**
- [ ] Identifies markdown header levels (H1, H2, H3, H4) as hierarchy
- [ ] Parses Obsidian Tasks syntax (`- [ ]`, `- [x]`, due dates, tags)
- [ ] Extracts ordered task lists and detects milestone markers
- [ ] Outputs structured JSON representation (L0-L4 hierarchy)
- [ ] Preserves parent-child relationships in parsed structure
- [ ] Handles nested lists up to 4 levels deep

**Dependencies:** None

**Technical Notes:**
- L0: Product (entire map)
- L1: Milestones/Phases (islands/worlds)
- L2: Epics/Requirements (levels on roads)
- L3: Tickets/Tasks (landmarks within levels)
- L4: Sub-tasks (bonus levels inside landmarks)

---

#### FR-003: Document Preview
**Priority:** Should Have

**Description:**
User can preview parsed hierarchical structure before generating map to verify correctness.

**Acceptance Criteria:**
- [ ] Shows hierarchy tree view with expand/collapse
- [ ] Displays detected milestones with counts per level
- [ ] Allows manual adjustments (edit labels, reorder items)
- [ ] Clear indication of which items will appear at which level (L0-L4)
- [ ] "Generate Map" button enabled only after structure validation

**Dependencies:** FR-002

---

### Area 2: Map Generation Pipeline

#### FR-004: Artist Agent - Style Selection
**Priority:** Must Have

**Description:**
Multi-agent system generates 3-5 style variations for user to choose from before final map generation.

**Acceptance Criteria:**
- [ ] Produces 3-5 aesthetic variations (SMB3-inspired by default for free tier)
- [ ] Displays options as thumbnail previews with style name
- [ ] User selects preferred style before full generation
- [ ] Free tier: Only SMB3 style available, premium styles locked with upgrade prompt
- [ ] Art Director agent provides final approval (or human override)
- [ ] Style variations include color palette preview

**Dependencies:** FR-002 (requires parsed structure)

**Technical Notes:**
- Art Director agent validates aesthetic quality before presenting options
- Random generation with approval gates prevents low-quality outputs

---

#### FR-005: Road/Path Generator
**Priority:** Must Have

**Description:**
System generates stylized, non-linear road/path with natural curves and visual appeal matching selected theme.

**Acceptance Criteria:**
- [ ] Creates non-linear path (avoids straight lines, adds organic curves)
- [ ] Path winds naturally across canvas without overlapping
- [ ] Path texture and color match selected theme
- [ ] Path is continuous from start milestone to finish milestone
- [ ] Path respects canvas boundaries and leaves margin for icons
- [ ] Algorithm produces aesthetically pleasing curves (Bézier/spline-based)

**Dependencies:** FR-004 (theme selection)

---

#### FR-006: Coordinate Spline Mapping
**Priority:** Must Have

**Description:**
System converts visual road into mathematical spline with ordered coordinates for precise milestone placement.

**Acceptance Criteria:**
- [ ] Generates spline equation fitting the visual road
- [ ] Provides ordered coordinate points along spline (parameterized 0.0 to 1.0)
- [ ] Coordinate ordering reflects project sequence (start = 0.0, end = 1.0)
- [ ] Spline data exportable as JSON for programmatic access
- [ ] Scatter plot algorithm determines milestone placement positions
- [ ] Distance thresholds prevent milestone overlap

**Dependencies:** FR-005 (road generation)

**Technical Notes:**
- Spline must support non-linear parameterization (arc-length parameterization)
- Coordinate system enables ordered milestone placement along arbitrary curves

---

#### FR-007: Milestone Icon Placement (MVP)
**Priority:** Must Have

**Description:**
System places milestone markers along the path at aesthetically balanced intervals (MVP: numbered circles).

**Acceptance Criteria:**
- [ ] MVP: Numbered circles (1, 2, 3...) placed evenly along spline
- [ ] Markers positioned near path with configurable offset (scatter threshold)
- [ ] Marker count matches detected milestones from parsed document
- [ ] Visual spacing is aesthetically balanced (no clustering)
- [ ] Markers avoid overlapping with path or each other
- [ ] Numbering sequence reflects document order

**Dependencies:** FR-006 (spline coordinates)

---

#### FR-008: Custom Icon Placement (Post-MVP)
**Priority:** Could Have

**Description:**
System places thematic icons (castles, plants, pipes, stars) based on milestone type or keywords.

**Acceptance Criteria:**
- [ ] Icon library available (themed to selected style)
- [ ] Milestone keywords/tags map to icon types (e.g., "deploy" → castle, "feature" → star)
- [ ] Icons scale appropriately to map size and surrounding elements
- [ ] Fallback to numbered circles if no icon match found
- [ ] Icon placement respects scatter threshold to avoid overlap

**Dependencies:** FR-007, FR-018 (theme library)

---

#### FR-023: Multi-Level Interactive Navigation
**Priority:** Must Have (Phase 2 - Post-MVP for L1-L4)

**Description:**
Maps support 4-level hierarchy with click-through navigation between product/worlds/levels/landmarks, creating "game-like" exploration experience.

**Acceptance Criteria:**
- [ ] L0: Entire product displayed as single overworld map
- [ ] L1: Milestones/Phases displayed as disconnected themed islands (Mario worlds analogy)
- [ ] L2: Epics/Requirements displayed as levels encountered on roads within islands
- [ ] L3: Tasks/Landmarks displayed within levels (clickable landmarks)
- [ ] L4: Sub-tasks displayed as bonus level detail view inside landmarks
- [ ] Smooth animated transitions between levels (zoom in/out effects)
- [ ] Breadcrumb navigation to return to parent levels (always visible)
- [ ] Level completion visualization (e.g., collecting stars à la Super Mario 64)
- [ ] Order-agnostic completion for parallel tasks (island model)

**Dependencies:** FR-006, FR-007, FR-009, FR-010

**Technical Notes:**
- L1+ navigation unlocks unlimited depth within reason (computational limits apply)
- Interactive hierarchy is core differentiator for "game-like" engagement

---

### Area 3: Rendering & Visualization

#### FR-009: 2D Rendering Engine
**Priority:** Must Have

**Description:**
System renders maps using 2D graphics toolkit (PlayCanvas, PixiJS, Phaser, or Canvas API) with smooth animations and game-like interactivity.

**Acceptance Criteria:**
- [ ] Renders complete map in browser with high visual fidelity
- [ ] Supports smooth zoom/pan interactions (60 FPS minimum)
- [ ] Renders at high DPI for crisp visuals on retina displays
- [ ] Performance: Renders maps with 50+ milestones in < 3 seconds
- [ ] Animation support: Smooth transitions, hover effects, click animations
- [ ] Supports particle effects and visual flourishes for engagement

**Dependencies:** FR-005, FR-006, FR-007

**Technical Notes:**
- Animation support is Must Have (game-like feel requires motion)
- Technology choice (PlayCanvas vs PixiJS vs Phaser) deferred to Architecture phase
- Consider 3D engine with orthogonal view if 2D options insufficient

---

#### FR-010: Interactive Map Navigation
**Priority:** Should Have

**Description:**
Users can interact with generated maps (zoom, pan, click milestones for details).

**Acceptance Criteria:**
- [ ] Click milestone to see details modal (name, description, status)
- [ ] Zoom in/out with mouse wheel or pinch gestures (mobile)
- [ ] Pan across large maps with drag gesture
- [ ] Smooth zoom without quality loss (vector-based or dynamic re-rendering)
- [ ] Tooltip on hover showing milestone name and completion status
- [ ] Keyboard navigation support (arrow keys for pan, +/- for zoom)

**Dependencies:** FR-009, FR-023

---

### Area 4: User Management & Authentication

#### FR-011: User Registration & Authentication
**Priority:** Must Have

**Description:**
Users can create accounts with email/password or OAuth, with anonymous access for evaluation.

**Acceptance Criteria:**
- [ ] Email + password registration with validation
- [ ] OAuth support (Google, GitHub) via standard OAuth2 flow
- [ ] Email verification required before full account activation
- [ ] Password reset flow via email token
- [ ] Anonymous generation with hard daily budget cap (cost control)
- [ ] IP-based rate limiting (max 3 generations/day per IP for anonymous)
- [ ] Cookie-based tracking for soft limits (browser fingerprinting)
- [ ] BYO API key option for anonymous users (provide own LLM provider key to bypass daily limits)

**Dependencies:** None

**Technical Notes:**
- Anonymous tier critical for "try before buy" UX
- Hard budget cap prevents runaway LLM costs (e.g., $50/day max for anonymous)
- BYO API key escapes cost constraints for power users evaluating service

---

#### FR-012: User Dashboard
**Priority:** Must Have

**Description:**
Authenticated users have dashboard showing generated maps, token balance, and usage history.

**Acceptance Criteria:**
- [ ] Lists all user-generated maps with thumbnails and creation dates
- [ ] Shows current token balance prominently
- [ ] Displays usage history (generations, tokens spent, generation dates)
- [ ] Access to account settings (profile, password change, billing)
- [ ] Quick actions: Generate new map, purchase tokens, view/edit past maps
- [ ] Filter/search past maps by name or date

**Dependencies:** FR-011

---

### Area 5: Monetization & Token System

#### FR-013: Token Allocation
**Priority:** Must Have

**Description:**
System grants 10 free tokens per month to all authenticated users, resetting monthly.

**Acceptance Criteria:**
- [ ] New users receive 10 tokens immediately upon signup
- [ ] Tokens reset to 10 on 1st of each month (UTC timezone)
- [ ] Unused tokens do not roll over (reset to 10, not incremented)
- [ ] Token balance visible on dashboard with reset date
- [ ] Email notification 3 days before monthly reset (if user has 0 tokens)

**Dependencies:** FR-011, FR-012

---

#### FR-014: Token Consumption
**Priority:** Must Have

**Description:**
Map generation consumes tokens based on generation type (basic = 1 token, custom theme = 5 tokens).

**Acceptance Criteria:**
- [ ] Basic generation (default SMB3 theme) = 1 token
- [ ] Custom theme generation = 5 tokens
- [ ] Token deducted before generation starts (pre-flight check)
- [ ] Insufficient tokens: Clear error message with "Purchase Tokens" CTA
- [ ] Token consumption logged in usage history with timestamp
- [ ] Refund tokens if generation fails (server error, not user error)

**Dependencies:** FR-013

**Technical Notes:**
- Token costs subject to business analysis and market testing
- Default costs: 1 token (basic), 5 tokens (custom theme)

---

#### FR-015: Token Purchase & Subscription
**Priority:** Must Have

**Description:**
Users can purchase additional tokens via one-time packs or subscribe for unlimited generation.

**Acceptance Criteria:**
- [ ] One-time token packs purchasable (e.g., 50 tokens for $9.99, 150 tokens for $24.99)
- [ ] Subscription tier: Unlimited generations for $19/month (cancel anytime)
- [ ] Payment via Stripe with saved payment methods
- [ ] Receipt/invoice generation via email immediately after purchase
- [ ] Purchased tokens added to balance immediately (no monthly reset for purchased tokens)
- [ ] Subscription includes access to all premium themes

**Dependencies:** FR-014

**Technical Notes:**
- Pricing deferred to business analysis (suggested defaults above)
- Stripe integration handles PCI compliance

---

#### FR-016: Anonymous Rate Limiting
**Priority:** Must Have

**Description:**
Free tier and anonymous users subject to rate limits to control costs.

**Acceptance Criteria:**
- [ ] Anonymous users: Max 3 generations per day per IP (rolling 24-hour window)
- [ ] Hard daily budget enforced server-side (e.g., $50/day total for all anonymous users)
- [ ] Once budget reached, anonymous generation disabled until next day (UTC reset)
- [ ] Clear messaging: "Anonymous limit reached. Sign up for free tokens or use BYO API key."
- [ ] BYO API key flow: User provides OpenAI/Anthropic key, bypasses anonymous budget
- [ ] Authenticated free tier: 10 tokens/month (not daily limit)

**Dependencies:** FR-011, FR-013, NFR-006

---

### Area 6: Theme Management

#### FR-017: Default Theme (SMB3)
**Priority:** Must Have

**Description:**
System provides Super Mario Bros 3 inspired aesthetic as default free theme available to all users.

**Acceptance Criteria:**
- [ ] Color palette matches 8/16-bit era gaming (vibrant, limited palette)
- [ ] Road textures evoke retro gaming (pixelated, tile-based patterns)
- [ ] Icon style consistent with 8-bit sprites (low resolution, charming)
- [ ] Theme always available to all users (free and paid)
- [ ] Theme assets optimized for fast loading (<500KB total)

**Dependencies:** FR-004

---

#### FR-018: Custom Theme Library
**Priority:** Should Have

**Description:**
Premium users access library of additional themes inspired by other game aesthetics or modern design styles.

**Acceptance Criteria:**
- [ ] At least 3 additional themes at launch (e.g., Zelda-inspired, Metroid-inspired, Modern Flat)
- [ ] Theme previews displayed before generation (thumbnail + description)
- [ ] Themes locked for free tier users with upgrade prompt
- [ ] Clear upgrade path to unlock themes (subscribe or pay 5 tokens per generation)
- [ ] Theme metadata includes name, description, inspiration source

**Dependencies:** FR-017

**Technical Notes:**
- Additional themes considered premium features
- 5-token cost per custom theme generation for non-subscribers

---

#### FR-019: User-Uploaded Themes (Post-MVP)
**Priority:** Could Have

**Description:**
Advanced users can create and upload custom themes for personal use or sharing.

**Acceptance Criteria:**
- [ ] Theme editor or upload specification (JSON + asset files)
- [ ] Validation of theme assets (required files, color palette compliance)
- [ ] Personal theme library per user (accessible via dashboard)
- [ ] Option to share themes publicly (theme marketplace consideration)
- [ ] Theme approval process to prevent inappropriate content

**Dependencies:** FR-018

---

### Area 7: Export & Sharing

#### FR-020: Image Export
**Priority:** Must Have

**Description:**
Users can export generated maps as high-resolution images in multiple formats.

**Acceptance Criteria:**
- [ ] Export as PNG with transparent background option
- [ ] Export as SVG (vector format for infinite scaling)
- [ ] Resolution options: 1080p (1920x1080), 4K (3840x2160)
- [ ] Free tier: Watermarked exports (small "Generated by Overworld" text)
- [ ] Premium tier: No watermark
- [ ] Download triggered immediately after export generation

**Dependencies:** FR-009

**Technical Notes:**
- Watermark placement must be subtle but visible (corner placement)
- SVG export valuable for professional use (scalable for presentations)

---

#### FR-021: Shareable Links
**Priority:** Should Have

**Description:**
Users can generate public shareable links to view maps online without requiring recipient authentication.

**Acceptance Criteria:**
- [ ] Public link generation with unique URL slug
- [ ] View-only mode (no editing, no download without account)
- [ ] Optional password protection for sensitive projects
- [ ] Link analytics: View count, last accessed date
- [ ] Links expire after 90 days of inactivity (configurable per user for premium)

**Dependencies:** FR-009, FR-012

---

#### FR-022: Embed Code
**Priority:** Could Have

**Description:**
Premium users can embed interactive maps in external websites via iframe.

**Acceptance Criteria:**
- [ ] Generates iframe embed code with customizable dimensions
- [ ] Responsive embed sizing (percentage-based or fixed)
- [ ] Premium-only feature (free tier cannot embed)
- [ ] Embedded maps support zoom/pan interactions
- [ ] No Overworld branding visible in embedded view (white-label)

**Dependencies:** FR-021

---

## Non-Functional Requirements (NFRs)

### NFR-001: Performance - Map Generation Speed
**Priority:** Must Have

**Description:**
Map generation completes in under 30 seconds for documents with up to 50 milestones to maintain user engagement.

**Acceptance Criteria:**
- [ ] 95th percentile generation time < 30 seconds for 50-milestone documents
- [ ] Progressive feedback during generation (loading states, progress bar)
- [ ] Generation timeout at 120 seconds with clear error and retry option
- [ ] Background processing for large documents (>50 milestones) with email notification

**Rationale:**
User engagement drops significantly above 30-second wait times. Progressive feedback prevents perceived abandonment.

---

### NFR-002: Performance - Rendering Performance
**Priority:** Must Have

**Description:**
Interactive map maintains 60 FPS during navigation and animations to deliver game-like experience.

**Acceptance Criteria:**
- [ ] 60 FPS minimum for zoom/pan operations (measured via browser performance APIs)
- [ ] Smooth animations with no visible jank (frame drops)
- [ ] Maps with 100+ elements render without performance degradation
- [ ] Performance profiling integrated into CI pipeline

**Rationale:**
Game-like feel requires smooth, responsive interactions. Poor performance breaks immersion.

---

### NFR-003: Security - Authentication & Authorization
**Priority:** Must Have

**Description:**
Secure authentication with industry-standard practices (JWT tokens, OAuth2, password hashing).

**Acceptance Criteria:**
- [ ] Passwords hashed with bcrypt (cost factor 12 minimum)
- [ ] JWT tokens expire after 24 hours with secure refresh flow
- [ ] OAuth2 integration follows OpenID Connect standards
- [ ] CSRF protection on all state-changing operations (tokens, cookies)
- [ ] Rate limiting on authentication endpoints (prevent brute force)
- [ ] Secrets stored in environment variables, never in code

**Rationale:**
Protect user accounts and prevent unauthorized access. Compliance with security best practices.

---

### NFR-004: Security - Payment Security
**Priority:** Must Have

**Description:**
PCI-DSS compliant payment processing via Stripe with no credit card data stored on our servers.

**Acceptance Criteria:**
- [ ] No credit card data stored on our servers (Stripe handles all payment data)
- [ ] Stripe integration for all payment operations (no DIY payment handling)
- [ ] TLS 1.3 enforced for all payment-related traffic
- [ ] Webhook signature verification for Stripe events
- [ ] Payment failure handling with clear user messaging

**Rationale:**
Legal and financial risk mitigation. PCI compliance without certification overhead.

---

### NFR-005: Scalability - Concurrent Users
**Priority:** Should Have

**Description:**
System handles 1,000 concurrent users without degradation to support viral growth.

**Acceptance Criteria:**
- [ ] Load testing validates 1,000 concurrent users with <1% error rate
- [ ] Auto-scaling configured for compute resources (horizontal scaling)
- [ ] Database connection pooling configured to handle load spikes
- [ ] CDN integration for static assets (images, themes)
- [ ] Queue-based architecture for map generation (prevents resource exhaustion)

**Rationale:**
Support viral growth scenarios (e.g., ProductHunt launch, social media sharing) without service interruption.

---

### NFR-006: Scalability - Cost Control for Anonymous Users
**Priority:** Must Have

**Description:**
Hard daily budget cap for anonymous generations with BYO provider escape hatch to prevent runaway costs.

**Acceptance Criteria:**
- [ ] Daily budget limit enforced server-side (e.g., $50/day for anonymous usage)
- [ ] IP-based rate limiting (max 3 generations/day per IP, rolling 24-hour window)
- [ ] Cookie-based tracking for soft limits (browser fingerprinting as secondary layer)
- [ ] BYO API key option: User provides OpenAI/Anthropic/Claude key to bypass budget
- [ ] Real-time cost tracking dashboard (admin-only) to monitor anonymous spend
- [ ] Automatic budget reset at UTC midnight

**Rationale:**
Prevent runaway LLM costs while maintaining accessibility for evaluation users.

---

### NFR-007: Reliability - Uptime
**Priority:** Should Have

**Description:**
99.5% uptime SLA to balance cost with user expectations for a freemium tool.

**Acceptance Criteria:**
- [ ] Monthly uptime > 99.5% (measured via uptime monitoring service)
- [ ] Automated health checks every 60 seconds with alerting
- [ ] Incident response SLA: 4 hours to acknowledge, 24 hours to resolve
- [ ] Status page publicly available (e.g., status.overworld.com)
- [ ] Database backups every 24 hours with point-in-time recovery

**Rationale:**
Balance cost (99.9% would require expensive redundancy) with user expectations for freemium service.

---

### NFR-008: Usability - Browser Support
**Priority:** Must Have

**Description:**
Full functionality on modern browsers (Chrome, Firefox, Safari, Edge - last 2 versions) with graceful degradation for older browsers.

**Acceptance Criteria:**
- [ ] Chrome 120+, Firefox 120+, Safari 17+, Edge 120+ fully supported
- [ ] Graceful degradation for older browsers (read-only mode, basic rendering)
- [ ] No IE11 support (display unsupported browser message)
- [ ] Mobile browser support (Chrome Android, Safari iOS)
- [ ] Automated browser compatibility testing in CI pipeline

**Rationale:**
Focus on modern browsers reduces development complexity. Graceful degradation prevents complete failure on older browsers.

---

### NFR-009: Maintainability - Code Quality
**Priority:** Should Have

**Description:**
Maintain high code quality with automated testing, linting, and strict TypeScript enforcement.

**Acceptance Criteria:**
- [ ] Unit test coverage > 80% for business logic (map generation, token system, auth)
- [ ] E2E tests for critical user flows (signup, map generation, payment)
- [ ] TypeScript strict mode enabled (no implicit any, null checks)
- [ ] ESLint + Prettier enforced via pre-commit hooks and CI
- [ ] Code review required for all PRs (minimum 1 approval)
- [ ] Documentation for all public APIs and complex logic

**Rationale:**
Long-term maintainability and reduced bug surface. High code quality enables faster feature development.

---

### NFR-010: Compatibility - API Design
**Priority:** Should Have

**Description:**
RESTful API with OpenAPI 3.0 specification for future integrations (mobile apps, third-party tools).

**Acceptance Criteria:**
- [ ] All endpoints documented in OpenAPI 3.0 spec (auto-generated from code)
- [ ] Versioned API with v1 prefix (e.g., /api/v1/maps)
- [ ] JSON responses follow consistent structure (success, data, errors)
- [ ] CORS configured for web clients with allowlist
- [ ] Rate limiting per API endpoint to prevent abuse
- [ ] API documentation site (e.g., Swagger UI) publicly accessible

**Rationale:**
Enable future third-party integrations, mobile apps, and API-first growth strategies.

---

## Epic Breakdown & Traceability

| Epic ID | Epic Name | Related FRs | Story Estimate | Priority | Business Value |
|---------|-----------|-------------|----------------|----------|----------------|
| EPIC-001 | Document Ingestion & Parsing | FR-001, FR-002, FR-003 | 5-7 stories | Must Have | Foundation for all map generation |
| EPIC-002 | Core Map Generation Pipeline | FR-004, FR-005, FR-006, FR-007, FR-008, FR-009 | 8-10 stories | Must Have | Core product differentiator |
| EPIC-003 | Interactive Multi-Level Navigation | FR-023, FR-010 | 6-8 stories | Must Have (Phase 2) | Game-like engagement, deep exploration |
| EPIC-004 | User Management & Authentication | FR-011, FR-012 | 5-6 stories | Must Have | Required for monetization |
| EPIC-005 | Monetization & Token System | FR-013, FR-014, FR-015, FR-016, NFR-006 | 7-9 stories | Must Have | Revenue generation |
| EPIC-006 | Theme Library & Customization | FR-017, FR-018, FR-019 | 4-6 stories | Should Have | Premium tier differentiation |
| EPIC-007 | Export & Sharing | FR-020, FR-021, FR-022 | 4-5 stories | Must Have (Export), Should Have (Sharing) | Viral growth potential |

**Total Estimated Stories:** 39-51 stories
**Target for Level 2:** 5-15 stories (MVP focuses on EPIC-001, EPIC-002, EPIC-004, EPIC-005)

---

## Prioritization Summary

### Must Have (MVP)
- **Functional:** 18 FRs (FR-001, FR-002, FR-004, FR-005, FR-006, FR-007, FR-009, FR-011, FR-012, FR-013, FR-014, FR-015, FR-016, FR-017, FR-020, FR-023*)
- **Non-Functional:** 6 NFRs (NFR-001, NFR-002, NFR-003, NFR-004, NFR-006, NFR-008)
- **Epics:** EPIC-001, EPIC-002, EPIC-004, EPIC-005

*FR-023 (Interactive Navigation) is Must Have but Phase 2 (post-MVP)

### Should Have (Phase 2)
- **Functional:** 3 FRs (FR-003, FR-010, FR-018, FR-021)
- **Non-Functional:** 4 NFRs (NFR-005, NFR-007, NFR-009, NFR-010)
- **Epics:** EPIC-003, EPIC-006, EPIC-007

### Could Have (Future)
- **Functional:** 3 FRs (FR-008, FR-019, FR-022)

**MVP Focus:** Core map generation (EPIC-002), basic auth/monetization (EPIC-004, EPIC-005), simple export (FR-020)

---

## Dependencies

### Internal Dependencies
- None (greenfield project)

### External Dependencies
| Dependency | Purpose | Critical? | Alternatives |
|------------|---------|-----------|--------------|
| Stripe | Payment processing | Yes | PayPal, Paddle |
| LLM Provider API | Multi-agent map generation | Yes | OpenAI, Anthropic, local models |
| 2D Rendering Library | Map visualization | Yes | PlayCanvas, PixiJS, Phaser, Canvas API |
| Email Service | Transactional emails | No | SendGrid, AWS SES, Postmark |
| Hosting Platform | Infrastructure | Yes | Vercel, AWS, GCP |

---

## Assumptions

1. **Users have structured documents:** We assume users provide documents already organized hierarchically. We do not restructure unorganized content.
2. **Target audience has gaming context:** Users understand 8/16-bit gaming aesthetics (nostalgia factor critical for engagement).
3. **LLM costs remain stable:** Monetization model assumes current LLM API pricing. Significant price increases would require model adjustment.
4. **Modern browser adoption:** 95%+ of users on Chrome/Firefox/Safari last 2 versions. Legacy browser support not prioritized.
5. **Stripe availability:** Stripe services available in target markets (US, EU initially).

---

## Out of Scope (Version 1)

- Real-time collaborative editing of maps (multiple users editing simultaneously)
- Native mobile apps (iOS/Android) - web-first strategy
- Gantt chart integration or traditional project management features
- AI-generated content suggestions beyond map aesthetics
- Video export or animated map playback
- Integration with project management tools (Jira, Asana, Monday) - API-first enables future integration
- White-label or enterprise SSO (defer to post-v1)
- Marketplace for user-generated themes (defer to post-v1)

---

## Open Questions (For Architecture Phase)

### Technical Stack Questions
1. **LLM Provider:** Which LLM for multi-agent pipeline? (Claude, GPT-4, Gemini, local models)
   - Cost implications per generation
   - Quality of art/style generation
   - Rate limits and quotas

2. **2D Rendering Technology:** PlayCanvas vs PixiJS vs Phaser vs raw Canvas API?
   - Performance benchmarks for 100+ element maps
   - Animation capabilities
   - Learning curve and community support
   - Licensing (commercial vs open source)

3. **Database Choice:** Postgres, MongoDB, or Firebase for user/token management?
   - Schema requirements (relational vs document)
   - Scaling characteristics
   - Cost at scale

4. **Hosting Infrastructure:** Vercel (serverless) vs AWS/GCP (containerized)?
   - Cost modeling for compute-heavy map generation
   - Auto-scaling capabilities
   - Vendor lock-in considerations

### Business Model Questions
1. **Token Pack Pricing:** Finalize pricing tiers (suggested: 50/$9.99, 150/$24.99)
2. **Subscription Price:** Finalize monthly unlimited price (suggested: $19/month)
3. **Anonymous Daily Budget:** Confirm $50/day cap for cost control
4. **Educational Discounts:** Policy for students/nonprofits?

### User Experience Questions
1. **Map Canvas Size:** Fixed aspect ratio (16:9) or responsive?
2. **Mobile Responsiveness:** Touch gesture support depth?
3. **Accessibility:** WCAG 2.1 AA compliance priority?

---

## Stakeholders

| Stakeholder | Role | Interest |
|-------------|------|----------|
| Jarad DeLorenzo | Product Owner & Architect | Vision, technical decisions, monetization strategy |
| Product Managers | Primary Users | Roadmap visualization, stakeholder communication |
| Developers | Primary Users | Project tracking, progress visualization |
| Team Leads | Primary Users | Status reporting to executives |
| Stripe | Payment Partner | Financial compliance, payment processing |

---

## Glossary

- **L0-L4:** Hierarchical levels (L0 = Product, L1 = Worlds, L2 = Levels, L3 = Landmarks, L4 = Bonus Levels)
- **Spline:** Mathematical curve used to represent non-linear road paths
- **Token:** Virtual currency for map generation (10 free/month, purchasable)
- **MVP:** Minimum Viable Product (core features for initial launch)
- **SMB3:** Super Mario Bros 3 (8-bit aesthetic inspiration)
- **BYO:** Bring Your Own (user-provided API keys for cost bypass)
- **MoSCoW:** Prioritization method (Must Have, Should Have, Could Have, Won't Have)

---

## Appendix A: Transcript Analysis (UltraThink Methodology)

### Source: Overworld_Braindump.md

**Key Insights Extracted:**
1. **Core Concept:** Transform linear roadmaps → stylized overworld maps
2. **Aesthetic:** 8/16-bit era (Super Mario Bros 3 aesthetic)
3. **Multi-Agent Architecture:** Artist → Road Generator → Coordinate Mapper → Icon Placer
4. **MVP Scope:** Numbered circles along spline path (milestones)
5. **Input Flexibility:** Markdown or PDF with hierarchical structure
6. **Technical Challenge:** Spline generation for non-linear coordinate mapping

**UltraThink Analysis:**
- **Hypothesis:** Visual gamification reduces cognitive load for roadmap comprehension
- **Evidence:** Gaming metaphors widely understood (overworld maps = familiar mental model)
- **Pattern Recognition:** Multi-agent separation of concerns enables modular development
- **Synthesis:** Combine document parsing + LLM-based art generation + mathematical spline mapping
- **Validation:** MVP focuses on simplest viable output (numbered circles) before icon complexity

### Source: Overworld_Research_workflow.md

**Key Insights Extracted:**
1. **Research Process:** Investigate 2D rendering before implementation (PlayCanvas candidate)
2. **Proof of Concept Approach:** Build minimal toolkit to validate rendering capabilities
3. **Flexibility:** 2D native or 3D with orthogonal view (both valid paths)
4. **Validation:** Draw single line with styles/textures to prove rendering viability

**UltraThink Analysis:**
- **Hypothesis:** 2D rendering technology choice impacts all downstream development
- **Evidence:** Need programmatic SVG rendering or equivalent for dynamic map generation
- **Pattern Recognition:** POC-first approach reduces risk of technology dead-ends
- **Synthesis:** Defer final rendering stack choice to Architecture phase after POC validation
- **Validation:** Single-line rendering test confirms basic capability before full commitment

---

## Document Metadata

**Author:** Product Manager (BMAD Method v6)
**Reviewers:** Pending Architecture phase
**Approval Status:** Draft (pending user review)
**Related Documents:**
- Source Transcripts: `/home/delorenj/code/overworld/docs/transcriptions/Overworld_Braindump.md`
- Source Transcripts: `/home/delorenj/code/overworld/docs/transcriptions/Overworld_Research_workflow.md`
- BMAD Config: `/home/delorenj/code/overworld/bmad/config.yaml`
- Workflow Status: `/home/delorenj/code/overworld/docs/bmm-workflow-status.yaml`

**Version History:**
- v1.0 (2026-01-05): Initial PRD based on transcript analysis and requirements gathering

---

**END OF DOCUMENT**
