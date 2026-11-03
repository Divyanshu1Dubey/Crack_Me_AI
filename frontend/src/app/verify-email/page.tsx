'use client';

/**
 * /verify-email -- the emailed confirmation link of the Django-native sign-in
 * (NEXT_PUBLIC_AUTH_MODE=django):
 *   #token=<t>            finishes a new sign-up (the account is created now)
 *   #uid=<u>&token=<t>    confirms the email of an existing account
 * The values are read once from the URL fragment (never the query string) and
 * removed from the address bar, then posted to /api/auth/native/verify-email/,
 * which signs this browser in. The link works once.
 */
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { CheckCircle, Loader2, MailWarning } from 'lucide-react';
import AuthShell from '@/components/AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { consumePostAuthPath, useAuth } from '@/lib/auth';
import { navigateAfterAuthChange } from '@/lib/authNavigation';
import { takeAuthFragment } from '@/lib/authFragment';
import { AuthApiError, resendVerificationEmail, verifyEmailLink, type TokenAuthResult } from '@/lib/localAuth';
import { isDjangoAuthBuild } from '@/lib/localSession';

type Outcome =
    | { kind: 'signed-in'; result: TokenAuthResult }
    | { kind: 'missing' }
    | { kind: 'error'; code?: string; message: string };

const isAdminProfile = (profile: { is_admin?: boolean; role?: string } | null | undefined) =>
    profile?.is_admin === true || (profile?.role || '').toLowerCase() === 'admin';

export default function VerifyEmailPage() {
    const djangoAuth = isDjangoAuthBuild();
    const router = useRouter();
    const { completeTokenSignIn } = useAuth();
    // One request per page load: the link is single-use, and React runs this
    // effect twice in development.
    const started = useRef<Promise<Outcome> | null>(null);
    const [state, setState] = useState<'verifying' | 'done' | 'missing' | 'error'>('verifying');
    const [failure, setFailure] = useState<{ code?: string; message: string } | null>(null);
    const [email, setEmail] = useState('');
    const [resendState, setResendState] = useState<'idle' | 'sending' | 'sent'>('idle');
    const [resendMessage, setResendMessage] = useState('');

    useEffect(() => {
        if (!djangoAuth) return;
        let active = true;
        if (!started.current) {
            const link = takeAuthFragment();
            started.current = link.token
                ? verifyEmailLink({ token: link.token, uid: link.uid })
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
            let destination = consumePostAuthPath() || '/dashboard';
            try {
                const signedIn = await completeTokenSignIn(outcome.result);
                if (destination === '/dashboard' && isAdminProfile(signedIn)) destination = '/admin';
            } catch {
                destination = '/login';
            }
            if (active) navigateAfterAuthChange(destination, { replace: true });
        });
        return () => {
            active = false;
        };
    }, [djangoAuth]);

    const handleResend = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!email.trim().includes('@')) return;
        setResendState('sending');
        setResendMessage('');
        try {
            setResendMessage(await resendVerificationEmail(email));
            setResendState('sent');
        } catch (err: unknown) {
            setResendState('idle');
            setResendMessage(err instanceof Error && err.message ? err.message : 'Could not send the email. Please try again.');
        }
    };

    const resendForm = (
        <form onSubmit={handleResend} className="space-y-3 text-left">
            <label htmlFor="verify-resend-email" className="block text-sm font-semibold text-foreground">
                Send a new confirmation link
            </label>
            <Input
                id="verify-resend-email"
                type="email"
                name="email"
                placeholder="you@example.com"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
            />
            <Button type="submit" variant="outline" className="w-full rounded-2xl" disabled={resendState !== 'idle'}>
                {resendState === 'sending' ? 'Sending...' : resendState === 'sent' ? 'Sent' : 'Send new link'}
            </Button>
            {resendMessage && <p role="status" className="text-xs text-muted-foreground">{resendMessage}</p>}
        </form>
    );

    let body: React.ReactNode;
    if (!djangoAuth) {
        body = (
            <div className="space-y-5 text-center">
                <p className="text-sm text-muted-foreground">There is nothing to confirm on this page. Please sign in.</p>
                <Button asChild className="w-full rounded-2xl" size="lg">
                    <Link href="/login">Go to sign in</Link>
                </Button>
            </div>
        );
    } else if (state === 'verifying' || state === 'done') {
        body = (
            <div role="status" className="space-y-4 text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/40">
                    {state === 'done'
                        ? <CheckCircle className="h-8 w-8 text-emerald-600 dark:text-emerald-300" />
                        : <Loader2 className="h-8 w-8 animate-spin text-emerald-600 dark:text-emerald-300" />}
                </div>
                <p className="text-sm font-medium text-foreground">
                    {state === 'done' ? 'Email confirmed. Signing you in...' : 'Confirming your email address...'}
                </p>
            </div>
        );
    } else {
        const code = failure?.code;
        body = (
            <div className="space-y-5">
                <div className="flex items-start gap-3 rounded-2xl border border-destructive/20 bg-destructive/8 px-4 py-3 text-sm text-destructive" role="alert">
                    <MailWarning className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>
                        {state === 'missing'
                            ? 'This page needs the link from your confirmation email. Open the link from the email again, or request a new one below.'
                            : failure?.message}
                        {code === 'account_blocked' && (
                            <>
                                {' '}
                                <Link href="/contact" className="font-semibold underline underline-offset-2">Contact support</Link>
                            </>
                        )}
                    </span>
                </div>
                {code === 'account_exists' ? (
                    <div className="space-y-3">
                        <Button asChild className="w-full rounded-2xl" size="lg">
                            <Link href="/login">Go to sign in</Link>
                        </Button>
                        <p className="text-center text-xs text-muted-foreground">
                            Forgot the password?{' '}
                            <Link href="/forgot-password" className="font-medium text-primary hover:underline">Reset it</Link>
                        </p>
                    </div>
                ) : code === 'account_blocked' ? null : (
                    resendForm
                )}
                <p className="text-center text-sm">
                    <Link href="/login" className="font-medium text-primary hover:underline">Back to Login</Link>
                </p>
            </div>
        );
    }

    return (
        <AuthShell
            badge="Confirm Email"
            title="Confirm your email address"
            description="One click finishes setting up your CrackLabs account."
            highlights={[
                'Confirmation links work once.',
                'Opening the link signs you in on this device.',
                'Ensure to check both your inbox and spam folders.',
            ]}
        >
            {body}
        </AuthShell>
    );
}
