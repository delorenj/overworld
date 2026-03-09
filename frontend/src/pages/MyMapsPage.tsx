/**
 * My Maps Page
 *
 * Full page view of all user maps with filtering and management options.
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { Button } from '../components/ui/button';
import { MapGallery } from '../components/dashboard/MapGallery';
import { getAllMaps } from '../services/mapsApi';
import type { MapItem, MapAction } from '../types/dashboard';

export function MyMapsPage() {
  const [maps, setMaps] = useState<MapItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadMaps = async () => {
      try {
        const mapsData = await getAllMaps(50, 0);
        setMaps(mapsData);
      } catch (error) {
        console.error('Failed to load maps:', error);
        setMaps([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadMaps();
  }, []);

  const handleMapAction = (mapId: string, action: MapAction) => {
    console.log(`Action ${action} on map ${mapId}`);

    switch (action) {
      case 'view':
        // Navigate to map view
        window.location.href = `/map?id=${mapId}`;
        break;
      case 'edit':
        // Navigate to map editor
        console.log('Edit map:', mapId);
        break;
      case 'delete':
        // Remove from state (API call would happen in MapCard)
        setMaps((prev) => prev.filter((m) => m.id !== mapId));
        break;
      case 'export':
        // Trigger download
        console.log('Export map:', mapId);
        break;
      case 'duplicate':
        // Create copy
        const mapToDuplicate = maps.find((m) => m.id === mapId);
        if (mapToDuplicate) {
          const newMap: MapItem = {
            ...mapToDuplicate,
            id: `map-${Date.now()}`,
            title: `${mapToDuplicate.title} (Copy)`,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
          };
          setMaps((prev) => [newMap, ...prev]);
        }
        break;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">My Maps</h1>
          <p className="text-muted-foreground">
            {isLoading ? 'Loading...' : `${maps.length} maps total`}
          </p>
        </div>
        <Button asChild>
          <Link to="/dashboard/upload">
            <Plus className="mr-2 h-4 w-4" />
            New Map
          </Link>
        </Button>
      </div>

      {/* Map Gallery */}
      <MapGallery
        maps={maps}
        isLoading={isLoading}
        onAction={handleMapAction}
        showFilters={true}
      />
    </div>
  );
}
