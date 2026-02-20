#!/bin/bash
# Automated Consensus Demo Runner
# This script executes the complete demo workflow from CONSENSUS_DEMO_RUNLIST.md
# Usage: ./run_consensus_demo.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_BASE="http://localhost:8778/api"
POLL_INTERVAL=10  # seconds
MAX_WAIT_TIME=600  # 10 minutes

# Track state
PROJECT_ID=""
DOC1_ID=""
ANALYSIS_ID=""
ARQ_JOB_ID=""

# Helper functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

check_prerequisites() {
    print_header "Step 0: Prerequisites Check"

    # Check API health
    print_info "Checking API health..."
    if curl -sf "$API_BASE/health" > /dev/null; then
        print_success "API is healthy"
    else
        print_error "API is not responding at $API_BASE/health"
        exit 1
    fi

    # Check service status
    print_info "Checking service status..."
    STATUS_JSON=$(curl -sf "$API_BASE/v1/status")
    REDIS_STATUS=$(echo "$STATUS_JSON" | jq -r '.services.redis')

    if [ "$REDIS_STATUS" = "connected" ]; then
        print_success "Redis is connected"
    else
        print_error "Redis is not connected: $REDIS_STATUS"
        exit 1
    fi

    # Check required tools
    for tool in curl jq docker; do
        if command -v $tool &> /dev/null; then
            print_success "$tool is installed"
        else
            print_error "$tool is not installed (required)"
            exit 1
        fi
    done
}

create_project() {
    print_header "Step 1: Create Project"

    PROJECT_JSON=$(curl -sf -X POST "$API_BASE/v1/projects" \
        -H "Content-Type: application/json" \
        -d '{
            "name": "Automated Demo Project",
            "description": "Auto-generated test project for consensus analysis"
        }')

    PROJECT_ID=$(echo "$PROJECT_JSON" | jq -r '.id')
    STATUS=$(echo "$PROJECT_JSON" | jq -r '.status')

    if [ "$STATUS" = "created" ]; then
        print_success "Project created: $PROJECT_ID"
        print_info "Status: $STATUS"
    else
        print_error "Failed to create project"
        echo "$PROJECT_JSON" | jq '.'
        exit 1
    fi
}

