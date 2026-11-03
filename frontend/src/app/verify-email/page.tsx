'use client';

/**
 * /verify-email -- the emailed confirmation link of the Django-native sign-in
 * (NEXT_PUBLIC_AUTH_MODE=django):
 *   #token=<t>            finishes a new sign-up: the account is created once
 *                         the password chosen at sign-up is entered here
 *   #uid=<u>&token=<t>    confirms the email of an existing account
 * The values are read once from the URL fragment (never the query string) and
 * removed from the address bar, then posted to /api/auth/native/verify-email/,
 * which signs this browser in. The link works once.
 *
 * Why the password: anyone can sign up with someone else's address. The link
 * proves the inbox; the password proves which sign-up is the inbox owner's,
 * so opening the mail never creates an account protected by a stranger's
 * password (backend: password_required / password_mismatch, the link stays
 * usable after a wrong password).
 */
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { CheckCircle, KeyRound, Loader2, MailWarning } from 'lucide-react';
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
    | { kind: 'error'; code?: string; message: string };

type EmailLink = { token: string; uid: string | null };

// Wrong or missing password: the link is still valid, ask again.
const PASSWORD_RETRY_CODES = new Set(['password_mismatch', 'password_required']);

const isAdminProfile = (profile: { is_admin?: boolean; role?: string } | null | undefined) =>
    profile?.is_admin === true || (profile?.role || '').toLowerCase() === 'admin';

const toOutcome = (request: Promise<TokenAuthResult>): Promise<Outcome> =>
    request
        .then((result): Outcome => ({ kind: 'signed-in', result }))
        .catch((err: unknown): Outcome => ({
            kind: 'error',
            code: err instanceof AuthApiError ? err.code : undefined,
            message: err instanceof Error && err.message ? err.message : 'This link could not be used. Please try again.',
        }));

export default function VerifyEmailPage() {
    const djangoAuth = isDjangoAuthBuild();
    const { completeTokenSignIn } = useAuth();
    // The link is read once per page load (the fragment is removed from the
    // address bar), and an existing account's link is posted once: it is
    // single-use, and React runs effects twice in development.
    const link = useRef<EmailLink | null | undefined>(undefined);
    const started = useRef<Promise<Outcome> | null>(null);
    const [state, setState] = useState<'verifying' | 'password' | 'done' | 'missing' | 'error'>('verifying');
    const [failure, setFailure] = useState<{ code?: string; message: string } | null>(null);
    const [password, setPassword] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [passwordError, setPasswordError] = useState('');
    const [email, setEmail] = useState('');
    const [resendState, setResendState] = useState<'idle' | 'sending' | 'sent'>('idle');
    const [resendMessage, setResendMessage] = useState('');

    const finish = async (outcome: Outcome, isActive: () => boolean = () => true) => {
        if (!isActive()) return;
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
        // Full page load: the router cache may hold redirects to /login (lib/authNavigation.ts).
        if (isActive()) navigateAfterAuthChange(destination, { replace: true });
    };

    useEffect(() => {
        if (!djangoAuth) return;
        let active = true;
        if (link.current === undefined) {
            const fragment = takeAuthFragment();
            link.current = fragment.token ? { token: fragment.token, uid: fragment.uid } : null;
        }
        const current = link.current;
        if (!current) {
            setState('missing');
            return;
        }
        if (!current.uid) {
            setState('password'); // a new sign-up: ask for the password chosen at sign-up
            return;
        }
        if (!started.current) started.current = toOutcome(verifyEmailLink({ token: current.token, uid: current.uid }));
        void started.current.then((outcome) => finish(outcome, () => active));
        return () => {
            active = false;
        };
    }, [djangoAuth]);

    const handlePassword = async (e: React.FormEvent) => {
        e.preventDefault();
        const current = link.current;
        if (!current || submitting) return;
        if (!password) {
            setPasswordError('Enter the password you chose when you signed up.');
            return;
        }
        setSubmitting(true);
        setPasswordError('');
        const outcome = await toOutcome(verifyEmailLink({ token: current.token, password }));
        setSubmitting(false);
        if (outcome.kind === 'error' && outcome.code && PASSWORD_RETRY_CODES.has(outcome.code)) {
            setPasswordError(outcome.message);
            return;
        }
        await finish(outcome);
    };

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
    } else if (state === 'password') {
        body = (
            <form onSubmit={handlePassword} className="space-y-4" noValidate>
                <div className="flex items-start gap-3 rounded-2xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-foreground">
                    <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <span>
                        Enter the password you chose when you signed up. This proves the sign-up is yours, so nobody
                        else&apos;s password can end up on your account.
                    </span>
                </div>
                <div className="space-y-2">
                    <label htmlFor="verify-password" className="block text-sm font-semibold text-foreground">
                        Password
                    </label>
                    <Input
                        id="verify-password"
                        type="password"
                        name="password"
                        autoComplete="current-password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        aria-invalid={passwordError ? true : undefined}
                        aria-describedby={passwordError ? 'verify-password-error' : undefined}
                        required
                    />
                    {passwordError && (
                        <p id="verify-password-error" role="alert" className="text-sm text-destructive">{passwordError}</p>
                    )}
                </div>
                <Button type="submit" className="w-full rounded-2xl" size="lg" disabled={submitting}>
                    {submitting ? 'Confirming...' : 'Confirm and create my account'}
                </Button>
                <p className="text-center text-xs text-muted-foreground">
                    Forgot it, or did not sign up yourself?{' '}
                    <Link href="/register" className="font-medium text-primary hover:underline">Sign up again</Link>
                    {' '}to choose a password.
                </p>
            </form>
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
            description="One step finishes setting up your CrackLabs account."
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
