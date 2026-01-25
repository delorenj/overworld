/**
 * TokenHistory Component
 *
 * Displays paginated transaction history with filtering options
 */

import { useState, useEffect, useCallback } from 'react';
import {
  getTransactionHistory,
  getTransactionTypeLabel,
  isDeduction,
} from '../../services/tokenApi';
import type { Transaction, TransactionType } from '../../types/token';
import './TokenHistory.css';

interface TokenHistoryProps {
  /** JWT auth token */
  authToken: string;
  /** Number of items per page */
  pageSize?: number;
  /** Show filter controls */
  showFilters?: boolean;
}

export function TokenHistory({
  authToken,
  pageSize = 10,
  showFilters = true,
}: TokenHistoryProps) {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<TransactionType | undefined>(undefined);

  const fetchHistory = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getTransactionHistory(authToken, {
        limit: pageSize,
        offset,
        transactionType: filter,
      });
      setTransactions(data.transactions);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load transaction history');
    } finally {
      setLoading(false);
    }
  }, [authToken, pageSize, offset, filter]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleFilterChange = (newFilter: TransactionType | undefined) => {
    setFilter(newFilter);
    setOffset(0); // Reset to first page
  };

  const totalPages = Math.ceil(total / pageSize);
  const currentPage = Math.floor(offset / pageSize) + 1;

  const goToPage = (page: number) => {
    setOffset((page - 1) * pageSize);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  };

  const formatDelta = (delta: number) => {
    const sign = delta >= 0 ? '+' : '';
    return `${sign}${delta}`;
  };

  return (
    <div className="token-history">
      <div className="token-history__header">
        <h3 className="token-history__title">Transaction History</h3>
        {showFilters && (
          <div className="token-history__filters">
            <select
              value={filter || ''}
              onChange={(e) =>
                handleFilterChange(
                  e.target.value ? (e.target.value as TransactionType) : undefined
                )
              }
              className="token-history__filter-select"
            >
              <option value="">All Transactions</option>
              <option value="generation">Map Generation</option>
              <option value="purchase">Purchases</option>
              <option value="refund">Refunds</option>
              <option value="grant">Bonuses</option>
              <option value="monthly_reset">Monthly Resets</option>
            </select>
          </div>
        )}
      </div>

      {loading && (
        <div className="token-history__loading">
          <span className="token-history__spinner" />
          <span>Loading transactions...</span>
        </div>
      )}

      {error && (
        <div className="token-history__error">
          <span className="token-history__error-icon">!</span>
          <span>{error}</span>
          <button onClick={fetchHistory} className="token-history__retry">
            Retry
          </button>
        </div>
      )}

      {!loading && !error && transactions.length === 0 && (
        <div className="token-history__empty">
          <span className="token-history__empty-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="48" height="48">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
              />
            </svg>
          </span>
          <span className="token-history__empty-text">No transactions found</span>
        </div>
      )}

      {!loading && !error && transactions.length > 0 && (
        <>
          <ul className="token-history__list">
            {transactions.map((tx) => (
              <li key={tx.id} className="token-history__item">
                <div className="token-history__item-icon">
                  <span
                    className={`token-history__type-badge token-history__type-badge--${tx.type}`}
                  >
                    {isDeduction(tx.type) ? '-' : '+'}
                  </span>
                </div>
                <div className="token-history__item-details">
                  <span className="token-history__item-type">
                    {getTransactionTypeLabel(tx.type)}
                  </span>
                  <span className="token-history__item-date">{formatDate(tx.created_at)}</span>
                  {tx.metadata && typeof tx.metadata.reason === 'string' && (
                    <span className="token-history__item-reason">
                      {tx.metadata.reason}
                    </span>
                  )}
                </div>
                <div
                  className={`token-history__item-delta ${
                    tx.tokens_delta >= 0
                      ? 'token-history__item-delta--positive'
                      : 'token-history__item-delta--negative'
                  }`}
                >
                  {formatDelta(tx.tokens_delta)}
                </div>
              </li>
            ))}
          </ul>

          {totalPages > 1 && (
            <div className="token-history__pagination">
              <button
                onClick={() => goToPage(currentPage - 1)}
                disabled={currentPage === 1}
                className="token-history__page-btn"
              >
                Previous
              </button>
              <span className="token-history__page-info">
                Page {currentPage} of {totalPages}
              </span>
              <button
                onClick={() => goToPage(currentPage + 1)}
                disabled={currentPage === totalPages}
                className="token-history__page-btn"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