create_test_document() {
    print_header "Step 2: Create Test Document"

    # Create test markdown file
    TEST_FILE="/tmp/demo_prd_$$.md"
    cat > "$TEST_FILE" << 'EOF'
# Product Requirements Document: Real-Time Collaboration Platform

## Executive Summary
Build a scalable real-time collaborative workspace with multi-user support,
presence awareness, and conflict-free replicated data types (CRDTs).

## Project Goals
- Enable 100+ concurrent users per workspace
- Sub-100ms latency for real-time updates
- Offline-first architecture with eventual consistency
- Rich text editing with operational transformations

## Technical Milestones

### 1. WebSocket Infrastructure
**Goal:** Establish reliable real-time communication layer
**Effort:** 2 weeks
**Dependencies:** None

**Requirements:**
- Socket.io server with Redis adapter
- Connection pooling and load balancing
- Heartbeat monitoring and reconnection logic
- Message queuing for offline clients

**Success Criteria:**
- 1000 concurrent connections per server instance
- <50ms message propagation latency
- 99.9% uptime

### 2. CRDT Implementation
**Goal:** Implement conflict-free data structures for concurrent editing
**Effort:** 3 weeks
**Dependencies:** WebSocket Infrastructure

**Requirements:**
- Yjs or Automerge integration
- Custom CRDT for presence data
- Snapshot and delta compression
- Garbage collection for tombstones

**Success Criteria:**
- Zero merge conflicts
- <1MB memory overhead per 1000 operations
- Deterministic convergence

### 3. Rich Text Editor
**Goal:** Build collaborative rich text editor with formatting
**Effort:** 2 weeks
**Dependencies:** CRDT Implementation

**Requirements:**
- Prosemirror or Draft.js integration
- Inline comments and suggestions
- Markdown import/export
- Accessibility (WCAG 2.1 AA)

**Success Criteria:**
- <16ms keystroke latency
- Format preservation across clients
- Screen reader compatible

### 4. User Authentication & Authorization
**Goal:** Secure workspace access with role-based permissions
**Effort:** 1.5 weeks
**Dependencies:** None

**Requirements:**
- OAuth2 with Google/GitHub providers
- JWT token management
- Workspace invitations via email
- Role-based access control (RBAC)

**Success Criteria:**
- <200ms authentication response time
- Token refresh without interruption
- Audit logs for all actions

### 5. Presence & Awareness
**Goal:** Real-time user presence indicators and cursor positions
**Effort:** 1 week
**Dependencies:** WebSocket Infrastructure, User Authentication

**Requirements:**
- Live cursor tracking
- User avatar badges
- "Who's viewing" sidebar
- Activity notifications

**Success Criteria:**
- <100ms cursor position updates
- Graceful degradation for 50+ users
- Minimal bandwidth usage (<1KB/s per user)

## Version Boundaries

### MVP (v0.1) - 4 weeks
**Release Goal:** Basic collaborative editing for small teams
**Includes:**
- WebSocket Infrastructure
- User Authentication & Authorization
- Basic text collaboration (no rich formatting)

### Beta (v0.5) - 8 weeks
**Release Goal:** Feature-complete editor with CRDT
**Includes:**
- CRDT Implementation
- Rich Text Editor
- Presence & Awareness

### Production (v1.0) - 12 weeks
**Release Goal:** Enterprise-ready with performance optimizations
**Additional Features:**
- Horizontal scaling
- Monitoring and observability
- Advanced conflict resolution UI

## Non-Functional Requirements

### Performance
- 10,000 operations/second write throughput
- 99th percentile latency <100ms
- Client bundle size <500KB

### Scalability
- 100,000 concurrent users (across clusters)
- 10,000 active workspaces
- 1TB document storage capacity

### Security
- End-to-end encryption for sensitive workspaces
- Rate limiting (100 req/min per user)
- XSS and CSRF protection

## Testing Strategy

### Unit Tests
- 80% code coverage minimum
- CRDT operation tests
- WebSocket message handlers

### Integration Tests
- Multi-client synchronization scenarios
- Network partition recovery
- Database consistency checks

### Performance Tests
- Load testing with k6 or Artillery
- Memory leak detection
- Latency profiling under load

### End-to-End Tests
- Critical user journeys with Playwright
- Cross-browser compatibility
- Mobile responsiveness

## Open Questions
1. Should we support video/audio calls? (Future consideration)
2. Maximum workspace size limit? (Recommend 50MB)
3. Document versioning strategy? (Snapshot every 1000 ops)
EOF

    print_info "Created test document: $TEST_FILE"

    # Upload document
    DOC_JSON=$(curl -sf -X POST "$API_BASE/v1/documents/upload" \
        -F "file=@$TEST_FILE" \
        -H "Content-Type: multipart/form-data")

    DOC1_ID=$(echo "$DOC_JSON" | jq -r '.document_id')
    FILENAME=$(echo "$DOC_JSON" | jq -r '.filename')

    if [ "$DOC1_ID" != "null" ] && [ -n "$DOC1_ID" ]; then
        print_success "Document uploaded: $DOC1_ID"
        print_info "Filename: $FILENAME"
        rm -f "$TEST_FILE"
    else
        print_error "Failed to upload document"
        echo "$DOC_JSON" | jq '.'
        exit 1
    fi
}

