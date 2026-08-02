'use client';

/**
 * UpgradeModal (Task 8) — Radix Dialog that opens whenever the backend
 * returns `code: 'upgrade_required'`. Copy is locked to the live ₹129/month
 * price; deep-link to /subscription with a `?feature=` query param so the
 * landing page can highlight the locked feature.
 */
import * as Dialog from '@radix-ui/react-dialog';
import { X, Lock } from 'lucide-react';
import Link from 'next/link';
import { useEffect } from 'react';

import { paywallView, paywallDismissed, upgradeClick } from '@/lib/analytics';
import { usePaywall } from '@/lib/paywall/paywallContext';

export function UpgradeModal() {
  const { state, dismiss } = usePaywall();

  useEffect(() => {
    if (state.open) {
      paywallView(state.feature);
    }
  }, [state.open, state.feature]);

  return (
    <Dialog.Root open={state.open} onOpenChange={(o) => { if (!o) { paywallDismissed(state.feature); dismiss(); } }}>
      <Dialog.Portal>
        <Dialog.Overlay
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm
            data-[state=open]:animate-in data-[state=open]:fade-in-0
            data-[state=closed]:animate-out data-[state=closed]:fade-out-0"
        />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-md -translate-x-1/2 -translate-y-1/2
            rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-slate-800
            border border-amber-500/30 p-6 text-slate-100 shadow-2xl
            data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95
            data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95"
        >
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex items-center gap-2">
              <div className="rounded-full bg-amber-500/15 p-2 text-amber-400">
                <Lock size={20} aria-hidden="true" />
              </div>
              <Dialog.Title className="text-lg font-semibold">
                Unlock {state.feature}
              </Dialog.Title>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className="rounded-md p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-100"
                onClick={() => { paywallDismissed(state.feature); dismiss(); }}
              >
                <X size={18} />
              </button>
            </Dialog.Close>
          </div>

          <Dialog.Description className="text-sm text-slate-300 mb-5 leading-relaxed">
            {state.remaining === 0 ? (
              <>You&rsquo;ve reached today&rsquo;s free limit for <strong>{state.feature}</strong>. Subscribe for unlimited access.</>
            ) : (
              <>Get <strong>{state.feature}</strong> and the rest of the CrackCMS library — adaptive tests, deep analytics, all PYQ years, all mock tests.</>
            )}
          </Dialog.Description>

          <ul className="space-y-1.5 text-sm text-slate-200 mb-6">
            <li className="flex items-center gap-2"><span className="text-amber-400">✓</span> Unlimited AI Tutor (11-provider rotation)</li>
            <li className="flex items-center gap-2"><span className="text-amber-400">✓</span> All 100+ mock tests + adaptive engine</li>
            <li className="flex items-center gap-2"><span className="text-amber-400">✓</span> Full PYQ bank with detailed explanations</li>
            <li className="flex items-center gap-2"><span className="text-amber-400">✓</span> Per-topic mastery &amp; PDF export</li>
          </ul>

          <div className="flex flex-col gap-2">
            <Link
              href={`/subscription?feature=${encodeURIComponent(state.feature)}`}
              onClick={() => { upgradeClick(state.feature); dismiss(); }}
              className="w-full text-center rounded-xl bg-amber-500 hover:bg-amber-400 active:bg-amber-600
                text-slate-900 font-semibold py-3 transition-colors"
            >
              Start Now — From just ₹129/month →
            </Link>
            <Dialog.Close asChild>
              <button
                type="button"
                onClick={() => { paywallDismissed(state.feature); dismiss(); }}
                className="w-full text-center rounded-xl bg-transparent hover:bg-slate-800
                  text-slate-400 text-sm py-2 transition-colors"
              >
                Maybe later
              </button>
            </Dialog.Close>
          </div>

          <p className="mt-4 text-center text-xs text-slate-500">
            Cancel anytime · Used by 10,000+ UPSC CMS aspirants
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}