/**
 * API service for token management operations
 */

import axios from 'axios';
import type {
  TokenBalance,
  TransactionHistory,
  CostEstimate,
  CostEstimateRequest,
  BalanceCheckResult,
  TransactionType,
} from '../types/token';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost/api';

/**
 * Create an axios instance with auth header
 */
function createAuthHeaders(token: string) {
  return {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  };
}

/**
 * Get current token balance for authenticated user
 *
 * @param authToken - JWT authentication token
 * @returns Promise with token balance details
 */
export async function getTokenBalance(authToken: string): Promise<TokenBalance> {
  const response = await axios.get<TokenBalance>(
    `${API_BASE_URL}/v1/tokens/balance`,
    createAuthHeaders(authToken)
  );
  return response.data;
}

/**
 * Get transaction history for authenticated user
 *
 * @param authToken - JWT authentication token
 * @param options - Optional pagination and filter options
 * @returns Promise with transaction history
 */
export async function getTransactionHistory(
  authToken: string,
  options?: {
    limit?: number;
    offset?: number;
    transactionType?: TransactionType;
  }
): Promise<TransactionHistory> {
  const params = new URLSearchParams();

  if (options?.limit) {
    params.append('limit', options.limit.toString());
  }
  if (options?.offset) {
    params.append('offset', options.offset.toString());
  }
  if (options?.transactionType) {
    params.append('transaction_type', options.transactionType);
  }

  const url = `${API_BASE_URL}/v1/tokens/history${params.toString() ? `?${params}` : ''}`;
  const response = await axios.get<TransactionHistory>(url, createAuthHeaders(authToken));
  return response.data;
}

/**
 * Estimate cost for a generation job
 *
 * @param request - Cost estimation request
 * @param authToken - Optional JWT token (for balance check)
 * @returns Promise with cost estimate
 */
export async function estimateCost(
  request: CostEstimateRequest,
  authToken?: string
): Promise<CostEstimate> {
  const config = authToken ? createAuthHeaders(authToken) : {};

  const response = await axios.post<CostEstimate>(
    `${API_BASE_URL}/v1/tokens/estimate`,
    request,
    config
  );
  return response.data;
}

/**
 * Check if user has sufficient balance for an amount
 *
 * @param authToken - JWT authentication token
 * @param amount - Required token amount
 * @returns Promise with balance check result
 */
export async function checkBalance(
  authToken: string,
  amount: number
): Promise<BalanceCheckResult> {
  const response = await axios.get<BalanceCheckResult>(
    `${API_BASE_URL}/v1/tokens/check/${amount}`,
    createAuthHeaders(authToken)
  );
  return response.data;
}

/**
 * Format token amount for display
 *
 * @param amount - Number of tokens
 * @returns Formatted string
 */
export function formatTokenAmount(amount: number): string {
  if (amount >= 1000) {
    return `${(amount / 1000).toFixed(1)}k`;
  }
  return amount.toString();
}

/**
 * Get human-readable transaction type label
 *
 * @param type - Transaction type
 * @returns Human-readable label
 */
export function getTransactionTypeLabel(type: TransactionType): string {
  const labels: Record<TransactionType, string> = {
    generation: 'Map Generation',
    purchase: 'Token Purchase',
    refund: 'Refund',
    grant: 'Bonus',
    monthly_reset: 'Monthly Reset',
  };
  return labels[type] || type;
}

/**
 * Check if a transaction is a deduction
 *
 * @param type - Transaction type
 * @returns True if transaction is a deduction
 */
export function isDeduction(type: TransactionType): boolean {
  return type === 'generation';
}
