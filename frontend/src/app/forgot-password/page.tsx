'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Mail, MailCheck } from 'lucide-react';
import AuthShell from '@/components/AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { authAPI } from '@/lib/api';

export default function ForgotPasswordPage() {
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
            await authAPI.requestPasswordReset({ email: email.trim() });
            setSubmitted(true);
        } catch {
            setError('Something went wrong. Please try again.');
        }
        setLoading(false);
    };

    return (
        <AuthShell
            badge="Account Recovery"
            title="Regain Access"
            description="Enter your registered email address to receive a secure password reset link."
            highlights={[
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
