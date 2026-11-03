'use client';

/**
 * Settings > Sign-in methods, for the Django-native sign-in only
 * (NEXT_PUBLIC_AUTH_MODE=django; the profile's `auth_methods`):
 *  - change the password (POST /api/auth/native/password/; the other
 *    sessions are signed out), or set a first one by email for Google-only
 *    accounts (the reset link);
 *  - connect Google sign-in (the GIS button, loaded only after "Connect
 *    Google" is clicked; POST /api/auth/google/link/, which needs a sign-in
 *    from the last 15 minutes) or disconnect it (DELETE, refused when it is
 *    the account's only way to sign in).
 */
import { useState } from 'react';
import Link from 'next/link';
import { CheckCircle, AlertCircle, KeyRound, ShieldCheck } from 'lucide-react';
import GoogleSignInButton from '@/components/auth/GoogleSignInButton';
import { authAPI, getApiErrorCode } from '@/lib/api';
import { useAuth } from '@/lib/auth';

/** The backend's reason ({detail} or the password validators' messages), else `fallback`. */
const reasonOf = (err: unknown, fallback: string): string => {
    const data = (err as { response?: { data?: { detail?: unknown; errors?: { new_password?: unknown } } } } | null)
        ?.response?.data;
    const validatorMessages = Array.isArray(data?.errors?.new_password)
        ? (data.errors.new_password as unknown[]).filter((m): m is string => typeof m === 'string')
        : [];
    if (validatorMessages.length) return validatorMessages.join(' ');
    if (typeof data?.detail === 'string' && data.detail) return data.detail;
    return fallback;
};

type Message = { type: 'success' | 'error'; text: string; code?: string };

