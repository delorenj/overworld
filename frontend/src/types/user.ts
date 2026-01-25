/**
 * User and authentication related types
 */

/**
 * User profile information
 */
export interface User {
  id: string;
  email: string;
  name: string;
  avatarUrl?: string;
  createdAt: string;
  updatedAt: string;
}

/**
 * OAuth provider types
 */
export type OAuthProvider = 'google' | 'github' | 'discord';

/**
 * Connected OAuth account
 */
export interface ConnectedAccount {
  provider: OAuthProvider;
  providerId: string;
  email: string;
  connectedAt: string;
}

/**
 * User usage statistics
 */
export interface UsageStats {
  /** Token balance remaining */
  tokenBalance: number;
  /** Total tokens used */
  tokensUsed: number;
  /** Number of maps generated */
  mapsGenerated: number;
  /** Storage used in bytes */
  storageUsed: number;
  /** Maximum storage allowed in bytes */
  storageLimit: number;
}

/**
 * Authentication state
 */
export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

/**
 * Login credentials
 */
export interface LoginCredentials {
  email: string;
  password: string;
}

/**
 * Password change request
 */
export interface PasswordChangeRequest {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}
