'use client';

import { useEffect, useRef, useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, CheckCircle, Lock } from 'lucide-react';
import AuthShell from '@/components/AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import PasswordStrength from '@/components/PasswordStrength';
import { authAPI } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { navigateAfterAuthChange } from '@/lib/authNavigation';
import { takeAuthFragment } from '@/lib/authFragment';
import { AuthApiError, confirmPasswordReset } from '@/lib/localAuth';
import { isDjangoAuthBuild } from '@/lib/localSession';

function ResetPasswordForm() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        if (password.length < 8) {
            setError('Password must be at least 8 characters.');
            return;
        }
        if (password !== confirmPassword) {
            setError('Passwords do not match.');
            return;
        }
        
        setLoading(true);
        try {
            // Supabase implicitly creates a session when the user clicks the reset link.
            // We just need to update the user's password.
            const { getSupabaseBrowserClient } = await import('@/lib/supabase');
            const supabase = getSupabaseBrowserClient();
            if (!supabase) throw new Error('Supabase client not initialized');

            const { error: updateError } = await supabase.auth.updateUser({ password });
            
            if (updateError) {
                throw new Error(updateError.message);
            }
            
            setSuccess(true);
            setTimeout(() => router.push('/login'), 3000);
        } catch (err: unknown) {
            const error = err as { message?: string };
            setError(error.message || 'Reset link is invalid or expired. Please request a new one.');
        }
        setLoading(false);
    };



    if (success) {
        return (
            <div className="space-y-4 text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/40">
                    <CheckCircle className="h-8 w-8 text-emerald-600 dark:text-emerald-300" />
                </div>
                <p className="text-sm font-medium text-foreground">Password reset successfully.</p>
                <p className="text-xs text-muted-foreground">Redirecting to login...</p>
            </div>
        );
    }

    return (
        <form onSubmit={handleSubmit} className="space-y-5">
            <div>
                <label className="mb-2 block text-sm font-semibold text-foreground">New Password</label>
                <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                        type="password"
                        name="password"
                        className="pl-10"
                        placeholder="Minimum 8 characters"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        required
                    />
                </div>
                <PasswordStrength password={password} />
            </div>

            <div>
                <label className="mb-2 block text-sm font-semibold text-foreground">Confirm Password</label>
                <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                        type="password"
                        name="password2"
                        className="pl-10"
                        placeholder="Re-enter password"
                        value={confirmPassword}
                        onChange={e => setConfirmPassword(e.target.value)}
                        required
                    />
                </div>
            </div>

            {error ? <p className="text-sm text-destructive">{error}</p> : null}

            <Button type="submit" className="w-full rounded-2xl" size="lg" disabled={loading}>
                {loading ? 'Resetting...' : 'Reset Password'}
            </Button>

            <Button asChild variant="ghost" className="w-full rounded-2xl">
                <Link href="/login">
                    <ArrowLeft className="w-4 h-4" /> Back to Login
                </Link>
            </Button>
        </form>
    );
}

/**
 * Django-native sign-in (NEXT_PUBLIC_AUTH_MODE=django): the emailed link is
 * /reset-password#uid=<u>&token=<t>. The values are read once from the URL
 * fragment (never the query string) and removed from the address bar; the
 * new password is posted with them to /api/auth/password-reset/confirm/,
 * which sets it, ends every other session and signs this browser in.
 */