export default function SignInMethods() {
    const { user, refreshProfile, googleSignInEnabled } = useAuth();
    const hasPassword = user?.auth_methods?.password ?? true;
    const hasGoogle = user?.auth_methods?.google ?? false;
    const [message, setMessage] = useState<Message | null>(null);
    const [changing, setChanging] = useState(false);
    const [form, setForm] = useState({ current: '', next: '', confirm: '' });
    const [savingPassword, setSavingPassword] = useState(false);
    const [connecting, setConnecting] = useState(false);
    const [googleBusy, setGoogleBusy] = useState(false);

    const handleChangePassword = async (e: React.FormEvent) => {
        e.preventDefault();
        setMessage(null);
        if (form.next.length < 8) {
            setMessage({ type: 'error', text: 'The new password must be at least 8 characters.' });
            return;
        }
        if (form.next !== form.confirm) {
            setMessage({ type: 'error', text: 'The new passwords do not match.' });
            return;
        }
        setSavingPassword(true);
        try {
            const { data } = await authAPI.changePassword({ current_password: form.current, new_password: form.next });
            setForm({ current: '', next: '', confirm: '' });
            setChanging(false);
            setMessage({ type: 'success', text: data?.detail || 'Password changed. Your other devices have been signed out.' });
        } catch (err: unknown) {
            setMessage({
                type: 'error',
                text: reasonOf(err, 'Could not change the password. Please try again.'),
                code: getApiErrorCode(err),
            });
        } finally {
            setSavingPassword(false);
        }
    };

    const handleConnectGoogle = async (credential: string) => {
        setMessage(null);
        setGoogleBusy(true);
        try {
            const { data } = await authAPI.googleLink(credential);
            await refreshProfile();
            setConnecting(false);
            setMessage({ type: 'success', text: data?.detail || 'Google account connected.' });
        } catch (err: unknown) {
            setMessage({
                type: 'error',
                text: reasonOf(err, 'Could not connect Google. Please try again.'),
                code: getApiErrorCode(err),
            });
        } finally {
            setGoogleBusy(false);
        }
    };

    const handleDisconnectGoogle = async () => {
        if (!confirm('Disconnect Google sign-in from this account? You can connect it again later.')) return;
        setMessage(null);
        try {
            const { data } = await authAPI.googleUnlink();
            await refreshProfile();
            setMessage({ type: 'success', text: data?.detail || 'Google account disconnected.' });
        } catch (err: unknown) {
            setMessage({
                type: 'error',
                text: reasonOf(err, 'Could not disconnect Google. Please try again.'),
                code: getApiErrorCode(err),
            });
        }
    };

    return (
        <div id="sign-in-methods" className="glass-card p-6 scroll-mt-24">
            <h3 className="font-bold mb-4 flex items-center gap-2">
                <ShieldCheck className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                Sign-in methods
            </h3>

            {message && (
                <div
                    role={message.type === 'error' ? 'alert' : 'status'}
                    className={`mb-4 flex items-start gap-2 rounded-lg p-3 text-sm ${message.type === 'success'
                        ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                        : 'bg-red-500/10 text-red-600 dark:text-red-400'}`}
                >
                    {message.type === 'success'
                        ? <CheckCircle className="w-4 h-4 mt-0.5 shrink-0" />
                        : <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />}
                    <span className="min-w-0">
                        {message.text}
                        {(message.code === 'password_not_set' || message.code === 'last_sign_in_method') && (
                            <>
                                {' '}
                                <Link href="/forgot-password" className="font-medium underline underline-offset-2">Set a password</Link>
                            </>
                        )}
                        {message.code === 'account_link_required' && (
                            <>
                                {' '}
                                <Link href="/contact" className="font-medium underline underline-offset-2">Contact support</Link>
                            </>
                        )}
                    </span>
                </div>
            )}

            <div className="space-y-3">
                <div className="p-3 rounded-xl bg-muted/40 border border-border">
                    <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                            <div className="text-sm font-medium flex items-center gap-2">
                                <KeyRound className="w-4 h-4 text-muted-foreground" /> Password
                            </div>
                            <div className="text-xs text-muted-foreground mt-0.5">
                                {hasPassword
                                    ? 'Sign in with your email address and password.'
                                    : 'No password yet. We can email you a link to set one.'}
                            </div>
                        </div>
                        {hasPassword ? (
                            <button
                                type="button"
                                onClick={() => {
                                    setChanging(!changing);
                                    setMessage(null);
                                }}
                                className="btn-secondary text-xs whitespace-nowrap"
                            >
                                {changing ? 'Cancel' : 'Change password'}
                            </button>
                        ) : (
                            <Link href="/forgot-password" className="btn-secondary text-xs whitespace-nowrap">Set a password</Link>
                        )}
                    </div>

                    {hasPassword && changing && (
                        <form onSubmit={handleChangePassword} className="mt-4 space-y-3">
                            <div>
                                <label htmlFor="settings-current-password" className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Current password</label>
                                <input id="settings-current-password" type="password" className="input-field" autoComplete="current-password"
                                    value={form.current} onChange={e => setForm({ ...form, current: e.target.value })} required />
                            </div>
                            <div>
                                <label htmlFor="settings-new-password" className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>New password</label>
                                <input id="settings-new-password" type="password" className="input-field" autoComplete="new-password" minLength={8}
                                    value={form.next} onChange={e => setForm({ ...form, next: e.target.value })} required />
                            </div>
                            <div>
                                <label htmlFor="settings-confirm-password" className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Confirm new password</label>
                                <input id="settings-confirm-password" type="password" className="input-field" autoComplete="new-password" minLength={8}
                                    value={form.confirm} onChange={e => setForm({ ...form, confirm: e.target.value })} required />
                            </div>
                            <div className="flex flex-wrap items-center gap-3">
                                <button type="submit" disabled={savingPassword} className="btn-primary text-xs">
                                    {savingPassword ? 'Saving...' : 'Save new password'}
                                </button>
                                <span className="text-xs text-muted-foreground">Your other devices will be signed out.</span>
                            </div>
                        </form>
                    )}
                </div>

                <div className="p-3 rounded-xl bg-muted/40 border border-border">
                    <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                            <div className="text-sm font-medium flex items-center gap-2">
                                <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden="true"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
                                Google
                            </div>
                            <div className="text-xs text-muted-foreground mt-0.5">
                                {hasGoogle ? 'Connected: you can use "Sign in with Google".' : 'Not connected.'}
                            </div>
                        </div>
                        {hasGoogle ? (
                            <button type="button" onClick={handleDisconnectGoogle} className="btn-secondary text-xs whitespace-nowrap">
                                Disconnect
                            </button>
                        ) : googleSignInEnabled ? (
                            <button
                                type="button"
                                onClick={() => {
                                    setConnecting(!connecting);
                                    setMessage(null);
                                }}
                                className="btn-secondary text-xs whitespace-nowrap"
                            >
                                {connecting ? 'Cancel' : 'Connect Google'}
                            </button>
                        ) : null}
                    </div>

                    {!hasGoogle && connecting && googleSignInEnabled && (
                        <div className="mt-4 space-y-2">
                            <p className="text-xs text-muted-foreground">
                                Choose the Google account to connect. For your security this works within 15 minutes of
                                signing in; if it is refused, sign out, sign in again and retry.
                            </p>
                            <GoogleSignInButton text="continue_with" onCredential={handleConnectGoogle} busy={googleBusy} />
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
