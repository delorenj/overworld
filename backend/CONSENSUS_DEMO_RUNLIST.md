# Project-Centric Consensus Analysis - Interactive Demo Walkthrough

## Overview
This demo validates the complete project-centric consensus analysis system in Overworld backend, which orchestrates multi-agent analysis (EM + PM + Notetaker) to extract milestones, checkpoints, and versions from project documents. The system uses ARQ for background processing and emits real-time events via Bloodbank.

**System Components Tested:**
- Project API endpoints (create, list, get, add documents)
- Document management integration
- Consensus analysis triggering (ARQ job enqueue)
- Multi-round agent orchestration (convergence detection)
- Database persistence (milestones, checkpoints, versions)
- Event emission (consensus lifecycle events)

**Key Implementation Files:**
- `/home/delorenj/code/overworld/backend/app/services/consensus_service.py` - Multi-agent consensus orchestration
- `/home/delorenj/code/overworld/backend/app/api/v1/routers/projects.py` - Project API endpoints
- `/home/delorenj/code/overworld/backend/app/workers/consensus_tasks.py` - ARQ background task
- `/home/delorenj/code/overworld/backend/app/models/project.py` - Project/ProjectDocument models
- `/home/delorenj/code/overworld/backend/app/models/consensus.py` - Consensus result models

---

## Prerequisites

### Required Services
Verify these services are running before starting the demo:

```bash
# Check Docker containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E 'overworld-backend|overworld-postgres|overworld-redis'
```

**Expected Output:**
```
overworld-backend      Up X hours      0.0.0.0:8778->8000/tcp
overworld-postgres     Up X hours (healthy)      5432/tcp
overworld-redis        Up X hours (healthy)      6379/tcp
```

### API Connectivity
```bash
# Test API health
curl -s http://localhost:8778/api/health
```

**Expected Response:**
```json
{"status":"ok","service":"overworld-backend"}
```

### Service Status Check
```bash
# Verify Redis connectivity and service health
curl -s http://localhost:8778/api/v1/status
```

**Expected Response:**
```json
{
  "status":"running",
  "version":"0.1.0",
  "environment":"development",
  "services":{
    "redis":"connected",
    "job_queue":"arq"
  }
}
```

**STOP HERE if any service shows as disconnected or unhealthy.**

---

## Demo Workflow

### Step 1: Create a New Project

**Command:**
```bash
curl -X POST http://localhost:8778/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Demo Consensus Project",
    "description": "Test project for multi-agent consensus analysis"
  }' | jq '.'
```

**Expected Response Structure:**
```json
{
  "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "user_id": 1,
  "name": "Demo Consensus Project",
  "description": "Test project for multi-agent consensus analysis",
  "status": "created",
  "document_count": 0,
  "created_at": "2026-01-27T...",
  "updated_at": "2026-01-27T...",
  "analyzed_at": null
}
```

**Verification Criteria:**
- Response status: `201 Created`
- `status` field equals `"created"`
- `document_count` equals `0`
- `analyzed_at` is `null`
- Valid UUID in `id` field

**Save the Project ID:**
```bash
# Extract and save project_id for subsequent steps
export PROJECT_ID="<paste-id-from-response>"
echo "Project ID: $PROJECT_ID"
```

**Database Verification:**
```bash
# Connect to PostgreSQL and verify project record
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT id, name, status, document_count FROM projects WHERE id = '$PROJECT_ID';"
```

**Expected Database Output:**
```
                  id                  |          name          | status  | document_count
--------------------------------------+------------------------+---------+----------------
 xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx | Demo Consensus Project | created |              0
```

---

### Step 2: Create Test Documents

Since the system requires documents to perform consensus analysis, we need to create document records in the database.

**LIMITATION ACKNOWLEDGEMENT:** The current implementation has a placeholder in `consensus_tasks.py:_merge_project_documents()` (line 194) that returns placeholder text instead of actual document content. This means:
- The demo will execute successfully through all steps
- Consensus analysis will run on placeholder data
- Milestones/checkpoints extracted will be based on placeholder content
- Real-world usage requires implementing actual document content extraction

