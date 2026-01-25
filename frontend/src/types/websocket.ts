/**
 * WebSocket Event Types and Interfaces
 *
 * TypeScript types for WebSocket communication with the backend.
 * These types mirror the backend Pydantic schemas.
 */

/**
 * Job status enum matching backend JobStatus
 */
export type JobStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled';

/**
 * WebSocket event types
 */
export type WebSocketEventType =
  | 'connection_established'
  | 'connection_error'
  | 'job_started'
  | 'progress_update'
  | 'job_completed'
  | 'job_failed'
  | 'job_cancelled'
  | 'ping'
  | 'pong';

/**
 * Base event interface
 */
export interface BaseWebSocketEvent {
  type: WebSocketEventType;
  timestamp: string;
}

/**
 * Connection established event
 */
export interface ConnectionEstablishedEvent extends BaseWebSocketEvent {
  type: 'connection_established';
  job_id: number;
  current_status: JobStatus;
  current_progress: number;
  message: string;
}

/**
 * Connection error event
 */
export interface ConnectionErrorEvent extends BaseWebSocketEvent {
  type: 'connection_error';
  error_code: string;
  message: string;
}

/**
 * Job started event
 */
export interface JobStartedEvent extends BaseWebSocketEvent {
  type: 'job_started';
  job_id: number;
  started_at: string;
  agent_name?: string;
}

/**
 * Progress update event
 */
export interface ProgressUpdateEvent extends BaseWebSocketEvent {
  type: 'progress_update';
  job_id: number;
  progress_pct: number;
  progress_message?: string;
  agent_name?: string;
  stage?: string;
}

/**
 * Job completed event
 */
export interface JobCompletedEvent extends BaseWebSocketEvent {
  type: 'job_completed';
  job_id: number;
  map_id?: number;
  completed_at: string;
  total_duration_seconds?: number;
}

/**
 * Job failed event
 */
export interface JobFailedEvent extends BaseWebSocketEvent {
  type: 'job_failed';
  job_id: number;
  error_message: string;
  error_code?: string;
  can_retry: boolean;
  retry_count: number;
  max_retries: number;
  failed_at: string;
}

/**
 * Job cancelled event
 */
export interface JobCancelledEvent extends BaseWebSocketEvent {
  type: 'job_cancelled';
  job_id: number;
  cancelled_at: string;
}

/**
 * Ping event (sent by client)
 */
export interface PingEvent extends BaseWebSocketEvent {
  type: 'ping';
}

/**
 * Pong event (received from server)
 */
export interface PongEvent extends BaseWebSocketEvent {
  type: 'pong';
}

/**
 * Union type for all WebSocket events
 */
export type WebSocketEvent =
  | ConnectionEstablishedEvent
  | ConnectionErrorEvent
  | JobStartedEvent
  | ProgressUpdateEvent
  | JobCompletedEvent
  | JobFailedEvent
  | JobCancelledEvent
  | PingEvent
  | PongEvent;

/**
 * WebSocket message wrapper
 */
export interface WebSocketMessage {
  event: WebSocketEvent;
  correlation_id?: string;
}

/**
 * WebSocket connection state
 */
export type WebSocketConnectionState =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'reconnecting'
  | 'error';

/**
 * Job progress state tracked by the hook
 */
export interface JobProgressState {
  jobId: number;
  status: JobStatus;
  progressPct: number;
  progressMessage?: string;
  agentName?: string;
  stage?: string;
  startedAt?: string;
  completedAt?: string;
  errorMessage?: string;
  errorCode?: string;
  canRetry: boolean;
  mapId?: number;
}

/**
 * Options for useWebSocket hook
 */
export interface UseWebSocketOptions {
  /** Auto-reconnect on disconnect (default: true) */
  autoReconnect?: boolean;
  /** Maximum reconnection attempts (default: 5) */
  maxReconnectAttempts?: number;
  /** Base delay for exponential backoff in ms (default: 1000) */
  reconnectBaseDelay?: number;
  /** Maximum delay between reconnection attempts in ms (default: 30000) */
  reconnectMaxDelay?: number;
  /** Ping interval in ms for keep-alive (default: 30000) */
  pingInterval?: number;
  /** Callback when connection established */
  onConnected?: (event: ConnectionEstablishedEvent) => void;
  /** Callback when job starts */
  onJobStarted?: (event: JobStartedEvent) => void;
  /** Callback when progress updates */
  onProgress?: (event: ProgressUpdateEvent) => void;
  /** Callback when job completes */
  onCompleted?: (event: JobCompletedEvent) => void;
  /** Callback when job fails */
  onFailed?: (event: JobFailedEvent) => void;
  /** Callback when connection error occurs */
  onError?: (event: ConnectionErrorEvent) => void;
}

/**
 * Return type for useWebSocket hook
 */
export interface UseWebSocketResult {
  /** Current connection state */
  connectionState: WebSocketConnectionState;
  /** Current job progress state */
  progress: JobProgressState | null;
  /** Whether currently connected */
  isConnected: boolean;
  /** Connect to job progress stream */
  connect: () => void;
  /** Disconnect from job progress stream */
  disconnect: () => void;
  /** Reconnect to job progress stream */
  reconnect: () => void;
  /** Last error message */
  error: string | null;
  /** Number of reconnection attempts */
  reconnectAttempts: number;
}
