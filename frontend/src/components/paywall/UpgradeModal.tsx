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
import { LARGE_BATCH_FEATURE } from '@/components/QuestionComposer/limits';
import { PREMIUM_PLANS } from '@/app/subscription/plans';

const YEAR_PLAN = PREMIUM_PLANS.find((plan) => plan.id === '1_year');

export function UpgradeModal() {
  const { state, dismiss } = usePaywall();
  // 20-MCQ generator batches come with unlimited AI, i.e. the 1-year plan only.
  const yearPlanOnly = state.feature === LARGE_BATCH_FEATURE && !!YEAR_PLAN;

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

          {/* Only what the plans really grant (accounts.models.PLAN_FEATURES,
              /subscription): analytics is free for everyone, there is no
              adaptive-test UI or PDF export, and unlimited AI is the 1-year
              plan only (the others add AI credits). */}
          <Dialog.Description className="text-sm text-slate-300 mb-5 leading-relaxed">
            {state.remaining === 0 ? (
              <>You&rsquo;ve reached today&rsquo;s free limit for <strong>{state.feature}</strong>. Subscribe to remove the daily limit.</>
            ) : yearPlanOnly ? (
              <>Batches of up to 20 MCQs come with the <strong>1-year plan</strong>, together with unlimited AI. Other plans generate up to 10 per batch.</>
            ) : (
              <>Get <strong>{state.feature}</strong> and the rest of the CrackCMS library — every answer and explanation in the question banks and all mock tests.</>
            )}
          </Dialog.Description>

          {/* What every paid plan really unlocks (accounts.utils.is_premium, /subscription). */}
          <ul className="space-y-1.5 text-sm text-slate-200 mb-6">
            <li className="flex items-start gap-2"><span className="text-amber-400" aria-hidden="true">✓</span> AI Tutor credits on every plan, unlimited on the 1-year plan</li>
            <li className="flex items-start gap-2"><span className="text-amber-400" aria-hidden="true">✓</span> All mock tests and year-wise simulations with negative marking</li>
            <li className="flex items-start gap-2"><span className="text-amber-400" aria-hidden="true">✓</span> Every answer and explanation in the CMS, NEET PG and INI-CET banks</li>
            <li className="flex items-start gap-2"><span className="text-amber-400" aria-hidden="true">✓</span> Every discussion thread and the answers in your Mistake Notebook</li>
          </ul>

          <div className="flex flex-col gap-2">
            <Link
              href={`/subscription?feature=${encodeURIComponent(state.feature)}`}
              onClick={() => { upgradeClick(state.feature); dismiss(); }}
              className="w-full text-center rounded-xl bg-amber-500 hover:bg-amber-400 active:bg-amber-600
                text-slate-900 font-semibold py-3 transition-colors"
            >
              {yearPlanOnly && YEAR_PLAN
                ? `Get the 1-year plan — ₹${YEAR_PLAN.priceInr.toLocaleString('en-IN')}/year →`
                : 'Start Now — From just ₹129/month →'}
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

          <p className="mt-4 text-center text-xs text-slate-400">
            One-time payment · No auto-renewal
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}