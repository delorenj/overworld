/**
 * Settings Page
 *
 * Account settings including profile info, password change,
 * connected accounts, and account deletion.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, Lock, Link2, Trash2, Github, Chrome, Loader2 } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
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
import { Badge } from '../components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
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

export function SettingsPage() {
  const navigate = useNavigate();
  const {
    user,
    updateUser,
    changePassword,
    deleteAccount,
    getConnectedAccounts,
    disconnectAccount,
  } = useAuth();

  // Profile form state
  const [profileForm, setProfileForm] = useState({
    name: user?.name || '',
    email: user?.email || '',
  });
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMessage, setProfileMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

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

  // Load connected accounts
  useEffect(() => {
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

    loadAccounts();
  }, [getConnectedAccounts]);

  // Update form when user changes
  useEffect(() => {
    if (user) {
      setProfileForm({
        name: user.name,
        email: user.email,
      });
    }
  }, [user]);

  /**
   * Handle profile form submission
   */
  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileSaving(true);
    setProfileMessage(null);

    try {
      await updateUser({ name: profileForm.name });
      setProfileMessage({ type: 'success', text: 'Profile updated successfully!' });
    } catch (error: any) {
      setProfileMessage({ type: 'error', text: error.message || 'Failed to update profile' });
    } finally {
      setProfileSaving(false);
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

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground">Manage your account settings and preferences.</p>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList>
          <TabsTrigger value="profile" className="flex items-center gap-2">
            <User className="h-4 w-4" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="security" className="flex items-center gap-2">
            <Lock className="h-4 w-4" />
            Security
          </TabsTrigger>
          <TabsTrigger value="connections" className="flex items-center gap-2">
            <Link2 className="h-4 w-4" />
            Connections
          </TabsTrigger>
        </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile">
          <Card>
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>Update your personal information and email address.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleProfileSubmit} className="space-y-6">
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
                    value={profileForm.name}
                    onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                    placeholder="Your name"
                  />
                </div>

                {/* Email */}
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={profileForm.email}
                    disabled
                    className="bg-muted"
                  />
                  <p className="text-xs text-muted-foreground">
                    Email cannot be changed. Contact support if you need to update it.
                  </p>
                </div>

                {/* Message */}
                {profileMessage && (
                  <div
                    className={`text-sm ${
                      profileMessage.type === 'success' ? 'text-green-600' : 'text-destructive'
                    }`}
                  >
                    {profileMessage.text}
                  </div>
                )}

                {/* Submit */}
                <Button type="submit" disabled={profileSaving}>
                  {profileSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Save Changes
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security Tab */}
        <TabsContent value="security" className="space-y-6">
          {/* Change Password */}
          <Card>
            <CardHeader>
              <CardTitle>Change Password</CardTitle>
              <CardDescription>Update your password to keep your account secure.</CardDescription>
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
                Permanently delete your account and all associated data.
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

        {/* Connections Tab */}
        <TabsContent value="connections">
          <Card>
            <CardHeader>
              <CardTitle>Connected Accounts</CardTitle>
              <CardDescription>
                Manage your connected OAuth accounts for easier sign-in.
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
