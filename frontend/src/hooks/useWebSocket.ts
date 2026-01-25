/**
 * useWebSocket Hook
 *
 * React hook for managing WebSocket connections to the job progress endpoint.
 * Provides automatic reconnection with exponential backoff, ping/pong keep-alive,
 * and comprehensive error handling.
 *
 * Usage:
 *   const { progress, isConnected, connect, disconnect } = useWebSocket(jobId, token, {
 *     onProgress: (event) => console.log('Progress:', event.progress_pct),
 *     onCompleted: (event) => console.log('Completed!', event.map_id),
 *   });
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import type {
  WebSocketConnectionState,
  WebSocketMessage,
  WebSocketEvent,
  JobProgressState,
  UseWebSocketOptions,
  UseWebSocketResult,
  ConnectionEstablishedEvent,
  JobStartedEvent,
  ProgressUpdateEvent,
  JobCompletedEvent,
  JobFailedEvent,
  ConnectionErrorEvent,
} from '../types/websocket';

/**
 * Get WebSocket URL for job progress
 */
function getWebSocketUrl(jobId: number, token: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = import.meta.env.VITE_WS_URL || window.location.host;
  return `${protocol}//${host}/api/v1/ws/jobs/${jobId}?token=${encodeURIComponent(token)}`;
}

/**
 * Calculate exponential backoff delay
 */
function calculateBackoff(
  attempt: number,
  baseDelay: number,
  maxDelay: number
): number {
  const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
  // Add jitter (random 0-30% of delay)
  const jitter = delay * Math.random() * 0.3;
  return Math.floor(delay + jitter);
}

/**
 * Default options for useWebSocket
 */
const defaultOptions: Required<UseWebSocketOptions> = {
  autoReconnect: true,
  maxReconnectAttempts: 5,
  reconnectBaseDelay: 1000,
  reconnectMaxDelay: 30000,
  pingInterval: 30000,
  onConnected: () => {},
  onJobStarted: () => {},
  onProgress: () => {},
  onCompleted: () => {},
  onFailed: () => {},
  onError: () => {},
};

/**
 * Hook for WebSocket connection to job progress endpoint
 *
 * @param jobId - ID of the job to monitor
 * @param token - JWT authentication token
 * @param options - Configuration options
 * @returns WebSocket state and control functions
 */
