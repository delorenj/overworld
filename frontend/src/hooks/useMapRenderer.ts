/**
 * useMapRenderer Hook
 *
 * Manages the PixiJS Application lifecycle for the map renderer.
 * Handles initialization, resize, and cleanup of the PixiJS canvas.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import * as PIXI from 'pixi.js';
import type { MapRendererConfig, ViewportState } from '../types/map';
import { DEFAULT_RENDERER_CONFIG } from '../types/map';

/**
 * Return type for useMapRenderer hook
 */
export interface UseMapRendererResult {
  /** Reference to attach to container element */
  containerRef: React.RefObject<HTMLDivElement>;
  /** PixiJS Application instance */
  app: PIXI.Application | null;
  /** Main stage container for map content */
  stage: PIXI.Container | null;
  /** Whether the renderer is ready */
  isReady: boolean;
  /** Current canvas dimensions */
  dimensions: { width: number; height: number };
  /** Force a resize of the canvas */
  resize: () => void;
  /** Current viewport state */
  viewport: ViewportState;
  /** Update viewport (pan/zoom) */
  setViewport: (viewport: Partial<ViewportState>) => void;
}

/**
 * Hook for managing PixiJS Application lifecycle
 *
 * @param config - Renderer configuration options
 * @returns Renderer state and controls
 */
export function useMapRenderer(
  config: MapRendererConfig = {}
): UseMapRendererResult {
  const mergedConfig = { ...DEFAULT_RENDERER_CONFIG, ...config };

  const containerRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<PIXI.Application | null>(null);
  const stageRef = useRef<PIXI.Container | null>(null);

  const [isReady, setIsReady] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [viewport, setViewportState] = useState<ViewportState>({
    x: mergedConfig.initialViewport?.x ?? 0,
    y: mergedConfig.initialViewport?.y ?? 0,
    scale: mergedConfig.initialViewport?.scale ?? 1,
  });

  /**
   * Initialize PixiJS Application
   */
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Get container dimensions
    const rect = container.getBoundingClientRect();
    const width = rect.width || 800;
    const height = rect.height || 600;

    // Create PixiJS Application
    const app = new PIXI.Application({
      width,
      height,
      backgroundColor: mergedConfig.backgroundColor,
      antialias: mergedConfig.antialias,
      resolution: mergedConfig.resolution,
      autoDensity: true,
      resizeTo: container,
    });

    // Add canvas to container
    container.appendChild(app.view as HTMLCanvasElement);

    // Create main stage container for map content
    const stage = new PIXI.Container();
    stage.sortableChildren = true;
    app.stage.addChild(stage);

    // Store references
    appRef.current = app;
    stageRef.current = stage;

    // Set initial dimensions
    setDimensions({ width, height });
    setIsReady(true);

    // Cleanup on unmount
    return () => {
      setIsReady(false);

      // Destroy PixiJS application
      if (appRef.current) {
        appRef.current.destroy(true, {
          children: true,
          texture: true,
          baseTexture: true,
        });
        appRef.current = null;
        stageRef.current = null;
      }

      // Remove canvas from container
      while (container.firstChild) {
        container.removeChild(container.firstChild);
      }
    };
  }, [
    mergedConfig.backgroundColor,
    mergedConfig.antialias,
    mergedConfig.resolution,
  ]);

  /**
   * Handle window resize
   */
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !appRef.current) return;

    const handleResize = () => {
      const rect = container.getBoundingClientRect();
      const width = rect.width || 800;
      const height = rect.height || 600;

      if (appRef.current) {
        appRef.current.renderer.resize(width, height);
        setDimensions({ width, height });
      }
    };

    // Create ResizeObserver for container size changes
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    // Also listen to window resize as fallback
    window.addEventListener('resize', handleResize);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', handleResize);
    };
  }, [isReady]);

  /**
   * Apply viewport transformations to stage
   */
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;

    stage.position.set(viewport.x, viewport.y);
    stage.scale.set(viewport.scale);
  }, [viewport]);

  /**
   * Manual resize trigger
   */
  const resize = useCallback(() => {
    const container = containerRef.current;
    if (!container || !appRef.current) return;

    const rect = container.getBoundingClientRect();
    const width = rect.width || 800;
    const height = rect.height || 600;

    appRef.current.renderer.resize(width, height);
    setDimensions({ width, height });
  }, []);

  /**
   * Update viewport with partial state
   */
  const setViewport = useCallback(
    (newViewport: Partial<ViewportState>) => {
      setViewportState((prev) => {
        const updated = { ...prev, ...newViewport };

        // Apply constraints
        const constraints = mergedConfig.constraints;
        if (constraints) {
          updated.scale = Math.max(
            constraints.minScale,
            Math.min(constraints.maxScale, updated.scale)
          );

          // Apply bounds constraints if defined
          if (constraints.bounds) {
            const { bounds } = constraints;
            updated.x = Math.max(
              -bounds.width * updated.scale + dimensions.width,
              Math.min(0, updated.x)
            );
            updated.y = Math.max(
              -bounds.height * updated.scale + dimensions.height,
              Math.min(0, updated.y)
            );
          }
        }

        return updated;
      });
    },
    [mergedConfig.constraints, dimensions]
  );

  return {
    containerRef,
    app: appRef.current,
    stage: stageRef.current,
    isReady,
    dimensions,
    resize,
    viewport,
    setViewport,
  };
}
