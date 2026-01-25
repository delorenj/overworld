/**
 * Map Gallery Component
 *
 * Displays a grid of map cards with filtering and sorting options.
 * Supports loading states and empty states.
 */

import { useState, useMemo } from 'react';
import { Search, SlidersHorizontal, Grid, List } from 'lucide-react';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import { MapCard } from './MapCard';
import { cn } from '../../lib/utils';
import type { MapItem, MapFilters, MapAction, MapStatus } from '../../types/dashboard';

interface MapGalleryProps {
  maps: MapItem[];
  isLoading?: boolean;
  onAction?: (mapId: string, action: MapAction) => void;
  limit?: number;
  showFilters?: boolean;
  className?: string;
}

/**
 * Skeleton loader for map cards
 */
function MapCardSkeleton() {
  return (
    <div className="rounded-lg border bg-card overflow-hidden animate-pulse">
      <div className="aspect-video bg-muted" />
      <div className="p-4 space-y-3">
        <div className="h-5 bg-muted rounded w-3/4" />
        <div className="h-4 bg-muted rounded w-1/2" />
        <div className="h-3 bg-muted rounded w-1/3" />
      </div>
      <div className="p-4 pt-0 flex justify-between">
        <div className="flex gap-2">
          <div className="h-8 w-8 bg-muted rounded" />
          <div className="h-8 w-8 bg-muted rounded" />
        </div>
        <div className="h-8 w-8 bg-muted rounded" />
      </div>
    </div>
  );
}

/**
 * Empty state when no maps exist
 */
function EmptyState() {
  return (
    <div className="text-center py-12">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-muted mb-4">
        <Grid className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium text-foreground mb-2">No maps yet</h3>
      <p className="text-muted-foreground mb-4">
        Upload a document to generate your first map.
      </p>
    </div>
  );
}

/**
 * No results state when filters don&apos;t match
 */
function NoResults({ onClear }: { onClear: () => void }) {
  return (
    <div className="text-center py-12">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-muted mb-4">
        <Search className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium text-foreground mb-2">No maps found</h3>
      <p className="text-muted-foreground mb-4">
        Try adjusting your search or filter criteria.
      </p>
      <Button variant="outline" onClick={onClear}>
        Clear filters
      </Button>
    </div>
  );
}

export function MapGallery({
  maps,
  isLoading = false,
  onAction,
  limit,
  showFilters = true,
  className,
}: MapGalleryProps) {
  const [filters, setFilters] = useState<MapFilters>({
    status: 'all',
    sortBy: 'updatedAt',
    sortOrder: 'desc',
    search: '',
  });
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // Filter and sort maps
  const filteredMaps = useMemo(() => {
    let result = [...maps];

    // Apply search filter
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      result = result.filter(
        (map) =>
          map.title.toLowerCase().includes(searchLower) ||
          map.description?.toLowerCase().includes(searchLower)
      );
    }

    // Apply status filter
    if (filters.status && filters.status !== 'all') {
      result = result.filter((map) => map.status === filters.status);
    }

    // Apply sorting
    if (filters.sortBy) {
      result.sort((a, b) => {
        let aVal: string | number = a[filters.sortBy!] as string;
        let bVal: string | number = b[filters.sortBy!] as string;

        if (filters.sortBy === 'title') {
          aVal = aVal.toLowerCase();
          bVal = bVal.toLowerCase();
        }

        if (aVal < bVal) return filters.sortOrder === 'asc' ? -1 : 1;
        if (aVal > bVal) return filters.sortOrder === 'asc' ? 1 : -1;
        return 0;
      });
    }

    // Apply limit
    if (limit) {
      result = result.slice(0, limit);
    }

    return result;
  }, [maps, filters, limit]);

  const clearFilters = () => {
    setFilters({
      status: 'all',
      sortBy: 'updatedAt',
      sortOrder: 'desc',
      search: '',
    });
  };

  // Loading state
  if (isLoading) {
    return (
      <div className={cn('grid gap-4 md:grid-cols-2 lg:grid-cols-3', className)}>
        {[1, 2, 3].map((i) => (
          <MapCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  // Empty state
  if (maps.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className={className}>
      {/* Filters and Controls */}
      {showFilters && (
        <div className="flex flex-col sm:flex-row gap-4 mb-4">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search maps..."
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              className="pl-9"
            />
          </div>

          {/* Filter/Sort Dropdown */}
          <div className="flex gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon">
                  <SlidersHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>Status</DropdownMenuLabel>
                <DropdownMenuRadioGroup
                  value={filters.status || 'all'}
                  onValueChange={(value) =>
                    setFilters({ ...filters, status: value as MapStatus | 'all' })
                  }
                >
                  <DropdownMenuRadioItem value="all">All</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="complete">Complete</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="generating">Generating</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="draft">Draft</DropdownMenuRadioItem>
                </DropdownMenuRadioGroup>

                <DropdownMenuSeparator />
                <DropdownMenuLabel>Sort By</DropdownMenuLabel>
                <DropdownMenuRadioGroup
                  value={filters.sortBy || 'updatedAt'}
                  onValueChange={(value) =>
                    setFilters({
                      ...filters,
                      sortBy: value as 'createdAt' | 'updatedAt' | 'title',
                    })
                  }
                >
                  <DropdownMenuRadioItem value="updatedAt">Last Updated</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="createdAt">Date Created</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="title">Title</DropdownMenuRadioItem>
                </DropdownMenuRadioGroup>

                <DropdownMenuSeparator />
                <DropdownMenuLabel>Order</DropdownMenuLabel>
                <DropdownMenuRadioGroup
                  value={filters.sortOrder || 'desc'}
                  onValueChange={(value) =>
                    setFilters({ ...filters, sortOrder: value as 'asc' | 'desc' })
                  }
                >
                  <DropdownMenuRadioItem value="desc">Newest First</DropdownMenuRadioItem>
                  <DropdownMenuRadioItem value="asc">Oldest First</DropdownMenuRadioItem>
                </DropdownMenuRadioGroup>
              </DropdownMenuContent>
            </DropdownMenu>

            {/* View Mode Toggle */}
            <div className="flex border rounded-md">
              <Button
                variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
                size="icon"
                onClick={() => setViewMode('grid')}
                className="rounded-r-none"
              >
                <Grid className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === 'list' ? 'secondary' : 'ghost'}
                size="icon"
                onClick={() => setViewMode('list')}
                className="rounded-l-none"
              >
                <List className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* No results */}
      {filteredMaps.length === 0 && maps.length > 0 && (
        <NoResults onClear={clearFilters} />
      )}

      {/* Map Grid */}
      {filteredMaps.length > 0 && (
        <div
          className={cn(
            viewMode === 'grid'
              ? 'grid gap-4 md:grid-cols-2 lg:grid-cols-3'
              : 'flex flex-col gap-4'
          )}
        >
          {filteredMaps.map((map) => (
            <MapCard key={map.id} map={map} onAction={onAction} />
          ))}
        </div>
      )}
    </div>
  );
}
