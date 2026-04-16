'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight, Eye, EyeOff, Github, LogIn, Mail } from 'lucide-react';
import AuthShell from '@/components/AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/lib/auth';
import { extractApiErrorMessage } from '@/lib/api';

export default function LoginClient() {
    const [identifier, setIdentifier] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [magicLinkSent, setMagicLinkSent] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [oauthLoading, setOauthLoading] = useState<'google' | 'github' | ''>('');
    const [magicLoading, setMagicLoading] = useState(false);
    const { login, isSupabaseAuth, magicLinkLogin, oauthLogin } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();
    const authErrorFromCallback = (searchParams.get('authError') || '').trim();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            const signedInUser = await login(identifier, password);
            const hasAdminAccess = signedInUser.role === 'admin' || signedInUser.is_admin;
            router.push(hasAdminAccess ? '/admin' : '/dashboard');
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
            description="Log in to access your personalized UPSC CMS study dashboard and continue climbing the ranks."
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
                    <label className="mb-2 block text-sm font-semibold text-foreground">
                        {isSupabaseAuth ? 'Email' : 'Username'}
                    </label>
                    <Input
                        type={isSupabaseAuth ? 'email' : 'text'}
                        name="identifier"
                        placeholder={isSupabaseAuth ? 'Enter your email' : 'Enter your username'}
                        value={identifier}
                        onChange={(e) => setIdentifier(e.target.value)}
                        required
                    />
                </div>

                <div>
                    <div className="mb-2 flex items-center justify-between gap-3">
                        <label className="block text-sm font-semibold text-foreground">Password</label>
                        <Link href="/forgot-password" className="text-xs font-medium text-primary hover:underline">
                            Forgot password?
                        </Link>
                    </div>
                    <div className="relative">
                        <Input
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

                {isSupabaseAuth && (
                    <>
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

                        <div className="grid grid-cols-2 gap-3">
                            <Button
                                type="button"
                                variant="outline"
                                className="rounded-2xl"
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
                                {oauthLoading === 'google' ? 'Redirecting...' : 'Google'}
                            </Button>

                            <Button
                                type="button"
                                variant="outline"
                                className="rounded-2xl"
                                disabled={oauthLoading !== ''}
                                onClick={async () => {
                                    setError('');
                                    setOauthLoading('github');
                                    try {
                                        await oauthLogin('github');
                                    } catch (err: unknown) {
                                        setError(err instanceof Error ? err.message : 'GitHub sign-in failed.');
                                        setOauthLoading('');
                                    }
                                }}
                            >
                                {oauthLoading === 'github' ? 'Redirecting...' : (<><Github className="w-4 h-4" /> GitHub</>)}
                            </Button>
                        </div>
                    </>
                )}
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
