/**
 * JobProgressModal Component
 *
 * A modal component that displays real-time job progress using WebSocket
 * connection. Shows progress bar, current stage, and status messages.
 */

import { useEffect, useCallback } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { ProgressBar } from './ProgressBar';
import type { JobStatus } from '../types/websocket';
import './JobProgressModal.css';

/**
 * Agent display names for human-readable output
 */
const AGENT_DISPLAY_NAMES: Record<string, string> = {
  parser: 'Document Parser',
  artist: 'Layout Artist',
  road: 'Road Network',
  icon: 'Icon Placement',
};

/**
 * Get progress bar variant based on job status
 */
function getProgressVariant(status: JobStatus): 'default' | 'success' | 'warning' | 'error' | 'info' {
  switch (status) {
    case 'completed':
      return 'success';
    case 'failed':
      return 'error';
    case 'cancelled':
      return 'warning';
    case 'processing':
      return 'info';
    default:
      return 'default';
  }
}

/**
 * Get status display text
 */
function getStatusText(status: JobStatus): string {
  switch (status) {
    case 'pending':
      return 'Waiting in queue...';
    case 'processing':
      return 'Processing';
    case 'completed':
      return 'Completed';
    case 'failed':
      return 'Failed';
    case 'cancelled':
      return 'Cancelled';
    default:
      return 'Unknown';
  }
}

/**
 * Props for JobProgressModal component
 */
export interface JobProgressModalProps {
  /** ID of the job to monitor */
  jobId: number | null;
  /** JWT authentication token */
  token: string | null;
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** Callback when job completes successfully */
  onComplete?: (mapId?: number) => void;
  /** Callback when job fails */
  onFailed?: (error: string, canRetry: boolean) => void;
  /** Title for the modal */
  title?: string;
}

/**
 * JobProgressModal component for displaying real-time job progress
 *
 * @example
 * <JobProgressModal
 *   jobId={123}
 *   token="jwt-token"
 *   isOpen={isModalOpen}
 *   onClose={() => setModalOpen(false)}
 *   onComplete={(mapId) => navigate(`/maps/${mapId}`)}
 * />
 */
