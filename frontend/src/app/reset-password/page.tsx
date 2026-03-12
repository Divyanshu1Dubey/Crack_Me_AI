'use client';
import { useState, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { authAPI } from '@/lib/api';
import { Lock, Zap, CheckCircle } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import PasswordStrength from '@/components/PasswordStrength';

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
        if (password.length < 8) { setError('Password must be at least 8 characters.'); return; }
        if (password !== confirmPassword) { setError('Passwords do not match.'); return; }
        if (!uid || !token) { setError('Invalid reset link. Please request a new one.'); return; }
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
            <div className="text-center space-y-4">
                <p className="text-sm text-destructive">Invalid reset link.</p>
                <Link href="/forgot-password">
                    <Button variant="outline">Request New Reset Link</Button>
                </Link>
            </div>
        );
    }

    return success ? (
        <div className="text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900 flex items-center justify-center mx-auto">
                <CheckCircle className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />
            </div>
            <p className="text-sm font-medium text-foreground">Password reset successfully!</p>
            <p className="text-xs text-muted-foreground">Redirecting to login...</p>
        </div>
    ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
            <div>
                <label className="text-sm font-medium mb-1.5 block text-foreground">New Password</label>
                <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input type="password" className="pl-10" placeholder="Minimum 8 characters"
                        value={password} onChange={e => setPassword(e.target.value)} required />
                </div>
                <PasswordStrength password={password} />
            </div>
            <div>
                <label className="text-sm font-medium mb-1.5 block text-foreground">Confirm Password</label>
                <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input type="password" className="pl-10" placeholder="Re-enter password"
                        value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} required />
                </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
                {loading ? 'Resetting...' : 'Reset Password'}
            </Button>
        </form>
    );
}

export default function ResetPasswordPage() {
    return (
        <div className="min-h-screen flex items-center justify-center bg-background px-4">
            <Card className="w-full max-w-md">
                <CardContent className="p-8">
                    <div className="text-center mb-6">
                        <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center mx-auto mb-4">
                            <Zap className="w-6 h-6 text-primary-foreground" />
                        </div>
                        <h1 className="text-2xl font-bold text-foreground">Set New Password</h1>
                    </div>
                    <Suspense fallback={<div className="text-center text-muted-foreground">Loading...</div>}>
                        <ResetPasswordForm />
                    </Suspense>
                </CardContent>
            </Card>
        </div>
    );
}
