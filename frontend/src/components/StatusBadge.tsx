/**
 * StatusBadge Component
 * 
 * Unified status indicator for all job/map states across the application.
 * Provides consistent visual language for status display.
 * 
 * From UX Audit P0 Item #3:
 * ✅ Complete (green checkmark)
 * ⏳ Loading (spinner with ETA)
 * ⚠️ Warning (yellow triangle)
 * ❌ Error (red X)
 */

import { CheckCircle2, Clock, AlertTriangle, XCircle, Loader2 } from 'lucide-react';
import { Badge } from './ui/badge';
import { cn } from '../lib/utils';

export type StatusType = 
  | 'complete'
  | 'generating'
  | 'pending'
  | 'processing'
  | 'draft'
  | 'warning'
  | 'error'
  | 'failed';

export interface StatusBadgeProps {
  status: StatusType;
  /** Optional estimated time remaining in seconds */
  eta?: number;
  /** Optional custom message */
  message?: string;
  /** Size variant */
  size?: 'sm' | 'default' | 'lg';
  /** Show icon */
  showIcon?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get badge variant based on status
 */
function getVariant(status: StatusType): 'default' | 'secondary' | 'success' | 'warning' | 'destructive' {
  switch (status) {
    case 'complete':
      return 'success';
    case 'generating':
    case 'processing':
    case 'pending':
      return 'warning';
    case 'draft':
      return 'secondary';
    case 'error':
    case 'failed':
      return 'destructive';
    case 'warning':
      return 'warning';
    default:
      return 'default';
  }
}

/**
 * Get status icon component
 */
function getIcon(status: StatusType) {
  switch (status) {
    case 'complete':
      return CheckCircle2;
    case 'generating':
    case 'processing':
      return Loader2;
    case 'pending':
      return Clock;
    case 'warning':
      return AlertTriangle;
    case 'error':
    case 'failed':
      return XCircle;
    default:
      return Clock;
  }
}

/**
 * Get status display text
 */
function getStatusText(status: StatusType, eta?: number, message?: string): string {
  if (message) return message;

  switch (status) {
    case 'complete':
      return 'Complete';
    case 'generating':
      return eta ? `Generating (~${formatEta(eta)})` : 'Generating...';
    case 'processing':
      return eta ? `Processing (~${formatEta(eta)})` : 'Processing...';
    case 'pending':
      return 'Pending';
    case 'draft':
      return 'Draft';
    case 'warning':
      return 'Warning';
    case 'error':
      return 'Error';
    case 'failed':
      return 'Failed';
    default:
      return status;
  }
}

/**
 * Format ETA in human-readable form
 */
function formatEta(seconds: number): string {
  if (seconds < 60) {
    return `${Math.ceil(seconds)}s`;
  } else if (seconds < 3600) {
    const minutes = Math.ceil(seconds / 60);
    return `${minutes} min`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.ceil((seconds % 3600) / 60);
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
}

/**
 * StatusBadge Component
 */
export function StatusBadge({
  status,
  eta,
  message,
  size = 'default',
  showIcon = true,
  className,
}: StatusBadgeProps) {
  const Icon = getIcon(status);
  const text = getStatusText(status, eta, message);
  const variant = getVariant(status);

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    default: 'text-sm px-2.5 py-1',
    lg: 'text-base px-3 py-1.5',
  };

  const iconSizeClasses = {
    sm: 'h-3 w-3',
    default: 'h-4 w-4',
    lg: 'h-5 w-5',
  };

  const isAnimated = status === 'generating' || status === 'processing';

  return (
    <Badge
      variant={variant}
      className={cn(
        'font-medium inline-flex items-center gap-1.5',
        sizeClasses[size],
        className
      )}
    >
      {showIcon && (
        <Icon
          className={cn(
            iconSizeClasses[size],
            isAnimated && 'animate-spin'
          )}
        />
      )}
      <span>{text}</span>
    </Badge>
  );
}

/**
 * Convenience exports for common status types
 */
export const CompleteStatus = (props: Omit<StatusBadgeProps, 'status'>) => (
  <StatusBadge status="complete" {...props} />
);

export const GeneratingStatus = (props: Omit<StatusBadgeProps, 'status'>) => (
  <StatusBadge status="generating" {...props} />
);

export const PendingStatus = (props: Omit<StatusBadgeProps, 'status'>) => (
  <StatusBadge status="pending" {...props} />
);

export const ErrorStatus = (props: Omit<StatusBadgeProps, 'status'>) => (
  <StatusBadge status="error" {...props} />
);

export const WarningStatus = (props: Omit<StatusBadgeProps, 'status'>) => (
  <StatusBadge status="warning" {...props} />
);