export function JobProgressModal({
  jobId,
  token,
  isOpen,
  onClose,
  onComplete,
  onFailed,
  title = 'Generating Map',
}: JobProgressModalProps) {
  // Connect to WebSocket for progress updates
  const {
    progress,
    connectionState,
    isConnected,
    connect,
    disconnect,
    error: connectionError,
    reconnectAttempts,
  } = useWebSocket(jobId, token, {
    autoReconnect: true,
    maxReconnectAttempts: 5,
    onCompleted: (event) => {
      if (onComplete) {
        onComplete(event.map_id);
      }
    },
    onFailed: (event) => {
      if (onFailed) {
        onFailed(event.error_message, event.can_retry);
      }
    },
  });

  // Connect when modal opens
  useEffect(() => {
    if (isOpen && jobId && token) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [isOpen, jobId, token, connect, disconnect]);

  // Handle close with disconnect
  const handleClose = useCallback(() => {
    disconnect();
    onClose();
  }, [disconnect, onClose]);

  // Handle backdrop click
  const handleBackdropClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) {
        // Only close on backdrop click if job is complete or failed
        if (
          progress?.status === 'completed' ||
          progress?.status === 'failed' ||
          progress?.status === 'cancelled'
        ) {
          handleClose();
        }
      }
    },
    [progress?.status, handleClose]
  );

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (
          progress?.status === 'completed' ||
          progress?.status === 'failed' ||
          progress?.status === 'cancelled'
        ) {
          handleClose();
        }
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, progress?.status, handleClose]);

  if (!isOpen) return null;

  const isTerminal =
    progress?.status === 'completed' ||
    progress?.status === 'failed' ||
    progress?.status === 'cancelled';

  const currentAgent = progress?.agentName
    ? AGENT_DISPLAY_NAMES[progress.agentName] || progress.agentName
    : null;

  return (
    <div className="job-progress-modal-backdrop" onClick={handleBackdropClick}>
      <div
        className="job-progress-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="job-progress-title"
      >
        {/* Header */}
        <div className="job-progress-modal-header">
          <h2 id="job-progress-title" className="job-progress-modal-title">
            {title}
          </h2>
          {isTerminal && (
            <button
              className="job-progress-modal-close"
              onClick={handleClose}
              aria-label="Close"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 20 20"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M15 5L5 15M5 5l10 10" />
              </svg>
            </button>
          )}
        </div>

        {/* Content */}
        <div className="job-progress-modal-content">
          {/* Connection status */}
          {connectionState === 'connecting' && (
            <div className="job-progress-status job-progress-status--connecting">
              <span className="job-progress-spinner" />
              Connecting...
            </div>
          )}

          {connectionState === 'reconnecting' && (
            <div className="job-progress-status job-progress-status--reconnecting">
              <span className="job-progress-spinner" />
              Reconnecting (attempt {reconnectAttempts})...
            </div>
          )}

          {connectionState === 'error' && (
            <div className="job-progress-status job-progress-status--error">
              <svg
                className="job-progress-icon"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              {connectionError || 'Connection failed'}
            </div>
          )}

          {/* Job progress */}
          {isConnected && progress && (
            <>
              {/* Status badge */}
              <div className={`job-progress-badge job-progress-badge--${progress.status}`}>
                {getStatusText(progress.status)}
              </div>

              {/* Progress bar */}
              <div className="job-progress-bar-wrapper">
                <ProgressBar
                  progress={progress.progressPct}
                  variant={getProgressVariant(progress.status)}
                  size="lg"
                  showLabel
                  animated={progress.status === 'processing'}
                  striped={progress.status === 'processing'}
                  stripedAnimated={progress.status === 'processing'}
                />
              </div>

              {/* Current stage */}
              {currentAgent && progress.status === 'processing' && (
                <div className="job-progress-stage">
                  <span className="job-progress-spinner job-progress-spinner--sm" />
                  {currentAgent}
                </div>
              )}

              {/* Progress message */}
              {progress.progressMessage && (
                <p className="job-progress-message">{progress.progressMessage}</p>
              )}

              {/* Error message */}
              {progress.status === 'failed' && progress.errorMessage && (
                <div className="job-progress-error">
                  <svg
                    className="job-progress-icon"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <div>
                    <p className="job-progress-error-title">Generation Failed</p>
                    <p className="job-progress-error-message">
                      {progress.errorMessage}
                    </p>
                    {progress.canRetry && (
                      <p className="job-progress-error-retry">
                        This error may be temporary. You can try again.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* Success message */}
              {progress.status === 'completed' && (
                <div className="job-progress-success">
                  <svg
                    className="job-progress-icon"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <div>
                    <p className="job-progress-success-title">Map Generated!</p>
                    <p className="job-progress-success-message">
                      Your map has been created successfully.
                    </p>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {isTerminal && (
          <div className="job-progress-modal-footer">
            {progress?.status === 'completed' && progress.mapId && (
              <button
                className="job-progress-btn job-progress-btn--primary"
                onClick={() => {
                  if (onComplete) {
                    onComplete(progress.mapId);
                  }
                  handleClose();
                }}
              >
                View Map
              </button>
            )}
            {progress?.status === 'failed' && progress.canRetry && (
              <button
                className="job-progress-btn job-progress-btn--secondary"
                onClick={() => {
                  // Retry logic would be handled by parent component
                  handleClose();
                }}
              >
                Try Again
              </button>
            )}
            <button
              className="job-progress-btn job-progress-btn--ghost"
              onClick={handleClose}
            >
              {progress?.status === 'completed' ? 'Close' : 'Dismiss'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default JobProgressModal;