add_document_to_project() {
    print_header "Step 3: Add Document to Project"

    RESULT=$(curl -sf -X POST "$API_BASE/v1/projects/$PROJECT_ID/documents" \
        -H "Content-Type: application/json" \
        -d "{\"document_id\": \"$DOC1_ID\"}")

    ORDER_INDEX=$(echo "$RESULT" | jq -r '.order_index')

    if [ "$ORDER_INDEX" = "0" ]; then
        print_success "Document added to project"
        print_info "Order index: $ORDER_INDEX"
    else
        print_error "Failed to add document to project"
        echo "$RESULT" | jq '.'
        exit 1
    fi

    # Verify project status changed to 'ready'
    PROJECT_STATUS=$(curl -sf "$API_BASE/v1/projects/$PROJECT_ID" | jq -r '.status')
    if [ "$PROJECT_STATUS" = "ready" ]; then
        print_success "Project status: $PROJECT_STATUS"
    else
        print_error "Expected status 'ready', got '$PROJECT_STATUS'"
        exit 1
    fi
}

trigger_analysis() {
    print_header "Step 4: Trigger Consensus Analysis"

    ANALYSIS_JSON=$(curl -sf -X POST "$API_BASE/v1/projects/$PROJECT_ID/analyze" \
        -H "Content-Type: application/json" \
        -d '{"force_reanalyze": false}')

    ANALYSIS_ID=$(echo "$ANALYSIS_JSON" | jq -r '.analysis_id')
    ARQ_JOB_ID=$(echo "$ANALYSIS_JSON" | jq -r '.arq_job_id')
    STATUS=$(echo "$ANALYSIS_JSON" | jq -r '.status')

    if [ "$STATUS" = "pending" ]; then
        print_success "Analysis triggered: $ANALYSIS_ID"
        print_info "ARQ Job ID: $ARQ_JOB_ID"
        print_info "Status: $STATUS"
    else
        print_error "Failed to trigger analysis"
        echo "$ANALYSIS_JSON" | jq '.'
        exit 1
    fi
}

monitor_progress() {
    print_header "Step 5: Monitor Analysis Progress"

    print_info "Polling analysis status every $POLL_INTERVAL seconds..."
    print_info "(Max wait time: ${MAX_WAIT_TIME}s / ~$((MAX_WAIT_TIME/60)) minutes)"

    START_TIME=$(date +%s)

    while true; do
        CURRENT_TIME=$(date +%s)
        ELAPSED=$((CURRENT_TIME - START_TIME))

        if [ $ELAPSED -gt $MAX_WAIT_TIME ]; then
            print_error "Timeout: Analysis did not complete within $MAX_WAIT_TIME seconds"
            exit 1
        fi

        # Fetch analysis status
        ANALYSIS_RESULT=$(curl -sf "$API_BASE/v1/projects/$PROJECT_ID/analysis")
        STATUS=$(echo "$ANALYSIS_RESULT" | jq -r '.analysis.status')
        CONVERGED=$(echo "$ANALYSIS_RESULT" | jq -r '.analysis.converged')
        ROUNDS=$(echo "$ANALYSIS_RESULT" | jq -r '.analysis.total_rounds')

        TIMESTAMP=$(date '+%H:%M:%S')
        echo -ne "\r[$TIMESTAMP] Status: $STATUS | Rounds: $ROUNDS | Elapsed: ${ELAPSED}s   "

        # Check for completion
        if [ "$STATUS" = "converged" ]; then
            echo ""  # New line after progress
            print_success "Analysis converged!"
            print_info "Total rounds: $ROUNDS"
            break
        elif [ "$STATUS" = "failed" ]; then
            echo ""
            print_error "Analysis failed!"
            ERROR_MSG=$(echo "$ANALYSIS_RESULT" | jq -r '.analysis.error_msg // "Unknown error"')
            print_error "Error: $ERROR_MSG"
            exit 1
        fi

        sleep $POLL_INTERVAL
    done
}

