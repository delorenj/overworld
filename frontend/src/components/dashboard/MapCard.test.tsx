/**
 * MapCard Component Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MapCard } from './MapCard';
import type { MapItem } from '../../types/dashboard';

// Mock the UI components
vi.mock('../ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => <div data-testid="dropdown-trigger">{children}</div>,
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => <div data-testid="dropdown-content">{children}</div>,
  DropdownMenuItem: ({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) => (
    <button onClick={onClick}>{children}</button>
  ),
  DropdownMenuSeparator: () => <hr />,
}));

vi.mock('../ui/alert-dialog', () => ({
  AlertDialog: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogContent: ({ children }: { children: React.ReactNode }) => <div data-testid="alert-dialog">{children}</div>,
  AlertDialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
  AlertDialogDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
  AlertDialogAction: ({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) => (
    <button onClick={onClick}>{children}</button>
  ),
  AlertDialogCancel: ({ children }: { children: React.ReactNode }) => <button>{children}</button>,
}));

const mockMap: MapItem = {
  id: 'map-1',
  title: 'Test Map',
  description: 'A test map description',
  thumbnailUrl: 'https://example.com/thumb.jpg',
  status: 'complete',
  createdAt: '2024-01-15T10:30:00Z',
  updatedAt: '2024-01-15T14:45:00Z',
  size: 1024000,
};

describe('MapCard', () => {
  const mockOnAction = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders map title and description', () => {
    render(<MapCard map={mockMap} onAction={mockOnAction} />);

    expect(screen.getByText('Test Map')).toBeInTheDocument();
    expect(screen.getByText('A test map description')).toBeInTheDocument();
  });

  it('displays the correct status badge', () => {
    render(<MapCard map={mockMap} onAction={mockOnAction} />);

    expect(screen.getByText('Complete')).toBeInTheDocument();
  });

  it('shows generating status with loader', () => {
    const generatingMap = { ...mockMap, status: 'generating' as const };
    render(<MapCard map={generatingMap} onAction={mockOnAction} />);

    expect(screen.getByText('Generating')).toBeInTheDocument();
  });

  it('displays formatted creation date', () => {
    render(<MapCard map={mockMap} onAction={mockOnAction} />);

    // Check for the date format
    expect(screen.getByText(/Created Jan 15, 2024/)).toBeInTheDocument();
  });

  it('renders thumbnail image when provided', () => {
    render(<MapCard map={mockMap} onAction={mockOnAction} />);

    const img = screen.getByRole('img');
    expect(img).toHaveAttribute('src', mockMap.thumbnailUrl);
    expect(img).toHaveAttribute('alt', mockMap.title);
  });

  it('shows placeholder when no thumbnail is provided', () => {
    const noThumbMap = { ...mockMap, thumbnailUrl: undefined };
    render(<MapCard map={noThumbMap} onAction={mockOnAction} />);

    expect(screen.getByText('No preview available')).toBeInTheDocument();
  });

  it('calls onAction with view when view button is clicked', async () => {
    const user = userEvent.setup();
    render(<MapCard map={mockMap} onAction={mockOnAction} />);

    // Find the View button (there should be one in the quick actions)
    const viewButtons = screen.getAllByRole('button', { name: /view/i });
    await user.click(viewButtons[0]);

    expect(mockOnAction).toHaveBeenCalledWith('map-1', 'view');
  });

  it('disables export button for non-complete maps', () => {
    const draftMap = { ...mockMap, status: 'draft' as const };
    render(<MapCard map={draftMap} onAction={mockOnAction} />);

    // Find export button (the one with download icon)
    const exportButton = screen.getByTitle('Export');
    expect(exportButton).toBeDisabled();
  });

  it('enables export button for complete maps', () => {
    render(<MapCard map={mockMap} onAction={mockOnAction} />);

    const exportButton = screen.getByTitle('Export');
    expect(exportButton).not.toBeDisabled();
  });

  it('handles duplicate action', async () => {
    const user = userEvent.setup();
    render(<MapCard map={mockMap} onAction={mockOnAction} />);

    const duplicateButton = screen.getByTitle('Duplicate');
    await user.click(duplicateButton);

    expect(mockOnAction).toHaveBeenCalledWith('map-1', 'duplicate');
  });
});
