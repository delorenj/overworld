/**
 * useMapControls Hook
 *
 * Manages pan, zoom, and navigation controls for the map renderer.
 * Handles mouse drag, scroll wheel zoom, and touch gestures.
 */

import { useEffect, useRef, useCallback, useMemo } from 'react';
import type { ViewportState, ViewportConstraints, Point } from '../types/map';
import { DEFAULT_VIEWPORT_CONSTRAINTS } from '../types/map';

/**
 * Configuration options for map controls
 */
export interface MapControlsConfig {
  /** Viewport constraints (min/max zoom) */
  constraints?: ViewportConstraints;
  /** Zoom sensitivity for scroll wheel (default: 0.001) */
  zoomSensitivity?: number;
  /** Enable panning with mouse drag */
  enablePan?: boolean;
  /** Enable zooming with scroll wheel */
  enableZoom?: boolean;
  /** Enable touch gestures */
  enableTouch?: boolean;
  /** Zoom button increment */
  zoomButtonStep?: number;
}

/**
 * Return type for useMapControls hook
 */
export interface UseMapControlsResult {
  /** Bind controls to a DOM element */
  bindControls: (element: HTMLElement | null) => void;
  /** Zoom in by step amount */
  zoomIn: () => void;
  /** Zoom out by step amount */
  zoomOut: () => void;
  /** Reset to initial viewport */
  resetView: () => void;
  /** Center view on a specific point */
  centerOn: (point: Point) => void;
  /** Fit map to container */
  fitToContainer: (mapWidth: number, mapHeight: number) => void;
  /** Current drag state */
  isDragging: boolean;
}

/**
 * Default controls configuration
 */
const DEFAULT_CONTROLS_CONFIG: Required<MapControlsConfig> = {
  constraints: DEFAULT_VIEWPORT_CONSTRAINTS,
  zoomSensitivity: 0.001,
  enablePan: true,
  enableZoom: true,
  enableTouch: true,
  zoomButtonStep: 0.25,
};

/**
 * Hook for managing map pan/zoom controls
 *
 * @param viewport - Current viewport state
 * @param setViewport - Function to update viewport
 * @param dimensions - Current canvas dimensions
 * @param config - Controls configuration
 * @returns Control functions and state
 */