**Create Document 1:**
```bash
curl -X POST http://localhost:8778/api/v1/documents/upload \
  -F "file=@/tmp/test-prd.md" \
  -H "Content-Type: multipart/form-data" | jq '.'
```

**If you don't have a test file, create one:**
```bash
cat > /tmp/test-prd.md << 'EOF'
# Product Requirements Document

## Overview
Build a real-time collaborative drawing tool with multi-user support.

## Milestones
1. WebSocket infrastructure setup
2. Canvas rendering engine
3. User authentication system
4. Real-time synchronization
5. Drawing tools implementation

## Technical Requirements
- WebSocket server using Socket.io
- HTML5 Canvas API
- User session management
- Conflict resolution for concurrent edits
EOF

# Upload the document
curl -X POST http://localhost:8778/api/v1/documents/upload \
  -F "file=@/tmp/test-prd.md" \
  -H "Content-Type: multipart/form-data" | jq '.'
```

**Expected Response:**
```json
{
  "id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
  "filename": "test-prd.md",
  "file_size_bytes": 512,
  "mime_type": "text/markdown",
  "status": "uploaded",
  "r2_url": "https://...",
  "created_at": "2026-01-27T..."
}
```

**Save Document ID:**
```bash
export DOC1_ID="<paste-document-id-from-response>"
echo "Document 1 ID: $DOC1_ID"
```

**Verification:**
```bash
# Verify document in database
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT id, filename, status, user_id FROM documents WHERE id = '$DOC1_ID';"
```

---

### Step 3: Add Document to Project

**Command:**
```bash
curl -X POST http://localhost:8778/api/v1/projects/$PROJECT_ID/documents \
  -H "Content-Type: application/json" \
  -d "{
    \"document_id\": \"$DOC1_ID\"
  }" | jq '.'
```

**Expected Response:**
```json
{
  "message": "Document added to project successfully",
  "project_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "document_id": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
  "order_index": 0
}
```

**Verification Criteria:**
- Response status: `201 Created`
- `order_index` equals `0` (first document)
- Project and document IDs match saved values

**Database Verification:**
```bash
# Verify project_documents join table
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT project_id, document_id, order_index, added_at FROM project_documents WHERE project_id = '$PROJECT_ID';"
```

**Expected Output:**
```
              project_id              |             document_id              | order_index |         added_at
--------------------------------------+--------------------------------------+-------------+---------------------------
 xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx | yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy |           0 | 2026-01-27 ...
```

**Verify Project Status Change:**
```bash
# Check project status changed to 'ready'
curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID | jq '.status, .document_count'
```

**Expected Output:**
```json
"ready"
1
```

---

### Step 4: Trigger Consensus Analysis

This step enqueues an ARQ background job that will orchestrate the multi-agent consensus analysis.

**Command:**
```bash
curl -X POST http://localhost:8778/api/v1/projects/$PROJECT_ID/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "force_reanalyze": false
  }' | jq '.'
```

**Expected Response:**
```json
{
  "analysis_id": "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz",
  "project_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "status": "pending",
  "arq_job_id": "consensus-zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz",
  "converged": false,
  "total_rounds": 0,
  "milestones_count": 0,
  "checkpoints_count": 0,
  "versions_count": 0,
  "total_tokens": 0,
  "total_cost": 0.0,
  "created_at": "2026-01-27T...",
  "started_at": null,
  "completed_at": null
}
```

**Verification Criteria:**
- Response status: `202 Accepted`
- `status` equals `"pending"`
- `arq_job_id` is present and starts with `"consensus-"`
- All counts (`milestones_count`, `checkpoints_count`, etc.) are `0`

**Save Analysis ID:**
```bash
export ANALYSIS_ID="<paste-analysis-id-from-response>"
export ARQ_JOB_ID="<paste-arq-job-id-from-response>"
echo "Analysis ID: $ANALYSIS_ID"
echo "ARQ Job ID: $ARQ_JOB_ID"
```

