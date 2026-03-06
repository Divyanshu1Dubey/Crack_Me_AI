'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { Zap, Eye, EyeOff, LogIn } from 'lucide-react';

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
            await login(username, password);
            router.push('/dashboard');
        } catch {
            setError('Invalid username or password');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg-primary)' }}>
            <div className="glass-card p-8 w-full max-w-md animate-fadeInUp">
                <div className="text-center mb-8">
                    <div className="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-4" style={{ background: 'var(--gradient-primary)' }}>
                        <Zap className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold">Welcome Back</h1>
                    <p style={{ color: 'var(--text-secondary)' }}>Sign in to continue your CMS preparation</p>
                </div>

                {error && (
                    <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-2">Username</label>
                        <input
                            type="text"
                            className="input-field"
                            placeholder="Enter your username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-2">Password</label>
                        <div className="relative">
                            <input
                                type={showPassword ? 'text' : 'password'}
                                className="input-field pr-12"
                                placeholder="Enter your password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                            <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2"
                                onClick={() => setShowPassword(!showPassword)} style={{ color: 'var(--text-secondary)' }}>
                                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                            </button>
                        </div>
                    </div>
                    <button type="submit" className="btn-primary w-full justify-center py-3" disabled={loading}>
                        {loading ? 'Signing in...' : (<><LogIn className="w-5 h-5" /> Sign In</>)}
                    </button>
                </form>

                <p className="text-center mt-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Don&apos;t have an account?{' '}
                    <Link href="/register" className="font-medium" style={{ color: 'var(--accent-primary)' }}>Create one</Link>
                </p>
            </div>
        </div>
    );
}
