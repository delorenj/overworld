/**
 * Profile Page (OWRLD-20)
 * 
 * Displays user profile with:
 * - Identity (email, premium badge)
 * - Activity stats (maps created, exports)
 * - Preferences panel
 * 
 * Backend API: Lenoon (commit b5d64f3)
 */

import { useState, useEffect } from 'react';
import { Crown, Map, Download, Calendar, Settings as SettingsIcon, Loader2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { getUserProfile, type UserProfile } from '../services/userApi';
import { PreferencesPanel } from '../components/PreferencesPanel';

export function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getUserProfile();
      setProfile(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="container max-w-4xl mx-auto p-6">
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle>Error</CardTitle>
            <CardDescription>
              {error || 'Failed to load profile'}
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const memberSince = new Date(profile.history.member_since).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
  });

  return (
    <div className="container max-w-6xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Profile</h1>
          <p className="text-muted-foreground">
            Manage your account settings and preferences
          </p>
        </div>
        {profile.is_premium && (
          <Badge variant="default" className="gap-1">
            <Crown className="w-4 h-4" />
            Premium
          </Badge>
        )}
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="preferences">
            <SettingsIcon className="w-4 h-4 mr-2" />
            Preferences
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Account Info */}
            <Card>
              <CardHeader>
                <CardTitle>Account Information</CardTitle>
                <CardDescription>Your basic account details</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <div className="text-sm font-medium text-muted-foreground">Email</div>
                  <div className="text-sm">{profile.email}</div>
                </div>

                <div>
                  <div className="text-sm font-medium text-muted-foreground">Account Type</div>
                  <div className="flex items-center gap-2 mt-1">
                    <Badge variant={profile.is_premium ? 'default' : 'secondary'}>
                      {profile.is_premium ? 'Premium' : 'Free'}
                    </Badge>
                    {profile.is_verified && (
                      <Badge variant="outline">Verified</Badge>
                    )}
                  </div>
                </div>

                {profile.oauth_provider && (
                  <div>
                    <div className="text-sm font-medium text-muted-foreground">Sign-in Method</div>
                    <div className="text-sm capitalize">{profile.oauth_provider}</div>
                  </div>
                )}

                <div>
                  <div className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                    <Calendar className="w-4 h-4" />
                    Member Since
                  </div>
                  <div className="text-sm">{memberSince}</div>
                </div>
              </CardContent>
            </Card>

            {/* Activity Stats */}
            <Card>
              <CardHeader>
                <CardTitle>Activity</CardTitle>
                <CardDescription>Your usage statistics</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Map className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm">Maps Created</span>
                  </div>
                  <span className="text-2xl font-bold">{profile.history.total_maps_created}</span>
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Download className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm">Exports Generated</span>
                  </div>
                  <span className="text-2xl font-bold">{profile.history.total_exports}</span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Preferences Preview */}
          <Card>
            <CardHeader>
              <CardTitle>Current Preferences</CardTitle>
              <CardDescription>Your default settings</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-3">
                <div>
                  <div className="text-sm font-medium text-muted-foreground">Color Mode</div>
                  <div className="text-sm capitalize">{profile.preferences.color_mode}</div>
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground">Default Visibility</div>
                  <div className="text-sm capitalize">{profile.preferences.default_map_visibility}</div>
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground">Notifications</div>
                  <div className="text-sm">{profile.preferences.notifications_enabled ? 'Enabled' : 'Disabled'}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Preferences Tab */}
        <TabsContent value="preferences">
          <PreferencesPanel 
            initialPreferences={profile.preferences} 
            onUpdate={loadProfile}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
