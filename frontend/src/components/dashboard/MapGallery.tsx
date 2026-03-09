/**
 * Map Gallery Component
 *
 * Displays a grid of map cards with filtering and sorting options.
 * Supports loading states and empty states.
 */

import { useState, useMemo, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, SlidersHorizontal, Grid, List, X } from 'lucide-react';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
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
import { OnboardingEmptyState } from './OnboardingEmptyState';
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
  const [searchParams, setSearchParams] = useSearchParams();
  const searchInputRef = useRef<HTMLInputElement>(null);
  
  // Initialize filters from URL params
  const [filters, setFilters] = useState<MapFilters>({
    status: (searchParams.get('status') as MapStatus) || 'all',
    sortBy: (searchParams.get('sortBy') as 'createdAt' | 'updatedAt' | 'title') || 'updatedAt',
    sortOrder: (searchParams.get('sortOrder') as 'asc' | 'desc') || 'desc',
    search: searchParams.get('search') || '',
  });
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // Sync filters to URL params
  useEffect(() => {
    const params = new URLSearchParams();
    if (filters.search) params.set('search', filters.search);
    if (filters.status && filters.status !== 'all') params.set('status', filters.status);
    if (filters.sortBy && filters.sortBy !== 'updatedAt') params.set('sortBy', filters.sortBy);
    if (filters.sortOrder && filters.sortOrder !== 'desc') params.set('sortOrder', filters.sortOrder);
    
    setSearchParams(params, { replace: true });
  }, [filters, setSearchParams]);

  // Keyboard shortcut: Cmd/Ctrl+K to focus search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

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

  // Check if any filters are active
  const hasActiveFilters = 
    filters.search !== '' ||
    (filters.status !== 'all' && filters.status !== undefined) ||
    filters.sortBy !== 'updatedAt' ||
    filters.sortOrder !== 'desc';

  // Get active filter count
  const activeFilterCount = [
    filters.search !== '',
    filters.status !== 'all' && filters.status !== undefined,
    filters.sortBy !== 'updatedAt',
    filters.sortOrder !== 'desc',
  ].filter(Boolean).length;

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

  // Empty state - show interactive onboarding for first-time users
  if (maps.length === 0) {
    return <OnboardingEmptyState />;
  }

  return (
    <div className={className}>
      {/* Filters and Controls */}
      {showFilters && (
        <div className="space-y-3 mb-4">
          <div className="flex flex-col sm:flex-row gap-4">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                ref={searchInputRef}
                placeholder="Search maps... (⌘K)"
                value={filters.search}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                className="pl-9 pr-10"
              />
              {filters.search && (
                <button
                  onClick={() => setFilters({ ...filters, search: '' })}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label="Clear search"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            {/* Filter/Sort Dropdown */}
            <div className="flex gap-2">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" className="relative">
                    <SlidersHorizontal className="h-4 w-4 mr-2" />
                    Filters
                    {activeFilterCount > 0 && (
                      <Badge 
                        variant="default" 
                        className="ml-2 h-5 min-w-5 px-1.5 text-xs"
                      >
                        {activeFilterCount}
                      </Badge>
                    )}
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

              {/* Clear All Filters */}
              {hasActiveFilters && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearFilters}
                  className="text-muted-foreground"
                >
                  <X className="h-4 w-4 mr-1" />
                  Clear
                </Button>
              )}
            </div>
          </div>

          {/* Active Filters & Result Count */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Result Count */}
            <span className="text-sm text-muted-foreground">
              {filteredMaps.length === maps.length ? (
                <>
                  <strong className="text-foreground">{maps.length}</strong> map
                  {maps.length !== 1 && 's'}
                </>
              ) : (
                <>
                  <strong className="text-foreground">{filteredMaps.length}</strong> of{' '}
                  <strong className="text-foreground">{maps.length}</strong> map
                  {maps.length !== 1 && 's'}
                </>
              )}
            </span>

            {/* Active Filter Badges */}
            {filters.status && filters.status !== 'all' && (
              <Badge variant="secondary" className="gap-1">
                Status: {filters.status}
                <button
                  onClick={() => setFilters({ ...filters, status: 'all' })}
                  className="hover:bg-muted rounded-sm"
                  aria-label="Remove status filter"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            )}

            {filters.sortBy && filters.sortBy !== 'updatedAt' && (
              <Badge variant="secondary" className="gap-1">
                Sort: {filters.sortBy === 'createdAt' ? 'Created' : filters.sortBy}
                <button
                  onClick={() => setFilters({ ...filters, sortBy: 'updatedAt' })}
                  className="hover:bg-muted rounded-sm"
                  aria-label="Remove sort filter"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            )}

            {filters.sortOrder && filters.sortOrder !== 'desc' && (
              <Badge variant="secondary" className="gap-1">
                Order: {filters.sortOrder === 'asc' ? 'Oldest first' : 'Newest first'}
                <button
                  onClick={() => setFilters({ ...filters, sortOrder: 'desc' })}
                  className="hover:bg-muted rounded-sm"
                  aria-label="Remove order filter"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            )}
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
