/**
 * useMapData Hook
 *
 * Manages map data fetching and state for the map renderer.
 * Provides loading states, error handling, and data refresh capabilities.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import type { MapData, MapIcon, Road } from '../types/map';

/**
 * API base URL
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost/api';

/**
 * Configuration for useMapData hook
 */
export interface UseMapDataConfig {
  /** Map ID to fetch */
  mapId?: string;
  /** Auto-fetch on mount */
  autoFetch?: boolean;
  /** Polling interval in ms (0 = disabled) */
  pollingInterval?: number;
  /** Initial map data (for static maps) */
  initialData?: MapData;
}

/**
 * Return type for useMapData hook
 */
export interface UseMapDataResult {
  /** Map data */
  mapData: MapData | null;
  /** Loading state */
  isLoading: boolean;
  /** Error message */
  error: string | null;
  /** Fetch/refresh map data */
  fetchMapData: (mapId?: string) => Promise<void>;
  /** Update map data locally */
  updateMapData: (updates: Partial<MapData>) => void;
  /** Add an icon to the map */
  addIcon: (icon: MapIcon) => void;
  /** Remove an icon from the map */
  removeIcon: (iconId: string) => void;
  /** Update an icon */
  updateIcon: (iconId: string, updates: Partial<MapIcon>) => void;
  /** Add a road to the map */
  addRoad: (road: Road) => void;
  /** Remove a road from the map */
  removeRoad: (roadId: string) => void;
  /** Clear all map data */
  clearMapData: () => void;
}

/**
 * Create sample map data for development/testing
 */
export function createSampleMapData(): MapData {
  return {
    id: 'sample-map',
    name: 'Sample Map',
    width: 2048,
    height: 2048,
    tileSize: 64,
    backgroundColor: 0x1a1a2e,
    roads: [
      {
        id: 'road-1',
        name: 'Main Road',
        type: 'main',
        points: [
          { x: 100, y: 100 },
          { x: 300, y: 200 },
          { x: 500, y: 150 },
          { x: 700, y: 300 },
          { x: 900, y: 250 },
        ],
      },
      {
        id: 'road-2',
        name: 'Side Path',
        type: 'path',
        points: [
          { x: 300, y: 200 },
          { x: 350, y: 400 },
          { x: 400, y: 600 },
        ],
      },
      {
        id: 'river-1',
        name: 'Blue River',
        type: 'river',
        points: [
          { x: 800, y: 100 },
          { x: 750, y: 300 },
          { x: 800, y: 500 },
          { x: 700, y: 700 },
        ],
      },
    ],
    icons: [
      {
        id: 'icon-1',
        name: 'Castle',
        position: { x: 500, y: 150 },
        category: 'landmark',
        sprite: 'fallback:landmark',
        scale: 1.5,
        interactive: true,
        metadata: { description: 'The main castle' },
      },
      {
        id: 'icon-2',
        name: 'Village',
        position: { x: 300, y: 200 },
        category: 'building',
        sprite: 'fallback:building',
        interactive: true,
      },
      {
        id: 'icon-3',
        name: 'Forest',
        position: { x: 700, y: 300 },
        category: 'location',
        sprite: 'fallback:location',
        interactive: true,
      },
      {
        id: 'icon-4',
        name: 'Gold Mine',
        position: { x: 400, y: 600 },
        category: 'resource',
        sprite: 'fallback:resource',
        interactive: true,
      },
      {
        id: 'icon-5',
        name: 'Dragon Lair',
        position: { x: 900, y: 250 },
        category: 'danger',
        sprite: 'fallback:danger',
        scale: 1.3,
        interactive: true,
      },
      {
        id: 'icon-6',
        name: 'Quest Giver',
        position: { x: 350, y: 400 },
        category: 'quest',
        sprite: 'fallback:quest',
        interactive: true,
      },
    ],
    labels: [
      {
        id: 'label-1',
        text: 'Northern Region',
        position: { x: 500, y: 50 },
        fontSize: 18,
        color: 0xffffff,
      },
      {
        id: 'label-2',
        text: 'Southern Lands',
        position: { x: 500, y: 800 },
        fontSize: 18,
        color: 0xffffff,
      },
    ],
  };
}

/**
 * Hook for managing map data fetching and state
 *
 * @param config - Configuration options
 * @returns Map data state and control functions
 */
export function useMapData(config: UseMapDataConfig = {}): UseMapDataResult {
  const { mapId, autoFetch = false, pollingInterval = 0, initialData } = config;

  const [mapData, setMapData] = useState<MapData | null>(initialData ?? null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollingRef = useRef<number | null>(null);

  /**
   * Fetch map data from API
   */
  const fetchMapData = useCallback(async (fetchMapId?: string) => {
    const id = fetchMapId ?? mapId;
    if (!id) {
      setError('No map ID provided');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await axios.get<MapData>(`${API_BASE_URL}/v1/maps/${id}`);
      setMapData(response.data);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to fetch map data';
      setError(errorMessage);
      console.error('Failed to fetch map data:', err);
    } finally {
      setIsLoading(false);
    }
  }, [mapId]);

  /**
   * Update map data locally
   */
  const updateMapData = useCallback((updates: Partial<MapData>) => {
    setMapData((prev) => {
      if (!prev) return prev;
      return { ...prev, ...updates };
    });
  }, []);

  /**
   * Add an icon to the map
   */
  const addIcon = useCallback((icon: MapIcon) => {
    setMapData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        icons: [...prev.icons, icon],
      };
    });
  }, []);

  /**
   * Remove an icon from the map
   */
  const removeIcon = useCallback((iconId: string) => {
    setMapData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        icons: prev.icons.filter((icon) => icon.id !== iconId),
      };
    });
  }, []);

  /**
   * Update an icon
   */
  const updateIcon = useCallback((iconId: string, updates: Partial<MapIcon>) => {
    setMapData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        icons: prev.icons.map((icon) =>
          icon.id === iconId ? { ...icon, ...updates } : icon
        ),
      };
    });
  }, []);

  /**
   * Add a road to the map
   */
  const addRoad = useCallback((road: Road) => {
    setMapData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        roads: [...prev.roads, road],
      };
    });
  }, []);

  /**
   * Remove a road from the map
   */
  const removeRoad = useCallback((roadId: string) => {
    setMapData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        roads: prev.roads.filter((road) => road.id !== roadId),
      };
    });
  }, []);

  /**
   * Clear all map data
   */
  const clearMapData = useCallback(() => {
    setMapData(null);
    setError(null);
  }, []);

  /**
   * Auto-fetch on mount if enabled
   */
  useEffect(() => {
    if (autoFetch && mapId) {
      fetchMapData();
    }
  }, [autoFetch, mapId, fetchMapData]);

  /**
   * Set up polling if enabled
   */
  useEffect(() => {
    if (pollingInterval > 0 && mapId) {
      pollingRef.current = window.setInterval(() => {
        fetchMapData();
      }, pollingInterval);

      return () => {
        if (pollingRef.current) {
          window.clearInterval(pollingRef.current);
        }
      };
    }
  }, [pollingInterval, mapId, fetchMapData]);

  return {
    mapData,
    isLoading,
    error,
    fetchMapData,
    updateMapData,
    addIcon,
    removeIcon,
    updateIcon,
    addRoad,
    removeRoad,
    clearMapData,
  };
}
