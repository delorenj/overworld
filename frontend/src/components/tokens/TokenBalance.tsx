/**
 * TokenBalance Component
 *
 * Displays the user's current token balance with visual indicators
 * for low balance warnings.
 */

import { useState, useEffect } from 'react';
import { getTokenBalance, formatTokenAmount } from '../../services/tokenApi';
import type { TokenBalance as TokenBalanceType } from '../../types/token';
import './TokenBalance.css';

interface TokenBalanceProps {
  /** JWT auth token */
  authToken: string;
  /** Callback when balance is loaded */
  onBalanceLoaded?: (balance: TokenBalanceType) => void;
  /** Show compact version */
  compact?: boolean;
  /** Auto-refresh interval in ms (0 to disable) */
  refreshInterval?: number;
}

export function TokenBalance({
  authToken,
  onBalanceLoaded,
  compact = false,
  refreshInterval = 0,
}: TokenBalanceProps) {
  const [balance, setBalance] = useState<TokenBalanceType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBalance = async () => {
    try {
      setError(null);
      const data = await getTokenBalance(authToken);
      setBalance(data);
      onBalanceLoaded?.(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load balance');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBalance();

    // Set up auto-refresh if interval is specified
    if (refreshInterval > 0) {
      const interval = setInterval(fetchBalance, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [authToken, refreshInterval]);

  if (loading) {
    return (
      <div className={`token-balance ${compact ? 'token-balance--compact' : ''}`}>
        <div className="token-balance__loading">
          <span className="token-balance__spinner" />
          {!compact && <span>Loading balance...</span>}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`token-balance token-balance--error ${compact ? 'token-balance--compact' : ''}`}>
        <span className="token-balance__error-icon">!</span>
        {!compact && <span className="token-balance__error-text">{error}</span>}
        <button onClick={fetchBalance} className="token-balance__retry">
          Retry
        </button>
      </div>
    );
  }

  if (!balance) {
    return null;
  }

  const balanceClass = balance.is_low_balance
    ? 'token-balance--low'
    : balance.total_tokens > 50
    ? 'token-balance--good'
    : 'token-balance--medium';

  if (compact) {
    return (
      <div className={`token-balance token-balance--compact ${balanceClass}`}>
        <span className="token-balance__icon">
          <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" fill="none" />
            <text x="12" y="16" textAnchor="middle" fontSize="10" fill="currentColor">T</text>
          </svg>
        </span>
        <span className="token-balance__total">{formatTokenAmount(balance.total_tokens)}</span>
        {balance.is_low_balance && (
          <span className="token-balance__warning-dot" title="Low balance" />
        )}
      </div>
    );
  }

  return (
    <div className={`token-balance ${balanceClass}`}>
      <div className="token-balance__header">
        <h3 className="token-balance__title">Token Balance</h3>
        {balance.is_low_balance && (
          <span className="token-balance__badge token-balance__badge--warning">Low Balance</span>
        )}
      </div>

      <div className="token-balance__total-section">
        <span className="token-balance__total-label">Total Available</span>
        <span className="token-balance__total-value">{balance.total_tokens}</span>
        <span className="token-balance__total-unit">tokens</span>
      </div>

      <div className="token-balance__breakdown">
        <div className="token-balance__breakdown-item">
          <span className="token-balance__breakdown-label">Free Tokens</span>
          <span className="token-balance__breakdown-value">{balance.free_tokens}</span>
        </div>
        <div className="token-balance__breakdown-item">
          <span className="token-balance__breakdown-label">Purchased</span>
          <span className="token-balance__breakdown-value">{balance.purchased_tokens}</span>
        </div>
      </div>

      <div className="token-balance__footer">
        <span className="token-balance__reset-info">
          Last reset: {new Date(balance.last_reset_at).toLocaleDateString()}
        </span>
        <button onClick={fetchBalance} className="token-balance__refresh" title="Refresh">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="16" height="16">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
