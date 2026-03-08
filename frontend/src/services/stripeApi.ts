import axios from 'axios';
import type {
  CheckoutRequest,
  CheckoutResponse,
  StripeConfigResponse,
  TokenPackagesResponse,
} from '../types/stripe';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost/api';
const ANONYMOUS_SESSION_KEY = 'overworld_anon_session_id';

export function getOrCreateAnonymousSessionId(): string {
  const existing = localStorage.getItem(ANONYMOUS_SESSION_KEY);
  if (existing) {
    return existing;
  }

  const generated =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  localStorage.setItem(ANONYMOUS_SESSION_KEY, generated);
  return generated;
}

function buildHeaders(authToken?: string | null, sessionId?: string) {
  const headers: Record<string, string> = {};

  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }

  if (sessionId) {
    headers['X-Session-ID'] = sessionId;
  }

  return { headers };
}

export async function getStripeConfig(): Promise<StripeConfigResponse> {
  const response = await axios.get<StripeConfigResponse>(`${API_BASE_URL}/v1/stripe/config`);
  return response.data;
}

export async function getTokenPackages(): Promise<TokenPackagesResponse> {
  const response = await axios.get<TokenPackagesResponse>(`${API_BASE_URL}/v1/stripe/packages`);
  return response.data;
}

export async function createCheckoutSession(
  payload: CheckoutRequest,
  options?: { authToken?: string | null; sessionId?: string }
): Promise<CheckoutResponse> {
  const response = await axios.post<CheckoutResponse>(
    `${API_BASE_URL}/v1/stripe/checkout`,
    payload,
    buildHeaders(options?.authToken, options?.sessionId)
  );

  return response.data;
}