**Database Verification:**
```bash
# Verify consensus_analyses record created
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT id, project_id, status, arq_job_id, converged, total_rounds FROM consensus_analyses WHERE id = '$ANALYSIS_ID';"
```

**Expected Output:**
```
                  id                  |              project_id              | status  |                 arq_job_id                 | converged | total_rounds
--------------------------------------+--------------------------------------+---------+--------------------------------------------+-----------+--------------
 zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz | xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx | pending | consensus-zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzz | f         |            0
```

**Verify Project Status:**
```bash
# Project should now be 'analyzing'
curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID | jq '.status'
```

**Expected Output:**
```json
"analyzing"
```

---

### Step 5: Monitor Job Progress

The ARQ worker will process the job asynchronously. Monitor progress through database queries since we don't have a job status endpoint yet.

**IMPORTANT:** The consensus analysis involves multiple LLM API calls (EM, PM, Notetaker agents) and can take 30 seconds to several minutes depending on:
- Document size/complexity
- Number of rounds (min 2, max 5)
- OpenRouter API response times
- Convergence speed

**Monitoring Command (run repeatedly):**
```bash
# Check analysis status every 10 seconds
watch -n 10 "docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  \"SELECT status, converged, total_rounds, milestones_count, started_at, completed_at \
   FROM consensus_analyses WHERE id = '$ANALYSIS_ID';\""
```

**Status Progression:**

1. **Initial State (PENDING):**
```
 status  | converged | total_rounds | milestones_count | started_at | completed_at
---------+-----------+--------------+------------------+------------+--------------
 pending |     f     |            0 |                0 |            |
```

2. **Processing State (ANALYZING):**
```
 status    | converged | total_rounds | milestones_count | started_at          | completed_at
-----------+-----------+--------------+------------------+---------------------+--------------
 analyzing |     f     |            0 |                0 | 2026-01-27 10:15:23 |
```

3. **Converged State (SUCCESS):**
```
 status    | converged | total_rounds | milestones_count | started_at          | completed_at
-----------+-----------+--------------+------------------+---------------------+---------------------
 converged |     t     |            3 |                5 | 2026-01-27 10:15:23 | 2026-01-27 10:17:45
```

**Alternative: Poll via API**
```bash
# Check via API (uses same database query internally)
while true; do
  STATUS=$(curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID/analysis | jq -r '.analysis.status')
  ROUNDS=$(curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID/analysis | jq -r '.analysis.total_rounds')
  echo "$(date '+%H:%M:%S') - Status: $STATUS, Rounds: $ROUNDS"

  if [ "$STATUS" = "converged" ] || [ "$STATUS" = "failed" ]; then
    break
  fi

  sleep 10
done
```

**Expected Behavior:**
- Status changes: `pending` → `analyzing` → `converged`
- `total_rounds` increments during analysis (typically 2-5 rounds)
- `started_at` timestamp appears when processing begins
- `completed_at` timestamp appears when converged/failed

**If Status Shows FAILED:**
Check error message:
```bash
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT error_msg FROM consensus_analyses WHERE id = '$ANALYSIS_ID';"
```

---

### Step 6: Retrieve Analysis Results

Once the analysis status is `converged`, retrieve the complete results including milestones, checkpoints, and versions.

**Command:**
```bash
curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID/analysis | jq '.'
```

