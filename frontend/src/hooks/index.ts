/**
 * Hooks
 *
 * Export all custom hooks.
 */

// Authentication hooks
export { useAuth, AuthProvider } from './useAuth';

// Map hooks
export { useMapRenderer } from './useMapRenderer';
export type { UseMapRendererResult } from './useMapRenderer';

export { useMapControls } from './useMapControls';
export type { MapControlsConfig, UseMapControlsResult } from './useMapControls';

export { useMapData, createSampleMapData } from './useMapData';
export type { UseMapDataConfig, UseMapDataResult } from './useMapData';

export { useMapExport } from './useMapExport';
export type {
  ExportFormat,
  ExportStatus,
  ExportRequest,
  ExportResponse,
  ExportStatusResponse,
  UseMapExportResult,
} from './useMapExport';

// WebSocket hooks
export { useWebSocket } from './useWebSocket';
export type { UseWebSocketOptions, UseWebSocketResult } from './useWebSocket';
