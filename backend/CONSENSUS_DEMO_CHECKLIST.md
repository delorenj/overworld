# Consensus Demo Validation Checklist

Quick reference card for verifying demo success. Print this and check boxes as you validate each criterion.

## Pre-Demo Verification

- [ ] `docker ps` shows `overworld-backend` running (port 8778)
- [ ] `docker ps` shows `overworld-postgres` healthy
- [ ] `docker ps` shows `overworld-redis` healthy
- [ ] `curl http://localhost:8778/api/health` returns `{"status":"ok"}`
- [ ] `curl http://localhost:8778/api/v1/status` shows `redis: connected`
- [ ] `jq --version` command exists
- [ ] OpenRouter API key is configured (check backend env vars)

## Step 1: Project Creation

**Command:** `POST /api/v1/projects`

- [ ] Response status: `201 Created`
- [ ] Response contains valid UUID in `id` field
- [ ] `status` field equals `"created"`
- [ ] `document_count` equals `0`
- [ ] `analyzed_at` is `null`
- [ ] Database record exists: `SELECT * FROM projects WHERE id = '$PROJECT_ID'`

## Step 2: Document Upload

**Command:** `POST /api/v1/documents/upload`

- [ ] Response status: `201 Created`
- [ ] Response contains valid UUID in `id` field
- [ ] `status` field equals `"uploaded"`
- [ ] `mime_type` is `"text/markdown"` or `"application/pdf"`
- [ ] `file_size_bytes` > 0
- [ ] Database record exists: `SELECT * FROM documents WHERE id = '$DOC1_ID'`

## Step 3: Add Document to Project

**Command:** `POST /api/v1/projects/{id}/documents`

- [ ] Response status: `201 Created`
- [ ] Response message: `"Document added to project successfully"`
- [ ] `order_index` equals `0` (first document)
- [ ] Join table record exists: `SELECT * FROM project_documents WHERE project_id = '$PROJECT_ID'`
- [ ] Project status changed to `"ready"`: `GET /api/v1/projects/{id}` returns `status: "ready"`
- [ ] Project `document_count` equals `1`

## Step 4: Trigger Analysis

**Command:** `POST /api/v1/projects/{id}/analyze`

- [ ] Response status: `202 Accepted`
- [ ] Response contains valid UUID in `analysis_id` field
- [ ] `status` field equals `"pending"`
- [ ] `arq_job_id` is present and starts with `"consensus-"`
- [ ] `converged` is `false`
- [ ] All counts (`milestones_count`, `checkpoints_count`, `versions_count`) are `0`
- [ ] `started_at` and `completed_at` are `null`
- [ ] Database record exists: `SELECT * FROM consensus_analyses WHERE id = '$ANALYSIS_ID'`
- [ ] Project status changed to `"analyzing"`

## Step 5: Monitor Progress

**Polling:** `GET /api/v1/projects/{id}/analysis` every 10 seconds

- [ ] Status changes from `"pending"` to `"analyzing"` (within 30 seconds)
- [ ] `started_at` timestamp appears when status becomes `"analyzing"`
- [ ] `total_rounds` increments during processing (0 → 1 → 2 → 3...)
- [ ] Status eventually reaches `"converged"` OR `"failed"` (within 10 minutes)
- [ ] If failed: `error_msg` field contains explanation

## Step 6: Results Validation (after convergence)

**Command:** `GET /api/v1/projects/{id}/analysis`

### Analysis Metadata
- [ ] `analysis.status` equals `"converged"`
- [ ] `analysis.converged` is `true`
- [ ] `analysis.total_rounds` is between `2` and `5`
- [ ] `analysis.total_tokens` > `0`
- [ ] `analysis.total_cost` > `0.0`
- [ ] `analysis.started_at` is present (not null)
- [ ] `analysis.completed_at` is present (not null)
- [ ] Duration between timestamps is reasonable (30s - 5min)

### Convergence Metrics
- [ ] `analysis.final_confidence` > `0.5` (preferably > 0.85)
- [ ] `analysis.final_novelty` < `1.0` (preferably < 0.2)
- [ ] Either: confidence > 0.85 OR novelty < 0.2 (convergence criterion met)

### Milestones Array
- [ ] `milestones` array is not empty (`length > 0`)
- [ ] Each milestone has: `id`, `title`, `description`, `type`, `estimated_effort`, `dependencies`, `created_order`
- [ ] `type` values are valid: `"technical"`, `"product"`, or `"hybrid"`
- [ ] `estimated_effort` values are valid: `"S"`, `"M"`, `"L"`, or `"XL"`
- [ ] `dependencies` is an array (can be empty)
- [ ] `created_order` values are sequential (0, 1, 2, ...)
- [ ] Titles are substantive (not just "Milestone 1", "Milestone 2")
- [ ] Descriptions are non-empty and relevant

### Checkpoints Array
- [ ] `checkpoints` array is not empty (`length > 0`)
- [ ] Each checkpoint has: `id`, `title`, `type`, `validation_criteria`, `milestone_id`
- [ ] `type` values are valid: `"poc"`, `"demo"`, `"test"`, or `"review"`
- [ ] `validation_criteria` is a non-empty array of strings
- [ ] `milestone_id` references a milestone from the milestones array
- [ ] Titles are descriptive

### Versions Array
- [ ] `versions` array is not empty (`length > 0`)
- [ ] Each version has: `id`, `name`, `release_goal`, `milestone_titles`, `created_order`
- [ ] `name` values are reasonable (e.g., "MVP", "v1.0", "Beta")
- [ ] `release_goal` is non-empty string
- [ ] `milestone_titles` is a non-empty array
- [ ] Milestone titles in array match actual milestone titles
- [ ] `created_order` values are sequential (0, 1, 2, ...)

