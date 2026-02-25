/**
 * User Profile API Service
 * 
 * Handles profile, preferences, and user stats endpoints.
 * Backend implemented by Lenoon (OWRLD-20).
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8778/api/v1';

export interface UserPreferences {
  default_theme_id: number | null;
  default_map_visibility: 'private' | 'unlisted' | 'public';
  color_mode: 'light' | 'dark' | 'system';
  language: string;
  notifications_enabled: boolean;
  email_marketing: boolean;
  auto_watermark: boolean;
}

export interface UserHistory {
  total_maps_created: number;
  total_exports: number;
  member_since: string;
}

export interface UserProfile {
  id: number;
  email: string;
  is_verified: boolean;
  is_premium: boolean;
  oauth_provider: string | null;
  created_at: string;
  updated_at: string | null;
  preferences: UserPreferences;
  history: UserHistory;
}

export interface UserPreferencesUpdate {
  default_theme_id?: number | null;
  default_map_visibility?: 'private' | 'unlisted' | 'public';
  color_mode?: 'light' | 'dark' | 'system';
  language?: string;
  notifications_enabled?: boolean;
  email_marketing?: boolean;
  auto_watermark?: boolean;
}

/**
 * Get current user's full profile
 */
export async function getUserProfile(): Promise<UserProfile> {
  const token = localStorage.getItem('accessToken');
  if (!token) {
    throw new Error('Not authenticated');
  }

  const response = await fetch(`${API_BASE}/users/me/profile`, {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch profile' }));
    throw new Error(error.detail);
  }

  return response.json();
}

/**
 * Get current user's preferences only
 */
export async function getUserPreferences(): Promise<UserPreferences> {
  const token = localStorage.getItem('accessToken');
  if (!token) {
    throw new Error('Not authenticated');
  }

  const response = await fetch(`${API_BASE}/users/me/preferences`, {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch preferences' }));
    throw new Error(error.detail);
  }

  return response.json();
}

/**
 * Update user preferences
 */
export async function updateUserPreferences(
  updates: UserPreferencesUpdate
): Promise<UserPreferences> {
  const token = localStorage.getItem('accessToken');
  if (!token) {
    throw new Error('Not authenticated');
  }

  const response = await fetch(`${API_BASE}/users/me/preferences`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updates),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update preferences' }));
    throw new Error(error.detail);
  }

  return response.json();
}
