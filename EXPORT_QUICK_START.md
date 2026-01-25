# Map Export - Quick Start Guide

Quick guide to get the map export feature running.

## 1. Install Dependencies

```bash
# Backend
cd backend
pip install -r requirements.txt  # Includes Pillow 10.2.0

# Frontend (no new dependencies needed)
cd frontend
npm install
```

## 2. Database Migration

```bash
cd backend
alembic upgrade head
```

This creates the `exports` table with all necessary fields and indexes.

## 3. Environment Variables

Ensure R2 credentials are set in `.env`:

```bash
R2_ACCESS_KEY_ID=your_key
R2_SECRET_ACCESS_KEY=your_secret
R2_ENDPOINT_URL=https://your-account.r2.cloudflarestorage.com
R2_BUCKET_EXPORTS=overworld  # Or your export bucket name
```

## 4. Run Tests

```bash
# Backend tests
cd backend
pytest tests/test_export.py -v

# Frontend tests (if you add them)
cd frontend
npm test -- ExportDialog.test.tsx
```

## 5. Start Services

```bash
# Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm run dev
```

## 6. Test Export Flow

### Via API (curl)

```bash
# 1. Get auth token (replace with your login method)
TOKEN="your-jwt-token"

# 2. Request export
curl -X POST http://localhost:8000/api/v1/maps/1/export \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "png",
    "resolution": 1,
    "include_watermark": false
  }'

# Response: {"id": 1, "status": "pending", ...}

# 3. Check status
curl http://localhost:8000/api/v1/maps/1/export/1/status \
  -H "Authorization: Bearer $TOKEN"

# 4. Get download URL (when completed)
curl http://localhost:8000/api/v1/maps/1/export/1 \
  -H "Authorization: Bearer $TOKEN"
```

### Via Frontend

1. Navigate to a map view
2. Click "Export Map" button
3. Select format (PNG/SVG) and resolution
4. Click "Export Map"
5. Wait for processing (status updates automatically)
6. Click "Download" when ready

## 7. Integration Example

Add export button to your map component:

```tsx
import { useState } from 'react';
import { ExportDialog } from './components/map';
import { useAuth } from './hooks';

function MyMapComponent({ mapId, mapName }) {
  const [showExport, setShowExport] = useState(false);
  const { user } = useAuth();
  const isPremium = user?.tokenBalance > 0;

  return (
    <div>
      <button onClick={() => setShowExport(true)}>
        Export
      </button>

      <ExportDialog
        mapId={mapId}
        mapName={mapName}
        isPremium={isPremium}
        isOpen={showExport}
        onClose={() => setShowExport(false)}
      />
    </div>
  );
}
```

## 8. Common Issues

### "Pillow not found"
```bash
pip install Pillow==10.2.0
```

### "Table exports does not exist"
```bash
alembic upgrade head
```

### "R2 upload failed"
- Check R2 credentials in `.env`
- Verify bucket exists
- Check network connectivity

### "Download URL null"
- Wait for export to complete (status = "completed")
- Check export hasn't expired (24-hour limit)

## 9. File Locations

### Backend
- Service: `/home/delorenj/code/overworld/backend/app/services/export_service.py`
- Router: `/home/delorenj/code/overworld/backend/app/api/v1/routers/export.py`
- Model: `/home/delorenj/code/overworld/backend/app/models/export.py`
- Tests: `/home/delorenj/code/overworld/backend/tests/test_export.py`

### Frontend
- Hook: `/home/delorenj/code/overworld/frontend/src/hooks/useMapExport.ts`
- Component: `/home/delorenj/code/overworld/frontend/src/components/map/ExportDialog.tsx`
- Example: `/home/delorenj/code/overworld/frontend/src/components/map/MapViewerExample.tsx`

## 10. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/maps/{map_id}/export` | Request export |
| GET | `/api/v1/maps/{map_id}/export/{export_id}/status` | Poll status |
| GET | `/api/v1/maps/{map_id}/export/{export_id}` | Get details + URL |
| GET | `/api/v1/maps/{map_id}/exports` | List map exports |
| GET | `/api/v1/exports` | List user exports |

## 11. Resolution Options

| Resolution | Dimensions | Use Case |
|------------|------------|----------|
| 1x | 1024×768 | Preview, web display |
| 2x | 2048×1536 | HD display, printing |
| 4x | 4096×3072 | High-quality print |

## 12. Watermark Behavior

```python
# Free user (tokens = 0)
→ Always watermarked (ignores include_watermark=false)

# Premium user (tokens > 0)
→ Respects include_watermark setting
→ Default: no watermark
```

## 13. Monitoring

Watch logs for export processing:

```bash
# Backend logs
tail -f backend/logs/app.log | grep export

# Check export status in DB
psql -d overworld -c "SELECT id, status, format, resolution FROM exports ORDER BY created_at DESC LIMIT 10;"
```

## Done!

You now have a fully functional map export system. For detailed documentation, see:
- `/home/delorenj/code/overworld/backend/docs/EXPORT_FEATURE.md`
- `/home/delorenj/code/overworld/STORY-015-IMPLEMENTATION.md`
