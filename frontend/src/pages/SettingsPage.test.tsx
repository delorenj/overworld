/**
 * SettingsPage Component Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { SettingsPage } from './SettingsPage';

// Mock navigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock the auth hook
const mockUpdateUser = vi.fn();
const mockChangePassword = vi.fn();
const mockDeleteAccount = vi.fn();
const mockGetConnectedAccounts = vi.fn();
const mockDisconnectAccount = vi.fn();

const mockUser = {
  id: 'user-1',
  name: 'Test User',
  email: 'test@example.com',
  avatarUrl: 'https://example.com/avatar.jpg',
};

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: mockUser,
    updateUser: mockUpdateUser,
    changePassword: mockChangePassword,
    deleteAccount: mockDeleteAccount,
    getConnectedAccounts: mockGetConnectedAccounts,
    disconnectAccount: mockDisconnectAccount,
  }),
}));

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetConnectedAccounts.mockResolvedValue([
      {
        provider: 'google',
        providerId: 'google-123',
        email: 'test@gmail.com',
        connectedAt: '2024-01-01T00:00:00Z',
      },
    ]);
    mockUpdateUser.mockResolvedValue(undefined);
    mockChangePassword.mockResolvedValue(undefined);
    mockDeleteAccount.mockResolvedValue(undefined);
  });

  const renderWithRouter = () => {
    return render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );
  };

  it('renders settings page with correct title', () => {
    renderWithRouter();

    expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument();
  });

  it('displays user profile information', () => {
    renderWithRouter();

    expect(screen.getByDisplayValue('Test User')).toBeInTheDocument();
    expect(screen.getByDisplayValue('test@example.com')).toBeInTheDocument();
  });

  it('shows all tabs', () => {
    renderWithRouter();

    expect(screen.getByRole('tab', { name: /Profile/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Security/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Connections/i })).toBeInTheDocument();
  });

  it('updates profile when form is submitted', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    const nameInput = screen.getByDisplayValue('Test User');
    await user.clear(nameInput);
    await user.type(nameInput, 'New Name');

    const saveButton = screen.getByRole('button', { name: /Save Changes/i });
    await user.click(saveButton);

    await waitFor(() => {
      expect(mockUpdateUser).toHaveBeenCalledWith({ name: 'New Name' });
    });
  });

  it('shows success message after profile update', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    const nameInput = screen.getByDisplayValue('Test User');
    await user.clear(nameInput);
    await user.type(nameInput, 'New Name');

    const saveButton = screen.getByRole('button', { name: /Save Changes/i });
    await user.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText(/Profile updated successfully/i)).toBeInTheDocument();
    });
  });

  it('validates password match on change password form', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    // Switch to security tab
    const securityTab = screen.getByRole('tab', { name: /Security/i });
    await user.click(securityTab);

    // Fill in password form with mismatched passwords
    const currentPasswordInput = screen.getByLabelText(/Current Password/i);
    const newPasswordInput = screen.getByLabelText(/^New Password/i);
    const confirmPasswordInput = screen.getByLabelText(/Confirm New Password/i);

    await user.type(currentPasswordInput, 'oldpassword');
    await user.type(newPasswordInput, 'newpassword123');
    await user.type(confirmPasswordInput, 'differentpassword');

    const updateButton = screen.getByRole('button', { name: /Update Password/i });
    await user.click(updateButton);

    await waitFor(() => {
      expect(screen.getByText(/Passwords do not match/i)).toBeInTheDocument();
    });
  });

  it('shows connected accounts', async () => {
    renderWithRouter();

    // Switch to connections tab
    const user = userEvent.setup();
    const connectionsTab = screen.getByRole('tab', { name: /Connections/i });
    await user.click(connectionsTab);

    await waitFor(() => {
      expect(screen.getByText('google')).toBeInTheDocument();
      expect(screen.getByText('test@gmail.com')).toBeInTheDocument();
    });
  });

  it('shows delete account button in security tab', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    const securityTab = screen.getByRole('tab', { name: /Security/i });
    await user.click(securityTab);

    expect(screen.getByRole('button', { name: /Delete Account/i })).toBeInTheDocument();
  });

  it('disables email field', () => {
    renderWithRouter();

    const emailInput = screen.getByDisplayValue('test@example.com');
    expect(emailInput).toBeDisabled();
  });
});
