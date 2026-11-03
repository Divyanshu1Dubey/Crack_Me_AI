'use client';

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight, Eye, EyeOff, LogIn, Mail } from 'lucide-react';
import AuthShell from '@/components/AuthShell';
import GoogleSignInButton from '@/components/auth/GoogleSignInButton';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/lib/auth';
import { navigateAfterAuthChange } from '@/lib/authNavigation';
import { extractApiErrorMessage } from '@/lib/api';
import { safeInternalPath } from '@/lib/auth-redirect';
import { AuthApiError, resendVerificationEmail } from '@/lib/localAuth';

const isAdminProfile = (profile: unknown): boolean =>
    String((profile as { is_admin?: boolean } | null)?.is_admin) === 'true' ||
    ((profile as { role?: string } | null)?.role || '').toLowerCase() === 'admin';

// Django-native sign-in: 409 google_link_required (an account with this email
// exists but is not linked to that Google account yet; the backend mailed a
// single-use link to the account's address).
const GOOGLE_LINK_NOTICE =
    'Check your email to link your Google account. An account with this email address already exists, '
    + 'so we sent a link to that address. Open it within 30 minutes to connect Google sign-in; you will be signed in.';

export default function LoginClient() {
    const [identifier, setIdentifier] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [magicLinkSent, setMagicLinkSent] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [oauthLoading, setOauthLoading] = useState<'google' | ''>('');
    const [magicLoading, setMagicLoading] = useState(false);
    // Django-native sign-in: the error's code (extra help next to it), an
    // informational notice, the "resend confirmation" button and the Google button.
    const [errorCode, setErrorCode] = useState('');
    const [notice, setNotice] = useState('');
    const [resendState, setResendState] = useState<'idle' | 'sending' | 'sent'>('idle');
    const [googleBusy, setGoogleBusy] = useState(false);
    const signingIn = useRef(false);
    const {
        user, loading: authLoading, login, magicLinkLogin, oauthLogin, googleLogin,
        isSupabaseAuth, authMode, googleSignInEnabled,
    } = useAuth();
    const isDjangoAuth = authMode === 'django';
    const searchParams = useSearchParams();
    const authErrorFromCallback = (searchParams.get('authError') || '').trim();

    // Send admins to the control tower, students to their dashboard. Guard
    // against open-redirect: only same-origin relative paths are accepted
    // (rejects protocol-relative `//evil.com`, absolute URLs, scheme
    // separators, etc.).
    const destinationFor = (signedIn: unknown) =>
        safeInternalPath(searchParams.get('next'), isAdminProfile(signedIn) ? '/admin' : '/dashboard');

    // Django mode: a visitor whose stored session is still valid leaves
    // /login (in Supabase mode the middleware redirects; the token-mode
    // middleware cannot tell a valid session from a stale presence cookie).
    useEffect(() => {
        if (!isDjangoAuth || authLoading || !user || signingIn.current) return;
        navigateAfterAuthChange(destinationFor(user), { replace: true });
    }, [isDjangoAuth, authLoading, user]);

    const clearMessages = () => {
        setError('');
        setErrorCode('');
        setNotice('');
        setResendState('idle');
    };

    /** Django-native sign-in errors carry a code ({detail, code}). */
    const showNativeError = (err: AuthApiError) => {
        setErrorCode(err.code || '');
        if (err.code === 'google_link_required') {
            setNotice(GOOGLE_LINK_NOTICE);
            return;
        }
        setError(err.message || 'Sign-in failed. Please try again.');
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        clearMessages();
        setLoading(true);
        signingIn.current = true;
        try {
            // login() resolves with the freshly-fetched profile (see
            // lib/auth.tsx#login), so we MUST use that value instead of
            // the `user` captured at render time — the render-time
            // snapshot is still the pre-login (often stale or null) value.
            const signedIn = await login(identifier, password);
            // Full page load: the router cache may hold redirects to /login for the
            // protected links prefetched while signed out (lib/authNavigation.ts).
            navigateAfterAuthChange(destinationFor(signedIn));
        } catch (err: unknown) {
            signingIn.current = false;
            if (err instanceof AuthApiError) {
                showNativeError(err);
                return;
            }
            const error = err as { response?: { data?: unknown } };
            if (error.response?.data) {
                setError(extractApiErrorMessage(error.response.data, 'Invalid username or password'));
                return;
            }
            if (err instanceof Error && err.message) {
                if (err.message.toLowerCase().includes('network error')) {
                    setError('Unable to reach authentication server. Please try again in 30-60 seconds.');
                    return;
                }
                if (err.message.toLowerCase().includes('invalid login credentials')) {
                    setError('Invalid email or password. If you signed up before Supabase was enabled, please reset your password to sign in here.');
                    return;
                }
                setError(err.message);
                return;
            }
            setError('Invalid username or password');
        } finally {
            setLoading(false);
        }
    };

    const handleGoogleCredential = async (credential: string) => {
        clearMessages();
        setGoogleBusy(true);
        signingIn.current = true;
        try {
            const signedIn = await googleLogin(credential);
            navigateAfterAuthChange(destinationFor(signedIn));
        } catch (err: unknown) {
            signingIn.current = false;
            if (err instanceof AuthApiError) {
                showNativeError(err);
            } else {
                setError(err instanceof Error && err.message ? err.message : 'Google sign-in failed. Please try again.');
            }
        } finally {
            setGoogleBusy(false);
        }
    };

    const handleResendConfirmation = async () => {
        if (!identifier.includes('@')) return;
        setResendState('sending');
        try {
            setNotice(await resendVerificationEmail(identifier));
            setResendState('sent');
        } catch (err: unknown) {
            setResendState('idle');
            setError(err instanceof Error && err.message ? err.message : 'Could not send the email. Please try again.');
        }
    };

    return (
        <AuthShell
            badge="Welcome Back"
            title="Resume Your Winning Streak"
            description="Log in to access your personalized study dashboard across UPSC CMS, NEET PG, INI-CET, FMGE and USMLE."
            highlights={[
                'Track your daily progress, accuracy, and weak topics.',
                'Access deep AI explanations and medical mnemonics.',
                'Join top medical aspirants competing daily on the leaderboard.',
            ]}
        >
            {authErrorFromCallback && (
                <div className="mb-5 rounded-2xl border border-destructive/20 bg-destructive/8 px-4 py-3 text-sm text-destructive">
                    {decodeURIComponent(authErrorFromCallback)}
                </div>
            )}

            {error && (
                <div role="alert" className="mb-5 rounded-2xl border border-destructive/20 bg-destructive/8 px-4 py-3 text-sm text-destructive">
                    {error}
                    {errorCode === 'account_link_required' && (
                        <>
                            {' '}
                            <Link href="/contact" className="font-semibold underline underline-offset-2">Contact support</Link>
                        </>
                    )}
                    {isDjangoAuth && errorCode === 'invalid_credentials' && (
                        <span className="mt-1.5 block text-xs text-muted-foreground">
                            Signed up with Google? Use the Google button below. Never set a password, or forgot it?{' '}
                            <Link href="/forgot-password" className="font-medium text-primary hover:underline">Reset it here</Link>.
                        </span>
                    )}
                    {errorCode === 'email_not_confirmed' && identifier.includes('@') && (
                        <span className="mt-2 block">
                            <button
                                type="button"
                                onClick={handleResendConfirmation}
                                disabled={resendState !== 'idle'}
                                className="text-xs font-semibold text-primary underline underline-offset-2 disabled:opacity-60"
                            >
                                {resendState === 'sending' ? 'Sending...' : resendState === 'sent' ? 'Confirmation email sent' : 'Resend confirmation email'}
                            </button>
                        </span>
                    )}
                </div>
            )}

            {notice && (
                <div role="status" className="mb-5 rounded-2xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">
                    {notice}
                </div>
            )}

            {magicLinkSent && (
                <div className="mb-5 rounded-2xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">
                    Magic link sent. Check your email inbox and spam folder.
                </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                    <label htmlFor="login-email" className="mb-2 block text-sm font-semibold text-foreground">
                        Email
                    </label>
                    <Input
                        id="login-email"
                        type="email"
                        name="identifier"
                        placeholder="Enter your email"
                        autoComplete="email"
                        value={identifier}
                        onChange={(e) => setIdentifier(e.target.value)}
                        required
                    />
                </div>

                <div>
                    <div className="mb-2 flex items-center justify-between gap-3">
                        <label htmlFor="login-password" className="block text-sm font-semibold text-foreground">Password</label>
                        <Link href="/forgot-password" className="text-xs font-medium text-primary hover:underline">
                            Forgot password?
                        </Link>
                    </div>
                    <div className="relative">
                        <Input
                            id="login-password"
                            type={showPassword ? 'text' : 'password'}
                            name="password"
                            className="pr-12"
                            placeholder="Enter your password"
                            autoComplete="current-password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                        <button
                            type="button"
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                            onClick={() => setShowPassword(!showPassword)}
                            aria-label={showPassword ? 'Hide password' : 'Show password'}
                            aria-pressed={showPassword}
                        >
                            {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                        </button>
                    </div>
                </div>

                <Button type="submit" className="w-full rounded-2xl" size="lg" disabled={loading || googleBusy}>
                    {loading ? 'Signing in...' : (<><LogIn className="w-5 h-5" /> Sign In</>)}
                </Button>

                {isDjangoAuth && googleSignInEnabled && (<>
                <div className="relative py-1">
                    <div className="absolute inset-0 flex items-center">
                        <span className="w-full border-t border-border" />
                    </div>
                    <div className="relative flex justify-center text-xs uppercase">
                        <span className="bg-card px-2 text-muted-foreground">or continue with</span>
                    </div>
                </div>
                <GoogleSignInButton text="signin_with" onCredential={handleGoogleCredential} busy={googleBusy || loading} />
                {googleBusy && <p className="text-center text-xs text-muted-foreground">Signing in with Google...</p>}
                </>)}

                {isSupabaseAuth && (<>
                <div className="relative py-1">
                    <div className="absolute inset-0 flex items-center">
                        <span className="w-full border-t border-border" />
                    </div>
                    <div className="relative flex justify-center text-xs uppercase">
                        <span className="bg-card px-2 text-muted-foreground">or continue with</span>
                    </div>
                </div>

                <Button
                    type="button"
                    variant="outline"
                    className="w-full rounded-2xl"
                    disabled={magicLoading}
                    onClick={async () => {
                        setError('');
                        setMagicLinkSent(false);
                        setMagicLoading(true);
                        try {
                            await magicLinkLogin(identifier);
                            setMagicLinkSent(true);
                        } catch (err: unknown) {
                            setError(err instanceof Error ? err.message : 'Unable to send magic link.');
                        } finally {
                            setMagicLoading(false);
                        }
                    }}
                >
                    {magicLoading ? 'Sending magic link...' : (<><Mail className="w-4 h-4 mr-2" /> Send Magic Link</>)}
                </Button>

                <Button
                    type="button"
                    variant="outline"
                    className="w-full rounded-2xl"
                    disabled={oauthLoading !== ''}
                    onClick={async () => {
                        setError('');
                        setOauthLoading('google');
                        try {
                            await oauthLogin('google');
                        } catch (err: unknown) {
                            setError(err instanceof Error ? err.message : 'Google sign-in failed.');
                            setOauthLoading('');
                        }
                    }}
                >
                    {oauthLoading === 'google' ? 'Redirecting...' : (<><svg className="w-4 h-4 mr-2" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg> Continue with Google</>)}
                </Button>
                </>)}
            </form>

            {isDjangoAuth && (
                <p className="mt-5 text-center text-xs leading-5 text-muted-foreground">
                    Already have an account? Your email and password still work{googleSignInEnabled ? ', and so does Google' : ''}.
                    {' '}Never set a password? Use{' '}
                    <Link href="/forgot-password" className="font-medium text-primary hover:underline">Forgot password</Link>
                    {' '}to set one.
                </p>
            )}

            <p className="mt-6 text-center text-sm text-muted-foreground">
                Don&apos;t have an account?{' '}
                <Link href="/register" className="font-semibold text-primary hover:underline">
                    Create one <ArrowRight className="ml-1 inline h-3.5 w-3.5" />
                </Link>
            </p>
        </AuthShell>
    );
}
