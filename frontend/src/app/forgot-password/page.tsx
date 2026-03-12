'use client';
import { useState } from 'react';
import { authAPI } from '@/lib/api';
import { Mail, ArrowLeft, Zap } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';

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
        <div className="min-h-screen flex items-center justify-center bg-background px-4">
            <Card className="w-full max-w-md">
                <CardContent className="p-8">
                    <div className="text-center mb-6">
                        <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center mx-auto mb-4">
                            <Zap className="w-6 h-6 text-primary-foreground" />
                        </div>
                        <h1 className="text-2xl font-bold text-foreground">Reset Password</h1>
                        <p className="text-sm text-muted-foreground mt-1">
                            Enter your email and we&apos;ll send you a reset link
                        </p>
                    </div>

                    {submitted ? (
                        <div className="text-center space-y-4">
                            <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900 flex items-center justify-center mx-auto">
                                <Mail className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />
                            </div>
                            <p className="text-sm text-foreground font-medium">Check your email!</p>
                            <p className="text-xs text-muted-foreground">
                                If an account with that email exists, we&apos;ve sent a password reset link.
                                Check your inbox (and spam folder).
                            </p>
                            <Link href="/login">
                                <Button variant="outline" className="mt-4">
                                    <ArrowLeft className="w-4 h-4 mr-2" /> Back to Login
                                </Button>
                            </Link>
                        </div>
                    ) : (
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="text-sm font-medium mb-1.5 block text-foreground">Email Address</label>
                                <div className="relative">
                                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                    <Input
                                        type="email"
                                        className="pl-10"
                                        placeholder="you@example.com"
                                        value={email}
                                        onChange={e => setEmail(e.target.value)}
                                        required
                                    />
                                </div>
                            </div>
                            {error && <p className="text-sm text-destructive">{error}</p>}
                            <Button type="submit" className="w-full" disabled={loading}>
                                {loading ? 'Sending...' : 'Send Reset Link'}
                            </Button>
                            <div className="text-center">
                                <Link href="/login" className="text-sm text-primary hover:underline">
                                    Back to Login
                                </Link>
                            </div>
                        </form>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
