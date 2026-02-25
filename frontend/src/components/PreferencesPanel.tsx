/**
 * Preferences Panel Component (OWRLD-20)
 * 
 * Editable user preferences:
 * - Default theme
 * - Map visibility
 * - Color mode
 * - Notifications
 * - Auto-watermark
 * 
 * Backend: PATCH /users/me/preferences (Lenoon)
 */

import { useState } from 'react';
import { Save, Loader2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from './ui/select';
import { Switch } from './ui/switch';
import { updateUserPreferences, type UserPreferences, type UserPreferencesUpdate } from '../services/userApi';

interface PreferencesPanelProps {
  initialPreferences: UserPreferences;
  onUpdate?: () => void;
}

export function PreferencesPanel({ initialPreferences, onUpdate }: PreferencesPanelProps) {
  const [preferences, setPreferences] = useState<UserPreferences>(initialPreferences);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleSave = async () => {
    try {
      setSaving(true);
      setMessage(null);

      const updates: UserPreferencesUpdate = {
        default_theme_id: preferences.default_theme_id,
        default_map_visibility: preferences.default_map_visibility,
        color_mode: preferences.color_mode,
        language: preferences.language,
        notifications_enabled: preferences.notifications_enabled,
        email_marketing: preferences.email_marketing,
        auto_watermark: preferences.auto_watermark,
      };

      await updateUserPreferences(updates);
      
      setMessage({ type: 'success', text: 'Preferences saved successfully' });
      
      if (onUpdate) {
        onUpdate();
      }

      // Clear message after 3 seconds
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      setMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to save preferences',
      });
    } finally {
      setSaving(false);
    }
  };

  const updatePreference = <K extends keyof UserPreferences>(
    key: K,
    value: UserPreferences[K]
  ) => {
    setPreferences((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="space-y-4">
      {/* Map Defaults */}
      <Card>
        <CardHeader>
          <CardTitle>Map Defaults</CardTitle>
          <CardDescription>
            Default settings for new maps
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="default-visibility">Default Visibility</Label>
            <Select
              value={preferences.default_map_visibility}
              onValueChange={(value: 'private' | 'unlisted' | 'public') =>
                updatePreference('default_map_visibility', value)
              }
            >
              <SelectTrigger id="default-visibility">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="private">Private (only you)</SelectItem>
                <SelectItem value="unlisted">Unlisted (link only)</SelectItem>
                <SelectItem value="public">Public (discoverable)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between space-x-2">
            <div className="space-y-0.5">
              <Label htmlFor="auto-watermark">Auto-apply Watermark</Label>
              <div className="text-sm text-muted-foreground">
                Automatically watermark exports on free tier
              </div>
            </div>
            <Switch
              id="auto-watermark"
              checked={preferences.auto_watermark}
              onCheckedChange={(checked) => updatePreference('auto_watermark', checked)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Appearance */}
      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>
            Customize how Overworld looks
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="color-mode">Color Mode</Label>
            <Select
              value={preferences.color_mode}
              onValueChange={(value: 'light' | 'dark' | 'system') =>
                updatePreference('color_mode', value)
              }
            >
              <SelectTrigger id="color-mode">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="light">Light</SelectItem>
                <SelectItem value="dark">Dark</SelectItem>
                <SelectItem value="system">System Default</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="language">Language</Label>
            <Select
              value={preferences.language}
              onValueChange={(value) => updatePreference('language', value)}
            >
              <SelectTrigger id="language">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="es">Español</SelectItem>
                <SelectItem value="fr">Français</SelectItem>
                <SelectItem value="de">Deutsch</SelectItem>
                <SelectItem value="ja">日本語</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Notifications */}
      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
          <CardDescription>
            Manage email and in-app notifications
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between space-x-2">
            <div className="space-y-0.5">
              <Label htmlFor="notifications">Email Notifications</Label>
              <div className="text-sm text-muted-foreground">
                Receive updates about your maps and exports
              </div>
            </div>
            <Switch
              id="notifications"
              checked={preferences.notifications_enabled}
              onCheckedChange={(checked) => updatePreference('notifications_enabled', checked)}
            />
          </div>

          <div className="flex items-center justify-between space-x-2">
            <div className="space-y-0.5">
              <Label htmlFor="marketing">Marketing Emails</Label>
              <div className="text-sm text-muted-foreground">
                Product updates and feature announcements
              </div>
            </div>
            <Switch
              id="marketing"
              checked={preferences.email_marketing}
              onCheckedChange={(checked) => updatePreference('email_marketing', checked)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex items-center justify-between">
        <div>
          {message && (
            <p
              className={`text-sm ${
                message.type === 'success' ? 'text-green-600' : 'text-destructive'
              }`}
            >
              {message.text}
            </p>
          )}
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="w-4 h-4 mr-2" />
              Save Preferences
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
