export interface TokenPackage {
  id: string;
  name: string;
  tokens: number;
  price_cents: number;
  currency: string;
  popular: boolean;
  savings_percent?: number | null;
}

export interface TokenPackagesResponse {
  packages: TokenPackage[];
  currency: string;
}

export interface StripeConfigResponse {
  publishable_key: string;
}

export interface CheckoutRequest {
  package_id: string;
  success_url: string;
  cancel_url: string;
  customer_email?: string;
}

export interface CheckoutResponse {
  session_id: string;
  checkout_url: string;
  expires_at: number;
}
