'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight, Eye, EyeOff, ShieldCheck } from 'lucide-react';
import AuthShell from '@/components/AuthShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/lib/auth';
import { authAPI, extractApiErrorMessage } from '@/lib/api';

export default function AdminLoginPage() {
  const router = useRouter();
  const { login, logout, user, isAuthenticated, loading: authLoading } = useAuth();

  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!authLoading && isAuthenticated && (user?.role === 'admin' || user?.is_admin)) {
      router.replace('/admin');
    }
  }, [authLoading, isAuthenticated, router, user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(username, password);
      const profile = await authAPI.getProfile();
      const isAdmin = profile.data?.role === 'admin' || profile.data?.is_admin;

      if (!isAdmin) {
        logout();
        setError('This account does not have admin access.');
        return;
      }

      router.push('/admin');
    } catch (err: unknown) {
      const apiError = err as { response?: { data?: unknown } };
      setError(extractApiErrorMessage(apiError.response?.data, 'Admin login failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      badge="Admin Access"
      title="Admin Control Center"
      description="Sign in with administrator credentials to manage users, questions, and platform operations."
      mode="admin"
      highlights={[
        'Moderate feedback and grant AI tokens.',
        'Monitor growth metrics and quality signals.',
        'Manage announcements and student operations.',
      ]}
    >
      {error && (
        <div className="mb-5 rounded-2xl border border-destructive/20 bg-destructive/8 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="mb-2 block text-sm font-semibold text-foreground">Admin Username</label>
          <Input
            type="text"
            name="username"
            placeholder="admin"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
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
              placeholder="Enter admin password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              onClick={() => setShowPassword((prev) => !prev)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
        </div>

        <Button type="submit" className="w-full rounded-2xl" size="lg" disabled={loading}>
          {loading ? 'Signing in...' : (<><ShieldCheck className="w-5 h-5" /> Admin Sign In</>)}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Student account?{' '}
        <Link href="/login" className="font-semibold text-primary hover:underline">
          Go to student login <ArrowRight className="ml-1 inline h-3.5 w-3.5" />
        </Link>
      </p>
    </AuthShell>
  );
}
