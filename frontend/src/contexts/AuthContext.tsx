/**
 * Authentication Context
 *
 * Provides authentication state and methods throughout the application.
 * Handles login, logout, and user session management.
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import type {
  User,
  AuthState,
  LoginCredentials,
  UsageStats,
  ConnectedAccount,
  PasswordChangeRequest,
} from '../types/user';

/**
 * Authentication context value interface
 */
interface AuthContextValue extends AuthState {
  login: (credentials: LoginCredentials) => Promise<void>;
  loginWithOAuth: (provider: string) => Promise<void>;
  logout: () => Promise<void>;
  updateUser: (updates: Partial<User>) => Promise<void>;
  changePassword: (request: PasswordChangeRequest) => Promise<void>;
  deleteAccount: () => Promise<void>;
  getUsageStats: () => Promise<UsageStats>;
  getConnectedAccounts: () => Promise<ConnectedAccount[]>;
  disconnectAccount: (provider: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// API base URL from environment
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost/api';

/**
 * Mock user for development - remove in production
 */
const MOCK_USER: User = {
  id: 'user-123',
  email: 'demo@overworld.dev',
  name: 'Demo User',
  avatarUrl: 'https://api.dicebear.com/7.x/avataaars/svg?seed=demo',
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-15T00:00:00Z',
};

const MOCK_STATS: UsageStats = {
  tokenBalance: 5000,
  tokensUsed: 2500,
  mapsGenerated: 12,
  storageUsed: 52428800, // 50MB
  storageLimit: 104857600, // 100MB
};

const MOCK_CONNECTED_ACCOUNTS: ConnectedAccount[] = [
  {
    provider: 'google',
    providerId: 'google-123',
    email: 'demo@gmail.com',
    connectedAt: '2024-01-01T00:00:00Z',
  },
];

interface AuthProviderProps {
  children: React.ReactNode;
}

/**
 * Authentication Provider Component
 *
 * Wraps the application to provide authentication context.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    error: null,
  });

  /**
   * Check for existing session on mount
   */
  useEffect(() => {
    const checkSession = async () => {
      try {
        // Check localStorage for existing session
        const savedUser = localStorage.getItem('overworld_user');
        if (savedUser) {
          const user = JSON.parse(savedUser);
          setState({
            user,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
        } else {
          // In development, auto-login with mock user
          if (import.meta.env.DEV) {
            localStorage.setItem('overworld_user', JSON.stringify(MOCK_USER));
            setState({
              user: MOCK_USER,
              isAuthenticated: true,
              isLoading: false,
              error: null,
            });
          } else {
            setState((prev) => ({ ...prev, isLoading: false }));
          }
        }
      } catch (error) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: 'Failed to restore session',
        }));
      }
    };

    checkSession();
  }, []);

  /**
   * Login with email and password
   */
  const login = useCallback(async (credentials: LoginCredentials) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      // TODO: Replace with actual API call
      // const response = await axios.post(`${API_BASE_URL}/v1/auth/login`, credentials);
      // const user = response.data.user;

      // Mock login for development
      await new Promise((resolve) => setTimeout(resolve, 500));

      if (credentials.email === 'demo@overworld.dev') {
        localStorage.setItem('overworld_user', JSON.stringify(MOCK_USER));
        setState({
          user: MOCK_USER,
          isAuthenticated: true,
          isLoading: false,
          error: null,
        });
      } else {
        throw new Error('Invalid credentials');
      }
    } catch (error: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: error.message || 'Login failed',
      }));
      throw error;
    }
  }, []);

  /**
   * Login with OAuth provider
   */
  const loginWithOAuth = useCallback(async (provider: string) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      // TODO: Implement OAuth flow
      // Redirect to OAuth provider
      window.location.href = `${API_BASE_URL}/v1/auth/oauth/${provider}`;
    } catch (error: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: error.message || 'OAuth login failed',
      }));
      throw error;
    }
  }, []);

  /**
   * Logout and clear session
   */
  const logout = useCallback(async () => {
    try {
      // TODO: Call logout API endpoint
      // await axios.post(`${API_BASE_URL}/v1/auth/logout`);

      localStorage.removeItem('overworld_user');
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    } catch (error: any) {
      console.error('Logout error:', error);
      // Still clear local state even if API call fails
      localStorage.removeItem('overworld_user');
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  }, []);

  /**
   * Update user profile
   */
  const updateUser = useCallback(async (updates: Partial<User>) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      // TODO: Replace with actual API call
      // const response = await axios.patch(`${API_BASE_URL}/v1/users/me`, updates);
      // const updatedUser = response.data;

      await new Promise((resolve) => setTimeout(resolve, 500));

      setState((prev) => {
        if (!prev.user) return prev;
        const updatedUser = { ...prev.user, ...updates, updatedAt: new Date().toISOString() };
        localStorage.setItem('overworld_user', JSON.stringify(updatedUser));
        return {
          ...prev,
          user: updatedUser,
          isLoading: false,
        };
      });
    } catch (error: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: error.message || 'Failed to update profile',
      }));
      throw error;
    }
  }, []);

  /**
   * Change password
   */
  const changePassword = useCallback(async (request: PasswordChangeRequest) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      // Validate passwords match
      if (request.newPassword !== request.confirmPassword) {
        throw new Error('Passwords do not match');
      }

      // TODO: Replace with actual API call
      // await axios.post(`${API_BASE_URL}/v1/auth/change-password`, request);

      await new Promise((resolve) => setTimeout(resolve, 500));

      setState((prev) => ({ ...prev, isLoading: false }));
    } catch (error: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: error.message || 'Failed to change password',
      }));
      throw error;
    }
  }, []);

  /**
   * Delete account
   */
  const deleteAccount = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      // TODO: Replace with actual API call
      // await axios.delete(`${API_BASE_URL}/v1/users/me`);

      await new Promise((resolve) => setTimeout(resolve, 500));

      localStorage.removeItem('overworld_user');
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    } catch (error: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: error.message || 'Failed to delete account',
      }));
      throw error;
    }
  }, []);

  /**
   * Get usage statistics
   */
  const getUsageStats = useCallback(async (): Promise<UsageStats> => {
    try {
      // TODO: Replace with actual API call
      // const response = await axios.get(`${API_BASE_URL}/v1/users/me/stats`);
      // return response.data;

      await new Promise((resolve) => setTimeout(resolve, 200));
      return MOCK_STATS;
    } catch (error: any) {
      throw new Error(error.message || 'Failed to fetch usage stats');
    }
  }, []);

  /**
   * Get connected OAuth accounts
   */
  const getConnectedAccounts = useCallback(async (): Promise<ConnectedAccount[]> => {
    try {
      // TODO: Replace with actual API call
      // const response = await axios.get(`${API_BASE_URL}/v1/users/me/accounts`);
      // return response.data;

      await new Promise((resolve) => setTimeout(resolve, 200));
      return MOCK_CONNECTED_ACCOUNTS;
    } catch (error: any) {
      throw new Error(error.message || 'Failed to fetch connected accounts');
    }
  }, []);

  /**
   * Disconnect OAuth account
   */
  const disconnectAccount = useCallback(async (_provider: string) => {
    try {
      // TODO: Replace with actual API call
      // await axios.delete(`${API_BASE_URL}/v1/users/me/accounts/${_provider}`);

      await new Promise((resolve) => setTimeout(resolve, 500));
    } catch (error: any) {
      throw new Error(error.message || 'Failed to disconnect account');
    }
  }, []);

  const value: AuthContextValue = {
    ...state,
    login,
    loginWithOAuth,
    logout,
    updateUser,
    changePassword,
    deleteAccount,
    getUsageStats,
    getConnectedAccounts,
    disconnectAccount,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Hook to access authentication context
 *
 * @throws Error if used outside of AuthProvider
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export { AuthContext };