**Expected Response Structure:**
```json
{
  "analysis": {
    "analysis_id": "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz",
    "project_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "status": "converged",
    "arq_job_id": "consensus-zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz",
    "converged": true,
    "total_rounds": 3,
    "milestones_count": 5,
    "checkpoints_count": 8,
    "versions_count": 2,
    "total_tokens": 12450,
    "total_cost": 0.0623,
    "created_at": "2026-01-27T10:15:10Z",
    "started_at": "2026-01-27T10:15:23Z",
    "completed_at": "2026-01-27T10:17:45Z"
  },
  "milestones": [
    {
      "id": "m1-uuid",
      "title": "WebSocket Infrastructure Setup",
      "description": "Establish real-time communication foundation...",
      "type": "technical",
      "estimated_effort": "M",
      "dependencies": [],
      "created_order": 0
    },
    {
      "id": "m2-uuid",
      "title": "Canvas Rendering Engine",
      "description": "Implement HTML5 canvas drawing primitives...",
      "type": "technical",
      "estimated_effort": "L",
      "dependencies": ["WebSocket Infrastructure Setup"],
      "created_order": 1
    }
    // ... more milestones
  ],
  "checkpoints": [
    {
      "id": "c1-uuid",
      "title": "WebSocket Connection Test",
      "type": "poc",
      "validation_criteria": [
        "Client connects successfully",
        "Server acknowledges connection",
        "Ping/pong messages work"
      ],
      "milestone_id": "m1-uuid"
    }
    // ... more checkpoints
  ],
  "versions": [
    {
      "id": "v1-uuid",
      "name": "MVP",
      "release_goal": "Basic collaborative drawing with 2 users",
      "milestone_titles": [
        "WebSocket Infrastructure Setup",
        "Canvas Rendering Engine",
        "User Authentication System"
      ],
      "created_order": 0
    }
    // ... more versions
  ],
  "reasoning": "EM and PM achieved consensus after 3 rounds with stable novelty scores..."
}
```

**Verification Criteria:**

1. **Analysis Metadata:**
   - `converged` is `true`
   - `total_rounds` is between 2 and 5
   - `total_tokens` > 0
   - `total_cost` > 0
   - `started_at` and `completed_at` both present
   - Duration between timestamps is reasonable (30s - 5min)

2. **Milestones Array:**
   - Array is not empty (`length > 0`)
   - Each milestone has required fields: `id`, `title`, `description`, `type`, `estimated_effort`, `dependencies`, `created_order`
   - `type` is one of: `"technical"`, `"product"`, `"hybrid"`
   - `estimated_effort` is one of: `"S"`, `"M"`, `"L"`, `"XL"`
   - `dependencies` is an array of milestone titles (can be empty)
   - `created_order` values are sequential starting from 0

3. **Checkpoints Array:**
   - Array is not empty (`length > 0`)
   - Each checkpoint has: `id`, `title`, `type`, `validation_criteria`, `milestone_id`
   - `type` is one of: `"poc"`, `"demo"`, `"test"`, `"review"`
   - `validation_criteria` is a non-empty array of strings
   - `milestone_id` references a valid milestone from the milestones array

4. **Versions Array:**
   - Array is not empty (`length > 0`)
   - Each version has: `id`, `name`, `release_goal`, `milestone_titles`, `created_order`
   - `milestone_titles` is a non-empty array of strings matching milestone titles
   - `created_order` values are sequential

5. **Reasoning:**
   - `reasoning` field is present and non-null
   - Contains narrative explanation of consensus process

**Save Response to File:**
```bash
curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID/analysis > /tmp/consensus_result.json
echo "Results saved to /tmp/consensus_result.json"
```

**Extract Key Metrics:**
```bash
# Summary of analysis results
jq '{
  status: .analysis.status,
  converged: .analysis.converged,
  rounds: .analysis.total_rounds,
  duration_seconds: (
    (.analysis.completed_at | fromdateiso8601) -
    (.analysis.started_at | fromdateiso8601)
  ),
  tokens: .analysis.total_tokens,
  cost: .analysis.total_cost,
  milestone_count: (.milestones | length),
  checkpoint_count: (.checkpoints | length),
  version_count: (.versions | length)
}' /tmp/consensus_result.json
```

**Expected Metrics Output:**
```json
{
  "status": "converged",
  "converged": true,
  "rounds": 3,
  "duration_seconds": 142,
  "tokens": 12450,
  "cost": 0.0623,
  "milestone_count": 5,
  "checkpoint_count": 8,
  "version_count": 2
}
```

---

### Step 7: Database Deep Dive - Verify Data Persistence

Validate that all extracted entities were correctly persisted to the database with proper relationships.

