/**
 * LowBalanceWarning Component
 *
 * Displays a prominent warning when user's token balance is low
 * with options to purchase more tokens or dismiss
 */

import { useState, useEffect } from 'react';
import type { TokenBalance } from '../../types/token';
import './LowBalanceWarning.css';

interface LowBalanceWarningProps {
  /** Current token balance */
  balance: TokenBalance | null;
  /** Estimated cost of upcoming action (optional) */
  estimatedCost?: number;
  /** Callback when user clicks to buy tokens */
  onBuyTokens?: () => void;
  /** Whether warning can be dismissed */
  dismissible?: boolean;
  /** Storage key for dismissed state (for session persistence) */
  dismissKey?: string;
}

export function LowBalanceWarning({
  balance,
  estimatedCost,
  onBuyTokens,
  dismissible = true,
  dismissKey = 'lowBalanceWarningDismissed',
}: LowBalanceWarningProps) {
  const [dismissed, setDismissed] = useState(false);

  // Check if previously dismissed in this session
  useEffect(() => {
    if (dismissKey) {
      const wasDismissed = sessionStorage.getItem(dismissKey);
      if (wasDismissed === 'true') {
        setDismissed(true);
      }
    }
  }, [dismissKey]);

  const handleDismiss = () => {
    setDismissed(true);
    if (dismissKey) {
      sessionStorage.setItem(dismissKey, 'true');
    }
  };

  // Don't show if no balance data
  if (!balance) {
    return null;
  }

  // Don't show if balance is not low
  if (!balance.is_low_balance) {
    return null;
  }

  // Don't show if dismissed
  if (dismissed) {
    return null;
  }

  const canAfford = !estimatedCost || balance.total_tokens >= estimatedCost;
  const shortfall = estimatedCost ? Math.max(0, estimatedCost - balance.total_tokens) : 0;

  return (
    <div
      className={`low-balance-warning ${
        !canAfford ? 'low-balance-warning--insufficient' : ''
      }`}
      role="alert"
    >
      <div className="low-balance-warning__icon">
        <svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
        </svg>
      </div>

      <div className="low-balance-warning__content">
        <h4 className="low-balance-warning__title">
          {canAfford ? 'Low Token Balance' : 'Insufficient Tokens'}
        </h4>

        <p className="low-balance-warning__message">
          {canAfford ? (
            <>
              Your token balance is running low. You have{' '}
              <strong>{balance.total_tokens} tokens</strong> remaining.
              {estimatedCost && (
                <>
                  {' '}
                  This action will cost <strong>{estimatedCost} tokens</strong>.
                </>
              )}
            </>
          ) : (
            <>
              You need <strong>{estimatedCost} tokens</strong> for this action, but only have{' '}
              <strong>{balance.total_tokens}</strong>. You need{' '}
              <strong>{shortfall} more tokens</strong> to proceed.
            </>
          )}
        </p>

        <div className="low-balance-warning__actions">
          {onBuyTokens && (
            <button onClick={onBuyTokens} className="low-balance-warning__buy-btn">
              Buy More Tokens
            </button>
          )}
        </div>
      </div>

      {dismissible && canAfford && (
        <button
          onClick={handleDismiss}
          className="low-balance-warning__dismiss"
          aria-label="Dismiss warning"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="20" height="20">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      )}
    </div>
  );
}

/**
 * InsufficientBalanceModal Component
 *
 * Modal displayed when user tries to perform an action
 * without sufficient token balance
 */

interface InsufficientBalanceModalProps {
  /** Is modal open */
  isOpen: boolean;
  /** Close modal callback */
  onClose: () => void;
  /** Current balance */
  currentBalance: number;
  /** Required amount */
  requiredAmount: number;
  /** Buy tokens callback */
  onBuyTokens?: () => void;
}

export function InsufficientBalanceModal({
  isOpen,
  onClose,
  currentBalance,
  requiredAmount,
  onBuyTokens,
}: InsufficientBalanceModalProps) {
  if (!isOpen) {
    return null;
  }

  const shortfall = requiredAmount - currentBalance;

  return (
    <div className="insufficient-modal-overlay" onClick={onClose}>
      <div className="insufficient-modal" onClick={(e) => e.stopPropagation()}>
        <div className="insufficient-modal__icon">
          <svg viewBox="0 0 24 24" fill="currentColor" width="48" height="48">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
          </svg>
        </div>

        <h2 className="insufficient-modal__title">Insufficient Tokens</h2>

        <p className="insufficient-modal__message">
          This action requires <strong>{requiredAmount} tokens</strong>, but you only have{' '}
          <strong>{currentBalance} tokens</strong> available.
        </p>

        <div className="insufficient-modal__balance">
          <div className="insufficient-modal__balance-row">
            <span>Required:</span>
            <span className="insufficient-modal__amount">{requiredAmount}</span>
          </div>
          <div className="insufficient-modal__balance-row">
            <span>Available:</span>
            <span className="insufficient-modal__amount insufficient-modal__amount--available">
              {currentBalance}
            </span>
          </div>
          <div className="insufficient-modal__balance-row insufficient-modal__balance-row--shortfall">
            <span>Shortfall:</span>
            <span className="insufficient-modal__amount insufficient-modal__amount--shortfall">
              {shortfall}
            </span>
          </div>
        </div>

        <div className="insufficient-modal__actions">
          {onBuyTokens && (
            <button onClick={onBuyTokens} className="insufficient-modal__buy-btn">
              Purchase Tokens
            </button>
          )}
          <button onClick={onClose} className="insufficient-modal__close-btn">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
