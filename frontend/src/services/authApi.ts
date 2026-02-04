import axios from 'axios';
import type { LoginCredentials } from '../types/user';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost/api';

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface BackendUserResponse {
  id: number;
  email: string;
  is_verified: boolean;
  is_premium: boolean;
  created_at: string;
  updated_at: string | null;
}

/**
 * Login with email and password
 */
export async function login(credentials: LoginCredentials): Promise<TokenResponse> {
  const response = await axios.post<TokenResponse>(
    `${API_BASE_URL}/v1/auth/login`,
    credentials
  );
  return response.data;
}

/**
 * Get current user profile
 */
export async function getCurrentUser(token: string): Promise<BackendUserResponse> {
  const response = await axios.get<BackendUserResponse>(
    `${API_BASE_URL}/v1/auth/me`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
  return response.data;
}

/**
 * Logout
 */
export async function logout(token: string): Promise<void> {
  await axios.post(
    `${API_BASE_URL}/v1/auth/logout`,
    {},
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );
}
