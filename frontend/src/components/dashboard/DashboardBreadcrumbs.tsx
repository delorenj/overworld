/**
 * Dashboard Breadcrumbs Component
 * 
 * Automatic breadcrumb generation based on current route.
 * Shows navigation hierarchy: Dashboard → Section → Page
 * 
 * From UX Audit P1 Item #8:
 * - Impact: -20% back-clicks (users always know where they are)
 */

import { Link, useLocation } from 'react-router-dom';
import { Home } from 'lucide-react';
import {
  Breadcrumb,
  BreadcrumbList,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '../ui/breadcrumb';

interface BreadcrumbSegment {
  label: string;
  href?: string;
  isCurrentPage?: boolean;
}

/**
 * Generate breadcrumb segments from pathname
 */
function generateBreadcrumbs(pathname: string): BreadcrumbSegment[] {
  const segments: BreadcrumbSegment[] = [];

  // Always start with Dashboard
  if (pathname !== '/dashboard') {
    segments.push({
      label: 'Dashboard',
      href: '/dashboard',
    });
  }

  // Parse pathname segments
  const parts = pathname.split('/').filter(Boolean);

  // Handle different routes
  if (parts.includes('dashboard')) {
    const afterDashboard = parts.slice(parts.indexOf('dashboard') + 1);

    afterDashboard.forEach((part, index) => {
      const isLast = index === afterDashboard.length - 1;
      
      // Build href up to this point
      const hrefParts = parts.slice(0, parts.indexOf('dashboard') + 1 + index + 1);
      const href = '/' + hrefParts.join('/');

      // Format label
      let label = part
        .split('-')
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');

      // Special cases for better labels
      const labelMap: Record<string, string> = {
        'maps': 'My Maps',
        'upload': 'Upload',
        'profile': 'Profile',
        'settings': 'Settings',
      };

      label = labelMap[part.toLowerCase()] || label;

      segments.push({
        label,
        href: isLast ? undefined : href,
        isCurrentPage: isLast,
      });
    });
  }

  return segments;
}

export function DashboardBreadcrumbs() {
  const location = useLocation();
  const breadcrumbs = generateBreadcrumbs(location.pathname);

  // Don't show breadcrumbs on dashboard home
  if (location.pathname === '/dashboard' || breadcrumbs.length === 0) {
    return null;
  }

  return (
    <Breadcrumb className="mb-6">
      <BreadcrumbList>
        {breadcrumbs.map((crumb, index) => (
          <div key={index} className="contents">
            <BreadcrumbItem>
              {crumb.isCurrentPage ? (
                <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
              ) : crumb.href ? (
                <BreadcrumbLink asChild>
                  <Link to={crumb.href}>
                    {index === 0 && <Home className="h-4 w-4 mr-1" />}
                    {crumb.label}
                  </Link>
                </BreadcrumbLink>
              ) : (
                <span>{crumb.label}</span>
              )}
            </BreadcrumbItem>
            {index < breadcrumbs.length - 1 && <BreadcrumbSeparator />}
          </div>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
