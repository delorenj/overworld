#!/bin/bash
# Quick script to update R2 credentials and restart backend

echo "=== R2 Credentials Update ==="
echo ""
echo "Enter R2 Access Key ID:"
read -r ACCESS_KEY_ID

echo "Enter R2 Secret Access Key:"
read -r SECRET_ACCESS_KEY

echo ""
echo "Updating .env file..."

# Update .env file
sed -i "s|^R2_ACCESS_KEY_ID=.*|R2_ACCESS_KEY_ID=$ACCESS_KEY_ID|" .env
sed -i "s|^R2_SECRET_ACCESS_KEY=.*|R2_SECRET_ACCESS_KEY=$SECRET_ACCESS_KEY|" .env

echo "✓ .env updated"

echo ""
echo "Restarting backend..."
docker compose restart backend

echo ""
echo "Waiting for backend to start..."
sleep 5

echo ""
echo "Testing upload..."
curl -X POST http://localhost:8001/api/v1/documents/upload -F "file=@/tmp/test-document.md"

echo ""
echo ""
echo "=== Done ==="
