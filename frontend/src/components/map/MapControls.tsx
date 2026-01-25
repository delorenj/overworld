/**
 * MapControls Component
 *
 * UI controls for map navigation (zoom, pan, reset) and layer visibility.
 */

import { useState, useCallback } from 'react';
import type { LayerVisibility } from '../../types/map';
import './MapControls.css';

/**
 * Props for MapControls component
 */
export interface MapControlsProps {
  /** Zoom in handler */
  onZoomIn: () => void;
  /** Zoom out handler */
  onZoomOut: () => void;
  /** Reset view handler */
  onResetView: () => void;
  /** Fit to map handler */
  onFitToMap?: () => void;
  /** Current zoom level (scale) */
  currentZoom: number;
  /** Layer visibility state */
  layerVisibility?: LayerVisibility;
  /** Layer toggle handler */
  onToggleLayer?: (layer: keyof LayerVisibility) => void;
  /** Show layer controls */
  showLayerControls?: boolean;
  /** Position of controls */
  position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
}

/**
 * MapControls Component
 *
 * Provides zoom buttons, reset view, and layer visibility toggles.
 */
export function MapControls({
  onZoomIn,
  onZoomOut,
  onResetView,
  onFitToMap,
  currentZoom,
  layerVisibility,
  onToggleLayer,
  showLayerControls = true,
  position = 'top-right',
}: MapControlsProps) {
  const [isLayerMenuOpen, setIsLayerMenuOpen] = useState(false);

  /**
   * Toggle layer menu visibility
   */
  const toggleLayerMenu = useCallback(() => {
    setIsLayerMenuOpen((prev) => !prev);
  }, []);

  /**
   * Handle layer toggle
   */
  const handleLayerToggle = useCallback(
    (layer: keyof LayerVisibility) => {
      onToggleLayer?.(layer);
    },
    [onToggleLayer]
  );

  /**
   * Format zoom percentage
   */
  const zoomPercentage = Math.round(currentZoom * 100);

  return (
    <div className={`map-controls map-controls--${position}`}>
      {/* Zoom controls */}
      <div className="map-controls__group map-controls__zoom">
        <button
          className="map-controls__button"
          onClick={onZoomIn}
          title="Zoom in"
          aria-label="Zoom in"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>

        <div className="map-controls__zoom-level" title={`Zoom: ${zoomPercentage}%`}>
          {zoomPercentage}%
        </div>

        <button
          className="map-controls__button"
          onClick={onZoomOut}
          title="Zoom out"
          aria-label="Zoom out"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
      </div>

      {/* Navigation controls */}
      <div className="map-controls__group map-controls__nav">
        <button
          className="map-controls__button"
          onClick={onResetView}
          title="Reset view"
          aria-label="Reset view"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
            <path d="M3 3v5h5" />
          </svg>
        </button>

        {onFitToMap && (
          <button
            className="map-controls__button"
            onClick={onFitToMap}
            title="Fit to map"
            aria-label="Fit to map"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M15 3h6v6" />
              <path d="M9 21H3v-6" />
              <path d="M21 3l-7 7" />
              <path d="M3 21l7-7" />
            </svg>
          </button>
        )}
      </div>

      {/* Layer controls */}
      {showLayerControls && layerVisibility && onToggleLayer && (
        <div className="map-controls__group map-controls__layers">
          <button
            className={`map-controls__button ${isLayerMenuOpen ? 'map-controls__button--active' : ''}`}
            onClick={toggleLayerMenu}
            title="Toggle layers"
            aria-label="Toggle layers menu"
            aria-expanded={isLayerMenuOpen}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polygon points="12 2 2 7 12 12 22 7 12 2" />
              <polyline points="2 17 12 22 22 17" />
              <polyline points="2 12 12 17 22 12" />
            </svg>
          </button>

          {isLayerMenuOpen && (
            <div className="map-controls__layer-menu">
              <div className="map-controls__layer-menu-header">Layers</div>

              <label className="map-controls__layer-item">
                <input
                  type="checkbox"
                  checked={layerVisibility.background}
                  onChange={() => handleLayerToggle('background')}
                />
                <span className="map-controls__layer-checkbox" />
                <span className="map-controls__layer-label">Background</span>
              </label>

              <label className="map-controls__layer-item">
                <input
                  type="checkbox"
                  checked={layerVisibility.roads}
                  onChange={() => handleLayerToggle('roads')}
                />
                <span className="map-controls__layer-checkbox" />
                <span className="map-controls__layer-label">Roads</span>
              </label>

              <label className="map-controls__layer-item">
                <input
                  type="checkbox"
                  checked={layerVisibility.icons}
                  onChange={() => handleLayerToggle('icons')}
                />
                <span className="map-controls__layer-checkbox" />
                <span className="map-controls__layer-label">Icons</span>
              </label>

              <label className="map-controls__layer-item">
                <input
                  type="checkbox"
                  checked={layerVisibility.labels}
                  onChange={() => handleLayerToggle('labels')}
                />
                <span className="map-controls__layer-checkbox" />
                <span className="map-controls__layer-label">Labels</span>
              </label>

              <div className="map-controls__layer-divider" />

              <label className="map-controls__layer-item">
                <input
                  type="checkbox"
                  checked={layerVisibility.debug}
                  onChange={() => handleLayerToggle('debug')}
                />
                <span className="map-controls__layer-checkbox" />
                <span className="map-controls__layer-label">Debug Grid</span>
              </label>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
