'use client';

import { useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, CheckCircle, Lock } from 'lucide-react';
import AuthShell from '@/components/AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import PasswordStrength from '@/components/PasswordStrength';
import { authAPI } from '@/lib/api';

function ResetPasswordForm() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const uid = searchParams.get('uid') || '';
    const token = searchParams.get('token') || '';
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
        if (!uid || !token) {
            setError('Invalid reset link. Please request a new one.');
            return;
        }
        setLoading(true);
        try {
            await authAPI.confirmPasswordReset({ uid, token, new_password: password });
            setSuccess(true);
            setTimeout(() => router.push('/login'), 3000);
        } catch (err: unknown) {
            const msg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error;
            setError(msg || 'Reset link is invalid or expired. Please request a new one.');
        }
        setLoading(false);
    };

    if (!uid || !token) {
        return (
            <div className="space-y-4 text-center">
                <p className="text-sm text-destructive">Invalid reset link.</p>
                <Button asChild variant="outline" className="rounded-2xl">
                    <Link href="/forgot-password">Request New Reset Link</Link>
                </Button>
            </div>
        );
    }

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

export default function ResetPasswordPage() {
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
                <ResetPasswordForm />
            </Suspense>
        </AuthShell>
    );
}