**Verify Milestones:**
```bash
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT id, title, type, estimated_effort, created_order
   FROM milestones
   WHERE analysis_id = '$ANALYSIS_ID'
   ORDER BY created_order;"
```

**Expected Output:**
```
                  id                  |              title               |    type    | estimated_effort | created_order
--------------------------------------+----------------------------------+------------+------------------+---------------
 m1-uuid                              | WebSocket Infrastructure Setup   | technical  | M                |             0
 m2-uuid                              | Canvas Rendering Engine          | technical  | L                |             1
 m3-uuid                              | User Authentication System       | hybrid     | M                |             2
 ...
```

**Verify Checkpoints:**
```bash
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT c.id, c.title, c.type, m.title as milestone_title
   FROM checkpoints c
   JOIN milestones m ON c.milestone_id = m.id
   WHERE c.analysis_id = '$ANALYSIS_ID'
   ORDER BY m.created_order, c.title;"
```

**Expected Output:**
```
       id        |          title           |  type  |       milestone_title
-----------------+--------------------------+--------+------------------------------
 c1-uuid         | WebSocket Connection Test| poc    | WebSocket Infrastructure Setup
 c2-uuid         | Load Test 100 Concurrent | test   | WebSocket Infrastructure Setup
 ...
```

**Verify Versions:**
```bash
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT id, name, release_goal, milestone_titles, created_order
   FROM versions
   WHERE analysis_id = '$ANALYSIS_ID'
   ORDER BY created_order;"
```

**Expected Output:**
```
       id        | name |           release_goal            |           milestone_titles
-----------------+------+-----------------------------------+-------------------------------------
 v1-uuid         | MVP  | Basic collaborative drawing...    | {WebSocket Infrastructure Setup,...}
 v2-uuid         | v1.0 | Full-featured drawing tool...     | {Drawing Tools Implementation,...}
```

**Check Milestone Dependencies:**
```bash
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT title, dependencies
   FROM milestones
   WHERE analysis_id = '$ANALYSIS_ID'
     AND array_length(dependencies, 1) > 0
   ORDER BY created_order;"
```

**Expected Output:**
```
              title              |           dependencies
---------------------------------+----------------------------------
 Canvas Rendering Engine         | {WebSocket Infrastructure Setup}
 Real-time Synchronization       | {WebSocket Infrastructure Setup,Canvas Rendering Engine}
```

**Verify Consensus Rounds History:**
```bash
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT consensus_rounds
   FROM consensus_analyses
   WHERE id = '$ANALYSIS_ID';" \
  | jq '.'
```

**Expected Output:**
```json
{
  "rounds": [
    {
      "round_number": 1,
      "novelty_score": 1.0,
      "confidence": 0.65
    },
    {
      "round_number": 2,
      "novelty_score": 0.42,
      "confidence": 0.78
    },
    {
      "round_number": 3,
      "novelty_score": 0.15,
      "confidence": 0.85
    }
  ]
}
```

**Verification Criteria:**
- Novelty score decreases over rounds (convergence)
- Confidence score increases over rounds
- Final round has novelty < 0.2 or confidence > 0.85

---

### Step 8: Verify Project Status Updates

**Check Final Project Status:**
```bash
curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID | jq '{
  status: .status,
  document_count: .document_count,
  analyzed_at: .analyzed_at
}'
```

**Expected Output:**
```json
{
  "status": "analyzed",
  "document_count": 1,
  "analyzed_at": "2026-01-27T10:17:45Z"
}
```

**Verification Criteria:**
- `status` equals `"analyzed"`
- `analyzed_at` timestamp matches `completed_at` from analysis

**Database Cross-Check:**
```bash
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT p.status as project_status,
          ca.status as analysis_status,
          ca.converged
   FROM projects p
   JOIN consensus_analyses ca ON p.id = ca.project_id
   WHERE p.id = '$PROJECT_ID'
     AND ca.id = '$ANALYSIS_ID';"
```

**Expected Output:**
```
 project_status | analysis_status | converged
----------------+-----------------+-----------
 analyzed       | converged       | t
```

---

## Verification Summary

