/**
 * useMapExport Hook
 *
 * Manages map export operations including:
 * - Creating export requests
 * - Polling export status
 * - Downloading completed exports
 * - Managing export history
 */

import { useState, useCallback, useEffect } from 'react';
import { useAuth } from './useAuth';

/**
 * Export format types
 */
export type ExportFormat = 'png' | 'svg';

/**
 * Export status types
 */
export type ExportStatus = 'pending' | 'processing' | 'completed' | 'failed';

/**
 * Export request configuration
 */
export interface ExportRequest {
  format: ExportFormat;
  resolution: 1 | 2 | 4;
  include_watermark?: boolean;
}

/**
 * Export response from API
 */
export interface ExportResponse {
  id: number;
  map_id: number;
  user_id: number;
  format: ExportFormat;
  resolution: number;
  status: ExportStatus;
  watermarked: boolean;
  file_size?: number;
  download_url?: string;
  error_message?: string;
  created_at: string;
  completed_at?: string;
  expires_at?: string;
}

/**
 * Export status response for polling
 */
export interface ExportStatusResponse {
  status: ExportStatus;
  progress?: number;
  download_url?: string;
  error_message?: string;
}

/**
 * Hook state
 */
interface UseMapExportState {
  loading: boolean;
  error: string | null;
  currentExport: ExportResponse | null;
  exports: ExportResponse[];
  pollingActive: boolean;
}

/**
 * Hook return type
 */
export interface UseMapExportResult extends UseMapExportState {
  requestExport: (mapId: number, config: ExportRequest) => Promise<ExportResponse>;
  pollExportStatus: (mapId: number, exportId: number) => Promise<void>;
  stopPolling: () => void;
  downloadExport: (exportId: number) => void;
  fetchExportHistory: (mapId: number) => Promise<void>;
  clearError: () => void;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const POLL_INTERVAL_MS = 2000; // Poll every 2 seconds

/**
 * Hook for managing map exports
 */
export function useMapExport(): UseMapExportResult {
  const { isAuthenticated } = useAuth();
  const [state, setState] = useState<UseMapExportState>({
    loading: false,
    error: null,
    currentExport: null,
    exports: [],
    pollingActive: false,
  });

  const [pollTimeoutId, setPollTimeoutId] = useState<NodeJS.Timeout | null>(null);

  /**
   * Clear any active polling
   */
  const stopPolling = useCallback(() => {
    if (pollTimeoutId) {
      clearTimeout(pollTimeoutId);
      setPollTimeoutId(null);
    }
    setState((prev) => ({ ...prev, pollingActive: false }));
  }, [pollTimeoutId]);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  /**
   * Make authenticated API request
   */
  const apiRequest = useCallback(
    async <T,>(url: string, options: RequestInit = {}): Promise<T> => {
      if (!isAuthenticated) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(`${API_BASE_URL}${url}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        credentials: 'include', // Send cookies for session-based auth
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }

      return response.json();
    },
    [isAuthenticated]
  );

  /**
   * Request a new export
   */
  const requestExport = useCallback(
    async (mapId: number, config: ExportRequest): Promise<ExportResponse> => {
      setState((prev) => ({ ...prev, loading: true, error: null }));

      try {
        const response = await apiRequest<ExportResponse>(
          `/api/v1/maps/${mapId}/export`,
          {
            method: 'POST',
            body: JSON.stringify(config),
          }
        );

        setState((prev) => ({
          ...prev,
          loading: false,
          currentExport: response,
        }));

        // Start polling for status
        pollExportStatus(mapId, response.id);

        return response;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to request export';
        setState((prev) => ({
          ...prev,
          loading: false,
          error: errorMessage,
        }));
        throw error;
      }
    },
    [apiRequest]
  );

  /**
   * Poll export status until completed or failed
   */
  const pollExportStatus = useCallback(
    async (mapId: number, exportId: number): Promise<void> => {
      setState((prev) => ({ ...prev, pollingActive: true }));

      const poll = async () => {
        try {
          const status = await apiRequest<ExportStatusResponse>(
            `/api/v1/maps/${mapId}/export/${exportId}/status`
          );

          // Update current export with status
          setState((prev) => ({
            ...prev,
            currentExport: prev.currentExport
              ? { ...prev.currentExport, status: status.status, download_url: status.download_url }
              : null,
          }));

          // Continue polling if not complete
          if (status.status === 'pending' || status.status === 'processing') {
            const timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
            setPollTimeoutId(timeoutId);
          } else {
            // Export complete or failed
            setState((prev) => ({ ...prev, pollingActive: false }));
            setPollTimeoutId(null);

            if (status.status === 'failed') {
              setState((prev) => ({
                ...prev,
                error: status.error_message || 'Export failed',
              }));
            }
          }
        } catch (error) {
          setState((prev) => ({
            ...prev,
            pollingActive: false,
            error: error instanceof Error ? error.message : 'Failed to check export status',
          }));
          setPollTimeoutId(null);
        }
      };

      // Start polling
      poll();
    },
    [apiRequest]
  );

  /**
   * Download export file
   */
  const downloadExport = useCallback((exportId: number) => {
    const exportItem = state.exports.find((e) => e.id === exportId) || state.currentExport;

    if (!exportItem?.download_url) {
      setState((prev) => ({
        ...prev,
        error: 'Download URL not available',
      }));
      return;
    }

    // Trigger download
    const link = document.createElement('a');
    link.href = exportItem.download_url;
    link.download = `map_${exportItem.map_id}_export.${exportItem.format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [state.currentExport, state.exports]);

  /**
   * Fetch export history for a map
   */
  const fetchExportHistory = useCallback(
    async (mapId: number): Promise<void> => {
      setState((prev) => ({ ...prev, loading: true, error: null }));

      try {
        const response = await apiRequest<{ exports: ExportResponse[] }>(
          `/api/v1/maps/${mapId}/exports`
        );

        setState((prev) => ({
          ...prev,
          loading: false,
          exports: response.exports,
        }));
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to fetch exports';
        setState((prev) => ({
          ...prev,
          loading: false,
          error: errorMessage,
        }));
      }
    },
    [apiRequest]
  );

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  return {
    ...state,
    requestExport,
    pollExportStatus,
    stopPolling,
    downloadExport,
    fetchExportHistory,
    clearError,
  };
}
