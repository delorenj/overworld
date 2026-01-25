/**
 * Map Card Component
 *
 * Displays a single map item with preview, status, and action buttons.
 * Used in the MapGallery grid layout.
 */

import { useState } from 'react';
import { Eye, Edit, Trash2, Download, Copy, MoreVertical, Loader2 } from 'lucide-react';
import { Card, CardContent, CardFooter } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';
import { cn } from '../../lib/utils';
import { formatDate } from '../../lib/utils';
import type { MapItem, MapStatus, MapAction } from '../../types/dashboard';

interface MapCardProps {
  map: MapItem;
  onAction?: (mapId: string, action: MapAction) => void;
}

/**
 * Get badge variant based on map status
 */
function getStatusBadgeVariant(status: MapStatus): 'default' | 'secondary' | 'success' | 'warning' | 'destructive' {
  switch (status) {
    case 'complete':
      return 'success';
    case 'generating':
      return 'warning';
    case 'draft':
      return 'secondary';
    case 'error':
      return 'destructive';
    default:
      return 'default';
  }
}

/**
 * Get status display text
 */
function getStatusText(status: MapStatus): string {
  switch (status) {
    case 'complete':
      return 'Complete';
    case 'generating':
      return 'Generating';
    case 'draft':
      return 'Draft';
    case 'error':
      return 'Error';
    default:
      return status;
  }
}

export function MapCard({ map, onAction }: MapCardProps) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  const handleAction = (action: MapAction) => {
    if (action === 'delete') {
      setShowDeleteDialog(true);
    } else {
      onAction?.(map.id, action);
    }
  };

  const confirmDelete = () => {
    onAction?.(map.id, 'delete');
    setShowDeleteDialog(false);
  };

  const isGenerating = map.status === 'generating';

  return (
    <>
      <Card
        className={cn(
          'group overflow-hidden transition-all duration-200',
          'hover:shadow-lg hover:border-primary/50'
        )}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {/* Thumbnail */}
        <div className="relative aspect-video overflow-hidden bg-muted">
          {map.thumbnailUrl ? (
            <img
              src={map.thumbnailUrl}
              alt={map.title}
              className={cn(
                'w-full h-full object-cover transition-transform duration-300',
                isHovered && 'scale-105'
              )}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              No preview available
            </div>
          )}

          {/* Generating Overlay */}
          {isGenerating && (
            <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
              <div className="text-white text-center">
                <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
                <span className="text-sm">Generating...</span>
              </div>
            </div>
          )}

          {/* Hover Actions Overlay */}
          <div
            className={cn(
              'absolute inset-0 bg-black/60 flex items-center justify-center gap-2 transition-opacity duration-200',
              isHovered && !isGenerating ? 'opacity-100' : 'opacity-0'
            )}
          >
            <Button
              size="sm"
              variant="secondary"
              onClick={() => handleAction('view')}
              disabled={isGenerating}
            >
              <Eye className="h-4 w-4 mr-1" />
              View
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => handleAction('edit')}
              disabled={isGenerating}
            >
              <Edit className="h-4 w-4 mr-1" />
              Edit
            </Button>
          </div>

          {/* Status Badge */}
          <Badge
            variant={getStatusBadgeVariant(map.status)}
            className="absolute top-2 right-2"
          >
            {isGenerating && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
            {getStatusText(map.status)}
          </Badge>
        </div>

        {/* Content */}
        <CardContent className="p-4">
          <h3 className="font-semibold text-foreground truncate" title={map.title}>
            {map.title}
          </h3>
          {map.description && (
            <p className="text-sm text-muted-foreground truncate mt-1" title={map.description}>
              {map.description}
            </p>
          )}
          <p className="text-xs text-muted-foreground mt-2">
            Created {formatDate(map.createdAt)}
          </p>
        </CardContent>

        {/* Footer Actions */}
        <CardFooter className="p-4 pt-0 flex justify-between items-center">
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => handleAction('export')}
              disabled={map.status !== 'complete'}
              title="Export"
            >
              <Download className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => handleAction('duplicate')}
              title="Duplicate"
            >
              <Copy className="h-4 w-4" />
            </Button>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreVertical className="h-4 w-4" />
                <span className="sr-only">More options</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleAction('view')}>
                <Eye className="mr-2 h-4 w-4" />
                View
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleAction('edit')}>
                <Edit className="mr-2 h-4 w-4" />
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleAction('export')} disabled={map.status !== 'complete'}>
                <Download className="mr-2 h-4 w-4" />
                Export
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleAction('duplicate')}>
                <Copy className="mr-2 h-4 w-4" />
                Duplicate
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => handleAction('delete')}
                className="text-destructive"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardFooter>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Map</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{map.title}&quot;? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
