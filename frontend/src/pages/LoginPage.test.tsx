/**
 * LoginPage Component Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { LoginPage } from './LoginPage';

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
const mockLogin = vi.fn();
const mockLoginWithOAuth = vi.fn();

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    login: mockLogin,
    loginWithOAuth: mockLoginWithOAuth,
    isLoading: false,
    isAuthenticated: false,
  }),
}));

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLogin.mockResolvedValue(undefined);
    mockLoginWithOAuth.mockResolvedValue(undefined);
  });

  const renderWithRouter = () => {
    return render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );
  };

  it('renders login form', () => {
    renderWithRouter();

    expect(screen.getByText('Welcome to Overworld')).toBeInTheDocument();
    expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();
  });

  it('shows OAuth buttons', () => {
    renderWithRouter();

    expect(screen.getByRole('button', { name: /Google/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /GitHub/i })).toBeInTheDocument();
  });

  it('submits login form with credentials', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    const emailInput = screen.getByLabelText(/Email/i);
    const passwordInput = screen.getByLabelText(/Password/i);

    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');

    const submitButton = screen.getByRole('button', { name: /Sign In/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123',
      });
    });
  });

  it('redirects to dashboard after successful login', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    const emailInput = screen.getByLabelText(/Email/i);
    const passwordInput = screen.getByLabelText(/Password/i);

    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');

    const submitButton = screen.getByRole('button', { name: /Sign In/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });

  it('shows error message on login failure', async () => {
    mockLogin.mockRejectedValue(new Error('Invalid credentials'));

    const user = userEvent.setup();
    renderWithRouter();

    const emailInput = screen.getByLabelText(/Email/i);
    const passwordInput = screen.getByLabelText(/Password/i);

    await user.type(emailInput, 'wrong@example.com');
    await user.type(passwordInput, 'wrongpassword');

    const submitButton = screen.getByRole('button', { name: /Sign In/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });
  });

  it('triggers OAuth login when Google button is clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    const googleButton = screen.getByRole('button', { name: /Google/i });
    await user.click(googleButton);

    expect(mockLoginWithOAuth).toHaveBeenCalledWith('google');
  });

  it('triggers OAuth login when GitHub button is clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    const githubButton = screen.getByRole('button', { name: /GitHub/i });
    await user.click(githubButton);

    expect(mockLoginWithOAuth).toHaveBeenCalledWith('github');
  });

  it('shows forgot password link', () => {
    renderWithRouter();

    expect(screen.getByText(/Forgot password/i)).toBeInTheDocument();
  });

  it('shows sign up link', () => {
    renderWithRouter();

    expect(screen.getByText(/Sign up/i)).toBeInTheDocument();
  });

  it('requires email and password fields', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    const submitButton = screen.getByRole('button', { name: /Sign In/i });
    await user.click(submitButton);

    // Form should not submit, login should not be called
    expect(mockLogin).not.toHaveBeenCalled();
  });
});
