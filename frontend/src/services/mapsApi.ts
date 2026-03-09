/**
 * Maps API Service
 * 
 * Handles map listing and management endpoints.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8778/api/v1';

export interface MapItem {
  id: string;
  title: string;
  description?: string;
  thumbnailUrl?: string;
  status: 'draft' | 'generating' | 'complete' | 'error';
  createdAt: string;
  updatedAt: string;
  size?: number;
  mapId?: number;
  jobId?: number;
}

/**
 * Get user's recent maps (from generation jobs)
 */
export async function getRecentMaps(limit: number = 5): Promise<MapItem[]> {
  const token = localStorage.getItem('accessToken');
  if (!token) {
    throw new Error('Not authenticated');
  }

  try {
    // TODO: Replace with proper /maps endpoint when backend implements it
    // For now, use generation jobs endpoint
    const response = await fetch(`${API_BASE}/jobs?limit=${limit}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch recent maps');
    }

    const jobs = await response.json();

    // Transform generation jobs into map items
    return jobs.map((job: any) => ({
      id: job.map_id?.toString() || job.id.toString(),
      title: `Map #${job.map_id || job.id}`,
      description: getStatusDescription(job.status),
      thumbnailUrl: undefined, // Will be populated from export service later
      status: mapJobStatusToMapStatus(job.status),
      createdAt: job.created_at,
      updatedAt: job.completed_at || job.started_at || job.created_at,
      size: undefined,
      mapId: job.map_id,
      jobId: job.id,
    }));
  } catch (error) {
    console.error('Failed to fetch recent maps:', error);
    return [];
  }
}

/**
 * Get all user maps
 */
export async function getAllMaps(limit: number = 50, offset: number = 0): Promise<MapItem[]> {
  const token = localStorage.getItem('accessToken');
  if (!token) {
    throw new Error('Not authenticated');
  }

  try {
    const response = await fetch(`${API_BASE}/jobs?limit=${limit}&offset=${offset}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch maps');
    }

    const jobs = await response.json();

    return jobs.map((job: any) => ({
      id: job.map_id?.toString() || job.id.toString(),
      title: `Map #${job.map_id || job.id}`,
      description: getStatusDescription(job.status),
      thumbnailUrl: undefined,
      status: mapJobStatusToMapStatus(job.status),
      createdAt: job.created_at,
      updatedAt: job.completed_at || job.started_at || job.created_at,
      size: undefined,
      mapId: job.map_id,
      jobId: job.id,
    }));
  } catch (error) {
    console.error('Failed to fetch maps:', error);
    return [];
  }
}

/**
 * Map job status to frontend map status
 */
function mapJobStatusToMapStatus(jobStatus: string): MapItem['status'] {
  switch (jobStatus) {
    case 'PENDING':
    case 'PROCESSING':
      return 'generating';
    case 'COMPLETED':
      return 'complete';
    case 'FAILED':
      return 'error';
    default:
      return 'draft';
  }
}

/**
 * Get status description
 */
function getStatusDescription(status: string): string {
  switch (status) {
    case 'PENDING':
      return 'Waiting in queue...';
    case 'PROCESSING':
      return 'Generating map...';
    case 'COMPLETED':
      return 'Map generated successfully';
    case 'FAILED':
      return 'Generation failed';
    default:
      return 'Draft';
  }
}
