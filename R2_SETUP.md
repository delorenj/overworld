# R2 Setup Instructions

## Get R2 API Credentials

1. Open: https://dash.cloudflare.com/f68a196c5c84014bb85f8ab97b386994/r2/overview
2. Click "Manage R2 API Tokens" in right sidebar
3. Click "Create API Token"
4. Set permissions: **Admin Read & Write**
5. Click "Create API Token"
6. Copy the values shown:
   - Access Key ID: `<COPY_THIS>`
   - Secret Access Key: `<COPY_THIS>`

## Update .env

Replace these lines in `/home/delorenj/code/overworld/.env`:

```bash
R2_ACCESS_KEY_ID=<PASTE_ACCESS_KEY_ID_HERE>
R2_SECRET_ACCESS_KEY=<PASTE_SECRET_ACCESS_KEY_HERE>
```

The endpoint URL is already correct:
```bash
R2_ENDPOINT_URL=https://f68a196c5c84014bb85f8ab97b386994.r2.cloudflarestorage.com/
```

## Apply Changes

```bash
# Update docker-compose to use .env vars
docker compose restart backend

# Test upload
curl -X POST http://localhost:8001/api/v1/documents/upload -F "file=@/tmp/test-document.md"
```

Expected success response:
```json
{
  "document_id": "...",
  "filename": "test-document.md",
  "size_bytes": 322,
  "r2_url": "https://...",
  "uploaded_at": "2026-01-09T..."
}
```
