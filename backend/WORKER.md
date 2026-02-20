# Overworld Generation Worker

## Overview

The generation worker is a background service that processes map generation jobs from the RabbitMQ queue. It consumes jobs created by the API and executes the full generation pipeline, broadcasting real-time progress updates via Redis pub/sub.

## Architecture

```
[API] → [RabbitMQ Queue] → [Worker] → [Database + Redis]
                                    ↓
                              [WebSocket Clients]
```

**Flow:**
1. User uploads document via API → job created in DB + message published to RabbitMQ
2. Worker consumes message from queue
3. Worker processes job (parse → layout → render)
4. Worker broadcasts progress events to Redis
5. WebSocket clients receive real-time updates
6. Job status updated in DB (PENDING → PROCESSING → COMPLETED/FAILED)

## Running the Worker

### Via Docker Compose (Recommended)

The worker service is included in `compose.yml`:

```bash
# Start all services including worker
docker compose up -d

# View worker logs
docker compose logs -f worker

# Restart worker only
docker compose restart worker
```

### Standalone (Development)

```bash
cd backend
python run_worker.py
```

**Requirements:**
- PostgreSQL, Redis, and RabbitMQ must be running
- Environment variables must be configured (see `.env`)

## Environment Variables

The worker uses the same environment variables as the backend:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/overworld
REDIS_URL=redis://:password@localhost:6379/0
RABBITMQ_URL=amqp://user:pass@localhost:5672/
OPENROUTER_API_KEY=sk-...  # For AI generation
R2_ACCESS_KEY_ID=...       # For R2 storage
R2_SECRET_ACCESS_KEY=...
R2_ENDPOINT_URL=https://...
R2_BUCKET_NAME=overworld
```

## Job Processing

The worker handles these job lifecycle stages:

1. **PENDING** - Job queued, waiting for worker
2. **PROCESSING** - Worker actively processing
3. **COMPLETED** - Successfully generated map
4. **FAILED** - Processing failed (with error message)

### Progress Events

The worker broadcasts these Redis pub/sub events:

- `job_started` - Job processing begins
- `progress_update` - Periodic progress (0-100%)
- `job_completed` - Job finished successfully
- `job_failed` - Job failed with error

## Queue Topology

**Queues:**
- `overworld.jobs.pending` - New jobs waiting for processing
- `overworld.jobs.retry` - Failed jobs eligible for retry
- `overworld.jobs.failed` - Permanently failed jobs (DLQ)

**Routing Keys:**
- `job.pending` - Route to pending queue
- `job.retry` - Route to retry queue
- `job.failed` - Route to failed queue

## Monitoring

```bash
# Check worker health
docker compose ps worker

# View recent logs
docker compose logs --tail=100 worker

# Follow logs in real-time
docker compose logs -f worker

# Check RabbitMQ queue status
# Visit http://localhost:15672 (user: overworld, pass: see .env)
```

## Troubleshooting

### Worker not consuming jobs

1. Check RabbitMQ is healthy: `docker compose ps rabbitmq`
2. Verify queue exists: Visit RabbitMQ management UI
3. Check worker logs: `docker compose logs worker`

### Jobs stuck in PENDING

- Ensure worker service is running
- Check RABBITMQ_URL is correct in worker environment
- Verify queue topology is set up (worker creates this on startup)

### Jobs failing immediately

- Check OPENROUTER_API_KEY is configured
- Verify R2 credentials are correct
- Check worker logs for specific error messages

## Development

The worker code is in `app/workers/generation_worker.py`. Key classes:

- `GenerationWorker` - Main worker class
- `start_worker()` - Entry point function
- `broadcast_progress()` - Utility for progress updates

### Testing

```bash
# Run worker tests
pytest tests/test_generation_worker.py -v

# Test job queue
pytest tests/test_job_queue.py -v
```

## Future Enhancements

- [ ] Integrate CoordinatorAgent for actual generation pipeline
- [ ] Add worker scaling (multiple worker instances)
- [ ] Implement priority queues for premium users
- [ ] Add metrics/observability (Prometheus)
- [ ] Dead letter queue processing UI
