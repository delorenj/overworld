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
import { BuyTokensModal } from '../components/tokens/BuyTokensModal';
import { getUserProfile } from '../services/userApi';
import { getRecentMaps } from '../services/mapsApi';
import type { UsageStats } from '../types/user';
import type { MapItem } from '../types/dashboard';
import { formatBytes } from '../lib/utils';

export function DashboardPage() {
  const { user, token } = useAuth();
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [recentMaps, setRecentMaps] = useState<MapItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        const [profile, maps] = await Promise.all([
          getUserProfile(),
          getRecentMaps(3),
        ]);

        // Transform profile data to stats format
        const usageStats: UsageStats = {
          tokenBalance: 0, // TODO: Wire token API when available
          tokensUsed: 0,
          mapsGenerated: profile.history.total_maps_created,
          storageUsed: 0, // TODO: Calculate from map sizes
          storageLimit: 10 * 1024 * 1024 * 1024, // 10GB default
        };

        setStats(usageStats);
        setRecentMaps(maps);
      } catch (error) {
        console.error('Failed to load dashboard data:', error);
        // Show empty state on error
        setRecentMaps([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadDashboardData();
  }, []);

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
            <div className="mt-3">
              <BuyTokensModal authToken={token} defaultEmail={user?.email} />
            </div>
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
