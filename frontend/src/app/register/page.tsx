'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { Zap, Eye, EyeOff, UserPlus } from 'lucide-react';

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
        <div className="min-h-screen flex items-center justify-center px-4 py-8" style={{ background: 'var(--bg-primary)' }}>
            <div className="glass-card p-8 w-full max-w-md animate-fadeInUp">
                <div className="text-center mb-8">
                    <div className="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-4" style={{ background: 'var(--gradient-primary)' }}>
                        <Zap className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold">Create Account</h1>
                    <p style={{ color: 'var(--text-secondary)' }}>Start your UPSC CMS preparation journey</p>
                </div>

                {error && (
                    <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium mb-2">First Name</label>
                            <input type="text" name="first_name" className="input-field" placeholder="First name"
                                value={form.first_name} onChange={handleChange} />
                        </div>
                        <div>
                            <label className="block text-sm font-medium mb-2">Last Name</label>
                            <input type="text" name="last_name" className="input-field" placeholder="Last name"
                                value={form.last_name} onChange={handleChange} />
                        </div>
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-2">Username</label>
                        <input type="text" name="username" className="input-field" placeholder="Choose a username"
                            value={form.username} onChange={handleChange} required />
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-2">Email</label>
                        <input type="email" name="email" className="input-field" placeholder="your@email.com"
                            value={form.email} onChange={handleChange} required />
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-2">Password</label>
                        <div className="relative">
                            <input type={showPassword ? 'text' : 'password'} name="password" className="input-field pr-12"
                                placeholder="Min 6 characters" value={form.password} onChange={handleChange} required />
                            <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2"
                                onClick={() => setShowPassword(!showPassword)} style={{ color: 'var(--text-secondary)' }}>
                                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                            </button>
                        </div>
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-2">Confirm Password</label>
                        <input type="password" name="password2" className="input-field" placeholder="Retype password"
                            value={form.password2} onChange={handleChange} required />
                    </div>
                    <button type="submit" className="btn-primary w-full justify-center py-3" disabled={loading}>
                        {loading ? 'Creating account...' : (<><UserPlus className="w-5 h-5" /> Create Account</>)}
                    </button>
                </form>

                <p className="text-center mt-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Already have an account?{' '}
                    <Link href="/login" className="font-medium" style={{ color: 'var(--accent-primary)' }}>Sign in</Link>
                </p>
            </div>
        </div>
    );
}
