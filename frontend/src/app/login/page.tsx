'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight, Eye, EyeOff, LogIn } from 'lucide-react';
import AuthShell from '@/components/AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/lib/auth';
import { extractApiErrorMessage } from '@/lib/api';

export default function LoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            const signedInUser = await login(username, password);
            const hasAdminAccess = signedInUser.role === 'admin' || signedInUser.is_admin;
            router.push(hasAdminAccess ? '/admin' : '/dashboard');
        } catch (err: unknown) {
            const error = err as { response?: { data?: unknown } };
            if (error.response?.data) {
                setError(extractApiErrorMessage(error.response.data, 'Invalid username or password'));
                return;
            }
            if (err instanceof Error && err.message) {
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
            {error && (
                <div className="mb-5 rounded-2xl border border-destructive/20 bg-destructive/8 px-4 py-3 text-sm text-destructive">
                    {error}
                </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                    <label className="mb-2 block text-sm font-semibold text-foreground">Username</label>
                    <Input
                        type="text"
                        name="username"
                        placeholder="Enter your username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
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
