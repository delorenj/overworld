/**
 * MapRenderer Component
 *
 * Main React component for rendering interactive maps using PixiJS.
 * Manages layers, viewport controls, and user interactions.
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { useMapRenderer } from '../../hooks/useMapRenderer';
import { useMapControls } from '../../hooks/useMapControls';
import { BackgroundLayer } from './layers/BackgroundLayer';
import { RoadsLayer } from './layers/RoadsLayer';
import { IconsLayer, LabelsLayer } from './layers/IconsLayer';
import type {
  MapData,
  MapRendererConfig,
  MapInteractionEvent,
  MapIcon,
  Road,
  LayerVisibility,
  Point,
} from '../../types/map';
import { MapControls } from './MapControls';
import './MapRenderer.css';

/**
 * Props for MapRenderer component
 */
export interface MapRendererProps {
  /** Map data to render */
  mapData?: MapData;
  /** Renderer configuration */
  config?: MapRendererConfig;
  /** Show navigation controls */
  showControls?: boolean;
  /** Initial layer visibility */
  layerVisibility?: Partial<LayerVisibility>;
  /** Callback when an icon is clicked */
  onIconClick?: (icon: MapIcon, event: MapInteractionEvent) => void;
  /** Callback when an icon is hovered */
  onIconHover?: (icon: MapIcon | null) => void;
  /** Callback when a road is clicked */
  onRoadClick?: (road: Road, event: MapInteractionEvent) => void;
  /** Callback when the map is clicked (empty space) */
  onMapClick?: (position: Point, event: MapInteractionEvent) => void;
  /** Additional CSS class name */
  className?: string;
  /** Loading state */
  isLoading?: boolean;
  /** Error message */
  error?: string | null;
}

/**
 * Default layer visibility
 */
const DEFAULT_LAYER_VISIBILITY: LayerVisibility = {
  background: true,
  roads: true,
  icons: true,
  labels: true,
  debug: false,
};

/**
 * MapRenderer Component
 *
 * Renders an interactive map with pan/zoom controls using PixiJS.
 */