retrieve_results() {
    print_header "Step 6: Retrieve Analysis Results"

    RESULT_FILE="/tmp/consensus_result_$$.json"
    curl -sf "$API_BASE/v1/projects/$PROJECT_ID/analysis" > "$RESULT_FILE"

    # Extract metrics
    MILESTONE_COUNT=$(jq '.milestones | length' "$RESULT_FILE")
    CHECKPOINT_COUNT=$(jq '.checkpoints | length' "$RESULT_FILE")
    VERSION_COUNT=$(jq '.versions | length' "$RESULT_FILE")
    TOTAL_ROUNDS=$(jq '.analysis.total_rounds' "$RESULT_FILE")
    TOTAL_TOKENS=$(jq '.analysis.total_tokens' "$RESULT_FILE")
    TOTAL_COST=$(jq '.analysis.total_cost' "$RESULT_FILE")

    print_success "Results retrieved"
    echo ""
    print_info "Analysis Metrics:"
    echo "  - Total Rounds: $TOTAL_ROUNDS"
    echo "  - Milestones: $MILESTONE_COUNT"
    echo "  - Checkpoints: $CHECKPOINT_COUNT"
    echo "  - Versions: $VERSION_COUNT"
    echo "  - Tokens Consumed: $TOTAL_TOKENS"
    echo "  - Total Cost: \$$TOTAL_COST"
    echo ""

    # Display milestones
    if [ "$MILESTONE_COUNT" -gt 0 ]; then
        print_info "Extracted Milestones:"
        jq -r '.milestones[] | "  [\(.created_order)] \(.title) (\(.type), \(.estimated_effort))"' "$RESULT_FILE"
    fi

    echo ""
    print_success "Full results saved to: $RESULT_FILE"
}

verify_database() {
    print_header "Step 7: Verify Database Persistence"

    # Check milestones
    DB_MILESTONES=$(docker exec overworld-postgres psql -U overworld -d overworld -t -c \
        "SELECT COUNT(*) FROM milestones WHERE analysis_id = '$ANALYSIS_ID';" 2>/dev/null | xargs)

    if [ "$DB_MILESTONES" -gt 0 ]; then
        print_success "Database milestones: $DB_MILESTONES"
    else
        print_error "No milestones found in database"
        exit 1
    fi

    # Check checkpoints
    DB_CHECKPOINTS=$(docker exec overworld-postgres psql -U overworld -d overworld -t -c \
        "SELECT COUNT(*) FROM checkpoints WHERE analysis_id = '$ANALYSIS_ID';" 2>/dev/null | xargs)

    if [ "$DB_CHECKPOINTS" -gt 0 ]; then
        print_success "Database checkpoints: $DB_CHECKPOINTS"
    else
        print_error "No checkpoints found in database"
        exit 1
    fi

    # Check versions
    DB_VERSIONS=$(docker exec overworld-postgres psql -U overworld -d overworld -t -c \
        "SELECT COUNT(*) FROM versions WHERE analysis_id = '$ANALYSIS_ID';" 2>/dev/null | xargs)

    if [ "$DB_VERSIONS" -gt 0 ]; then
        print_success "Database versions: $DB_VERSIONS"
    else
        print_error "No versions found in database"
        exit 1
    fi

    # Verify project status
    PROJECT_STATUS=$(curl -sf "$API_BASE/v1/projects/$PROJECT_ID" | jq -r '.status')
    if [ "$PROJECT_STATUS" = "analyzed" ]; then
        print_success "Project status: $PROJECT_STATUS"
    else
        print_error "Expected project status 'analyzed', got '$PROJECT_STATUS'"
        exit 1
    fi
}

print_summary() {
    print_header "Demo Summary"

    echo -e "${GREEN}All steps completed successfully!${NC}"
    echo ""
    echo "Project ID:  $PROJECT_ID"
    echo "Document ID: $DOC1_ID"
    echo "Analysis ID: $ANALYSIS_ID"
    echo "ARQ Job ID:  $ARQ_JOB_ID"
    echo ""
    echo "To view full results:"
    echo "  curl -s $API_BASE/v1/projects/$PROJECT_ID/analysis | jq '.'"
    echo ""
    echo "To cleanup:"
    echo "  curl -X DELETE $API_BASE/v1/projects/$PROJECT_ID"
    echo ""
}

# Main execution
main() {
    clear
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║  Overworld Consensus Analysis - Automated Demo Runner     ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    check_prerequisites
    create_project
    create_test_document
    add_document_to_project
    trigger_analysis
    monitor_progress
    retrieve_results
    verify_database
    print_summary
}

# Run main function
main
