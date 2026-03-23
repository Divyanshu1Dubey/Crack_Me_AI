'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight, Eye, EyeOff, UserPlus } from 'lucide-react';
import AuthShell from '@/components/AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import PasswordStrength from '@/components/PasswordStrength';
import { useAuth } from '@/lib/auth';

export default function RegisterPage() {
    const [form, setForm] = useState({ username: '', email: '', password: '', password2: '', first_name: '', last_name: '' });
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { register } = useAuth();
    const router = useRouter();

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setForm({ ...form, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        if (form.password !== form.password2) {
            setError('Passwords do not match');
            return;
        }
        setLoading(true);
        try {
            await register(form);
            router.push('/dashboard');
        } catch (err: unknown) {
            const error = err as { response?: { data?: Record<string, string[]> } };
            setError(error.response?.data ? Object.values(error.response.data).flat().join(', ') : 'Registration failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <AuthShell
            badge="100% Free to Start"
            title="Join the Elite CMS System"
            description="Sign up to unlock an intelligent, AI-powered UPSC CMS preparation platform."
            highlights={[
                'Identify your weak clinical subjects with smart diagnostics.',
                'Master concepts with doctor-grade AI explanations and mnemonics.',
                'Practice with realistic, time-bound PYQ simulators.',
            ]}
        >
            {error && (
                <div className="mb-5 rounded-2xl border border-destructive/20 bg-destructive/8 px-4 py-3 text-sm text-destructive">
                    {error}
                </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="mb-2 block text-sm font-semibold text-foreground">First Name</label>
                        <Input
                            type="text"
                            name="first_name"
                            placeholder="First name"
                            value={form.first_name}
                            onChange={handleChange}
                        />
                    </div>
                    <div>
                        <label className="mb-2 block text-sm font-semibold text-foreground">Last Name</label>
                        <Input
                            type="text"
                            name="last_name"
                            placeholder="Last name"
                            value={form.last_name}
                            onChange={handleChange}
                        />
                    </div>
                </div>

                <div>
                    <label className="mb-2 block text-sm font-semibold text-foreground">Username</label>
                    <Input
                        type="text"
                        name="username"
                        placeholder="Choose a username"
                        value={form.username}
                        onChange={handleChange}
                        required
                    />
                </div>

                <div>
                    <label className="mb-2 block text-sm font-semibold text-foreground">Email</label>
                    <Input
                        type="email"
                        name="email"
                        placeholder="your@email.com"
                        value={form.email}
                        onChange={handleChange}
                        required
                    />
                </div>

                <div>
                    <label className="mb-2 block text-sm font-semibold text-foreground">Password</label>
                    <div className="relative">
                        <Input
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
                    <label className="mb-2 block text-sm font-semibold text-foreground">Confirm Password</label>
                    <Input
                        type="password"
                        name="password2"
                        placeholder="Retype password"
                        value={form.password2}
                        onChange={handleChange}
                        required
                    />
                </div>

                <Button type="submit" className="w-full rounded-2xl" size="lg" disabled={loading}>
                    {loading ? 'Creating account...' : (<><UserPlus className="w-5 h-5" /> Create Account</>)}
                </Button>
            </form>

            <p className="mt-6 text-center text-sm text-muted-foreground">
                Already have an account?{' '}
                <Link href="/login" className="font-semibold text-primary hover:underline">
                    Sign in <ArrowRight className="ml-1 inline h-3.5 w-3.5" />
                </Link>
            </p>
        </AuthShell>
    );
}