export function MapRenderer({
  mapData,
  config,
  showControls = true,
  layerVisibility: initialLayerVisibility,
  onIconClick,
  onIconHover,
  onRoadClick,
  onMapClick,
  className = '',
  isLoading = false,
  error = null,
}: MapRendererProps) {
  // Layer refs
  const backgroundLayerRef = useRef<BackgroundLayer | null>(null);
  const roadsLayerRef = useRef<RoadsLayer | null>(null);
  const iconsLayerRef = useRef<IconsLayer | null>(null);
  const labelsLayerRef = useRef<LabelsLayer | null>(null);

  // Layer visibility state
  const [layerVisibility, setLayerVisibility] = useState<LayerVisibility>({
    ...DEFAULT_LAYER_VISIBILITY,
    ...initialLayerVisibility,
  });

  // Initialize map renderer
  const {
    containerRef,
    stage,
    isReady,
    dimensions,
    viewport,
    setViewport,
  } = useMapRenderer(config);

  // Initialize controls
  const {
    bindControls,
    zoomIn,
    zoomOut,
    resetView,
    fitToContainer,
  } = useMapControls(viewport, setViewport, dimensions, {
    constraints: config?.constraints,
  });

  /**
   * Initialize layers when stage is ready
   */
  useEffect(() => {
    if (!stage || !isReady) return;

    // Create layers
    const backgroundLayer = new BackgroundLayer({
      tileSize: mapData?.tileSize ?? 64,
      mapWidth: mapData?.width ?? 2048,
      mapHeight: mapData?.height ?? 2048,
      defaultTerrain: 'grass',
      showGrid: layerVisibility.debug,
    });

    const roadsLayer = new RoadsLayer({
      interactive: true,
    });

    const iconsLayer = new IconsLayer({
      interactive: true,
      showLabels: layerVisibility.labels,
    });

    const labelsLayer = new LabelsLayer();

    // Add layers to stage in order
    stage.addChild(backgroundLayer.container);
    stage.addChild(roadsLayer.container);
    stage.addChild(iconsLayer.container);
    stage.addChild(labelsLayer.container);

    // Store refs
    backgroundLayerRef.current = backgroundLayer;
    roadsLayerRef.current = roadsLayer;
    iconsLayerRef.current = iconsLayer;
    labelsLayerRef.current = labelsLayer;

    // Cleanup on unmount
    return () => {
      backgroundLayer.destroy();
      roadsLayer.destroy();
      iconsLayer.destroy();
      labelsLayer.destroy();

      backgroundLayerRef.current = null;
      roadsLayerRef.current = null;
      iconsLayerRef.current = null;
      labelsLayerRef.current = null;
    };
    // Layer initialization should only happen once when stage becomes ready.
    // mapData values are used for initial config but layers are updated separately.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, isReady]);

  /**
   * Bind controls to container
   */
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !isReady) return;

    const cleanup = bindControls(container);
    return cleanup;
  }, [containerRef, isReady, bindControls]);

  /**
   * Update layers when map data changes
   */
  useEffect(() => {
    if (!mapData || !isReady) return;

    const backgroundLayer = backgroundLayerRef.current;
    const roadsLayer = roadsLayerRef.current;
    const iconsLayer = iconsLayerRef.current;
    const labelsLayer = labelsLayerRef.current;

    // Update background layer
    if (backgroundLayer) {
      backgroundLayer.updateConfig({
        mapWidth: mapData.width,
        mapHeight: mapData.height,
        tileSize: mapData.tileSize,
      });

      if (mapData.tiles) {
        backgroundLayer.setTiles(mapData.tiles);
      }

      // Update visible tiles based on current viewport
      backgroundLayer.updateVisibleTiles(viewport, dimensions.width, dimensions.height);
    }

    // Update roads layer
    if (roadsLayer && mapData.roads) {
      roadsLayer.setRoads(mapData.roads);
    }

    // Update icons layer
    if (iconsLayer && mapData.icons) {
      iconsLayer.setIcons(mapData.icons);
    }

    // Update labels layer
    if (labelsLayer && mapData.labels) {
      labelsLayer.setLabels(mapData.labels);
    }
  }, [mapData, isReady, viewport, dimensions]);

  /**
   * Set up event handlers for layers
   */
  useEffect(() => {
    const roadsLayer = roadsLayerRef.current;
    const iconsLayer = iconsLayerRef.current;

    if (roadsLayer && onRoadClick) {
      roadsLayer.setOnRoadClick((road, event) => {
        onRoadClick(road, {
          type: 'road-click',
          position: { x: event.globalX, y: event.globalY },
          targetId: road.id,
          target: road,
          originalEvent: event.nativeEvent as PointerEvent,
        });
      });
    }

    if (iconsLayer) {
      if (onIconClick) {
        iconsLayer.setOnIconClick((icon, event) => {
          onIconClick(icon, {
            type: 'icon-click',
            position: icon.position,
            targetId: icon.id,
            target: icon,
            originalEvent: event.nativeEvent as PointerEvent,
          });
        });
      }

      if (onIconHover) {
        iconsLayer.setOnIconHover(onIconHover);
      }
    }
  }, [isReady, onRoadClick, onIconClick, onIconHover]);

  /**
   * Update layer visibility
   */
  useEffect(() => {
    const backgroundLayer = backgroundLayerRef.current;
    const roadsLayer = roadsLayerRef.current;
    const iconsLayer = iconsLayerRef.current;
    const labelsLayer = labelsLayerRef.current;

    if (backgroundLayer) {
      backgroundLayer.container.visible = layerVisibility.background;
      backgroundLayer.setGridVisible(layerVisibility.debug);
    }

    if (roadsLayer) {
      roadsLayer.container.visible = layerVisibility.roads;
    }

    if (iconsLayer) {
      iconsLayer.container.visible = layerVisibility.icons;
      iconsLayer.setLabelsVisible(layerVisibility.labels);
    }

    if (labelsLayer) {
      labelsLayer.container.visible = layerVisibility.labels;
    }
  }, [layerVisibility]);

  /**
   * Update visible tiles on viewport change
   */
  useEffect(() => {
    const backgroundLayer = backgroundLayerRef.current;
    if (backgroundLayer && isReady) {
      backgroundLayer.updateVisibleTiles(viewport, dimensions.width, dimensions.height);
    }
  }, [viewport, dimensions, isReady]);

  /**
   * Handle map click on empty space
   */
  const handleContainerClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!onMapClick || !isReady) return;

      // Check if click was on canvas (not on controls)
      const target = e.target as HTMLElement;
      if (!target.tagName || target.tagName.toLowerCase() !== 'canvas') return;

      // Convert screen position to world position
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;

      const screenX = e.clientX - rect.left;
      const screenY = e.clientY - rect.top;

      const worldX = (screenX - viewport.x) / viewport.scale;
      const worldY = (screenY - viewport.y) / viewport.scale;

      onMapClick(
        { x: worldX, y: worldY },
        {
          type: 'map-click',
          position: { x: worldX, y: worldY },
          originalEvent: e.nativeEvent,
        }
      );
    },
    [onMapClick, isReady, viewport, containerRef]
  );

  /**
   * Handle fit to map
   */
  const handleFitToMap = useCallback(() => {
    if (mapData) {
      fitToContainer(mapData.width, mapData.height);
    }
  }, [mapData, fitToContainer]);

  /**
   * Toggle layer visibility
   */
  const toggleLayer = useCallback((layer: keyof LayerVisibility) => {
    setLayerVisibility((prev) => ({
      ...prev,
      [layer]: !prev[layer],
    }));
  }, []);

  return (
    <div className={`map-renderer ${className}`}>
      {/* Loading overlay */}
      {isLoading && (
        <div className="map-renderer__loading">
          <div className="map-renderer__spinner" />
          <span>Loading map...</span>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="map-renderer__error">
          <span className="map-renderer__error-icon">!</span>
          <span>{error}</span>
        </div>
      )}

      {/* Canvas container */}
      <div
        ref={containerRef}
        className="map-renderer__canvas"
        onClick={handleContainerClick}
      />

      {/* Navigation controls */}
      {showControls && isReady && (
        <MapControls
          onZoomIn={zoomIn}
          onZoomOut={zoomOut}
          onResetView={resetView}
          onFitToMap={handleFitToMap}
          currentZoom={viewport.scale}
          layerVisibility={layerVisibility}
          onToggleLayer={toggleLayer}
        />
      )}

      {/* Debug info */}
      {layerVisibility.debug && isReady && (
        <div className="map-renderer__debug">
          <div>Viewport: x={viewport.x.toFixed(0)}, y={viewport.y.toFixed(0)}</div>
          <div>Scale: {(viewport.scale * 100).toFixed(0)}%</div>
          <div>Canvas: {dimensions.width}x{dimensions.height}</div>
          {mapData && (
            <div>Map: {mapData.width}x{mapData.height}</div>
          )}
        </div>
      )}
    </div>
  );
}