export function useWebSocket(
  jobId: number | null,
  token: string | null,
  options: UseWebSocketOptions = {}
): UseWebSocketResult {
  // Merge options with defaults
  const opts = { ...defaultOptions, ...options };

  // State
  const [connectionState, setConnectionState] =
    useState<WebSocketConnectionState>('disconnected');
  const [progress, setProgress] = useState<JobProgressState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  // Refs for stable references
  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const mountedRef = useRef(true);
  const optionsRef = useRef(opts);

  // Update options ref when options change
  useEffect(() => {
    optionsRef.current = { ...defaultOptions, ...options };
  }, [options]);

  /**
   * Clear all timeouts and intervals
   */
  const clearTimers = useCallback(() => {
    if (pingIntervalRef.current) {
      window.clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  /**
   * Send a ping message for keep-alive
   */
  const sendPing = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const pingMessage: WebSocketMessage = {
        event: {
          type: 'ping',
          timestamp: new Date().toISOString(),
        },
      };
      wsRef.current.send(JSON.stringify(pingMessage));
    }
  }, []);

  /**
   * Handle incoming WebSocket message
   */
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      const wsEvent = message.event as WebSocketEvent;

      switch (wsEvent.type) {
        case 'connection_established': {
          const connEvent = wsEvent as ConnectionEstablishedEvent;
          setProgress({
            jobId: connEvent.job_id,
            status: connEvent.current_status,
            progressPct: connEvent.current_progress,
            canRetry: false,
          });
          optionsRef.current.onConnected(connEvent);
          break;
        }

        case 'job_started': {
          const startEvent = wsEvent as JobStartedEvent;
          setProgress((prev) =>
            prev
              ? {
                  ...prev,
                  status: 'processing',
                  startedAt: startEvent.started_at,
                  agentName: startEvent.agent_name,
                }
              : null
          );
          optionsRef.current.onJobStarted(startEvent);
          break;
        }

        case 'progress_update': {
          const progressEvent = wsEvent as ProgressUpdateEvent;
          setProgress((prev) =>
            prev
              ? {
                  ...prev,
                  progressPct: progressEvent.progress_pct,
                  progressMessage: progressEvent.progress_message,
                  agentName: progressEvent.agent_name,
                  stage: progressEvent.stage,
                }
              : null
          );
          optionsRef.current.onProgress(progressEvent);
          break;
        }

        case 'job_completed': {
          const completeEvent = wsEvent as JobCompletedEvent;
          setProgress((prev) =>
            prev
              ? {
                  ...prev,
                  status: 'completed',
                  progressPct: 100,
                  completedAt: completeEvent.completed_at,
                  mapId: completeEvent.map_id,
                }
              : null
          );
          optionsRef.current.onCompleted(completeEvent);
          break;
        }

        case 'job_failed': {
          const failEvent = wsEvent as JobFailedEvent;
          setProgress((prev) =>
            prev
              ? {
                  ...prev,
                  status: 'failed',
                  errorMessage: failEvent.error_message,
                  errorCode: failEvent.error_code,
                  canRetry: failEvent.can_retry,
                }
              : null
          );
          optionsRef.current.onFailed(failEvent);
          break;
        }

        case 'job_cancelled': {
          // Job was cancelled
          setProgress((prev) =>
            prev
              ? {
                  ...prev,
                  status: 'cancelled',
                }
              : null
          );
          break;
        }

        case 'connection_error': {
          const errEvent = wsEvent as ConnectionErrorEvent;
          setError(errEvent.message);
          setConnectionState('error');
          optionsRef.current.onError(errEvent);
          break;
        }

        case 'pong':
          // Keep-alive response, no action needed
          break;

        default:
          console.warn('Unknown WebSocket event type:', (wsEvent as WebSocketEvent).type);
      }
    } catch (err) {
      console.error('Failed to parse WebSocket message:', err);
    }
  }, []);

  /**
   * Attempt to reconnect with exponential backoff
   */
  const attemptReconnect = useCallback(() => {
    if (!mountedRef.current) return;

    const opts = optionsRef.current;

    if (reconnectAttempts >= opts.maxReconnectAttempts) {
      setConnectionState('error');
      setError(`Failed to connect after ${opts.maxReconnectAttempts} attempts`);
      return;
    }

    setConnectionState('reconnecting');
    const delay = calculateBackoff(
      reconnectAttempts,
      opts.reconnectBaseDelay,
      opts.reconnectMaxDelay
    );

    console.log(
      `Reconnecting in ${delay}ms (attempt ${reconnectAttempts + 1}/${opts.maxReconnectAttempts})`
    );

    reconnectTimeoutRef.current = window.setTimeout(() => {
      if (mountedRef.current) {
        setReconnectAttempts((prev) => prev + 1);
        // Trigger connect
        connectInternal();
      }
    }, delay);
  }, [reconnectAttempts]);

  /**
   * Internal connect function
   */
  const connectInternal = useCallback(() => {
    if (!jobId || !token) {
      setError('Missing job ID or authentication token');
      return;
    }

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    clearTimers();

    setConnectionState('connecting');
    setError(null);

    const url = getWebSocketUrl(jobId, token);
    const ws = new WebSocket(url);

    ws.onopen = () => {
      if (!mountedRef.current) {
        ws.close();
        return;
      }

      console.log(`WebSocket connected for job ${jobId}`);
      setConnectionState('connected');
      setReconnectAttempts(0);

      // Start ping interval
      pingIntervalRef.current = window.setInterval(
        sendPing,
        optionsRef.current.pingInterval
      );
    };

    ws.onmessage = handleMessage;

    ws.onerror = (event) => {
      console.error('WebSocket error:', event);
      setError('WebSocket connection error');
    };

    ws.onclose = (event) => {
      if (!mountedRef.current) return;

      console.log(`WebSocket closed for job ${jobId}, code: ${event.code}`);
      clearTimers();

      // Don't reconnect on intentional close or auth errors
      if (event.code === 1000 || event.code === 4001 || event.code === 4003) {
        setConnectionState('disconnected');
        return;
      }

      // Check if job is in terminal state (no need to reconnect)
      const currentProgress = progress;
      if (
        currentProgress?.status === 'completed' ||
        currentProgress?.status === 'failed' ||
        currentProgress?.status === 'cancelled'
      ) {
        setConnectionState('disconnected');
        return;
      }

      // Attempt reconnection
      if (optionsRef.current.autoReconnect) {
        attemptReconnect();
      } else {
        setConnectionState('disconnected');
      }
    };

    wsRef.current = ws;
  }, [jobId, token, clearTimers, sendPing, handleMessage, attemptReconnect, progress]);

  /**
   * Public connect function
   */
  const connect = useCallback(() => {
    setReconnectAttempts(0);
    connectInternal();
  }, [connectInternal]);

  /**
   * Disconnect from WebSocket
   */
  const disconnect = useCallback(() => {
    clearTimers();

    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnected');
      wsRef.current = null;
    }

    setConnectionState('disconnected');
    setReconnectAttempts(0);
  }, [clearTimers]);

  /**
   * Reconnect to WebSocket (reset attempts)
   */
  const reconnect = useCallback(() => {
    disconnect();
    // Small delay to ensure clean disconnect
    setTimeout(connect, 100);
  }, [disconnect, connect]);

  // Clean up on unmount
  useEffect(() => {
    mountedRef.current = true;

    return () => {
      mountedRef.current = false;
      clearTimers();

      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted');
        wsRef.current = null;
      }
    };
  }, [clearTimers]);

  return {
    connectionState,
    progress,
    isConnected: connectionState === 'connected',
    connect,
    disconnect,
    reconnect,
    error,
    reconnectAttempts,
  };
}

export type { UseWebSocketOptions, UseWebSocketResult };
