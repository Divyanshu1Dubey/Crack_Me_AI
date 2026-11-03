'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Mail, MailCheck } from 'lucide-react';
import AuthShell from '@/components/AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/lib/auth';

export default function ForgotPasswordPage() {
    const { resetPassword, authMode } = useAuth();
    // Django-native sign-in: the link works once and for PASSWORD_RESET_TIMEOUT
    // (1 hour by default); it also sets a first password for Google-only accounts.
    const isDjangoAuth = authMode === 'django';
    const [email, setEmail] = useState('');
    const [submitted, setSubmitted] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!email.trim()) return;
        setLoading(true);
        setError('');
        try {
            await resetPassword(email.trim());
            setSubmitted(true);
        } catch (err: unknown) {
            const error = err as { message?: string };
            setError(error.message || 'Something went wrong. Please try again.');
        }
        setLoading(false);
    };

    return (
        <AuthShell
            badge="Account Recovery"
            title="Regain Access"
            description="Enter your registered email address to receive a secure password reset link."
            highlights={isDjangoAuth ? [
                'Reset links work once and expire after an hour.',
                'Signed up with Google? The same link sets a first password.',
                'Ensure to check both your inbox and spam folders.',
            ] : [
                'Secure reset links remain active for 24 hours.',
                'Ensure to check both your inbox and spam folders.',
                'Regain access to your study dashboard seamlessly.',
            ]}
        >
            {submitted ? (
                <div className="space-y-5 text-center">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/40">
                        <MailCheck className="h-8 w-8 text-emerald-600 dark:text-emerald-300" />
                    </div>
                    <div>
                        <p className="text-lg font-semibold text-foreground">Check your email</p>
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                            If an account with that email exists, CrackCMS has sent a reset link. Check your inbox and spam folder.
                        </p>
                        {isDjangoAuth && (
                            <p className="mt-2 text-xs leading-5 text-muted-foreground">
                                The link works once and expires after an hour. Open it on any device to choose a new password; you will be signed in.
                            </p>
                        )}
                    </div>
                    <Button asChild variant="outline" className="rounded-2xl">
                        <Link href="/login">
                            <ArrowLeft className="w-4 h-4" /> Back to Login
                        </Link>
                    </Button>
                </div>
            ) : (
                <form onSubmit={handleSubmit} className="space-y-5">
                    <div>
                        <label className="mb-2 block text-sm font-semibold text-foreground">Email Address</label>
                        <div className="relative">
                            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <Input
                                type="email"
                                name="email"
                                className="pl-10"
                                placeholder="you@example.com"
                                value={email}
                                onChange={e => setEmail(e.target.value)}
                                required
                            />
                        </div>
                    </div>
                    {error ? <p className="text-sm text-destructive">{error}</p> : null}
                    <Button type="submit" className="w-full rounded-2xl" size="lg" disabled={loading}>
                        {loading ? 'Sending...' : 'Send Reset Link'}
                    </Button>
                    <div className="text-center">
                        <Link href="/login" className="text-sm font-medium text-primary hover:underline">
                            Back to Login
                        </Link>
                    </div>
                </form>
            )}
        </AuthShell>
    );
}
