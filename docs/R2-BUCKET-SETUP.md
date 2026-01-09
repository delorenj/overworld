# Cloudflare R2 Bucket Setup

This document provides instructions for creating and configuring Cloudflare R2 buckets for the Overworld project.

## Prerequisites

1. **Cloudflare Account** with R2 enabled
2. **Wrangler CLI** installed: `npm install -g wrangler`
3. **Cloudflare API Token** with R2 edit permissions

## Authentication

Login to Cloudflare via Wrangler:

```bash
wrangler login
```

Or set API token as environment variable:

```bash
export CLOUDFLARE_API_TOKEN=your_api_token_here
export CLOUDFLARE_ACCOUNT_ID=your_account_id_here
```

## Bucket Creation

Create all four required buckets:

```bash
# Bucket 1: Uploaded documents (markdown, PDF)
wrangler r2 bucket create overworld-uploads \
  --location auto

# Bucket 2: Generated map JSON
wrangler r2 bucket create overworld-maps \
  --location auto

# Bucket 3: Theme assets (sprites, icons, textures)
wrangler r2 bucket create overworld-themes \
  --location auto

# Bucket 4: Exported maps (PNG, SVG)
wrangler r2 bucket create overworld-exports \
  --location auto
```

## CORS Configuration

Enable CORS for frontend access (if needed):

```bash
# Create CORS config file
cat > r2-cors.json << 'EOF'
{
  "AllowedOrigins": ["https://overworld.com", "http://localhost:5173"],
  "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
  "AllowedHeaders": ["*"],
  "ExposeHeaders": ["ETag"],
  "MaxAgeSeconds": 3600
}
EOF

# Apply CORS to each bucket
wrangler r2 bucket cors set overworld-uploads --cors-file r2-cors.json
wrangler r2 bucket cors set overworld-maps --cors-file r2-cors.json
wrangler r2 bucket cors set overworld-themes --cors-file r2-cors.json
wrangler r2 bucket cors set overworld-exports --cors-file r2-cors.json
```

## Lifecycle Policies

Set up automatic cleanup for temporary exports:

```bash
# Create lifecycle policy for exports (delete after 7 days)
cat > r2-lifecycle.json << 'EOF'
{
  "Rules": [
    {
      "ID": "DeleteOldExports",
      "Status": "Enabled",
      "Expiration": {
        "Days": 7
      },
      "Filter": {
        "Prefix": ""
      }
    }
  ]
}
EOF

# Apply lifecycle policy to exports bucket
wrangler r2 bucket lifecycle set overworld-exports --lifecycle-file r2-lifecycle.json
```

## Access Credentials

Create R2 API tokens for application access:

```bash
# Via Cloudflare dashboard:
# 1. Go to R2 → Settings → API Tokens
# 2. Create API Token with:
#    - Permissions: Object Read & Write
#    - Buckets: All buckets (or specific buckets)
# 3. Copy Access Key ID and Secret Access Key

# Store in 1Password or environment:
R2_ACCESS_KEY_ID=<your-access-key-id>
R2_SECRET_ACCESS_KEY=<your-secret-access-key>
R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
```

## Bucket URLs

R2 buckets are accessible via S3-compatible API:

```
Endpoint: https://<account-id>.r2.cloudflarestorage.com
Bucket URLs:
  - s3://overworld-uploads
  - s3://overworld-maps
  - s3://overworld-themes
  - s3://overworld-exports
```

## Testing Connection

Test R2 connectivity using boto3:

```python
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url="https://<account-id>.r2.cloudflarestorage.com",
    aws_access_key_id="<R2_ACCESS_KEY_ID>",
    aws_secret_access_key="<R2_SECRET_ACCESS_KEY>",
)

# List buckets
response = s3.list_buckets()
print([bucket["Name"] for bucket in response["Buckets"]])

# Upload test file
s3.put_object(
    Bucket="overworld-uploads",
    Key="test.txt",
    Body=b"Hello R2!",
)

# Download test file
obj = s3.get_object(Bucket="overworld-uploads", Key="test.txt")
print(obj["Body"].read())
```

## Public Access (Optional)

For public assets (themes, exports with watermark):

```bash
# Enable public access for themes bucket
wrangler r2 bucket publicaccess set overworld-themes --public
```

Public URL format:
```
https://pub-<hash>.r2.dev/<key>
```

## Cost Optimization

R2 pricing (as of 2026):
- **Storage:** $0.015/GB/month
- **Class A Operations (PUT, LIST):** $4.50/million
- **Class B Operations (GET, HEAD):** $0.36/million
- **Egress:** FREE (major advantage over S3)

**Optimization tips:**
1. Use lifecycle policies to delete old exports automatically
2. Cache frequently accessed theme assets in Redis
3. Use pre-signed URLs for temporary access
4. Batch operations where possible

## Security Best Practices

1. **Never commit R2 credentials** to version control
2. **Use 1Password** or similar secret manager for production credentials
3. **Rotate API tokens** quarterly
4. **Set bucket permissions** to least privilege (Object Read/Write only)
5. **Enable audit logging** in Cloudflare dashboard
6. **Use pre-signed URLs** for temporary access (1-hour expiry)

## Backup Strategy

Configure automated backups:

```bash
# Backup script (run daily via cron or K8s CronJob)
#!/bin/bash

DATE=$(date +%Y-%m-%d)
BACKUP_BUCKET="overworld-backups"

# Sync each bucket to backup bucket with date prefix
wrangler r2 object sync overworld-uploads "$BACKUP_BUCKET/$DATE/uploads"
wrangler r2 object sync overworld-maps "$BACKUP_BUCKET/$DATE/maps"
wrangler r2 object sync overworld-themes "$BACKUP_BUCKET/$DATE/themes"

# Keep backups for 30 days, then delete
```

## Troubleshooting

### "Bucket already exists" error
- Bucket names are globally unique across all Cloudflare accounts
- Try a different name: `overworld-uploads-production`

### "Access denied" error
- Verify R2 API token has correct permissions
- Check endpoint URL format: `https://<account-id>.r2.cloudflarestorage.com`
- Ensure bucket name matches exactly (case-sensitive)

### Slow upload/download
- Check network connectivity to Cloudflare
- Use multi-part uploads for files >5MB
- Consider CDN/caching for frequently accessed files

## References

- [Cloudflare R2 Documentation](https://developers.cloudflare.com/r2/)
- [Wrangler CLI Reference](https://developers.cloudflare.com/workers/wrangler/)
- [boto3 S3 API](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
- [R2 Pricing](https://developers.cloudflare.com/r2/pricing/)

---

**Created:** 2026-01-09
**Last Updated:** 2026-01-09
**Owner:** Overworld DevOps
