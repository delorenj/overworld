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
import type { MapItem, MapAction } from '../types/dashboard';

// Mock data - replace with API call
const MOCK_MAPS: MapItem[] = [
  {
    id: 'map-1',
    title: 'Project Architecture',
    description: 'System architecture overview for the main platform',
    thumbnailUrl: 'https://via.placeholder.com/300x200/667eea/ffffff?text=Architecture',
    status: 'complete',
    createdAt: '2024-01-15T10:30:00Z',
    updatedAt: '2024-01-15T14:45:00Z',
    size: 1024000,
  },
  {
    id: 'map-2',
    title: 'API Documentation',
    description: 'REST API endpoints and data flow visualization',
    thumbnailUrl: 'https://via.placeholder.com/300x200/764ba2/ffffff?text=API+Docs',
    status: 'generating',
    createdAt: '2024-01-14T09:00:00Z',
    updatedAt: '2024-01-14T09:15:00Z',
    size: 512000,
  },
  {
    id: 'map-3',
    title: 'User Flow Diagram',
    description: 'User journey and onboarding flow',
    thumbnailUrl: 'https://via.placeholder.com/300x200/f093fb/ffffff?text=User+Flow',
    status: 'draft',
    createdAt: '2024-01-13T16:20:00Z',
    updatedAt: '2024-01-13T16:20:00Z',
    size: 256000,
  },
  {
    id: 'map-4',
    title: 'Database Schema',
    description: 'Entity relationship diagram for PostgreSQL database',
    thumbnailUrl: 'https://via.placeholder.com/300x200/4facfe/ffffff?text=Database',
    status: 'complete',
    createdAt: '2024-01-12T11:00:00Z',
    updatedAt: '2024-01-12T15:30:00Z',
    size: 768000,
  },
  {
    id: 'map-5',
    title: 'Microservices Architecture',
    description: 'Service mesh and communication patterns',
    thumbnailUrl: 'https://via.placeholder.com/300x200/00f2fe/ffffff?text=Microservices',
    status: 'complete',
    createdAt: '2024-01-11T08:45:00Z',
    updatedAt: '2024-01-11T12:00:00Z',
    size: 1536000,
  },
  {
    id: 'map-6',
    title: 'DevOps Pipeline',
    description: 'CI/CD workflow and deployment architecture',
    thumbnailUrl: 'https://via.placeholder.com/300x200/43e97b/ffffff?text=DevOps',
    status: 'error',
    createdAt: '2024-01-10T14:20:00Z',
    updatedAt: '2024-01-10T14:25:00Z',
    size: 128000,
  },
];

export function MyMapsPage() {
  const [maps, setMaps] = useState<MapItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // TODO: Replace with actual API call
    const loadMaps = async () => {
      await new Promise((resolve) => setTimeout(resolve, 500));
      setMaps(MOCK_MAPS);
      setIsLoading(false);
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