### Success Criteria Checklist

Run this final validation script to confirm all criteria are met:

```bash
#!/bin/bash
# Save as: /tmp/validate_consensus_demo.sh

echo "=== Consensus Demo Validation ==="
echo ""

# 1. Project exists and analyzed
PROJECT_STATUS=$(curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID | jq -r '.status')
echo "✓ Project Status: $PROJECT_STATUS"
[ "$PROJECT_STATUS" = "analyzed" ] && echo "  PASS" || echo "  FAIL"

# 2. Analysis converged
ANALYSIS_CONVERGED=$(curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID/analysis | jq -r '.analysis.converged')
echo "✓ Analysis Converged: $ANALYSIS_CONVERGED"
[ "$ANALYSIS_CONVERGED" = "true" ] && echo "  PASS" || echo "  FAIL"

# 3. Milestones extracted
MILESTONE_COUNT=$(curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID/analysis | jq '.milestones | length')
echo "✓ Milestones Extracted: $MILESTONE_COUNT"
[ "$MILESTONE_COUNT" -gt 0 ] && echo "  PASS" || echo "  FAIL"

# 4. Checkpoints extracted
CHECKPOINT_COUNT=$(curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID/analysis | jq '.checkpoints | length')
echo "✓ Checkpoints Extracted: $CHECKPOINT_COUNT"
[ "$CHECKPOINT_COUNT" -gt 0 ] && echo "  PASS" || echo "  FAIL"

# 5. Versions extracted
VERSION_COUNT=$(curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID/analysis | jq '.versions | length')
echo "✓ Versions Extracted: $VERSION_COUNT"
[ "$VERSION_COUNT" -gt 0 ] && echo "  PASS" || echo "  FAIL"

# 6. Database persistence
DB_MILESTONE_COUNT=$(docker exec overworld-postgres psql -U overworld -d overworld -t -c \
  "SELECT COUNT(*) FROM milestones WHERE analysis_id = '$ANALYSIS_ID';" | xargs)
echo "✓ Database Milestones: $DB_MILESTONE_COUNT"
[ "$DB_MILESTONE_COUNT" = "$MILESTONE_COUNT" ] && echo "  PASS" || echo "  FAIL"

# 7. Tokens consumed
TOTAL_TOKENS=$(curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID/analysis | jq '.analysis.total_tokens')
echo "✓ Tokens Consumed: $TOTAL_TOKENS"
[ "$TOTAL_TOKENS" -gt 0 ] && echo "  PASS" || echo "  FAIL"

# 8. Cost tracked
TOTAL_COST=$(curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID/analysis | jq '.analysis.total_cost')
echo "✓ Total Cost: \$$TOTAL_COST"
[ "$(echo "$TOTAL_COST > 0" | bc)" -eq 1 ] && echo "  PASS" || echo "  FAIL"

echo ""
echo "=== Validation Complete ==="
```

**Run Validation:**
```bash
chmod +x /tmp/validate_consensus_demo.sh
/tmp/validate_consensus_demo.sh
```

**Expected Output:**
```
=== Consensus Demo Validation ===

✓ Project Status: analyzed
  PASS
✓ Analysis Converged: true
  PASS
✓ Milestones Extracted: 5
  PASS
✓ Checkpoints Extracted: 8
  PASS
✓ Versions Extracted: 2
  PASS
✓ Database Milestones: 5
  PASS
✓ Tokens Consumed: 12450
  PASS
✓ Total Cost: $0.0623
  PASS

=== Validation Complete ===
```

---

## Known Limitations & Caveats

### 1. Document Content Placeholder
**Location:** `/home/delorenj/code/overworld/backend/app/workers/consensus_tasks.py:194`

**Current Behavior:**
```python
def _merge_project_documents(db: AsyncSession, project_id: UUID) -> str:
    # TODO: Implement proper text extraction from hierarchy structure
    # For now, use placeholder
    merged_parts.append(f"# {doc.filename}\n\n[Document content placeholder]")
```

