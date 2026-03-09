/**
 * Application Entry Point
 *
 * Sets up React Router with authentication-protected routes
 * and the dashboard layout system.
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';

// Pages
import { UploadPage } from './pages/UploadPage';
import { MapPage } from './pages/MapPage';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { MyMapsPage } from './pages/MyMapsPage';
import { AccountPage } from './pages/AccountPage';

// Layout
import { DashboardLayout } from './components/dashboard/DashboardLayout';

// Styles
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/upload-legacy" element={<UploadPage />} />

          {/* Protected Dashboard Routes */}
          <Route path="/dashboard" element={<DashboardLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="maps" element={<MyMapsPage />} />
            <Route path="upload" element={<UploadPage />} />
            <Route path="account" element={<AccountPage />} />
            {/* Legacy route redirects (OWRLD-25) */}
            <Route path="settings" element={<Navigate to="/dashboard/account?tab=security" replace />} />
            <Route path="profile" element={<Navigate to="/dashboard/account?tab=identity" replace />} />
          </Route>

          {/* Map View (can be accessed with map ID) */}
          <Route path="/map" element={<MapPage />} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>
);
