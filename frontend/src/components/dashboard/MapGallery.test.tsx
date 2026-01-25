/**
 * MapGallery Component Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MapGallery } from './MapGallery';
import type { MapItem } from '../../types/dashboard';

// Mock MapCard to simplify testing
vi.mock('./MapCard', () => ({
  MapCard: ({ map, onAction }: { map: MapItem; onAction?: (id: string, action: string) => void }) => (
    <div data-testid={`map-card-${map.id}`}>
      <span>{map.title}</span>
      <button onClick={() => onAction?.(map.id, 'view')}>View</button>
      <button onClick={() => onAction?.(map.id, 'delete')}>Delete</button>
    </div>
  ),
}));

const mockMaps: MapItem[] = [
  {
    id: 'map-1',
    title: 'Architecture Map',
    description: 'System architecture',
    status: 'complete',
    createdAt: '2024-01-15T10:30:00Z',
    updatedAt: '2024-01-15T14:45:00Z',
  },
  {
    id: 'map-2',
    title: 'API Documentation',
    description: 'API endpoints map',
    status: 'generating',
    createdAt: '2024-01-14T09:00:00Z',
    updatedAt: '2024-01-14T09:15:00Z',
  },
  {
    id: 'map-3',
    title: 'User Flow',
    description: 'User journey',
    status: 'draft',
    createdAt: '2024-01-13T16:20:00Z',
    updatedAt: '2024-01-13T16:20:00Z',
  },
];

describe('MapGallery', () => {
  const mockOnAction = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all maps in the gallery', () => {
    render(<MapGallery maps={mockMaps} onAction={mockOnAction} />);

    expect(screen.getByTestId('map-card-map-1')).toBeInTheDocument();
    expect(screen.getByTestId('map-card-map-2')).toBeInTheDocument();
    expect(screen.getByTestId('map-card-map-3')).toBeInTheDocument();
  });

  it('shows loading skeletons when isLoading is true', () => {
    render(<MapGallery maps={[]} isLoading={true} onAction={mockOnAction} />);

    // Check for skeleton elements (they should have animate-pulse class)
    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('shows empty state when no maps exist', () => {
    render(<MapGallery maps={[]} isLoading={false} onAction={mockOnAction} />);

    expect(screen.getByText('No maps yet')).toBeInTheDocument();
    expect(screen.getByText(/Upload a document/)).toBeInTheDocument();
  });

  it('filters maps by search term', async () => {
    const user = userEvent.setup();
    render(<MapGallery maps={mockMaps} onAction={mockOnAction} showFilters={true} />);

    const searchInput = screen.getByPlaceholderText('Search maps...');
    await user.type(searchInput, 'Architecture');

    expect(screen.getByTestId('map-card-map-1')).toBeInTheDocument();
    expect(screen.queryByTestId('map-card-map-2')).not.toBeInTheDocument();
    expect(screen.queryByTestId('map-card-map-3')).not.toBeInTheDocument();
  });

  it('shows no results state when search has no matches', async () => {
    const user = userEvent.setup();
    render(<MapGallery maps={mockMaps} onAction={mockOnAction} showFilters={true} />);

    const searchInput = screen.getByPlaceholderText('Search maps...');
    await user.type(searchInput, 'nonexistent map');

    expect(screen.getByText('No maps found')).toBeInTheDocument();
  });

  it('limits displayed maps when limit prop is provided', () => {
    render(<MapGallery maps={mockMaps} onAction={mockOnAction} limit={2} />);

    expect(screen.getByTestId('map-card-map-1')).toBeInTheDocument();
    expect(screen.getByTestId('map-card-map-2')).toBeInTheDocument();
    expect(screen.queryByTestId('map-card-map-3')).not.toBeInTheDocument();
  });

  it('calls onAction when map card action is triggered', async () => {
    const user = userEvent.setup();
    render(<MapGallery maps={mockMaps} onAction={mockOnAction} />);

    const viewButtons = screen.getAllByText('View');
    await user.click(viewButtons[0]);

    expect(mockOnAction).toHaveBeenCalledWith('map-1', 'view');
  });

  it('hides filters when showFilters is false', () => {
    render(<MapGallery maps={mockMaps} onAction={mockOnAction} showFilters={false} />);

    expect(screen.queryByPlaceholderText('Search maps...')).not.toBeInTheDocument();
  });

  it('clears filters when clear button is clicked', async () => {
    const user = userEvent.setup();
    render(<MapGallery maps={mockMaps} onAction={mockOnAction} showFilters={true} />);

    const searchInput = screen.getByPlaceholderText('Search maps...');
    await user.type(searchInput, 'nonexistent');

    expect(screen.getByText('No maps found')).toBeInTheDocument();

    const clearButton = screen.getByText('Clear filters');
    await user.click(clearButton);

    // All maps should be visible again
    expect(screen.getByTestId('map-card-map-1')).toBeInTheDocument();
    expect(screen.getByTestId('map-card-map-2')).toBeInTheDocument();
  });
});
