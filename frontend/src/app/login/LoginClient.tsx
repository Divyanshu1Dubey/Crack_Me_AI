'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight, Eye, EyeOff, LogIn, Mail } from 'lucide-react';
import AuthShell from '@/components/AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/lib/auth';
import { extractApiErrorMessage } from '@/lib/api';
import { safeInternalPath } from '@/lib/auth-redirect';

export default function LoginClient() {
    const [identifier, setIdentifier] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [magicLinkSent, setMagicLinkSent] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [oauthLoading, setOauthLoading] = useState<'google' | ''>('');
    const [magicLoading, setMagicLoading] = useState(false);
    const { login, magicLinkLogin, oauthLogin } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();
    const authErrorFromCallback = (searchParams.get('authError') || '').trim();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            // login() resolves with the freshly-fetched profile (see
            // lib/auth.tsx#login), so we MUST use that value instead of
            // the `user` captured at render time — the render-time
            // snapshot is still the pre-login (often stale or null) value.
            const signedIn = await login(identifier, password);
            // Send admins to the control tower, students to their dashboard.
            const rawNext = searchParams.get('next');
            const isAdmin =
                String((signedIn as { is_admin?: boolean } | null)?.is_admin) === 'true' ||
                ((signedIn as { role?: string } | null)?.role || '').toLowerCase() === 'admin';
            const fallback = isAdmin ? '/admin' : '/dashboard';
            // Guard against open-redirect: only accept same-origin relative paths
            // (rejects protocol-relative `//evil.com`, absolute URLs, scheme
            // separators, etc.).
            router.push(safeInternalPath(rawNext, fallback));
        } catch (err: unknown) {
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
                <div className="mb-5 rounded-2xl border border-destructive/20 bg-destructive/8 px-4 py-3 text-sm text-destructive">
                    {error}
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
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
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
                </div>

                <Button type="submit" className="w-full rounded-2xl" size="lg" disabled={loading}>
                    {loading ? 'Signing in...' : (<><LogIn className="w-5 h-5" /> Sign In</>)}
                </Button>

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
                    {magicLoading ? 'Sending magic link...' : (<><Mail className="w-4 h-4" /> Send Magic Link</>)}
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
            </form>

            <p className="mt-6 text-center text-sm text-muted-foreground">
                Don&apos;t have an account?{' '}
                <Link href="/register" className="font-semibold text-primary hover:underline">
                    Create one <ArrowRight className="ml-1 inline h-3.5 w-3.5" />
                </Link>
            </p>
        </AuthShell>
    );
}