**Impact:**
- Consensus analysis runs on placeholder text, not actual document content
- Extracted milestones/checkpoints are generic/placeholder-based
- Real-world usage blocked until document extraction implemented

**Workaround for Demo:**
- Demo validates the orchestration flow, not content quality
- To test with real content, manually update `processed_content` in database

### 2. Authentication Hardcoded
**Locations:** Multiple endpoints use `user_id = 1`

**Impact:**
- All projects/documents belong to user_id 1
- No multi-user isolation in demo

**Acceptable for Demo:** Yes, auth implementation is separate story

### 3. No Job Status Endpoint
**Gap:** No dedicated endpoint for querying ARQ job status

**Workaround:**
- Poll via `/api/v1/projects/{id}/analysis` endpoint
- Direct database queries via `psql`

**Future Enhancement:** Implement `/api/v1/analysis/{id}/status` endpoint

### 4. Event Emission Not Verified
**Gap:** Demo doesn't verify Bloodbank event emission

**Reason:**
- Events are emitted to Redis Streams
- No consumer exists in demo environment to verify delivery
- Would require WebSocket client or Redis XREAD monitoring

**Service-Level Verification:**
Events ARE emitted (code inspection confirms), but demo doesn't validate reception.

To verify events manually:
```bash
# Monitor Redis streams during analysis
docker exec -it overworld-redis redis-cli XREAD COUNT 10 STREAMS consensus:events 0
```

### 5. Checkpoint-Milestone Linking
**Location:** `/home/delorenj/code/overworld/backend/app/workers/consensus_tasks.py:304`

**Current Implementation:**
```python
# For now, link to first milestone as placeholder
if milestones:
    checkpoint.milestone_id = list(milestones.values())[0]
```

**Impact:**
- All checkpoints linked to first milestone
- Proper linking requires storing `milestone_title` in checkpoint schema

**Acceptable for Demo:** Structure is validated, linking logic is implementation detail

---

## Troubleshooting

### Problem: Analysis Status Stuck at "pending"

**Diagnosis:**
ARQ worker may not be running or processing jobs.

**Check Worker:**
```bash
# Check if ARQ worker container/process exists
docker ps | grep worker
# OR
ps aux | grep arq
```

**Solution:**
Start ARQ worker:
```bash
cd /home/delorenj/code/overworld/backend
uv run arq app.workers.worker.WorkerSettings
```

---

### Problem: Analysis Failed with Error

**Check Error Message:**
```bash
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT error_msg FROM consensus_analyses WHERE id = '$ANALYSIS_ID';"
```

**Common Errors:**

1. **"No document content found"**
   - Cause: No documents attached to project
   - Fix: Add at least one document (Step 2-3)

2. **"OpenRouter API key not configured"**
   - Cause: Missing `OPENROUTER_API_KEY` environment variable
   - Fix: Set environment variable in backend container

3. **"Connection refused" or Redis errors**
   - Cause: Redis/Bloodbank not running
   - Fix: Start Redis container

---

### Problem: Empty Milestones/Checkpoints

**Expected with Placeholder Content:**
Due to document content placeholder limitation, extracted entities may be minimal or generic.

**Verification:**
Check that SOME milestones exist:
```bash
curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID/analysis | jq '.milestones | length'
```

If returns `0`, check:
1. Analysis actually converged (not failed)
2. Consensus service model configuration
3. OpenRouter API connectivity

---

### Problem: API Returns 404 for Analysis

**Cause:** No analysis exists for project yet

**Verification:**
```bash
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT COUNT(*) FROM consensus_analyses WHERE project_id = '$PROJECT_ID';"
```

**Fix:** Trigger analysis first (Step 4)

---

## Cleanup

After completing the demo, clean up test data:

```bash
# Delete project (cascades to documents, analyses, milestones, etc.)
curl -X DELETE http://localhost:8778/api/v1/projects/$PROJECT_ID

# Verify deletion
docker exec -it overworld-postgres psql -U overworld -d overworld -c \
  "SELECT COUNT(*) FROM projects WHERE id = '$PROJECT_ID';"
```

