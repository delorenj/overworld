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
import { StatusBadge } from '../StatusBadge';
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
import type { MapItem, MapAction } from '../../types/dashboard';

interface MapCardProps {
  map: MapItem;
  onAction?: (mapId: string, action: MapAction) => void;
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
          <StatusBadge
            status={map.status}
            className="absolute top-2 right-2"
            size="sm"
          />
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
        <CardFooter className="p-4 pt-0 flex flex-col gap-2">
          {/* Primary Action: Export (Always Visible) */}
          <Button
            className="w-full"
            variant={map.status === 'complete' ? 'default' : 'secondary'}
            size="sm"
            onClick={() => handleAction('export')}
            disabled={map.status !== 'complete'}
          >
            <Download className="h-4 w-4 mr-2" />
            {map.status === 'complete' ? 'Download' : 'Not Ready'}
          </Button>

          {/* Secondary Actions */}
          <div className="flex gap-1 w-full">
            <Button
              variant="outline"
              size="sm"
              className="flex-1"
              onClick={() => handleAction('edit')}
              disabled={isGenerating}
            >
              <Edit className="h-4 w-4 mr-1" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1"
              onClick={() => handleAction('view')}
              disabled={isGenerating}
            >
              <Eye className="h-4 w-4 mr-1" />
              View
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="px-2">
                  <MoreVertical className="h-4 w-4" />
                  <span className="sr-only">More options</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
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
          </div>
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
