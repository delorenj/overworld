/**
 * Dashboard Page
 *
 * Main dashboard overview showing recent maps and usage statistics.
 * This is the landing page after authentication.
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Map, TrendingUp, HardDrive, Coins } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Progress } from '../components/ui/progress';
import { MapGallery } from '../components/dashboard/MapGallery';
import type { UsageStats } from '../types/user';
import type { MapItem } from '../types/dashboard';
import { formatBytes } from '../lib/utils';

// Mock data for recent maps - replace with API call
const MOCK_RECENT_MAPS: MapItem[] = [
  {
    id: 'map-1',
    title: 'Project Architecture',
    description: 'System architecture overview',
    thumbnailUrl: 'https://via.placeholder.com/300x200/667eea/ffffff?text=Map+1',
    status: 'complete',
    createdAt: '2024-01-15T10:30:00Z',
    updatedAt: '2024-01-15T14:45:00Z',
    size: 1024000,
  },
  {
    id: 'map-2',
    title: 'API Documentation',
    description: 'REST API endpoints map',
    thumbnailUrl: 'https://via.placeholder.com/300x200/764ba2/ffffff?text=Map+2',
    status: 'generating',
    createdAt: '2024-01-14T09:00:00Z',
    updatedAt: '2024-01-14T09:15:00Z',
    size: 512000,
  },
  {
    id: 'map-3',
    title: 'User Flow Diagram',
    description: 'User journey visualization',
    thumbnailUrl: 'https://via.placeholder.com/300x200/f093fb/ffffff?text=Map+3',
    status: 'draft',
    createdAt: '2024-01-13T16:20:00Z',
    updatedAt: '2024-01-13T16:20:00Z',
    size: 256000,
  },
];

export function DashboardPage() {
  const { user, getUsageStats } = useAuth();
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [recentMaps, setRecentMaps] = useState<MapItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        const [usageStats] = await Promise.all([
          getUsageStats(),
          // TODO: Add API call for recent maps
        ]);
        setStats(usageStats);
        setRecentMaps(MOCK_RECENT_MAPS);
      } catch (error) {
        console.error('Failed to load dashboard data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadDashboardData();
  }, [getUsageStats]);

  const handleMapAction = (mapId: string, action: string) => {
    console.log(`Action ${action} on map ${mapId}`);
    // TODO: Implement map actions
  };

  return (
    <div className="space-y-6">
      {/* Welcome Section */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            Welcome back, {user?.name?.split(' ')[0] || 'User'}!
          </h1>
          <p className="text-muted-foreground">
            Here&apos;s an overview of your maps and usage.
          </p>
        </div>
        <Button asChild>
          <Link to="/dashboard/upload">
            <Plus className="mr-2 h-4 w-4" />
            New Map
          </Link>
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Token Balance</CardTitle>
            <Coins className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? '...' : stats?.tokenBalance.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats ? `${stats.tokensUsed.toLocaleString()} tokens used` : 'Loading...'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Maps Generated</CardTitle>
            <Map className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? '...' : stats?.mapsGenerated}
            </div>
            <p className="text-xs text-muted-foreground">Total maps created</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Storage Used</CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {isLoading ? '...' : formatBytes(stats?.storageUsed || 0)}
            </div>
            {stats && (
              <Progress
                value={(stats.storageUsed / stats.storageLimit) * 100}
                className="mt-2 h-2"
              />
            )}
            <p className="text-xs text-muted-foreground mt-1">
              {stats ? `of ${formatBytes(stats.storageLimit)}` : 'Loading...'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Usage Trend</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">+12%</div>
            <p className="text-xs text-muted-foreground">From last month</p>
          </CardContent>
        </Card>
      </div>

      {/* Recent Maps */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-foreground">Recent Maps</h2>
          <Button variant="ghost" asChild>
            <Link to="/dashboard/maps">View all</Link>
          </Button>
        </div>
        <MapGallery
          maps={recentMaps}
          isLoading={isLoading}
          onAction={handleMapAction}
          limit={3}
        />
      </div>
    </div>
  );
}
