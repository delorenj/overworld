# Map Export Feature

This document describes the Map Export feature implementation for the Overworld platform.

## Overview

The Map Export feature allows users to export their generated maps as PNG or SVG files with configurable resolution. Free-tier users receive exports with a watermark, while premium users can export without watermarks.

## Architecture

### Backend Components

#### 1. Export Model (`app/models/export.py`)

Stores export records in PostgreSQL with the following fields:

- `id`: Primary key
- `map_id`: Foreign key to maps table
- `user_id`: Foreign key to users table
- `format`: Export format (PNG or SVG)
- `resolution`: Resolution multiplier (1x, 2x, or 4x)
- `status`: Export status (pending, processing, completed, failed)
- `file_path`: R2 storage path
- `file_size`: File size in bytes
- `watermarked`: Whether watermark was applied
- `error_message`: Error details if failed
- `created_at`, `completed_at`, `expires_at`: Timestamps

#### 2. Export Service (`app/services/export_service.py`)

Business logic for export operations:

- **Create Export**: Validates map ownership and user tier
- **Process Export**: Generates PNG/SVG files in background
- **Apply Watermark**: Adds "Overworld" watermark for free users
- **Upload to R2**: Stores files in Cloudflare R2
- **Generate URLs**: Creates time-limited download links

#### 3. Export Router (`app/api/v1/routers/export.py`)

REST API endpoints:

- `POST /api/v1/maps/{map_id}/export` - Request new export
- `GET /api/v1/maps/{map_id}/export/{export_id}` - Get export details
- `GET /api/v1/maps/{map_id}/export/{export_id}/status` - Poll status
- `GET /api/v1/maps/{map_id}/exports` - List map exports
- `GET /api/v1/exports` - List all user exports

#### 4. Export Schemas (`app/schemas/export.py`)

Pydantic models for API validation:

- `ExportRequest`: Export configuration
- `ExportResponse`: Export details with download URL
- `ExportStatusResponse`: Quick status for polling
- `ExportListResponse`: Paginated export list

### Frontend Components

#### 1. useMapExport Hook (`src/hooks/useMapExport.ts`)

Custom React hook managing export operations:

```typescript
const {
  loading,
  error,
  currentExport,
  exports,
  pollingActive,
  requestExport,
  pollExportStatus,
  stopPolling,
  downloadExport,
  fetchExportHistory,
  clearError,
} = useMapExport();
```

#### 2. ExportDialog Component (`src/components/map/ExportDialog.tsx`)

Modal dialog with:

- Format selector (PNG/SVG)
- Resolution selector (1x, 2x, 4x)
- Watermark notice for free users
- Export progress indicator
- Download button
- Export history list

## Usage

### Backend API

#### Request Export

```bash
POST /api/v1/maps/123/export
Authorization: Bearer <token>
Content-Type: application/json

{
  "format": "png",
  "resolution": 2,
  "include_watermark": false
}
```

Response:
```json
{
  "id": 456,
  "map_id": 123,
  "user_id": 789,
  "format": "png",
  "resolution": 2,
  "status": "pending",
  "watermarked": false,
  "expires_at": "2026-01-21T17:00:00Z",
  "created_at": "2026-01-20T17:00:00Z"
}
```

#### Poll Status

```bash
GET /api/v1/maps/123/export/456/status
Authorization: Bearer <token>
```

Response:
```json
{
  "status": "completed",
  "progress": 100,
  "download_url": "https://r2.example.com/exports/..."
}
```

### Frontend Usage

```tsx
import { ExportDialog } from './components/map';
import { useMapExport } from './hooks';

function MapView({ mapId, mapName }) {
  const [showExport, setShowExport] = useState(false);
  const { token } = useAuth();
  const isPremium = token?.balance > 0;

  return (
    <>
      <button onClick={() => setShowExport(true)}>
        Export Map
      </button>

      <ExportDialog
        mapId={mapId}
        mapName={mapName}
        isPremium={isPremium}
        isOpen={showExport}
        onClose={() => setShowExport(false)}
      />
    </>
  );
}
```

