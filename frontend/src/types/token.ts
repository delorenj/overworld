/**
 * TypeScript types for token management API
 */

export type TransactionType =
  | 'generation'
  | 'purchase'
  | 'refund'
  | 'grant'
  | 'monthly_reset';

export interface TokenBalance {
  free_tokens: number;
  purchased_tokens: number;
  total_tokens: number;
  last_reset_at: string;
  is_low_balance: boolean;
}

export interface Transaction {
  id: number;
  type: TransactionType;
  tokens_delta: number;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface TransactionHistory {
  transactions: Transaction[];
  total: number;
  limit: number;
  offset: number;
}

export interface CostBreakdown {
  base_cost: number;
  size_cost: number;
  total: number;
  capped: boolean;
}

export interface CostEstimate {
  estimated_cost: number;
  file_size_bytes: number | null;
  breakdown: CostBreakdown;
  can_afford: boolean;
  current_balance: number | null;
}

export interface CostEstimateRequest {
  document_id?: string;
  file_size_bytes?: number;
}

export interface InsufficientBalanceError {
  message: string;
  required: number;
  available: number;
  shortfall: number;
}

export interface BalanceCheckResult {
  sufficient: boolean;
  current_balance: number;
  required: number;
  shortfall?: number;
}