### Reasoning Field
- [ ] `reasoning` field is present
- [ ] `reasoning` is not null
- [ ] Reasoning text is substantive (explains consensus process)

## Step 7: Database Verification

### Milestones Table
```sql
SELECT COUNT(*) FROM milestones WHERE analysis_id = '$ANALYSIS_ID';
```
- [ ] Count matches `analysis.milestones_count` from API
- [ ] Records have non-null: `title`, `description`, `type`, `estimated_effort`
- [ ] `created_order` values are unique and sequential

### Checkpoints Table
```sql
SELECT COUNT(*) FROM checkpoints WHERE analysis_id = '$ANALYSIS_ID';
```
- [ ] Count matches `analysis.checkpoints_count` from API
- [ ] Records have non-null: `title`, `type`, `validation_criteria`
- [ ] All `milestone_id` foreign keys reference existing milestones

### Versions Table
```sql
SELECT COUNT(*) FROM versions WHERE analysis_id = '$ANALYSIS_ID';
```
- [ ] Count matches `analysis.versions_count` from API
- [ ] Records have non-null: `name`, `release_goal`, `milestone_titles`
- [ ] `created_order` values are unique and sequential

### ConsensusAnalysis Record
```sql
SELECT status, converged, total_rounds, final_confidence, final_novelty
FROM consensus_analyses WHERE id = '$ANALYSIS_ID';
```
- [ ] `status` = `converged`
- [ ] `converged` = `t` (true)
- [ ] `total_rounds` matches API response
- [ ] `final_confidence` is not null
- [ ] `final_novelty` is not null

### Consensus Rounds JSONB
```sql
SELECT consensus_rounds FROM consensus_analyses WHERE id = '$ANALYSIS_ID';
```
- [ ] JSON field contains `"rounds"` array
- [ ] Array length equals `total_rounds`
- [ ] Each round has: `round_number`, `novelty_score`, `confidence`
- [ ] Novelty scores generally decrease over rounds (convergence trend)
- [ ] Confidence scores generally increase over rounds

## Step 8: Project Status Verification

**Command:** `GET /api/v1/projects/{id}`

- [ ] `status` equals `"analyzed"`
- [ ] `document_count` equals `1` (or number of documents added)
- [ ] `analyzed_at` timestamp is present (not null)
- [ ] `analyzed_at` matches `completed_at` from analysis (within 1 second)

### Database Cross-Check
```sql
SELECT p.status, ca.status, ca.converged
FROM projects p
JOIN consensus_analyses ca ON p.id = ca.project_id
WHERE p.id = '$PROJECT_ID' AND ca.id = '$ANALYSIS_ID';
```
- [ ] Project status = `analyzed`
- [ ] Analysis status = `converged`
- [ ] Converged = `t`

## Performance Metrics

### Token Efficiency
- [ ] Total tokens: 5,000 - 50,000 (reasonable range)
- [ ] Average tokens per round: < 20,000
- [ ] No excessive retries (rounds <= 5)

### Cost Efficiency
- [ ] Total cost: $0.01 - $0.50 (reasonable for demo)
- [ ] Cost per round: < $0.20
- [ ] Cost per milestone: < $0.10

### Timing
- [ ] Analysis started within 30 seconds of triggering
- [ ] Total analysis time: 30 seconds - 10 minutes
- [ ] Each round: < 3 minutes
- [ ] API response times: < 2 seconds

## Final Validation Script

Run this command to auto-check all criteria:

```bash
curl -s http://localhost:8778/api/v1/projects/$PROJECT_ID/analysis | jq '{
  pass_converged: (.analysis.converged == true),
  pass_rounds: (.analysis.total_rounds >= 2 and .analysis.total_rounds <= 5),
  pass_tokens: (.analysis.total_tokens > 0),
  pass_cost: (.analysis.total_cost > 0),
  pass_milestones: ((.milestones | length) > 0),
  pass_checkpoints: ((.checkpoints | length) > 0),
  pass_versions: ((.versions | length) > 0),
  pass_reasoning: (.reasoning != null)
}'
```

Expected output: All fields should be `true`

## Cleanup Verification

After running `DELETE /api/v1/projects/{id}`:

- [ ] API returns 200 or 204
- [ ] `SELECT COUNT(*) FROM projects WHERE id = '$PROJECT_ID'` returns `0`
- [ ] `SELECT COUNT(*) FROM consensus_analyses WHERE project_id = '$PROJECT_ID'` returns `0`
- [ ] `SELECT COUNT(*) FROM milestones WHERE analysis_id = '$ANALYSIS_ID'` returns `0`
- [ ] Cascade deletion worked (all child records removed)

---

## Quick Pass/Fail Summary

**PASS Criteria:**
- ✓ Status = converged
- ✓ Converged = true
- ✓ Rounds: 2-5
- ✓ Milestones > 0
- ✓ Checkpoints > 0
- ✓ Versions > 0
- ✓ Tokens > 0
- ✓ Cost > 0
- ✓ Project status = analyzed
- ✓ Database counts match API

**FAIL Criteria:**
- ✗ Status = failed
- ✗ Timeout (> 10 minutes)
- ✗ Zero milestones/checkpoints/versions
- ✗ Database integrity violations
- ✗ API errors (4xx/5xx responses)
- ✗ Project stuck at "analyzing" indefinitely

---

**Print this checklist and mark boxes as you validate each step.**

**Completion Rate:** _____ / 100 checks passed

**Overall Status:** [ ] PASS  [ ] FAIL

**Date Tested:** ________________

**Tested By:** ________________