export function useMapControls(
  viewport: ViewportState,
  setViewport: (viewport: Partial<ViewportState>) => void,
  dimensions: { width: number; height: number },
  config: MapControlsConfig = {}
): UseMapControlsResult {
  // Memoize merged config to prevent dependency issues
  // We explicitly list the config properties rather than the whole object to avoid
  // unnecessary re-renders when the parent creates a new config object reference.
  const mergedConfig = useMemo(
    () => ({
      constraints: config.constraints ?? DEFAULT_CONTROLS_CONFIG.constraints,
      zoomSensitivity: config.zoomSensitivity ?? DEFAULT_CONTROLS_CONFIG.zoomSensitivity,
      enablePan: config.enablePan ?? DEFAULT_CONTROLS_CONFIG.enablePan,
      enableZoom: config.enableZoom ?? DEFAULT_CONTROLS_CONFIG.enableZoom,
      enableTouch: config.enableTouch ?? DEFAULT_CONTROLS_CONFIG.enableTouch,
      zoomButtonStep: config.zoomButtonStep ?? DEFAULT_CONTROLS_CONFIG.zoomButtonStep,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      config.constraints?.minScale,
      config.constraints?.maxScale,
      config.zoomSensitivity,
      config.enablePan,
      config.enableZoom,
      config.enableTouch,
      config.zoomButtonStep,
    ]
  );

  // Refs for tracking drag state
  const isDraggingRef = useRef(false);
  const lastPositionRef = useRef<Point>({ x: 0, y: 0 });
  const initialViewportRef = useRef<ViewportState>({ x: 0, y: 0, scale: 1 });

  // Touch gesture refs
  const lastTouchDistanceRef = useRef<number>(0);
  const lastTouchCenterRef = useRef<Point>({ x: 0, y: 0 });

  // Store initial viewport for reset (intentionally only on mount)
  useEffect(() => {
    initialViewportRef.current = { ...viewport };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Handle mouse wheel zoom
   */
  const handleWheel = useCallback(
    (e: WheelEvent) => {
      if (!mergedConfig.enableZoom) return;

      e.preventDefault();

      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      // Calculate zoom factor
      const delta = -e.deltaY * mergedConfig.zoomSensitivity;
      const newScale = Math.max(
        mergedConfig.constraints.minScale,
        Math.min(
          mergedConfig.constraints.maxScale,
          viewport.scale * (1 + delta)
        )
      );

      // Zoom towards mouse position
      const scaleFactor = newScale / viewport.scale;
      const newX = mouseX - (mouseX - viewport.x) * scaleFactor;
      const newY = mouseY - (mouseY - viewport.y) * scaleFactor;

      setViewport({
        x: newX,
        y: newY,
        scale: newScale,
      });
    },
    [viewport, setViewport, mergedConfig]
  );

  /**
   * Handle mouse down for drag start
   */
  const handleMouseDown = useCallback(
    (e: MouseEvent) => {
      if (!mergedConfig.enablePan) return;
      if (e.button !== 0) return; // Only left mouse button

      isDraggingRef.current = true;
      lastPositionRef.current = { x: e.clientX, y: e.clientY };

      // Change cursor
      (e.currentTarget as HTMLElement).style.cursor = 'grabbing';
    },
    [mergedConfig.enablePan]
  );

  /**
   * Handle mouse move for dragging
   */
  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDraggingRef.current) return;

      const deltaX = e.clientX - lastPositionRef.current.x;
      const deltaY = e.clientY - lastPositionRef.current.y;

      lastPositionRef.current = { x: e.clientX, y: e.clientY };

      setViewport({
        x: viewport.x + deltaX,
        y: viewport.y + deltaY,
      });
    },
    [viewport, setViewport]
  );

  /**
   * Handle mouse up for drag end
   */
  const handleMouseUp = useCallback((e: MouseEvent) => {
    if (isDraggingRef.current) {
      isDraggingRef.current = false;
      (e.currentTarget as HTMLElement).style.cursor = 'grab';
    }
  }, []);

  /**
   * Handle mouse leave
   */
  const handleMouseLeave = useCallback((e: MouseEvent) => {
    if (isDraggingRef.current) {
      isDraggingRef.current = false;
      (e.currentTarget as HTMLElement).style.cursor = 'grab';
    }
  }, []);

  /**
   * Get distance between two touch points
   */
  const getTouchDistance = (touches: TouchList): number => {
    if (touches.length < 2) return 0;
    const dx = touches[0].clientX - touches[1].clientX;
    const dy = touches[0].clientY - touches[1].clientY;
    return Math.sqrt(dx * dx + dy * dy);
  };

  /**
   * Get center point between two touches
   */
  const getTouchCenter = (touches: TouchList, rect: DOMRect): Point => {
    if (touches.length < 2) {
      return {
        x: touches[0].clientX - rect.left,
        y: touches[0].clientY - rect.top,
      };
    }
    return {
      x: (touches[0].clientX + touches[1].clientX) / 2 - rect.left,
      y: (touches[0].clientY + touches[1].clientY) / 2 - rect.top,
    };
  };

  /**
   * Handle touch start
   */
  const handleTouchStart = useCallback(
    (e: TouchEvent) => {
      if (!mergedConfig.enableTouch) return;

      if (e.touches.length === 1 && mergedConfig.enablePan) {
        // Single touch - start pan
        isDraggingRef.current = true;
        lastPositionRef.current = {
          x: e.touches[0].clientX,
          y: e.touches[0].clientY,
        };
      } else if (e.touches.length === 2 && mergedConfig.enableZoom) {
        // Two finger touch - start pinch zoom
        e.preventDefault();
        lastTouchDistanceRef.current = getTouchDistance(e.touches);
        const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
        lastTouchCenterRef.current = getTouchCenter(e.touches, rect);
      }
    },
    [mergedConfig]
  );

  /**
   * Handle touch move
   */
  const handleTouchMove = useCallback(
    (e: TouchEvent) => {
      if (!mergedConfig.enableTouch) return;

      if (e.touches.length === 1 && isDraggingRef.current) {
        // Single touch - pan
        const deltaX = e.touches[0].clientX - lastPositionRef.current.x;
        const deltaY = e.touches[0].clientY - lastPositionRef.current.y;

        lastPositionRef.current = {
          x: e.touches[0].clientX,
          y: e.touches[0].clientY,
        };

        setViewport({
          x: viewport.x + deltaX,
          y: viewport.y + deltaY,
        });
      } else if (e.touches.length === 2 && mergedConfig.enableZoom) {
        // Two finger touch - pinch zoom
        e.preventDefault();

        const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
        const currentDistance = getTouchDistance(e.touches);
        const currentCenter = getTouchCenter(e.touches, rect);

        if (lastTouchDistanceRef.current > 0) {
          const scaleFactor = currentDistance / lastTouchDistanceRef.current;
          const newScale = Math.max(
            mergedConfig.constraints.minScale,
            Math.min(mergedConfig.constraints.maxScale, viewport.scale * scaleFactor)
          );

          // Zoom towards pinch center
          const actualScaleFactor = newScale / viewport.scale;
          const newX =
            currentCenter.x - (currentCenter.x - viewport.x) * actualScaleFactor;
          const newY =
            currentCenter.y - (currentCenter.y - viewport.y) * actualScaleFactor;

          setViewport({
            x: newX,
            y: newY,
            scale: newScale,
          });
        }

        lastTouchDistanceRef.current = currentDistance;
        lastTouchCenterRef.current = currentCenter;
      }
    },
    [viewport, setViewport, mergedConfig]
  );

  /**
   * Handle touch end
   */
  const handleTouchEnd = useCallback((e: TouchEvent) => {
    if (e.touches.length === 0) {
      isDraggingRef.current = false;
      lastTouchDistanceRef.current = 0;
    } else if (e.touches.length === 1) {
      // Switched from pinch to pan
      lastPositionRef.current = {
        x: e.touches[0].clientX,
        y: e.touches[0].clientY,
      };
      isDraggingRef.current = true;
      lastTouchDistanceRef.current = 0;
    }
  }, []);

  /**
   * Bind event listeners to element
   */
  const bindControls = useCallback(
    (element: HTMLElement | null) => {
      if (!element) return;

      // Set initial cursor
      element.style.cursor = 'grab';

      // Add event listeners
      element.addEventListener('wheel', handleWheel, { passive: false });
      element.addEventListener('mousedown', handleMouseDown);
      element.addEventListener('mousemove', handleMouseMove);
      element.addEventListener('mouseup', handleMouseUp);
      element.addEventListener('mouseleave', handleMouseLeave);
      element.addEventListener('touchstart', handleTouchStart, { passive: false });
      element.addEventListener('touchmove', handleTouchMove, { passive: false });
      element.addEventListener('touchend', handleTouchEnd);

      // Return cleanup function
      return () => {
        element.removeEventListener('wheel', handleWheel);
        element.removeEventListener('mousedown', handleMouseDown);
        element.removeEventListener('mousemove', handleMouseMove);
        element.removeEventListener('mouseup', handleMouseUp);
        element.removeEventListener('mouseleave', handleMouseLeave);
        element.removeEventListener('touchstart', handleTouchStart);
        element.removeEventListener('touchmove', handleTouchMove);
        element.removeEventListener('touchend', handleTouchEnd);
      };
    },
    [
      handleWheel,
      handleMouseDown,
      handleMouseMove,
      handleMouseUp,
      handleMouseLeave,
      handleTouchStart,
      handleTouchMove,
      handleTouchEnd,
    ]
  );

  /**
   * Zoom in by step amount
   */
  const zoomIn = useCallback(() => {
    const newScale = Math.min(
      mergedConfig.constraints.maxScale,
      viewport.scale + mergedConfig.zoomButtonStep
    );

    // Zoom towards center
    const centerX = dimensions.width / 2;
    const centerY = dimensions.height / 2;
    const scaleFactor = newScale / viewport.scale;
    const newX = centerX - (centerX - viewport.x) * scaleFactor;
    const newY = centerY - (centerY - viewport.y) * scaleFactor;

    setViewport({ x: newX, y: newY, scale: newScale });
  }, [viewport, setViewport, dimensions, mergedConfig]);

  /**
   * Zoom out by step amount
   */
  const zoomOut = useCallback(() => {
    const newScale = Math.max(
      mergedConfig.constraints.minScale,
      viewport.scale - mergedConfig.zoomButtonStep
    );

    // Zoom towards center
    const centerX = dimensions.width / 2;
    const centerY = dimensions.height / 2;
    const scaleFactor = newScale / viewport.scale;
    const newX = centerX - (centerX - viewport.x) * scaleFactor;
    const newY = centerY - (centerY - viewport.y) * scaleFactor;

    setViewport({ x: newX, y: newY, scale: newScale });
  }, [viewport, setViewport, dimensions, mergedConfig]);

  /**
   * Reset to initial viewport
   */
  const resetView = useCallback(() => {
    setViewport(initialViewportRef.current);
  }, [setViewport]);

  /**
   * Center view on a specific point
   */
  const centerOn = useCallback(
    (point: Point) => {
      setViewport({
        x: dimensions.width / 2 - point.x * viewport.scale,
        y: dimensions.height / 2 - point.y * viewport.scale,
      });
    },
    [viewport.scale, dimensions, setViewport]
  );

  /**
   * Fit map to container with padding
   */
  const fitToContainer = useCallback(
    (mapWidth: number, mapHeight: number) => {
      const padding = 40;
      const availableWidth = dimensions.width - padding * 2;
      const availableHeight = dimensions.height - padding * 2;

      const scaleX = availableWidth / mapWidth;
      const scaleY = availableHeight / mapHeight;
      const newScale = Math.max(
        mergedConfig.constraints.minScale,
        Math.min(mergedConfig.constraints.maxScale, Math.min(scaleX, scaleY))
      );

      // Center the map
      const newX = (dimensions.width - mapWidth * newScale) / 2;
      const newY = (dimensions.height - mapHeight * newScale) / 2;

      setViewport({ x: newX, y: newY, scale: newScale });
    },
    [dimensions, setViewport, mergedConfig.constraints]
  );

  return {
    bindControls,
    zoomIn,
    zoomOut,
    resetView,
    centerOn,
    fitToContainer,
    isDragging: isDraggingRef.current,
  };
}
