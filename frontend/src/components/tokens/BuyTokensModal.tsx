import { useEffect, useMemo, useState } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Coins } from 'lucide-react';

import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../ui/dialog';
import {
  createCheckoutSession,
  getOrCreateAnonymousSessionId,
  getStripeConfig,
  getTokenPackages,
} from '../../services/stripeApi';
import type { TokenPackage } from '../../types/stripe';

interface BuyTokensModalProps {
  authToken: string | null;
  defaultEmail?: string;
}

function formatPrice(cents: number) {
  return `$${(cents / 100).toFixed(2)}`;
}

export function BuyTokensModal({ authToken, defaultEmail }: BuyTokensModalProps) {
  const [open, setOpen] = useState(false);
  const [packages, setPackages] = useState<TokenPackage[]>([]);
  const [selectedPackageId, setSelectedPackageId] = useState<string>('');
  const [email, setEmail] = useState(defaultEmail || '');
  const [isLoadingPackages, setIsLoadingPackages] = useState(false);
  const [isCreatingCheckout, setIsCreatingCheckout] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEmail(defaultEmail || '');
  }, [defaultEmail]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const loadPackages = async () => {
      try {
        setError(null);
        setIsLoadingPackages(true);

        const response = await getTokenPackages();
        setPackages(response.packages);

        if (response.packages.length > 0) {
          const preferred = response.packages.find((pkg) => pkg.popular) || response.packages[0];
          setSelectedPackageId(preferred.id);
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load token packages');
      } finally {
        setIsLoadingPackages(false);
      }
    };

    loadPackages();
  }, [open]);

  const selectedPackage = useMemo(
    () => packages.find((pkg) => pkg.id === selectedPackageId),
    [packages, selectedPackageId]
  );

  const handleCheckout = async () => {
    if (!selectedPackage) {
      setError('Please select a token package');
      return;
    }

    if (!authToken && !email.trim()) {
      setError('Email is required for guest checkout');
      return;
    }

    try {
      setError(null);
      setIsCreatingCheckout(true);

      const successUrl = `${window.location.origin}/dashboard?purchase=success`;
      const cancelUrl = `${window.location.origin}/dashboard?purchase=cancel`;

      const checkout = await createCheckoutSession(
        {
          package_id: selectedPackage.id,
          success_url: successUrl,
          cancel_url: cancelUrl,
          customer_email: authToken ? undefined : email.trim(),
        },
        {
          authToken,
          sessionId: getOrCreateAnonymousSessionId(),
        }
      );

      const { publishable_key } = await getStripeConfig();
      const stripe = await loadStripe(publishable_key);

      if (stripe) {
        const { error: redirectError } = await stripe.redirectToCheckout({
          sessionId: checkout.session_id,
        });

        if (redirectError) {
          window.location.assign(checkout.checkout_url);
        }
        return;
      }

      window.location.assign(checkout.checkout_url);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start checkout');
      setIsCreatingCheckout(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Coins className="mr-2 h-4 w-4" />
          Buy Tokens
        </Button>
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Buy Tokens</DialogTitle>
          <DialogDescription>
            Choose a token pack and continue to secure Stripe checkout.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {!authToken && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Email for receipt & account linking</label>
              <Input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          )}

          {isLoadingPackages ? (
            <p className="text-sm text-muted-foreground">Loading packages...</p>
          ) : (
            <div className="space-y-2">
              {packages.map((pkg) => (
                <button
                  key={pkg.id}
                  type="button"
                  onClick={() => setSelectedPackageId(pkg.id)}
                  className={`w-full rounded-lg border p-3 text-left transition ${
                    selectedPackageId === pkg.id
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{pkg.name}</div>
                      <div className="text-sm text-muted-foreground">{pkg.tokens} tokens</div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold">{formatPrice(pkg.price_cents)}</div>
                      {pkg.savings_percent ? (
                        <div className="text-xs text-muted-foreground">Save {pkg.savings_percent}%</div>
                      ) : null}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={isCreatingCheckout}>
            Cancel
          </Button>
          <Button onClick={handleCheckout} disabled={isLoadingPackages || isCreatingCheckout}>
            {isCreatingCheckout
              ? 'Redirecting...'
              : `Checkout${selectedPackage ? ` • ${formatPrice(selectedPackage.price_cents)}` : ''}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
