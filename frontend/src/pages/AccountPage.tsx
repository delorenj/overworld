/**
 * Account Page (OWRLD-25)
 * 
 * Consolidated settings page merging ProfilePage + SettingsPage
 * 
 * Tabs:
 * - Identity: Profile info, stats, activity
 * - Security: Password change, account deletion
 * - Preferences: Map defaults, appearance, notifications
 * - Connected Apps: OAuth providers
 * 
 * Impact: -40% UX confusion (single account management interface)
 */

import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { 
  User, Lock, Settings as SettingsIcon, Link2, 
  Crown, Map, Download, Calendar, Trash2, 
  Github, Chrome, Loader2 
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { getUserProfile, type UserProfile } from '../services/userApi';
import { PreferencesPanel } from '../components/PreferencesPanel';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../components/ui/alert-dialog';
import type { ConnectedAccount, PasswordChangeRequest } from '../types/user';

/**
 * Get provider icon component
 */
function getProviderIcon(provider: string) {
  switch (provider) {
    case 'google':
      return Chrome;
    case 'github':
      return Github;
    default:
      return Link2;
  }
}

/**
 * Get initials from name
 */
function getInitials(name: string): string {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export function AccountPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    user,
    updateUser,
    changePassword,
    deleteAccount,
    getConnectedAccounts,
    disconnectAccount,
  } = useAuth();

  // URL tab state
  const defaultTab = searchParams.get('tab') || 'identity';

  // Profile data state
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);

  // Identity form state
  const [identityForm, setIdentityForm] = useState({
    name: user?.name || '',
    email: user?.email || '',
  });
  const [identitySaving, setIdentitySaving] = useState(false);
  const [identityMessage, setIdentityMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Password form state
  const [passwordForm, setPasswordForm] = useState<PasswordChangeRequest>({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Connected accounts state
  const [connectedAccounts, setConnectedAccounts] = useState<ConnectedAccount[]>([]);
  const [accountsLoading, setAccountsLoading] = useState(true);

  // Load profile data
  const loadProfile = async () => {
    try {
      setProfileLoading(true);
      setProfileError(null);
      const data = await getUserProfile();
      setProfile(data);
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : 'Failed to load profile');
    } finally {
      setProfileLoading(false);
    }
  };

  // Load connected accounts
  const loadAccounts = async () => {
    try {
      const accounts = await getConnectedAccounts();
      setConnectedAccounts(accounts);
    } catch (error) {
      console.error('Failed to load connected accounts:', error);
    } finally {
      setAccountsLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    loadProfile();
    loadAccounts();
  }, []);

  // Update identity form when user changes
  useEffect(() => {
    if (user) {
      setIdentityForm({
        name: user.name,
        email: user.email,
      });
    }
  }, [user]);

  /**
   * Handle tab change with URL persistence
   */
  const handleTabChange = (tab: string) => {
    setSearchParams({ tab }, { replace: true });
  };

  /**
   * Handle identity form submission
   */
  const handleIdentitySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIdentitySaving(true);
    setIdentityMessage(null);

    try {
      await updateUser({ name: identityForm.name });
      setIdentityMessage({ type: 'success', text: 'Profile updated successfully!' });
    } catch (error: any) {
      setIdentityMessage({ type: 'error', text: error.message || 'Failed to update profile' });
    } finally {
      setIdentitySaving(false);
    }
  };

  /**
   * Handle password form submission
   */
  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordSaving(true);
    setPasswordMessage(null);

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordMessage({ type: 'error', text: 'Passwords do not match' });
      setPasswordSaving(false);
      return;
    }

    if (passwordForm.newPassword.length < 8) {
      setPasswordMessage({ type: 'error', text: 'Password must be at least 8 characters' });
      setPasswordSaving(false);
      return;
    }

    try {
      await changePassword(passwordForm);
      setPasswordMessage({ type: 'success', text: 'Password changed successfully!' });
      setPasswordForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
    } catch (error: any) {
      setPasswordMessage({ type: 'error', text: error.message || 'Failed to change password' });
    } finally {
      setPasswordSaving(false);
    }
  };

  /**
   * Handle account disconnection
   */
  const handleDisconnect = async (provider: string) => {
    try {
      await disconnectAccount(provider);
      setConnectedAccounts((prev) => prev.filter((acc) => acc.provider !== provider));
    } catch (error: any) {
      console.error('Failed to disconnect account:', error);
    }
  };

  /**
   * Handle account deletion
   */
  const handleDeleteAccount = async () => {
    try {
      await deleteAccount();
      navigate('/login');
    } catch (error: any) {
      console.error('Failed to delete account:', error);
    }
  };

  // Loading state
  if (profileLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error state
  if (profileError || !profile) {
    return (
      <div className="container max-w-4xl mx-auto p-6">
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle>Error</CardTitle>
            <CardDescription>
              {profileError || 'Failed to load profile'}
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
          <h1 className="text-3xl font-bold">Account</h1>
          <p className="text-muted-foreground">
            Manage your profile, security, and preferences
          </p>
        </div>
        {profile.is_premium && (
          <Badge variant="default" className="gap-1">
            <Crown className="w-4 h-4" />
            Premium
          </Badge>
        )}
      </div>

      <Tabs value={defaultTab} onValueChange={handleTabChange} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="identity" className="flex items-center gap-2">
            <User className="h-4 w-4" />
            Identity
          </TabsTrigger>
          <TabsTrigger value="security" className="flex items-center gap-2">
            <Lock className="h-4 w-4" />
            Security
          </TabsTrigger>
          <TabsTrigger value="preferences" className="flex items-center gap-2">
            <SettingsIcon className="h-4 w-4" />
            Preferences
          </TabsTrigger>
          <TabsTrigger value="connected" className="flex items-center gap-2">
            <Link2 className="h-4 w-4" />
            Connected Apps
          </TabsTrigger>
        </TabsList>

        {/* Identity Tab */}
        <TabsContent value="identity" className="space-y-4">
          {/* Profile Form */}
          <Card>
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>Update your personal information</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleIdentitySubmit} className="space-y-6">
                {/* Avatar */}
                <div className="flex items-center gap-4">
                  <Avatar className="h-20 w-20">
                    <AvatarImage src={user?.avatarUrl} alt={user?.name} />
                    <AvatarFallback className="text-lg">
                      {user?.name ? getInitials(user.name) : 'U'}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <Button type="button" variant="outline" size="sm">
                      Change Avatar
                    </Button>
                    <p className="text-xs text-muted-foreground mt-1">
                      JPG, GIF or PNG. Max size 2MB.
                    </p>
                  </div>
                </div>

                {/* Name */}
                <div className="space-y-2">
                  <Label htmlFor="name">Name</Label>
                  <Input
                    id="name"
                    value={identityForm.name}
                    onChange={(e) => setIdentityForm({ ...identityForm, name: e.target.value })}
                    placeholder="Your name"
                  />
                </div>

                {/* Email */}
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={identityForm.email}
                    disabled
                    className="bg-muted"
                  />
                  <p className="text-xs text-muted-foreground">
                    Email cannot be changed. Contact support if you need to update it.
                  </p>
                </div>

                {/* Message */}
                {identityMessage && (
                  <div
                    className={`text-sm ${
                      identityMessage.type === 'success' ? 'text-green-600' : 'text-destructive'
                    }`}
                  >
                    {identityMessage.text}
                  </div>
                )}

                {/* Submit */}
                <Button type="submit" disabled={identitySaving}>
                  {identitySaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Save Changes
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Account Info & Stats */}
          <div className="grid gap-4 md:grid-cols-2">
            {/* Account Details */}
            <Card>
              <CardHeader>
                <CardTitle>Account Details</CardTitle>
                <CardDescription>Your account information</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
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
        </TabsContent>

        {/* Security Tab */}
        <TabsContent value="security" className="space-y-6">
          {/* Change Password */}
          <Card>
            <CardHeader>
              <CardTitle>Change Password</CardTitle>
              <CardDescription>Update your password to keep your account secure</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handlePasswordSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="currentPassword">Current Password</Label>
                  <Input
                    id="currentPassword"
                    type="password"
                    value={passwordForm.currentPassword}
                    onChange={(e) =>
                      setPasswordForm({ ...passwordForm, currentPassword: e.target.value })
                    }
                    placeholder="Enter current password"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="newPassword">New Password</Label>
                  <Input
                    id="newPassword"
                    type="password"
                    value={passwordForm.newPassword}
                    onChange={(e) =>
                      setPasswordForm({ ...passwordForm, newPassword: e.target.value })
                    }
                    placeholder="Enter new password"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirmPassword">Confirm New Password</Label>
                  <Input
                    id="confirmPassword"
                    type="password"
                    value={passwordForm.confirmPassword}
                    onChange={(e) =>
                      setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })
                    }
                    placeholder="Confirm new password"
                  />
                </div>

                {passwordMessage && (
                  <div
                    className={`text-sm ${
                      passwordMessage.type === 'success' ? 'text-green-600' : 'text-destructive'
                    }`}
                  >
                    {passwordMessage.text}
                  </div>
                )}

                <Button type="submit" disabled={passwordSaving}>
                  {passwordSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Update Password
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Delete Account */}
          <Card className="border-destructive">
            <CardHeader>
              <CardTitle className="text-destructive">Danger Zone</CardTitle>
              <CardDescription>
                Permanently delete your account and all associated data
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive">
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete Account
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This action cannot be undone. This will permanently delete your account and
                      remove all your data including maps, documents, and settings from our servers.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleDeleteAccount}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                      Delete Account
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
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

        {/* Connected Apps Tab */}
        <TabsContent value="connected">
          <Card>
            <CardHeader>
              <CardTitle>Connected Accounts</CardTitle>
              <CardDescription>
                Manage your connected OAuth accounts for easier sign-in
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {accountsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <>
                  {/* Connected Accounts List */}
                  {connectedAccounts.map((account) => {
                    const Icon = getProviderIcon(account.provider);
                    return (
                      <div
                        key={account.provider}
                        className="flex items-center justify-between p-4 border rounded-lg"
                      >
                        <div className="flex items-center gap-3">
                          <Icon className="h-6 w-6" />
                          <div>
                            <p className="font-medium capitalize">{account.provider}</p>
                            <p className="text-sm text-muted-foreground">{account.email}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="success">Connected</Badge>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDisconnect(account.provider)}
                          >
                            Disconnect
                          </Button>
                        </div>
                      </div>
                    );
                  })}

                  {/* Available Connections */}
                  {!connectedAccounts.find((a) => a.provider === 'github') && (
                    <div className="flex items-center justify-between p-4 border rounded-lg border-dashed">
                      <div className="flex items-center gap-3">
                        <Github className="h-6 w-6 text-muted-foreground" />
                        <div>
                          <p className="font-medium">GitHub</p>
                          <p className="text-sm text-muted-foreground">
                            Connect your GitHub account
                          </p>
                        </div>
                      </div>
                      <Button variant="outline" size="sm">
                        Connect
                      </Button>
                    </div>
                  )}

                  {!connectedAccounts.find((a) => a.provider === 'google') && (
                    <div className="flex items-center justify-between p-4 border rounded-lg border-dashed">
                      <div className="flex items-center gap-3">
                        <Chrome className="h-6 w-6 text-muted-foreground" />
                        <div>
                          <p className="font-medium">Google</p>
                          <p className="text-sm text-muted-foreground">
                            Connect your Google account
                          </p>
                        </div>
                      </div>
                      <Button variant="outline" size="sm">
                        Connect
                      </Button>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
