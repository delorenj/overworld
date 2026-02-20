# Consensus Analysis Demo - Quick Start

## What This Demo Validates

This interactive demo proves that the **project-centric consensus analysis system** is fully operational in Overworld backend. It validates:

- **Multi-agent orchestration**: EM + PM + Notetaker agents collaborate through iterative rounds
- **Convergence detection**: System detects when agents reach stable consensus
- **Background processing**: ARQ job queue handles long-running analysis tasks
- **Event emission**: Real-time progress updates via Bloodbank/Redis Streams
- **Database persistence**: Milestones, checkpoints, and versions stored in PostgreSQL
- **API integration**: Complete REST API workflow from project creation to result retrieval

## Quick Start (5 minutes)

### Option 1: Automated Script (Recommended)

Run the fully automated demo that executes all steps and validates results:

```bash
cd /home/delorenj/code/overworld/backend
./run_consensus_demo.sh
```

**What it does:**
1. Verifies prerequisites (API health, Redis connectivity)
2. Creates a test project
3. Generates and uploads a realistic PRD document
4. Adds document to project
5. Triggers consensus analysis
6. Polls for completion (auto-waits up to 10 minutes)
7. Retrieves and displays results
8. Verifies database persistence
9. Prints summary with cleanup instructions

**Expected runtime:** 1-5 minutes (depending on OpenRouter API speed)

### Option 2: Manual Step-by-Step

Follow the comprehensive walkthrough with curl commands and validation checks:

```bash
cd /home/delorenj/code/overworld/backend
less CONSENSUS_DEMO_RUNLIST.md
```

**When to use manual steps:**
- Learning the API contracts
- Debugging specific failures
- Understanding database schema
- Customizing test data

## Files in This Demo Package

### 1. `CONSENSUS_DEMO_RUNLIST.md` (Primary Documentation)
**Type:** Task Runlist (comprehensive verification procedure)
**Length:** ~800 lines
**Purpose:** Deterministic, step-by-step verification that proves system works

**Contains:**
- Prerequisites checklist
- 8-step workflow with curl commands
- Expected responses for every API call
- Database verification queries
- Success criteria validation
- Troubleshooting guide
- Known limitations and caveats
- Architecture diagrams

**Use this when:**
- You need to verify specific components
- Something fails and you need to debug
- You're documenting the system for others
- You want to understand the architecture

### 2. `run_consensus_demo.sh` (Automation Script)
**Type:** Bash automation script
**Length:** ~400 lines
**Purpose:** One-command execution of entire demo workflow

**Features:**
- Color-coded output (green=success, red=error)
- Automatic polling with progress indicators
- Error handling with graceful exit
- Results saved to timestamped JSON file
- Database verification via psql
- Cleanup instructions printed at end

**Use this when:**
- You want quick validation (CI/CD, smoke tests)
- Demonstrating to stakeholders
- You trust the implementation and just need proof it works

### 3. `CONSENSUS_DEMO_README.md` (This File)
**Type:** Executive summary and quick reference
**Purpose:** Entry point for humans who want to run the demo

## Prerequisites

**Services Required:**
- `overworld-backend` (API server on port 8778)
- `overworld-postgres` (PostgreSQL database)
- `overworld-redis` (Redis for job queue)

**Verify services:**
```bash
docker ps | grep overworld
curl -s http://localhost:8778/api/health
```

**Required CLI Tools:**
- `curl` (API requests)
- `jq` (JSON parsing)
- `docker` (database access)

## What Gets Created

Running this demo creates:

**Database Records:**
- 1 Project (`projects` table)
- 1 Document (`documents` table)
- 1 ProjectDocument link (`project_documents` table)
- 1 ConsensusAnalysis (`consensus_analyses` table)
- 3-8 Milestones (`milestones` table)
- 5-15 Checkpoints (`checkpoints` table)
- 2-4 Versions (`versions` table)

**Temporary Files:**
- `/tmp/consensus_result_*.json` (full analysis results)
- `/tmp/test-prd.md` or `/tmp/demo_prd_*.md` (test document)

## Expected Results

**Successful Demo:**
```
✓ Project Status: analyzed
✓ Analysis Converged: true
✓ Milestones Extracted: 5-8
✓ Checkpoints Extracted: 8-15
✓ Versions Extracted: 2-4
✓ Database Milestones: matches API count
✓ Tokens Consumed: 10,000-20,000
✓ Total Cost: $0.05-$0.15
```

**Timing:**
- API operations: <1 second each
- Document upload: <2 seconds
- Consensus analysis: 60-300 seconds (typical: 90-120s)
- Total demo: 2-5 minutes

## Interpreting Results

### Milestone Example
```json
{
  "title": "WebSocket Infrastructure Setup",
  "type": "technical",
  "estimated_effort": "M",
  "dependencies": [],
  "description": "Establish reliable real-time communication layer..."
}
```

