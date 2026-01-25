/**
 * Dashboard and map gallery related types
 */

/**
 * Map generation status
 */
export type MapStatus = 'draft' | 'generating' | 'complete' | 'error';

/**
 * Map item for the gallery
 */
export interface MapItem {
  id: string;
  title: string;
  description?: string;
  thumbnailUrl?: string;
  status: MapStatus;
  createdAt: string;
  updatedAt: string;
  /** Size in bytes */
  size?: number;
}

/**
 * Map gallery filter options
 */
export interface MapFilters {
  status?: MapStatus | 'all';
  sortBy?: 'createdAt' | 'updatedAt' | 'title';
  sortOrder?: 'asc' | 'desc';
  search?: string;
}

/**
 * Map action types
 */
export type MapAction = 'view' | 'edit' | 'delete' | 'export' | 'duplicate';
