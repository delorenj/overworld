/**
 * Map Page
 *
 * Demo page for testing the interactive map renderer.
 */

import { useState, useCallback } from 'react';
import { MapRenderer } from '../components/map';
import { useMapData, createSampleMapData } from '../hooks';
import type { MapIcon, Road, Point } from '../types/map';
import './MapPage.css';

/**
 * MapPage Component
 *
 * Demonstrates the PixiJS-based map renderer with sample data.
 */
export function MapPage() {
  const [selectedItem, setSelectedItem] = useState<{
    type: 'icon' | 'road';
    data: MapIcon | Road;
  } | null>(null);

  // Initialize with sample data
  const { mapData, isLoading, error } = useMapData({
    initialData: createSampleMapData(),
  });

  /**
   * Handle icon click
   */
  const handleIconClick = useCallback((icon: MapIcon) => {
    setSelectedItem({ type: 'icon', data: icon });
  }, []);

  /**
   * Handle icon hover
   */
  const handleIconHover = useCallback((icon: MapIcon | null) => {
    // Could show tooltip or highlight
    if (icon) {
      console.log('Hovering:', icon.name);
    }
  }, []);

  /**
   * Handle road click
   */
  const handleRoadClick = useCallback((road: Road) => {
    setSelectedItem({ type: 'road', data: road });
  }, []);

  /**
   * Handle map click (empty space)
   */
  const handleMapClick = useCallback((position: Point) => {
    console.log('Map clicked at:', position);
    setSelectedItem(null);
  }, []);

  /**
   * Close info panel
   */
  const closeInfoPanel = useCallback(() => {
    setSelectedItem(null);
  }, []);

  return (
    <div className="map-page">
      <header className="map-page__header">
        <h1 className="map-page__title">Interactive Map</h1>
        <p className="map-page__subtitle">
          Pan with drag, zoom with scroll wheel or pinch
        </p>
      </header>

      <main className="map-page__content">
        <div className="map-page__renderer">
          <MapRenderer
            mapData={mapData ?? undefined}
            isLoading={isLoading}
            error={error}
            showControls={true}
            onIconClick={handleIconClick}
            onIconHover={handleIconHover}
            onRoadClick={handleRoadClick}
            onMapClick={handleMapClick}
            config={{
              backgroundColor: 0x2d5a27,
              debug: false,
            }}
          />
        </div>

        {/* Info Panel */}
        {selectedItem && (
          <div className="map-page__info-panel">
            <div className="info-panel">
              <div className="info-panel__header">
                <h2 className="info-panel__title">
                  {selectedItem.type === 'icon'
                    ? (selectedItem.data as MapIcon).name
                    : (selectedItem.data as Road).name || 'Road'}
                </h2>
                <button
                  className="info-panel__close"
                  onClick={closeInfoPanel}
                  aria-label="Close panel"
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>

              <div className="info-panel__content">
                {selectedItem.type === 'icon' && (
                  <IconInfo icon={selectedItem.data as MapIcon} />
                )}
                {selectedItem.type === 'road' && (
                  <RoadInfo road={selectedItem.data as Road} />
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="map-page__footer">
        <p>
          Map Renderer Demo - PixiJS + React
        </p>
      </footer>
    </div>
  );
}

/**
 * Icon info display
 */
function IconInfo({ icon }: { icon: MapIcon }) {
  return (
    <div className="info-details">
      <div className="info-row">
        <span className="info-label">Category:</span>
        <span className="info-value">{icon.category}</span>
      </div>
      <div className="info-row">
        <span className="info-label">Position:</span>
        <span className="info-value">
          ({icon.position.x.toFixed(0)}, {icon.position.y.toFixed(0)})
        </span>
      </div>
      {typeof icon.metadata?.description === 'string' && (
        <div className="info-row">
          <span className="info-label">Description:</span>
          <span className="info-value">{icon.metadata.description}</span>
        </div>
      )}
    </div>
  );
}

/**
 * Road info display
 */
function RoadInfo({ road }: { road: Road }) {
  return (
    <div className="info-details">
      <div className="info-row">
        <span className="info-label">Type:</span>
        <span className="info-value">{road.type}</span>
      </div>
      <div className="info-row">
        <span className="info-label">Points:</span>
        <span className="info-value">{road.points.length}</span>
      </div>
      <div className="info-row">
        <span className="info-label">Start:</span>
        <span className="info-value">
          ({road.points[0].x.toFixed(0)}, {road.points[0].y.toFixed(0)})
        </span>
      </div>
      <div className="info-row">
        <span className="info-label">End:</span>
        <span className="info-value">
          ({road.points[road.points.length - 1].x.toFixed(0)},{' '}
          {road.points[road.points.length - 1].y.toFixed(0)})
        </span>
      </div>
    </div>
  );
}