**Expected:** Returns `0`

---

## Appendix: Architecture Flow

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /projects/{id}/analyze
       ▼
┌─────────────────────────────────────────────────────┐
│          FastAPI (projects.py router)               │
│  1. Create ConsensusAnalysis record (status=pending)│
│  2. Update Project status = analyzing               │
│  3. Enqueue ARQ job: process_consensus_analysis     │
└──────┬──────────────────────────────────────────────┘
       │ Returns 202 Accepted with analysis_id
       │
       ▼
┌─────────────────────────────────────────────────────┐
│              ARQ Worker (consensus_tasks.py)        │
│  4. Fetch project documents                         │
│  5. Merge document content                          │
│  6. Initialize ProjectConsensusService              │
│  7. Start Bloodbank event emitter                   │
└──────┬──────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────┐
│      ProjectConsensusService (consensus_service.py) │
│  8. ROUND 1-5 (iterative):                          │
│     a. EM Agent analyzes documents                  │
│     b. PM Agent analyzes documents (parallel)       │
│     c. Notetaker extracts unified structure         │
│     d. Calculate novelty score                      │
│     e. Emit events (round.started, round.completed) │
│     f. Check convergence                            │
│  9. Emit consensus.converged/failed event           │
└──────┬──────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────┐
│          Database Persistence (consensus_tasks.py)  │
│  10. Update ConsensusAnalysis (status=converged)    │
│  11. Insert Milestones                              │
│  12. Insert Checkpoints                             │
│  13. Insert Versions                                │
│  14. Update Project (status=analyzed, analyzed_at)  │
└─────────────────────────────────────────────────────┘
```

---

## File Reference

**Core Implementation:**
- `/home/delorenj/code/overworld/backend/app/services/consensus_service.py` - Multi-agent orchestration (502 lines)
- `/home/delorenj/code/overworld/backend/app/api/v1/routers/projects.py` - REST API endpoints (546 lines)
- `/home/delorenj/code/overworld/backend/app/workers/consensus_tasks.py` - ARQ background tasks (364 lines)

**Data Models:**
- `/home/delorenj/code/overworld/backend/app/models/project.py` - Project, ProjectDocument (143 lines)
- `/home/delorenj/code/overworld/backend/app/models/consensus.py` - ConsensusAnalysis, Milestone, Checkpoint, Version (325 lines)
- `/home/delorenj/code/overworld/backend/app/models/document.py` - Document model (62 lines)

**Schemas (API contracts):**
- `/home/delorenj/code/overworld/backend/app/schemas/project.py` - Request/response schemas (130 lines)

**Configuration:**
- `/home/delorenj/code/overworld/backend/app/main.py` - FastAPI app initialization (129 lines)
- `/home/delorenj/code/overworld/backend/app/core/config.py` - Environment configuration

---

## Demo Success Definition

This demo is **SUCCESSFUL** if and only if:

1. ✓ Project created via API with status `"created"`
2. ✓ Document added to project, status changes to `"ready"`
3. ✓ Analysis triggered, ARQ job enqueued, status `"pending"` → `"analyzing"`
4. ✓ Consensus service executes 2-5 rounds with convergence
5. ✓ Analysis completes with status `"converged"` and `converged=true`
6. ✓ Database contains persisted milestones (count > 0)
7. ✓ Database contains persisted checkpoints (count > 0)
8. ✓ Database contains persisted versions (count > 0)
9. ✓ Project status updated to `"analyzed"` with `analyzed_at` timestamp
10. ✓ Token usage and cost tracked (total_tokens > 0, total_cost > 0)

**FAILURE CONDITIONS:**
- Analysis status = `"failed"` with error message
- Timeout after 10 minutes without convergence
- Zero milestones/checkpoints/versions extracted
- Database integrity violations (missing foreign keys, null required fields)
- Project status stuck at `"analyzing"` indefinitely

---

**Demo Last Updated:** 2026-01-27
**Backend Version:** 0.1.0
**Demo Architect:** Cynically validated every damn step