## Export Processing Flow

1. **Request Creation**
   - User submits export request via API
   - Service validates map ownership
   - Checks user tier (free vs premium)
   - Creates export record with PENDING status
   - Returns export ID immediately

2. **Background Processing**
   - FastAPI BackgroundTasks processes export
   - Status updated to PROCESSING
   - Map data rendered to PNG or SVG
   - Watermark applied if needed
   - File uploaded to R2 storage

3. **Completion**
   - Status updated to COMPLETED
   - File path and size stored
   - Expiration time set (24 hours)

4. **Download**
   - User requests export details
   - Service generates pre-signed R2 URL (1 hour)
   - User downloads file directly from R2

## Watermark Logic

```python
# Free users (tokens == 0): Always watermarked
if user_balance == 0:
    watermarked = True

# Premium users (tokens > 0): Optional watermark
else:
    watermarked = request.include_watermark
```

Watermark properties:
- Text: "Overworld"
- Position: Bottom-right corner
- Opacity: 50% (128/255)
- Font: DejaVu Sans Bold
- Size: Scales with resolution

## Storage and Expiry

- **Storage**: Cloudflare R2 (S3-compatible)
- **Bucket**: `overworld/exports/`
- **Path Format**: `exports/{user_id}/{timestamp}/{filename}`
- **Expiry**: 24 hours after creation
- **Download URL**: 1-hour pre-signed URL

## Resolution and File Sizes

| Resolution | Dimensions | PNG Size (Est.) | SVG Size (Est.) |
|------------|------------|-----------------|-----------------|
| 1x         | 1024×768   | ~100-500 KB     | ~50-200 KB      |
| 2x         | 2048×1536  | ~400-2 MB       | ~100-400 KB     |
| 4x         | 4096×3072  | ~1.5-8 MB       | ~200-800 KB     |

*Sizes vary based on map complexity*

## Error Handling

Common error scenarios:

1. **Map Not Found**: 404 error if map doesn't exist or user doesn't own it
2. **Upload Failure**: Export marked as FAILED with error message
3. **Expired Export**: Download URL returns null if export expired
4. **Processing Timeout**: Background task has reasonable timeout
5. **Invalid Format**: Validation error for unsupported formats

## Testing

Run export tests:

```bash
# Backend tests
cd backend
pytest tests/test_export.py -v

# Frontend tests
cd frontend
npm test -- ExportDialog.test.tsx
```

## Database Migration

Apply the export table migration:

```bash
cd backend
alembic upgrade head
```

The migration creates:
- `exports` table
- `exportformat` enum type
- `exportstatus` enum type
- Indexes on common query fields
- Foreign key constraints with CASCADE delete

## Performance Considerations

1. **Background Processing**: Export generation runs in FastAPI BackgroundTasks to avoid blocking requests
2. **Polling**: Frontend polls status every 2 seconds until complete
3. **Caching**: R2 serves files with CDN caching
4. **File Size Limits**: No hard limit, but larger resolutions take longer
5. **Concurrent Exports**: Users can have multiple pending exports

## Security

1. **Authentication**: All endpoints require JWT token
2. **Authorization**: Users can only access their own exports
3. **Pre-signed URLs**: Time-limited access to R2 files
4. **Input Validation**: Resolution and format validated
5. **SQL Injection**: Protected by SQLAlchemy ORM
6. **Rate Limiting**: Consider adding rate limits in production

## Future Enhancements

- [ ] Custom watermark text for premium users
- [ ] Export quality settings (compression level)
- [ ] Batch export for multiple maps
- [ ] Email notification when export completes
- [ ] Advanced export options (DPI, color modes)
- [ ] Export templates and presets
- [ ] Webhook notifications for export completion
- [ ] Export analytics and usage tracking

## API Reference

See [API Documentation](../docs/api/export.md) for detailed endpoint specifications.

## Support

For issues or questions:
- Backend: Check logs in `app/services/export_service.py`
- Frontend: Check browser console for hook errors
- R2: Verify credentials in `.env` file
- Database: Check migration status with `alembic current`
