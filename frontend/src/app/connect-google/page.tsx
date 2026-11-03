'use client';

/**
 * /connect-google -- the emailed "connect your Google account" link of the
 * Django-native sign-in (NEXT_PUBLIC_AUTH_MODE=django).
 *
 * "Sign in with Google" with a Google account whose email already belongs to
 * a CrackLabs account that is not linked to it answers 409
 * google_link_required and mails /connect-google#token=<t> to the account's
 * address (accounts/google_identity.py): opening the link proves the inbox is
 * the account owner's. The token is read once from the URL fragment (never
 * the query string), removed from the address bar and posted to
 * /api/auth/google/confirm-link/, which links the Google account and signs
 * this browser in. Single-use, valid 30 minutes.
 */
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { CheckCircle, Link2Off, Loader2 } from 'lucide-react';
import AuthShell from '@/components/AuthShell';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth';
import { takeAuthFragment } from '@/lib/authFragment';
import { AuthApiError, googleConfirmLink, type TokenAuthResult } from '@/lib/localAuth';
import { isDjangoAuthBuild } from '@/lib/localSession';

type Outcome =
    | { kind: 'signed-in'; result: TokenAuthResult }
    | { kind: 'missing' }
    | { kind: 'error'; code?: string; message: string };

const isAdminProfile = (profile: { is_admin?: boolean; role?: string } | null | undefined) =>
    profile?.is_admin === true || (profile?.role || '').toLowerCase() === 'admin';

export default function ConnectGooglePage() {
    const djangoAuth = isDjangoAuthBuild();
    const router = useRouter();
    const { completeTokenSignIn } = useAuth();
    // One request per page load: the link is single-use, and React runs this
    // effect twice in development.
    const started = useRef<Promise<Outcome> | null>(null);
    const [state, setState] = useState<'connecting' | 'done' | 'missing' | 'error'>('connecting');
    const [failure, setFailure] = useState<{ code?: string; message: string } | null>(null);

    useEffect(() => {
        if (!djangoAuth) return;
        let active = true;
        if (!started.current) {
            const { token } = takeAuthFragment();
            started.current = token
                ? googleConfirmLink(token)
                    .then((result): Outcome => ({ kind: 'signed-in', result }))
                    .catch((err: unknown): Outcome => ({
                        kind: 'error',
                        code: err instanceof AuthApiError ? err.code : undefined,
                        message: err instanceof Error && err.message ? err.message : 'This link could not be used. Please try again.',
                    }))
                : Promise.resolve<Outcome>({ kind: 'missing' });
        }
        void started.current.then(async (outcome) => {
            if (!active) return;
            if (outcome.kind === 'missing') {
                setState('missing');
                return;
            }
            if (outcome.kind === 'error') {
                setFailure({ code: outcome.code, message: outcome.message });
                setState('error');
                return;
            }
            setState('done');
            let destination = '/dashboard';
            try {
                const signedIn = await completeTokenSignIn(outcome.result);
                if (isAdminProfile(signedIn)) destination = '/admin';
            } catch {
                destination = '/login';
            }
            if (active) window.setTimeout(() => router.replace(destination), 1200);
        });
        return () => {
            active = false;
        };
    }, [djangoAuth]);

    let body: React.ReactNode;
    if (!djangoAuth) {
        body = (
            <div className="space-y-5 text-center">
                <p className="text-sm text-muted-foreground">There is nothing to connect on this page. Please sign in.</p>
                <Button asChild className="w-full rounded-2xl" size="lg">
                    <Link href="/login">Go to sign in</Link>
                </Button>
            </div>
        );
    } else if (state === 'connecting' || state === 'done') {
        body = (
            <div role="status" className="space-y-4 text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/40">
                    {state === 'done'
                        ? <CheckCircle className="h-8 w-8 text-emerald-600 dark:text-emerald-300" />
                        : <Loader2 className="h-8 w-8 animate-spin text-emerald-600 dark:text-emerald-300" />}
                </div>
                <p className="text-sm font-medium text-foreground">
                    {state === 'done'
                        ? 'Google sign-in is connected. You are signed in; next time just use "Sign in with Google".'
                        : 'Connecting your Google account...'}
                </p>
            </div>
        );
    } else {
        const code = failure?.code;
        const needsSupport = code === 'account_link_required' || code === 'account_blocked' || code === 'identity_in_use';
        body = (
            <div className="space-y-5">
                <div role="alert" className="flex items-start gap-3 rounded-2xl border border-destructive/20 bg-destructive/8 px-4 py-3 text-sm text-destructive">
                    <Link2Off className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>
                        {state === 'missing'
                            ? 'This page needs the link from the "Connect Google sign-in" email. Open the link from the email again, or sign in with Google once more to get a new one.'
                            : failure?.message}
                        {needsSupport && (
                            <>
                                {' '}
                                <Link href="/contact" className="font-semibold underline underline-offset-2">Contact support</Link>
                            </>
                        )}
                    </span>
                </div>
                <Button asChild className="w-full rounded-2xl" size="lg">
                    <Link href="/login">Back to sign in</Link>
                </Button>
                <p className="text-center text-xs text-muted-foreground">
                    You can always sign in with your email and password, or{' '}
                    <Link href="/forgot-password" className="font-medium text-primary hover:underline">reset the password</Link>.
                </p>
            </div>
        );
    }

    return (
        <AuthShell
            badge="Google Sign-in"
            title="Connect your Google account"
            description="Confirming the link from your email connects Google sign-in to your CrackLabs account."
            highlights={[
                'The link works once, for 30 minutes.',
                'Your progress, plan and tokens stay with your account.',
                'Next time, sign in with Google in one click.',
            ]}
        >
            {body}
        </AuthShell>
    );
}
