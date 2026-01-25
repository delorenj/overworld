/**
 * DashboardPage Component Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DashboardPage } from './DashboardPage';

// Mock the auth hook
const mockGetUsageStats = vi.fn();
const mockUser = {
  id: 'user-1',
  name: 'Test User',
  email: 'test@example.com',
};

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: mockUser,
    getUsageStats: mockGetUsageStats,
  }),
}));

// Mock the MapGallery component
vi.mock('../components/dashboard/MapGallery', () => ({
  MapGallery: ({ maps, isLoading }: { maps: unknown[]; isLoading: boolean }) => (
    <div data-testid="map-gallery">
      {isLoading ? 'Loading...' : `${maps.length} maps`}
    </div>
  ),
}));

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetUsageStats.mockResolvedValue({
      tokenBalance: 5000,
      tokensUsed: 2500,
      mapsGenerated: 12,
      storageUsed: 52428800,
      storageLimit: 104857600,
    });
  });

  const renderWithRouter = (component: React.ReactNode) => {
    return render(<MemoryRouter>{component}</MemoryRouter>);
  };

  it('displays welcome message with user name', async () => {
    renderWithRouter(<DashboardPage />);

    expect(screen.getByText(/Welcome back, Test!/)).toBeInTheDocument();
  });

  it('shows token balance after loading', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('5,000')).toBeInTheDocument();
    });
  });

  it('shows maps generated count', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('12')).toBeInTheDocument();
    });
  });

  it('displays storage usage', async () => {
    renderWithRouter(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('50 MB')).toBeInTheDocument();
    });
  });

  it('shows the new map button', () => {
    renderWithRouter(<DashboardPage />);

    expect(screen.getByText('New Map')).toBeInTheDocument();
  });

  it('displays recent maps section', async () => {
    renderWithRouter(<DashboardPage />);

    expect(screen.getByText('Recent Maps')).toBeInTheDocument();
  });

  it('shows view all link for maps', () => {
    renderWithRouter(<DashboardPage />);

    expect(screen.getByText('View all')).toBeInTheDocument();
  });

  it('renders stat cards with correct titles', () => {
    renderWithRouter(<DashboardPage />);

    expect(screen.getByText('Token Balance')).toBeInTheDocument();
    expect(screen.getByText('Maps Generated')).toBeInTheDocument();
    expect(screen.getByText('Storage Used')).toBeInTheDocument();
    expect(screen.getByText('Usage Trend')).toBeInTheDocument();
  });

  it('handles usage stats fetch error gracefully', async () => {
    mockGetUsageStats.mockRejectedValue(new Error('Failed to fetch'));

    renderWithRouter(<DashboardPage />);

    // Should still render without crashing
    expect(screen.getByText(/Welcome back/)).toBeInTheDocument();
  });
});
