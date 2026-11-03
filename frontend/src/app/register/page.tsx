'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Eye, EyeOff, MailCheck, UserPlus } from 'lucide-react';
import AuthShell from '@/components/AuthShell';
import GoogleSignInButton from '@/components/auth/GoogleSignInButton';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import PasswordStrength from '@/components/PasswordStrength';
import { useAuth } from '@/lib/auth';
import { navigateAfterAuthChange } from '@/lib/authNavigation';
import { extractApiErrorMessage } from '@/lib/api';
import { AuthApiError, resendVerificationEmail } from '@/lib/localAuth';
import {
    USERNAME_HINT,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
    USERNAME_PATTERN,
    usernameProblem,
} from '@/app/settings/username';

export default function RegisterPage() {
    const [form, setForm] = useState({ username: '', email: '', password: '', password2: '', first_name: '', last_name: '' });
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [oauthLoading, setOauthLoading] = useState<'google' | ''>('');
    // Set when Supabase "Confirm email" is on: the account exists but there
    // is no session until the emailed link is opened. Django-native sign-in:
    // always (the account is created when the link is opened).
    const [confirmationSentTo, setConfirmationSentTo] = useState('');
    // Django-native sign-in: error code (extra help), notices, resend, Google.
    const [errorCode, setErrorCode] = useState('');
    const [notice, setNotice] = useState('');
    const [resendState, setResendState] = useState<'idle' | 'sending' | 'sent'>('idle');
    const [googleBusy, setGoogleBusy] = useState(false);
    const { register, oauthLogin, googleLogin, isSupabaseAuth, authMode, googleSignInEnabled } = useAuth();
    const isDjangoAuth = authMode === 'django';

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setForm({ ...form, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setErrorCode('');
        setNotice('');
        if (form.password !== form.password2) {
            setError('Passwords do not match');
            return;
        }
        // Same rules as Settings (accounts/handles.py). The server would give
        // a name that breaks them a generated learner_<hex> handle instead.
        const usernameIssue = usernameProblem(form.username, form.email);
        if (usernameIssue) {
            setError(usernameIssue);
            return;
        }
        setLoading(true);
        try {
            const { needsEmailConfirmation } = await register(form);
            if (needsEmailConfirmation) {
                setConfirmationSentTo(form.email.trim());
                return;
            }
            navigateAfterAuthChange('/dashboard');
        } catch (err: unknown) {
            if (err instanceof AuthApiError) {
                // Django-native sign-up: {detail, code} (invalid_email,
                // invalid_password with the validators' first message,
                // signup_disabled, too_many_attempts).
                setErrorCode(err.code || '');
                setError(err.message || 'Registration failed');
                return;
            }
            const error = err as { response?: { data?: unknown } };
            if (error.response?.data) {
                setError(extractApiErrorMessage(error.response.data, 'Registration failed'));
                return;
            }
            if (err instanceof Error && err.message) {
                if (err.message.toLowerCase().includes('network error')) {
                    setError('Unable to reach authentication server. Please try again in 30-60 seconds.');
                    return;
                }
                setError(err.message);
                return;
            }
            setError('Registration failed');
        } finally {
            setLoading(false);
        }
    };

    // Django-native sign-in: a Google account signs up (or in) directly.
    const handleGoogleCredential = async (credential: string) => {
        setError('');
        setErrorCode('');
        setNotice('');
        setGoogleBusy(true);
        try {
            const signedIn = await googleLogin(credential);
            const isAdmin = signedIn?.is_admin === true || (signedIn?.role || '').toLowerCase() === 'admin';
            navigateAfterAuthChange(isAdmin ? '/admin' : '/dashboard');
        } catch (err: unknown) {
            const code = err instanceof AuthApiError ? err.code || '' : '';
            setErrorCode(code);
            if (code === 'google_link_required') {
                setNotice(
                    'Check your email to link your Google account. An account with this email address already exists, '
                    + 'so we sent a link to that address. Open it within 30 minutes to connect Google sign-in; you will be signed in.',
                );
            } else {
                setError(err instanceof Error && err.message ? err.message : 'Google sign-up failed. Please try again.');
            }
        } finally {
            setGoogleBusy(false);
        }
    };

    const handleResendConfirmation = async () => {
        setResendState('sending');
        try {
            setNotice(await resendVerificationEmail(confirmationSentTo));
            setResendState('sent');
        } catch (err: unknown) {
            setResendState('idle');
            setError(err instanceof Error && err.message ? err.message : 'Could not send the email. Please try again.');
        }
    };

    return (
        <AuthShell
            badge="100% Free to Start"
            title="Create your free CrackCMS account"
            description="Practise PYQs, mocks and AI explanations for UPSC CMS, NEET PG, INI-CET, FMGE and USMLE."
            highlights={[
                'Identify your weak clinical subjects with smart diagnostics.',
                'Master concepts with doctor-grade AI explanations and mnemonics.',
                'Practice with realistic, time-bound PYQ simulators.',
            ]}
        >
            {error && (
                <div role="alert" className="mb-5 rounded-2xl border border-destructive/20 bg-destructive/8 px-4 py-3 text-sm text-destructive">
                    {error}
                    {errorCode === 'account_link_required' && (
                        <>
                            {' '}
                            <Link href="/contact" className="font-semibold underline underline-offset-2">Contact support</Link>
                        </>
                    )}
                </div>
            )}

            {notice && (
                <div role="status" className="mb-5 rounded-2xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">
                    {notice}
                </div>
            )}

            {confirmationSentTo ? (
                <div role="status" className="space-y-4 rounded-2xl border border-primary/20 bg-primary/5 px-5 py-6 text-center">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                        <MailCheck className="h-6 w-6 text-primary" />
                    </div>
                    <div className="space-y-1.5">
                        <p className="text-base font-semibold text-foreground">Check your inbox</p>
                        {isDjangoAuth ? (
                            <p className="text-sm text-muted-foreground break-words">
                                We sent a confirmation link to <span className="font-semibold text-foreground">{confirmationSentTo}</span>.
                                Open it and enter the password you just chose to finish creating your account; you will
                                be signed in. Already have an account with this email? Then the email tells you how to
                                sign in instead.
                            </p>
                        ) : (
                            <p className="text-sm text-muted-foreground break-words">
                                We sent a confirmation link to <span className="font-semibold text-foreground">{confirmationSentTo}</span>.
                                Open it to activate your account, then sign in.
                            </p>
                        )}
                    </div>
                    {isDjangoAuth && (
                        <button
                            type="button"
                            onClick={handleResendConfirmation}
                            disabled={resendState !== 'idle'}
                            className="text-xs font-semibold text-primary underline underline-offset-2 disabled:opacity-60"
                        >
                            {resendState === 'sending' ? 'Sending...' : resendState === 'sent' ? 'Sent again' : "Didn't get it? Send it again"}
                        </button>
                    )}
                    <Button asChild variant="outline" className="w-full rounded-2xl">
                        <Link href="/login">Go to sign in</Link>
                    </Button>
                </div>
            ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                        <label htmlFor="register-first-name" className="mb-2 block text-sm font-semibold text-foreground">First Name</label>
                        <Input
                            id="register-first-name"
                            type="text"
                            name="first_name"
                            placeholder="First name"
                            value={form.first_name}
                            onChange={handleChange}
                        />
                    </div>
                    <div>
                        <label htmlFor="register-last-name" className="mb-2 block text-sm font-semibold text-foreground">Last Name</label>
                        <Input
                            id="register-last-name"
                            type="text"
                            name="last_name"
                            placeholder="Last name"
                            value={form.last_name}
                            onChange={handleChange}
                        />
                    </div>
                </div>

                <div>
                    <label htmlFor="register-username" className="mb-2 block text-sm font-semibold text-foreground">Username</label>
                    <Input
                        id="register-username"
                        type="text"
                        name="username"
                        placeholder="Choose a username"
                        value={form.username}
                        onChange={handleChange}
                        minLength={USERNAME_MIN_LENGTH}
                        maxLength={USERNAME_MAX_LENGTH}
                        pattern={USERNAME_PATTERN}
                        title="3–30 letters, numbers, _ or ."
                        autoComplete="nickname"
                        autoCapitalize="none"
                        spellCheck={false}
                        aria-describedby="register-username-hint"
                        required
                    />
                    <p id="register-username-hint" className="mt-1.5 text-xs text-muted-foreground">
                        {USERNAME_HINT}
                    </p>
                </div>

                <div>
                    <label htmlFor="register-email" className="mb-2 block text-sm font-semibold text-foreground">Email</label>
                    <Input
                        id="register-email"
                        type="email"
                        name="email"
                        placeholder="your@email.com"
                        value={form.email}
                        onChange={handleChange}
                        required
                    />
                </div>

                <div>
                    <label htmlFor="register-password" className="mb-2 block text-sm font-semibold text-foreground">Password</label>
                    <div className="relative">
                        <Input
                            id="register-password"
                            type={showPassword ? 'text' : 'password'}
                            name="password"
                            className="pr-12"
                            placeholder="Use at least 8 characters"
                            value={form.password}
                            onChange={handleChange}
                            required
                        />
                        <button
                            type="button"
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                            onClick={() => setShowPassword(!showPassword)}
                            aria-label={showPassword ? 'Hide password' : 'Show password'}
                        >
                            {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                        </button>
                    </div>
                    <PasswordStrength password={form.password} />
                </div>

                <div>
                    <label htmlFor="register-confirm-password" className="mb-2 block text-sm font-semibold text-foreground">Confirm Password</label>
                    <Input
                        id="register-confirm-password"
                        type="password"
                        name="password2"
                        placeholder="Retype password"
                        value={form.password2}
                        onChange={handleChange}
                        required
                    />
                </div>

                <Button type="submit" className="w-full rounded-2xl" size="lg" disabled={loading || googleBusy}>
                    {loading ? 'Creating account...' : (<><UserPlus className="w-5 h-5" /> Create Account</>)}
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
                <GoogleSignInButton text="signup_with" onCredential={handleGoogleCredential} busy={googleBusy || loading} />
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
                    disabled={oauthLoading !== ''}
                    onClick={async () => {
                        setError('');
                        setOauthLoading('google');
                        try {
                            await oauthLogin('google');
                        } catch (err: unknown) {
                            setError(err instanceof Error ? err.message : 'Google sign-up failed.');
                            setOauthLoading('');
                        }
                    }}
                >
                    {oauthLoading === 'google' ? 'Redirecting...' : (<><svg className="w-4 h-4 mr-2" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg> Continue with Google</>)}
                </Button>
                </>)}
            </form>
            )}

            <p className="mt-6 text-center text-sm text-muted-foreground">
                Already have an account?{' '}
                <Link href="/login" className="font-semibold text-primary hover:underline">
                    Sign in <ArrowRight className="ml-1 inline h-3.5 w-3.5" />
                </Link>
            </p>
        </AuthShell>
    );
}
