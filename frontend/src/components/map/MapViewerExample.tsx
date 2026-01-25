/**
 * MapViewerExample Component
 *
 * Example implementation showing how to integrate the ExportDialog
 * with a map viewer component. This demonstrates the complete flow
 * of displaying a map and allowing users to export it.
 */

import React, { useState, useEffect } from 'react';
import { MapRenderer } from './MapRenderer';
import { ExportDialog } from './ExportDialog';
import { useAuth } from '../../hooks/useAuth';
import { useMapData } from '../../hooks/useMapData';
import type { UsageStats } from '../../types/user';

interface MapViewerExampleProps {
  mapId: number;
  mapName: string;
}

/**
 * Example map viewer with export functionality
 */
export const MapViewerExample: React.FC<MapViewerExampleProps> = ({
  mapId,
  mapName,
}) => {
  const { user, getUsageStats } = useAuth();
  const { mapData, isLoading, error } = useMapData({ mapId: String(mapId), autoFetch: true });
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [stats, setStats] = useState<UsageStats | null>(null);

  // Fetch usage stats to determine premium status
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const usageStats = await getUsageStats();
        setStats(usageStats);
      } catch {
        // Stats unavailable, treat as non-premium
      }
    };
    if (user) fetchStats();
  }, [user, getUsageStats]);

  // Determine if user is premium (has tokens)
  const isPremium = (stats?.tokenBalance ?? 0) > 0;

  if (isLoading) {
    return <div className="map-loading">Loading map...</div>;
  }

  if (error) {
    return <div className="map-error">Error loading map: {error}</div>;
  }

  return (
    <div className="map-viewer">
      {/* Map Header with Export Button */}
      <div className="map-header">
        <h1>{mapName}</h1>
        <div className="map-actions">
          <button
            className="export-button"
            onClick={() => setShowExportDialog(true)}
            disabled={!user}
          >
            📥 Export Map
          </button>
        </div>
      </div>

      {/* Map Renderer */}
      <div className="map-container">
        <MapRenderer
          mapData={mapData ?? undefined}
          config={{
            backgroundColor: 0xf0f0f0,
            antialias: true,
            resolution: window.devicePixelRatio || 1,
          }}
        />
      </div>

      {/* Export Dialog */}
      {user && (
        <ExportDialog
          mapId={mapId}
          mapName={mapName}
          isPremium={isPremium}
          isOpen={showExportDialog}
          onClose={() => setShowExportDialog(false)}
        />
      )}

      {/* Premium Notice for Free Users */}
      {user && !isPremium && (
        <div className="premium-notice">
          <p>
            💡 Upgrade to premium to export maps without watermarks!
          </p>
          <button className="upgrade-button">
            Upgrade Now
          </button>
        </div>
      )}
    </div>
  );
};

/**
 * Example CSS (would be in a separate file)
 */
export const mapViewerStyles = `
.map-viewer {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f9fafb;
}

.map-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background-color: white;
  border-bottom: 1px solid #e5e7eb;
}

.map-header h1 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: #1f2937;
}

.map-actions {
  display: flex;
  gap: 12px;
}

.export-button {
  background-color: #3b82f6;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.export-button:hover:not(:disabled) {
  background-color: #2563eb;
}

.export-button:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

.map-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.map-loading,
.map-error {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  font-size: 1.125rem;
  color: #6b7280;
}

.map-error {
  color: #dc2626;
}

.premium-notice {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 16px 24px;
  text-align: center;
}

.premium-notice p {
  margin: 0 0 12px 0;
  font-size: 0.875rem;
}

.upgrade-button {
  background-color: white;
  color: #667eea;
  border: none;
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
}

.upgrade-button:hover {
  transform: translateY(-2px);
}
`;

// Example usage in a route or page:
export const ExampleUsage = () => {
  return (
    <MapViewerExample
      mapId={123}
      mapName="My Awesome Map"
    />
  );
};
