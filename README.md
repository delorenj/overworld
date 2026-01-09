# Overworld

**AI-Powered Project Mapping Platform**

Transform your linear project documentation into interactive 8/16-bit overworld maps. Built with FastAPI, React, and PixiJS.

## Quick Start

### Prerequisites

- [Docker](https://www.docker.com/get-started) (v24+)
- [mise](https://mise.jdx.dev/) (task runner & tool version manager)
- [1Password CLI](https://developer.1password.com/docs/cli/get-started/) (optional, for secret management)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/overworld.git
   cd overworld
   ```

2. **Set up environment variables:**
   ```bash
   # Option 1: Manual setup (simpler for quick start)
   cp .env.example .env
   # Edit .env with your configuration

   # Option 2: 1Password integration (recommended for teams)
   ./scripts/load-secrets.sh
   # See docs/1PASSWORD-SETUP.md for details
   ```

3. **Start all services:**
   ```bash
   mise run dev
   ```

   This single command will:
   - Build Docker images for backend and frontend
   - Start PostgreSQL, Redis, RabbitMQ
   - Start FastAPI backend with hot reload
   - Start React frontend with Vite hot reload
   - Configure Traefik reverse proxy

4. **Access the application:**
   - **Frontend:** http://localhost
   - **Backend API:** http://localhost/api/health
   - **API Docs:** http://localhost/docs
   - **Traefik Dashboard:** http://localhost:8080
   - **RabbitMQ Management:** http://localhost:15672 (user: overworld, pass: overworld_rabbitmq_password)

### First-Time Setup

After starting services for the first time, run database migrations:

```bash
mise run migrate
```

## Development

### Available Tasks

```bash
# Start all services (with build)
mise run dev

# Start in detached mode (background)
mise run dev-detached

# Stop all services
mise run down

# View logs
mise run logs

# Database migrations
mise run migrate                 # Apply migrations
mise run migrate-create "message" # Create new migration
mise run migrate-rollback        # Rollback last migration

# Seed database with test data
mise run seed

# Run tests
mise run test                    # Backend tests
mise run test-cov                # With coverage report

# Linting & Formatting
mise run lint                    # Backend linting
mise run lint-fix                # Backend linting with auto-fix
mise run format                  # Backend formatting
mise run frontend-lint           # Frontend linting
mise run frontend-format         # Frontend formatting

# Shell access
mise run shell-backend           # Open shell in backend container
mise run shell-db                # Open psql in database

# Clean up
mise run clean                   # Remove containers and volumes
mise run rebuild                 # Full rebuild from scratch
```

### Hot Reload

Both backend and frontend support hot reload out of the box:

#### Backend (FastAPI)
- **Powered by:** uvicorn --reload
- **Watches:** All Python files in `backend/app/`
- **Auto-restart:** On file save
- **Test:** Edit `backend/app/main.py` and refresh http://localhost/api/health

#### Frontend (React + Vite)
- **Powered by:** Vite dev server
- **Watches:** All files in `frontend/src/`
- **Hot Module Replacement (HMR):** Instant updates without page reload
- **Test:** Edit `frontend/src/main.tsx` and see changes instantly at http://localhost

### Code Quality

#### Pre-commit Hooks

Install pre-commit hooks to automatically lint and format code before commits:

```bash
bash scripts/setup-precommit.sh
```

Hooks configured:
- **Backend:** ruff (linting + formatting)
- **Frontend:** eslint + prettier
- **General:** trailing whitespace, YAML checks, private key detection

#### Manual Linting

```bash
# Backend
docker compose exec backend ruff check .
docker compose exec backend ruff format .

# Frontend
docker compose exec frontend npm run lint
docker compose exec frontend npm run format
```

### Running Tests

```bash
# Backend: pytest
mise run test

# Backend: pytest with coverage
mise run test-cov

# Frontend: Vitest (when tests are added)
docker compose exec frontend npm test
```

## Project Structure

```
overworld/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/v1/         # API routes
│   │   ├── core/           # Core configuration
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   ├── workers/        # Background workers
│   │   └── main.py         # Application entry point
│   ├── alembic/            # Database migrations
│   ├── tests/              # Backend tests
│   ├── Dockerfile          # Backend container
│   └── requirements.txt    # Python dependencies
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── services/       # API clients
│   │   ├── hooks/          # Custom React hooks
│   │   └── main.tsx        # Application entry point
│   ├── Dockerfile          # Frontend container
│   └── package.json        # Node.js dependencies
├── scripts/                # Utility scripts
├── docs/                   # Documentation
├── docker-compose.yml      # Docker Compose configuration
├── .mise.toml              # Mise task configuration
├── .env.example            # Environment variable template
└── README.md               # This file
```

## Architecture

Overworld uses a **Modular Monolith** architecture with:

- **Backend:** FastAPI (Python 3.12, async-native)
- **Frontend:** React 19 + TypeScript + PixiJS (60 FPS WebGL rendering)
- **Database:** PostgreSQL 16 (with JSONB for hierarchy storage)
- **Cache:** Redis 7 (session storage, rate limiting)
- **Queue:** RabbitMQ 3 (asynchronous job processing)
- **Proxy:** Traefik 2 (reverse proxy + routing)
- **Storage:** Cloudflare R2 (S3-compatible object storage)
- **LLM:** OpenRouter (multi-provider routing)

For detailed architecture documentation, see:
- [Architecture Document](/docs/architecture-overworld-2026-01-08.md)
- [Sprint Plan](/docs/sprint-plan-overworld-2026-01-09.md)

## Environment Variables

See `.env.example` for all available configuration options.

### Required for Development

```bash
# Database (defaults work for local development)
DATABASE_URL=postgresql://overworld:overworld_dev_password@postgres:5432/overworld

# Redis (defaults work for local development)
REDIS_URL=redis://:overworld_redis_password@redis:6379/0

# RabbitMQ (defaults work for local development)
RABBITMQ_URL=amqp://overworld:overworld_rabbitmq_password@rabbitmq:5672/
```

### Required for External Services

```bash
# OpenRouter (for AI map generation)
OPENROUTER_API_KEY=your_key_here

# Stripe (for payments)
STRIPE_API_KEY=your_key_here
STRIPE_WEBHOOK_SECRET=your_webhook_secret_here

# Cloudflare R2 (for file storage)
R2_ACCESS_KEY_ID=your_key_id
R2_SECRET_ACCESS_KEY=your_secret_key
R2_ENDPOINT_URL=https://your-account.r2.cloudflarestorage.com
```

## Troubleshooting

### Services won't start

```bash
# Check Docker is running
docker info

# Check for port conflicts
lsof -i :80 -i :5432 -i :6379 -i :5672

# Clean up and rebuild
mise run clean
mise run rebuild
```

### Database connection errors

```bash
# Check PostgreSQL health
docker compose exec postgres pg_isready -U overworld

# Restart PostgreSQL
docker compose restart postgres

# Reset database (WARNING: destroys all data)
mise run clean
mise run dev
mise run migrate
```

### Frontend build errors

```bash
# Rebuild frontend with clean install
docker compose exec frontend rm -rf node_modules
docker compose restart frontend
```

### Hot reload not working

```bash
# Backend: Check uvicorn logs
docker compose logs backend

# Frontend: Check Vite logs
docker compose logs frontend

# Ensure volumes are mounted correctly
docker compose config
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`mise run test && mise run lint`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Support

- **Documentation:** [/docs](/docs)
- **Issues:** [GitHub Issues](https://github.com/yourusername/overworld/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/overworld/discussions)

---

**Built with ❤️ using BMAD Method v6**
