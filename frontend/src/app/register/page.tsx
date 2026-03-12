'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { Zap, Eye, EyeOff, UserPlus } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import PasswordStrength from '@/components/PasswordStrength';

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
        <div className="min-h-screen flex items-center justify-center px-4 py-8 bg-background">
            <Card className="w-full max-w-md">
                <CardContent className="p-8">
                    <div className="text-center mb-8">
                        <div className="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-4 bg-primary">
                            <Zap className="w-8 h-8 text-primary-foreground" />
                        </div>
                        <h1 className="text-2xl font-bold text-foreground">Create Account</h1>
                        <p className="text-muted-foreground">Start your UPSC CMS preparation journey</p>
                    </div>

                    {error && (
                        <div className="mb-4 p-3 rounded-lg text-sm bg-destructive/10 text-destructive border border-destructive/20">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium mb-2 text-foreground">First Name</label>
                                <Input type="text" name="first_name" placeholder="First name"
                                    value={form.first_name} onChange={handleChange} />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-2 text-foreground">Last Name</label>
                                <Input type="text" name="last_name" placeholder="Last name"
                                    value={form.last_name} onChange={handleChange} />
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2 text-foreground">Username</label>
                            <Input type="text" name="username" placeholder="Choose a username"
                                value={form.username} onChange={handleChange} required />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2 text-foreground">Email</label>
                            <Input type="email" name="email" placeholder="your@email.com"
                                value={form.email} onChange={handleChange} required />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2 text-foreground">Password</label>
                            <div className="relative">
                                <Input type={showPassword ? 'text' : 'password'} name="password" className="pr-12"
                                    placeholder="Min 6 characters" value={form.password} onChange={handleChange} required />
                                <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                                    onClick={() => setShowPassword(!showPassword)}>
                                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                                </button>
                            </div>
                            <PasswordStrength password={form.password} />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2 text-foreground">Confirm Password</label>
                            <Input type="password" name="password2" placeholder="Retype password"
                                value={form.password2} onChange={handleChange} required />
                        </div>
                        <Button type="submit" className="w-full" disabled={loading}>
                            {loading ? 'Creating account...' : (<><UserPlus className="w-5 h-5" /> Create Account</>)}
                        </Button>
                    </form>

                    <p className="text-center mt-6 text-sm text-muted-foreground">
                        Already have an account?{' '}
                        <Link href="/login" className="font-medium text-primary hover:underline">Sign in</Link>
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}
