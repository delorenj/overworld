/**
 * ProgressBar Component
 *
 * A customizable progress bar component with percentage display.
 * Supports different variants, sizes, and animated transitions.
 */

import { useMemo } from 'react';
import './ProgressBar.css';

/**
 * Progress bar variants for different visual styles
 */
export type ProgressBarVariant = 'default' | 'success' | 'warning' | 'error' | 'info';

/**
 * Progress bar sizes
 */
export type ProgressBarSize = 'sm' | 'md' | 'lg';

/**
 * Props for ProgressBar component
 */
export interface ProgressBarProps {
  /** Progress percentage (0-100) */
  progress: number;
  /** Visual variant */
  variant?: ProgressBarVariant;
  /** Size variant */
  size?: ProgressBarSize;
  /** Show percentage label */
  showLabel?: boolean;
  /** Label position */
  labelPosition?: 'inside' | 'outside' | 'right';
  /** Custom label text (overrides percentage) */
  label?: string;
  /** Whether to animate progress changes */
  animated?: boolean;
  /** Show striped pattern */
  striped?: boolean;
  /** Animate stripes */
  stripedAnimated?: boolean;
  /** Additional CSS class */
  className?: string;
  /** Accessible label */
  ariaLabel?: string;
}

/**
 * Get CSS class for variant
 */
function getVariantClass(variant: ProgressBarVariant): string {
  const variantClasses: Record<ProgressBarVariant, string> = {
    default: 'progress-bar--default',
    success: 'progress-bar--success',
    warning: 'progress-bar--warning',
    error: 'progress-bar--error',
    info: 'progress-bar--info',
  };
  return variantClasses[variant];
}

/**
 * Get CSS class for size
 */
function getSizeClass(size: ProgressBarSize): string {
  const sizeClasses: Record<ProgressBarSize, string> = {
    sm: 'progress-bar--sm',
    md: 'progress-bar--md',
    lg: 'progress-bar--lg',
  };
  return sizeClasses[size];
}

/**
 * ProgressBar component for displaying progress percentage
 *
 * @example
 * <ProgressBar progress={75} variant="success" showLabel />
 */
export function ProgressBar({
  progress,
  variant = 'default',
  size = 'md',
  showLabel = true,
  labelPosition = 'right',
  label,
  animated = true,
  striped = false,
  stripedAnimated = false,
  className = '',
  ariaLabel,
}: ProgressBarProps) {
  // Clamp progress to valid range
  const clampedProgress = useMemo(
    () => Math.min(100, Math.max(0, progress)),
    [progress]
  );

  // Generate display label
  const displayLabel = useMemo(() => {
    if (label) return label;
    return `${Math.round(clampedProgress)}%`;
  }, [label, clampedProgress]);

  // Build class names
  const containerClasses = useMemo(() => {
    const classes = ['progress-bar-container', getSizeClass(size)];
    if (className) classes.push(className);
    return classes.join(' ');
  }, [size, className]);

  const trackClasses = useMemo(() => {
    return 'progress-bar-track';
  }, []);

  const fillClasses = useMemo(() => {
    const classes = ['progress-bar-fill', getVariantClass(variant)];
    if (animated) classes.push('progress-bar-fill--animated');
    if (striped) classes.push('progress-bar-fill--striped');
    if (stripedAnimated) classes.push('progress-bar-fill--striped-animated');
    return classes.join(' ');
  }, [variant, animated, striped, stripedAnimated]);

  // Determine if label should be shown inside the bar
  const showInsideLabel = showLabel && labelPosition === 'inside' && clampedProgress > 10;

  return (
    <div className={containerClasses}>
      {showLabel && labelPosition === 'outside' && (
        <span className="progress-bar-label progress-bar-label--outside">
          {displayLabel}
        </span>
      )}

      <div
        className={trackClasses}
        role="progressbar"
        aria-valuenow={clampedProgress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={ariaLabel || `Progress: ${displayLabel}`}
      >
        <div
          className={fillClasses}
          style={{ width: `${clampedProgress}%` }}
        >
          {showInsideLabel && (
            <span className="progress-bar-label progress-bar-label--inside">
              {displayLabel}
            </span>
          )}
        </div>
      </div>

      {showLabel && labelPosition === 'right' && (
        <span className="progress-bar-label progress-bar-label--right">
          {displayLabel}
        </span>
      )}
    </div>
  );
}

export default ProgressBar;