function DjangoResetPasswordForm() {
    const router = useRouter();
    const { completeTokenSignIn } = useAuth();
    const link = useRef<{ uid: string; token: string } | null>(null);
    const [linkState, setLinkState] = useState<'reading' | 'ready' | 'missing'>('reading');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [linkExpired, setLinkExpired] = useState(false);
    const [success, setSuccess] = useState(false);

    useEffect(() => {
        const { uid, token } = takeAuthFragment();
        if (uid && token) {
            link.current = { uid, token };
            setLinkState('ready');
        } else if (!link.current) {
            // (A second effect run in development finds the fragment already removed.)
            setLinkState('missing');
        }
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        const current = link.current;
        if (!current) {
            setLinkState('missing');
            return;
        }
        if (password.length < 8) {
            setError('Password must be at least 8 characters.');
            return;
        }
        if (password !== confirmPassword) {
            setError('Passwords do not match.');
            return;
        }
        setLoading(true);
        try {
            const result = await confirmPasswordReset({ uid: current.uid, token: current.token, newPassword: password });
            link.current = null; // single-use
            setSuccess(true);
            let destination = '/dashboard';
            try {
                const signedIn = await completeTokenSignIn(result);
                if (signedIn?.is_admin === true || (signedIn?.role || '').toLowerCase() === 'admin') destination = '/admin';
            } catch {
                destination = '/login';
            }
            window.setTimeout(() => navigateAfterAuthChange(destination, { replace: true }), 1500);
        } catch (err: unknown) {
            if (err instanceof AuthApiError && err.code === 'invalid_or_expired_link') {
                link.current = null;
                setLinkExpired(true);
            }
            setError(err instanceof Error && err.message ? err.message : 'Reset link is invalid or expired. Please request a new one.');
        } finally {
            setLoading(false);
        }
    };

    if (success) {
        return (
            <div role="status" className="space-y-4 text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/40">
                    <CheckCircle className="h-8 w-8 text-emerald-600 dark:text-emerald-300" />
                </div>
                <p className="text-sm font-medium text-foreground">Password changed. You are signed in.</p>
                <p className="text-xs text-muted-foreground">Your other devices were signed out. Opening your dashboard...</p>
            </div>
        );
    }

    if (linkState === 'reading') {
        return <div className="text-center text-sm text-muted-foreground">Loading...</div>;
    }

    if (linkState === 'missing' || linkExpired) {
        return (
            <div className="space-y-5 text-center">
                <p className="text-sm leading-6 text-muted-foreground">
                    {linkExpired
                        ? error || 'This reset link is invalid or has expired.'
                        : 'This page needs the link from your password reset email. Open the link from the email again, or request a new one.'}
                </p>
                <Button asChild className="w-full rounded-2xl" size="lg">
                    <Link href="/forgot-password">Request a new reset link</Link>
                </Button>
                <Button asChild variant="ghost" className="w-full rounded-2xl">
                    <Link href="/login">
                        <ArrowLeft className="w-4 h-4" /> Back to Login
                    </Link>
                </Button>
            </div>
        );
    }

    return (
        <form onSubmit={handleSubmit} className="space-y-5">
            <div>
                <label htmlFor="reset-new-password" className="mb-2 block text-sm font-semibold text-foreground">New Password</label>
                <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                        id="reset-new-password"
                        type="password"
                        name="password"
                        className="pl-10"
                        placeholder="Minimum 8 characters"
                        autoComplete="new-password"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        required
                    />
                </div>
                <PasswordStrength password={password} />
            </div>

            <div>
                <label htmlFor="reset-confirm-password" className="mb-2 block text-sm font-semibold text-foreground">Confirm Password</label>
                <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                        id="reset-confirm-password"
                        type="password"
                        name="password2"
                        className="pl-10"
                        placeholder="Re-enter password"
                        autoComplete="new-password"
                        value={confirmPassword}
                        onChange={e => setConfirmPassword(e.target.value)}
                        required
                    />
                </div>
            </div>

            {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}

            <Button type="submit" className="w-full rounded-2xl" size="lg" disabled={loading}>
                {loading ? 'Saving...' : 'Set New Password'}
            </Button>

            <Button asChild variant="ghost" className="w-full rounded-2xl">
                <Link href="/login">
                    <ArrowLeft className="w-4 h-4" /> Back to Login
                </Link>
            </Button>
        </form>
    );
}

export default function ResetPasswordPage() {
    const djangoAuth = isDjangoAuthBuild();
    return (
        <AuthShell
            badge="Security Update"
            title="Set Your New Password"
            description="Safeguard your progress by selecting a strong, unique password."
            highlights={[
                'Must be at least 8 characters in length.',
                'Include letters, numbers, and special symbols for maximum security.',
                'Instantly return to your dashboard after updating.',
            ]}
        >
            <Suspense fallback={<div className="text-center text-muted-foreground">Loading...</div>}>
                {djangoAuth ? <DjangoResetPasswordForm /> : <ResetPasswordForm />}
            </Suspense>
        </AuthShell>
    );
}
