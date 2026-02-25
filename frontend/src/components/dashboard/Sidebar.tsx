/**
 * Dashboard Sidebar Component
 *
 * Navigation sidebar with links to dashboard sections.
 * Supports collapsed/expanded state for responsive design.
 */

import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Map, Settings, Upload, ChevronLeft, ChevronRight, User } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from '../ui/button';

interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

interface NavItem {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}

const navItems: NavItem[] = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/dashboard/maps', icon: Map, label: 'My Maps' },
  { to: '/dashboard/upload', icon: Upload, label: 'Upload' },
  { to: '/dashboard/profile', icon: User, label: 'Profile' },
  { to: '/dashboard/settings', icon: Settings, label: 'Settings' },
];

export function Sidebar({ collapsed = false, onToggle }: SidebarProps) {
  return (
    <aside
      className={cn(
        'flex flex-col h-full bg-card border-r border-border transition-all duration-300',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Logo/Brand */}
      <div className="flex items-center h-16 px-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-primary-foreground font-bold">
            O
          </div>
          {!collapsed && (
            <span className="text-lg font-semibold text-foreground">Overworld</span>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/dashboard'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                'hover:bg-accent hover:text-accent-foreground',
                isActive
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground',
                collapsed && 'justify-center'
              )
            }
          >
            <item.icon className="h-5 w-5 flex-shrink-0" />
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Collapse Toggle */}
      {onToggle && (
        <div className="p-2 border-t border-border">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggle}
            className={cn('w-full', collapsed ? 'justify-center' : 'justify-start')}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4 mr-2" />
                Collapse
              </>
            )}
          </Button>
        </div>
      )}
    </aside>
  );
}
