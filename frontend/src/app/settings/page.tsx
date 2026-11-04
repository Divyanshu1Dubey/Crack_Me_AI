'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';
import { useAuth } from '@/lib/auth';
import { navigateAfterAuthChange } from '@/lib/authNavigation';
import { useRequireAuth } from '@/lib/hooks/useRequireAuth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { authAPI, extractApiErrorMessage } from '@/lib/api';
import { Settings, User, Bell, Save, CheckCircle, AlertCircle, LogOut, Gift, Laptop, Trash2, X } from 'lucide-react';
import { isDjangoAuthBuild } from '@/lib/localSession';
import { USERNAME_HINT, USERNAME_MAX_LENGTH, profileUpdatePayload, usernameProblem } from './username';
import SignInMethods from './SignInMethods';
import CustomizeSection from '@/components/customize/CustomizeSection';

const PROFILE_SAVE_FAILED = 'Failed to update profile. Please try again.';

const THEME_OPTIONS = [
    { value: 'light', label: 'Light' },
    { value: 'dark', label: 'Dark' },
    { value: 'system', label: 'System' },
];

export default function SettingsPage() {
    const { user, logout, refreshProfile } = useAuth();
    const { ready } = useRequireAuth();
    const router = useRouter();
    // The stored theme is only known on the client; render the picker after mount.
    const { theme, setTheme } = useTheme();
    const [themeReady, setThemeReady] = useState(false);
    useEffect(() => { setThemeReady(true); }, []);
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
    const [form, setForm] = useState({ username: '', first_name: '', last_name: '', phone: '', college: '', target_exam: '' });

    interface Device {
        id: number;
        device_name: string;
        browser: string;
        ip_address: string;
        last_login: string;
        is_active: boolean;
        /** Set by the API when this row is the device making the request. */
        is_current?: boolean;
    }
    const [devices, setDevices] = useState<Device[]>([]);
    const [loadingDevices, setLoadingDevices] = useState(false);
    const [deviceError, setDeviceError] = useState<string | null>(null);
    // api.ts sends a device that is over the limit here with ?deviceLimit=1.
    // Read after mount (client only) so the page needs no Suspense boundary.
    const [deviceLimitHit, setDeviceLimitHit] = useState(false);
    useEffect(() => {
        setDeviceLimitHit(new URLSearchParams(window.location.search).get('deviceLimit') === '1');
    }, []);
    const deviceLimit = user?.is_subscribed ? 4 : 2;

    /** Hide the device-limit notice and drop ?deviceLimit=1, so a refresh does not bring it back. */
    const dismissDeviceLimitNotice = () => {
        setDeviceLimitHit(false);
        const params = new URLSearchParams(window.location.search);
        if (!params.has('deviceLimit')) return;
        params.delete('deviceLimit');
        const query = params.toString();
        router.replace(`${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`, { scroll: false });
    };

    useEffect(() => {
        if (ready && user) {
            setForm({
                username: user.username || '',
                first_name: user.first_name || '',
                last_name: user.last_name || '',
                phone: user.phone || '',
                college: user.college || '',
                target_exam: user.target_exam || 'UPSC CMS',
            });
        }
    }, [ready, user]);

    const handleSave = async () => {
        setMessage(null);
        // The username is sent only when it changed (profileUpdatePayload).
        const payload = profileUpdatePayload(form, user?.username);
        const problem = 'username' in payload ? usernameProblem(payload.username, user?.email) : null;
        if (problem) {
            setMessage({ type: 'error', text: problem });
            return;
        }
        setSaving(true);
        try {
            await authAPI.updateProfile(payload);
            await refreshProfile();
            setMessage({ type: 'success', text: 'Profile updated successfully!' });
            setEditing(false);
        } catch (err: unknown) {
            // Show the server's reason (e.g. "This username is taken.").
            const data = (err as { response?: { data?: unknown } }).response?.data;
            setMessage({ type: 'error', text: data ? extractApiErrorMessage(data, PROFILE_SAVE_FAILED) : PROFILE_SAVE_FAILED });
        } finally {
            setSaving(false);
        }
    };

    const fetchDevices = async () => {
        setLoadingDevices(true);
        setDeviceError(null);
        try {
            const res = await authAPI.getDevices();
            setDevices(res.data);
        } catch (err: unknown) {
            const error = err as { response?: { data?: { detail?: string } } };
            setDeviceError(error.response?.data?.detail || "Failed to fetch devices");
        } finally {
            setLoadingDevices(false);
        }
    };

    useEffect(() => {
        if (ready) {
            fetchDevices();
        }
    }, [ready]);

    const handleRemoveDevice = async (device: Device) => {
        const confirmText = device.is_current === true
            ? 'This is the device you are using now. Remove it? You will be signed out here.'
            : 'Remove this device session? You will be logged out of that device.';
        if (!confirm(confirmText)) return;
        try {
            await authAPI.logoutDevice(device.id);
            setDevices(devices.filter(d => d.id !== device.id));
            if (device.is_current === true) {
                // Sign out here now, as the confirm said: the backend answers this
                // device's next request with device_inactive, and api.ts then
                // drops the device id, signs out and opens /login.
                void fetchDevices();
                return;
            }
            if (deviceLimitHit) {
                dismissDeviceLimitNotice();
                setMessage({ type: 'success', text: 'Device removed. You can keep using CrackLabs on this device.' });
            }
        } catch (err: unknown) {
            const error = err as { response?: { data?: { error?: string } } };
            setMessage({ type: 'error', text: error.response?.data?.error || 'Failed to remove device' });
        }
    };

    return (
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container">
                <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
                    <Settings className="w-6 h-6" style={{ color: 'var(--accent-primary)' }} />
                    Settings
                </h1>

                {message && (
                    <div className="glass-card p-4 mb-6 flex items-center gap-3 animate-fadeInUp" style={{
                        borderColor: message.type === 'success' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)',
                        background: message.type === 'success' ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
                    }}>
                        {message.type === 'success' ? <CheckCircle className="w-5 h-5" style={{ color: '#10b981' }} /> : <AlertCircle className="w-5 h-5" style={{ color: '#ef4444' }} />}
                        <span className="text-sm">{message.text}</span>
                    </div>
                )}

                {deviceLimitHit && (
                    <div role="alert" className="glass-card p-4 mb-6 flex items-start gap-3 max-w-2xl" style={{
                        borderColor: 'rgba(245,158,11,0.45)',
                        background: 'rgba(245,158,11,0.08)',
                    }}>
                        <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
                        <div className="text-sm flex-1 min-w-0">
                            <p className="font-semibold text-foreground">Device limit reached</p>
                            <p className="text-muted-foreground mt-0.5">
                                Your plan allows {deviceLimit} signed-in devices. Remove a device under{' '}
                                <a href="#connected-devices" className="font-medium text-primary underline-offset-2 hover:underline">Connected Devices</a>{' '}
                                to keep using CrackLabs on this one.
                                {/* Subscription stays usable from this over-limit device (lib/deviceLimit.ts). */}
                                {user && !user.is_subscribed && (
                                    <>
                                        {' '}Or{' '}
                                        <Link href="/subscription" className="font-medium text-primary underline-offset-2 hover:underline">upgrade to a plan</Link>
                                        , which allows 4 devices.
                                    </>
                                )}
                            </p>
                        </div>
                        <button
                            type="button"
                            onClick={dismissDeviceLimitNotice}
                            className="p-1 -m-1 rounded-md shrink-0 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                            aria-label="Dismiss device limit notice"
                            title="Dismiss"
                        >
                            <X className="w-4 h-4" aria-hidden="true" />
                        </button>
                    </div>
                )}

                <div className="space-y-6 max-w-2xl">
                    {/* Profile Bonus Banner (stacks on phones so the copy keeps its width) */}
                    {!user?.profile_bonus_rewarded && (
                        <div className="glass-card p-4 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 border-dashed animate-fadeInUp" style={{
                            borderColor: 'rgba(245,158,11,0.4)',
                            background: 'linear-gradient(135deg, rgba(245,158,11,0.07) 0%, rgba(251,191,36,0.03) 100%)',
                        }}>
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded-xl bg-amber-500/10 text-amber-500 shrink-0">
                                    <Gift className="w-5 h-5 animate-pulse" />
                                </div>
                                <div>
                                    <h4 className="font-bold text-sm text-foreground">Get 10 Free Tokens!&nbsp;🎁</h4>
                                    <p className="text-xs text-muted-foreground mt-0.5">Fill in both your Mobile Number and name of College in your profile to claim your bonus tokens.</p>
                                </div>
                            </div>
                            <button onClick={() => setEditing(true)} className="btn-primary text-xs whitespace-nowrap bg-amber-500 hover:bg-amber-600 border-none text-black">
                                Claim Bonus
                            </button>
                        </div>
                    )}
                    {user?.profile_bonus_rewarded && (
                        <div className="glass-card p-4 flex items-center gap-3 border-dashed animate-fadeInUp" style={{
                            borderColor: 'rgba(16,185,129,0.3)',
                            background: 'rgba(16,185,129,0.04)',
                        }}>
                            <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-500">
                                <CheckCircle className="w-5 h-5" />
                            </div>
                            <div>
                                <h4 className="font-bold text-sm text-foreground">Profile Bonus Claimed</h4>
                                <p className="text-xs text-muted-foreground mt-0.5">Thank you for completing your profile! 10 bonus tokens have been added to your balance.</p>
                            </div>
                        </div>
                    )}

                    {/* Profile */}
                    <div className="glass-card p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="font-bold flex items-center gap-2">
                                <User className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                                Profile
                            </h3>
                            {!editing ? (
                                <button onClick={() => setEditing(true)} className="btn-secondary text-xs">Edit Profile</button>
                            ) : (
                                <div className="flex gap-2">
                                    <button onClick={() => setEditing(false)} className="btn-secondary text-xs">Cancel</button>
                                    <button onClick={handleSave} disabled={saving} className="btn-primary text-xs">
                                        <Save className="w-3 h-3" /> {saving ? 'Saving...' : 'Save'}
                                    </button>
                                </div>
                            )}
                        </div>

                        {editing ? (
                            <div className="space-y-4">
                                <div>
                                    <label htmlFor="settings-username" className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Username</label>
                                    <input id="settings-username" className="input-field" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })}
                                        maxLength={USERNAME_MAX_LENGTH} autoComplete="nickname" autoCapitalize="none" spellCheck={false} aria-describedby="settings-username-hint" />
                                    <p id="settings-username-hint" className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                                        {USERNAME_HINT}
                                    </p>
                                </div>
                                <div>
                                    <label htmlFor="settings-first-name" className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>First Name</label>
                                    <input id="settings-first-name" className="input-field" value={form.first_name} onChange={e => setForm({ ...form, first_name: e.target.value })} />
                                </div>
                                <div>
                                    <label htmlFor="settings-last-name" className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Last Name</label>
                                    <input id="settings-last-name" className="input-field" value={form.last_name} onChange={e => setForm({ ...form, last_name: e.target.value })} />
                                </div>
                                <div>
                                    <label htmlFor="settings-email" className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Email</label>
                                    <input id="settings-email" className="input-field" value={user?.email || ''} readOnly />
                                </div>
                                <div>
                                    <label htmlFor="settings-phone" className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Mobile Number</label>
                                    <input id="settings-phone" type="tel" inputMode="numeric" autoComplete="tel" maxLength={15} className="input-field" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="Enter 10-digit mobile number" />
                                </div>
                                <div>
                                    <label htmlFor="settings-college" className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>College Name</label>
                                    <input id="settings-college" className="input-field" value={form.college} onChange={e => setForm({ ...form, college: e.target.value })} placeholder="Enter medical college name" />
                                </div>
                                <div>
                                    <label htmlFor="settings-target-exam" className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Target Exam</label>
                                    <select id="settings-target-exam" className="input-field" value={form.target_exam} onChange={e => setForm({ ...form, target_exam: e.target.value })}>
                                        <option value="UPSC CMS">UPSC CMS</option>
                                        <option value="NEET PG">NEET PG</option>
                                        <option value="FMGE">FMGE</option>
                                    </select>
                                </div>
                            </div>
                        ) : (
                            <div className="space-y-3 text-sm">
                                <div className="flex justify-between py-2" style={{ borderBottom: '1px solid rgba(139,149,168,0.05)' }}>
                                    <span style={{ color: 'var(--text-secondary)' }}>Username</span><span>{user?.username}</span>
                                </div>
                                <div className="flex justify-between py-2" style={{ borderBottom: '1px solid rgba(139,149,168,0.05)' }}>
                                    <span style={{ color: 'var(--text-secondary)' }}>Email</span><span>{user?.email}</span>
                                </div>
                                <div className="flex justify-between py-2" style={{ borderBottom: '1px solid rgba(139,149,168,0.05)' }}>
                                    <span style={{ color: 'var(--text-secondary)' }}>Name</span><span>{[user?.first_name, user?.last_name].filter(Boolean).join(' ') || 'Not provided'}</span>
                                </div>
                                <div className="flex justify-between py-2" style={{ borderBottom: '1px solid rgba(139,149,168,0.05)' }}>
                                    <span style={{ color: 'var(--text-secondary)' }}>Mobile Number</span><span>{user?.phone || 'Not provided'}</span>
                                </div>
                                <div className="flex justify-between py-2" style={{ borderBottom: '1px solid rgba(139,149,168,0.05)' }}>
                                    <span style={{ color: 'var(--text-secondary)' }}>College</span><span>{user?.college || 'Not provided'}</span>
                                </div>
                                <div className="flex justify-between py-2" style={{ borderBottom: '1px solid rgba(139,149,168,0.05)' }}>
                                    <span style={{ color: 'var(--text-secondary)' }}>Target Exam</span><span>{user?.target_exam || 'UPSC CMS'}</span>
                                </div>
                                <div className="flex justify-between py-2">
                                    <span style={{ color: 'var(--text-secondary)' }}>Role</span>
                                    <span className="badge" style={{ background: 'rgba(6, 182, 212, 0.1)', color: 'var(--accent-primary)' }}>{user?.role}</span>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Preferences */}
                    <div className="glass-card p-6">
                        <h3 className="font-bold mb-4 flex items-center gap-2">
                            <Bell className="w-5 h-5" style={{ color: '#10b981' }} />
                            Preferences
                        </h3>
                        <div className="space-y-4">
                            <div className="flex items-center justify-between gap-4">
                                <div>
                                    <div id="settings-theme-label" className="text-sm font-medium">Theme</div>
                                    <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>Light, dark, or follow your device setting</div>
                                </div>
                                <div className="flex gap-1 rounded-lg p-1" role="radiogroup" aria-labelledby="settings-theme-label"
                                    style={{ background: 'rgba(139,149,168,0.1)' }}>
                                    {THEME_OPTIONS.map(opt => {
                                        const active = themeReady && (theme || 'system') === opt.value;
                                        return (
                                            <button key={opt.value} type="button" role="radio" aria-checked={active}
                                                onClick={() => setTheme(opt.value)}
                                                className="px-2.5 py-1 rounded-md text-xs font-medium transition-colors"
                                                style={active
                                                    ? { background: 'rgba(16,185,129,0.15)', color: '#10b981' }
                                                    : { color: 'var(--text-secondary)' }}>
                                                {opt.label}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                            <div className="flex items-center justify-between">
                                <div>
                                    <div className="text-sm font-medium">AI Explanations</div>
                                    <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>Generated when you ask for one on a question</div>
                                </div>
                                <div className="badge" style={{ background: 'rgba(6,182,212,0.1)', color: 'var(--accent-primary)' }}>On request</div>
                            </div>
                        </div>
                    </div>

                    {/* Customise: sidebar / dashboard order and visibility, opening page (#customise) */}
                    <CustomizeSection />

                    {/* Sign-in methods (Django-native sign-in: password, Google) */}
                    {isDjangoAuthBuild() && <SignInMethods />}

                    {/* Connected Devices */}
                    <div id="connected-devices" className="glass-card p-6 scroll-mt-24">
                        <div className="flex items-center justify-between gap-3 mb-4">
                            <h3 className="font-bold flex items-center gap-2">
                                <Laptop className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                                Connected Devices
                            </h3>
                            <span className="text-xs font-medium px-2 py-1 rounded-full bg-muted text-muted-foreground whitespace-nowrap">
                                {devices.length} of {deviceLimit} devices
                            </span>
                        </div>
                        <p className="text-xs text-muted-foreground mb-4">
                            Manage the devices where you are currently logged in. You can remove older devices to free up your limit.
                        </p>
                        
                        {deviceError && (
                            <div className="p-3 mb-4 rounded-lg bg-red-500/10 text-red-500 text-sm">
                                {deviceError}
                            </div>
                        )}

                        <div className="space-y-3">
                            {loadingDevices ? (
                                <div className="text-sm text-muted-foreground animate-pulse">Loading devices...</div>
                            ) : devices.length === 0 ? (
                                <div className="text-sm text-muted-foreground">Only this device is signed in.</div>
                            ) : (
                                devices.map((device) => (
                                    <div key={device.id} className="flex items-center justify-between gap-3 p-3 rounded-xl bg-muted/40 border border-border">
                                        <div className="flex items-center gap-3 min-w-0">
                                            <div className="p-2 rounded-lg bg-muted shrink-0">
                                                <Laptop className="w-4 h-4 text-muted-foreground" />
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-sm font-medium flex items-center gap-2 min-w-0">
                                                    <span className="truncate" title={device.device_name || undefined}>{device.device_name || 'Unknown Device'}</span>
                                                    {/* Only when the API marks the row; the first row is just the most recent sign-in. */}
                                                    {device.is_current === true && (
                                                        <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 font-bold uppercase">This device</span>
                                                    )}
                                                </div>
                                                <div className="text-xs text-muted-foreground mt-0.5">
                                                    IP: {device.ip_address || 'Unknown'} • Last Active: {new Date(device.last_login).toLocaleDateString()}
                                                </div>
                                            </div>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => handleRemoveDevice(device)}
                                            className="p-2 rounded-lg shrink-0 hover:bg-red-500/10 text-red-500/70 hover:text-red-500 transition-colors"
                                            title="Log out this device"
                                            aria-label={`Log out ${device.device_name || 'this device'}`}
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Logout */}
                    <div className="glass-card p-6">
                        <h3 className="font-bold mb-4 flex items-center gap-2">
                            <LogOut className="w-5 h-5" style={{ color: 'var(--text-secondary)' }} />
                            Session
                        </h3>
                        <button onClick={async () => { await logout(); navigateAfterAuthChange('/'); }} className="btn-secondary text-sm">
                            Logout
                        </button>
                    </div>
                </div>
                </div>
            </div>
        </div>
    );
}
