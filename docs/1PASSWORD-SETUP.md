# 1Password CLI Integration

This document explains how to integrate 1Password CLI for secure secret management in development and production.

## Installation

### macOS
```bash
brew install --cask 1password-cli
```

### Linux
```bash
curl -sS https://downloads.1password.com/linux/keys/1password.asc | sudo gpg --dearmor --output /usr/share/keyrings/1password-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/1password-archive-keyring.gpg] https://downloads.1password.com/linux/debian/$(dpkg --print-architecture) stable main" | sudo tee /etc/apt/sources.list.d/1password.list
sudo apt update && sudo apt install 1password-cli
```

## Setup

1. **Sign in to 1Password CLI:**
   ```bash
   op signin
   ```

2. **Create a vault for Overworld secrets** (if not exists):
   ```bash
   op vault create "Overworld Development"
   ```

3. **Store secrets in 1Password:**
   ```bash
   # OpenRouter API Key
   op item create \
     --category=API \
     --vault="Overworld Development" \
     --title="OpenRouter API Key" \
     api_key="your-openrouter-api-key"

   # Stripe API Keys
   op item create \
     --category=API \
     --vault="Overworld Development" \
     --title="Stripe API Keys" \
     api_key="your-stripe-api-key" \
     webhook_secret="your-stripe-webhook-secret"

   # JWT Secret
   op item create \
     --category=Password \
     --vault="Overworld Development" \
     --title="JWT Secret Key" \
     password="$(openssl rand -hex 32)"

   # Cloudflare R2 Credentials
   op item create \
     --category=API \
     --vault="Overworld Development" \
     --title="Cloudflare R2" \
     access_key_id="your-r2-access-key" \
     secret_access_key="your-r2-secret-key" \
     endpoint_url="your-r2-endpoint-url"
   ```

## Usage with mise

The `.mise.toml` file is configured to load environment variables from `.env`. You can use 1Password to inject secrets:

### Option 1: Create .env from 1Password (Recommended for Development)

Create a script to generate `.env` from 1Password:

```bash
# scripts/load-secrets.sh
#!/bin/bash

# Load secrets from 1Password and write to .env
cat > .env << EOF
# Database Configuration (Development defaults, override for production)
POSTGRES_USER=overworld
POSTGRES_PASSWORD=overworld_dev_password
POSTGRES_DB=overworld
DATABASE_URL=postgresql://overworld:overworld_dev_password@postgres:5432/overworld

# Redis Configuration (Development defaults)
REDIS_PASSWORD=overworld_redis_password
REDIS_URL=redis://:overworld_redis_password@redis:6379/0

# RabbitMQ Configuration (Development defaults)
RABBITMQ_USER=overworld
RABBITMQ_PASSWORD=overworld_rabbitmq_password
RABBITMQ_URL=amqp://overworld:overworld_rabbitmq_password@rabbitmq:5672/

# JWT Secret (from 1Password)
JWT_SECRET_KEY=$(op read "op://Overworld Development/JWT Secret Key/password")

# External Services (from 1Password)
OPENROUTER_API_KEY=$(op read "op://Overworld Development/OpenRouter API Key/api_key")
STRIPE_API_KEY=$(op read "op://Overworld Development/Stripe API Keys/api_key")
STRIPE_WEBHOOK_SECRET=$(op read "op://Overworld Development/Stripe API Keys/webhook_secret")

# Cloudflare R2 (from 1Password)
R2_ACCESS_KEY_ID=$(op read "op://Overworld Development/Cloudflare R2/access_key_id")
R2_SECRET_ACCESS_KEY=$(op read "op://Overworld Development/Cloudflare R2/secret_access_key")
R2_ENDPOINT_URL=$(op read "op://Overworld Development/Cloudflare R2/endpoint_url")
R2_BUCKET_NAME=overworld-uploads

# Environment
ENVIRONMENT=development
EOF

echo "✓ Secrets loaded from 1Password into .env"
```

Run before starting services:
```bash
chmod +x scripts/load-secrets.sh
./scripts/load-secrets.sh
mise run dev
```

### Option 2: Direct Injection (Recommended for CI/CD)

Use `op run` to inject secrets directly:

```bash
op run --env-file=".env.op" -- mise run dev
```

Where `.env.op` contains 1Password secret references:
```
OPENROUTER_API_KEY=op://Overworld Development/OpenRouter API Key/api_key
STRIPE_API_KEY=op://Overworld Development/Stripe API Keys/api_key
# etc.
```

## Production Deployment

For production, use 1Password Connect or similar secret management:

1. **Deploy 1Password Connect** to Kubernetes cluster
2. **Use External Secrets Operator** to sync secrets from 1Password to Kubernetes Secrets
3. **Mount as environment variables** in pod specs

## Security Best Practices

1. **Never commit `.env`** to version control (already in `.gitignore`)
2. **Use different vaults** for development, staging, and production
3. **Rotate secrets regularly** (quarterly for API keys, monthly for JWT secrets)
4. **Limit access** to production vaults (only DevOps team)
5. **Audit access logs** in 1Password monthly

## Troubleshooting

### "unauthorized" error
```bash
# Re-authenticate
op signin
```

### "item not found" error
```bash
# List items to verify name
op item list --vault="Overworld Development"
```

### Permission denied
```bash
# Verify vault access
op vault list
```

## Alternative: Without 1Password

If you don't use 1Password, simply create a `.env` file manually:

```bash
cp .env.example .env
# Edit .env with your actual secrets
```

**Warning:** Never commit `.env` with real secrets to version control!