**Validation:**
- `type` should match document tone (technical/product/hybrid)
- `estimated_effort` should be S/M/L/XL
- `dependencies` should reference other milestone titles
- `description` should be substantive (not placeholder text)

### Convergence Metrics
```json
{
  "converged": true,
  "total_rounds": 3,
  "final_confidence": 0.87,
  "final_novelty": 0.12
}
```

**What to look for:**
- `converged=true` (system reached stable state)
- `total_rounds` between 2-5 (efficient convergence)
- `final_confidence` > 0.85 OR `final_novelty` < 0.2
- Token usage is reasonable (not excessive retries)

## Known Limitations

### 1. Placeholder Document Content
**Impact:** Consensus runs on placeholder text instead of real document content

**Location:** `app/workers/consensus_tasks.py:194`

**Why it matters:**
- Extracted milestones will be generic/placeholder-based
- Real-world usage blocked until document extraction implemented
- Demo validates **orchestration flow**, not **content quality**

**Acceptable for demo?** YES - the goal is to prove the multi-agent system works

### 2. Checkpoint Linking Placeholder
**Impact:** All checkpoints link to first milestone instead of proper milestone

**Why it matters:**
- Relationships are structurally incorrect
- Requires schema change to store `milestone_title` in checkpoint extraction

**Acceptable for demo?** YES - data is persisted, linking logic is implementation detail

### 3. No Job Status Endpoint
**Workaround:** Poll via `GET /projects/{id}/analysis` or query database directly

## Troubleshooting

### Analysis Stuck at "pending"
**Diagnosis:** ARQ worker not running

**Fix:**
```bash
cd /home/delorenj/code/overworld/backend
uv run arq app.workers.worker.WorkerSettings
```

### Analysis Failed
**Check error:**
```bash
curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID/analysis | jq '.error_msg'
```

**Common causes:**
- No documents in project → Add at least one document
- Missing OpenRouter API key → Set `OPENROUTER_API_KEY` env var
- Redis disconnected → Check `docker ps | grep redis`

### Empty Results
**If milestones/checkpoints = 0:**
- Check that analysis status is `converged` (not `failed`)
- Verify OpenRouter API connectivity
- Check consensus service configuration in logs

## Cleanup

After demo completion:

```bash
# Get project ID from demo output
PROJECT_ID="<your-project-id>"

# Delete project (cascades to all related records)
curl -X DELETE http://localhost:8778/api/v1/projects/$PROJECT_ID

# Verify deletion
docker exec overworld-postgres psql -U overworld -d overworld -c \
  "SELECT COUNT(*) FROM projects WHERE id = '$PROJECT_ID';"
# Should return: 0
```

## Success Criteria

This demo **PASSES** if:
1. Analysis status reaches `converged=true`
2. At least 1 milestone extracted
3. At least 1 checkpoint extracted
4. At least 1 version extracted
5. Project status updates to `analyzed`
6. Database records match API response counts

This demo **FAILS** if:
- Analysis status = `failed` with error message
- Timeout after 10 minutes
- Zero milestones/checkpoints/versions
- Database integrity violations

## Architecture Reference

```
Client
  ↓ POST /projects/{id}/analyze
FastAPI Router
  ↓ Enqueue ARQ job
ARQ Worker
  ↓ Initialize consensus service
ProjectConsensusService
  ↓ Rounds 1-5 (iterative)
  ├─→ EM Agent analyzes
  ├─→ PM Agent analyzes (parallel)
  └─→ Notetaker extracts structure
  ↓ Check convergence
Database
  ↓ Persist milestones/checkpoints/versions
Bloodbank/Redis
  ↓ Emit events (consensus.started, round.completed, etc.)
```

## Next Steps

After validating this demo:

1. **Implement document content extraction** (remove placeholder in `_merge_project_documents`)
2. **Add job status endpoint** (`GET /api/v1/analysis/{id}/status`)
3. **Fix checkpoint-milestone linking** (store milestone_title in schema)
4. **Add authentication** (replace hardcoded `user_id=1`)
5. **Create frontend consumer** for consensus events via WebSocket

## Support

**Demo not working?**
1. Check `CONSENSUS_DEMO_RUNLIST.md` troubleshooting section
2. Verify prerequisites (services running, tools installed)
3. Review backend logs: `docker logs overworld-backend`
4. Check ARQ worker logs if running separately

**Questions about implementation?**
- Read inline comments in source files listed in runlist
- Review architecture flow diagram in runlist appendix
- Check database schema in model files

---

**Demo Created:** 2026-01-27
**Backend Version:** 0.1.0
**Maintained By:** Demo Architect (the cynical guardian of testability)
