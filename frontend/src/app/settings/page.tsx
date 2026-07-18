'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { authAPI } from '@/lib/api';
import { Settings, User, Bell, Save, CheckCircle, AlertCircle, LogOut, Gift, Laptop, Trash2 } from 'lucide-react';

export default function SettingsPage() {
    const { user, isAuthenticated, loading: authLoading, logout, refreshProfile } = useAuth();
    const router = useRouter();
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
    const [form, setForm] = useState({ first_name: '', last_name: '', phone: '', college: '', target_exam: '' });

    interface Device {
        id: number;
        device_name: string;
        browser: string;
        ip_address: string;
        last_login: string;
        is_active: boolean;
    }
    const [devices, setDevices] = useState<Device[]>([]);
    const [loadingDevices, setLoadingDevices] = useState(false);
    const [deviceError, setDeviceError] = useState<string | null>(null);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push('/login');
    }, [authLoading, isAuthenticated, router]);

    useEffect(() => {
        if (user) {
            setForm({
                first_name: user.first_name || '',
                last_name: user.last_name || '',
                phone: user.phone || '',
                college: user.college || '',
                target_exam: user.target_exam || 'UPSC CMS',
            });
        }
    }, [user]);

    const handleSave = async () => {
        setSaving(true);
        setMessage(null);
        try {
            await authAPI.updateProfile(form);
            await refreshProfile();
            setMessage({ type: 'success', text: 'Profile updated successfully!' });
            setEditing(false);
        } catch {
            setMessage({ type: 'error', text: 'Failed to update profile. Please try again.' });
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
        if (isAuthenticated) {
            fetchDevices();
        }
    }, [isAuthenticated]);

    const handleRemoveDevice = async (deviceId: number) => {
        try {
            await authAPI.logoutDevice(deviceId);
            setDevices(devices.filter(d => d.id !== deviceId));
        } catch (err: unknown) {
            const error = err as { response?: { data?: { error?: string } } };
            alert(error.response?.data?.error || "Failed to remove device");
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

                <div className="space-y-6 max-w-2xl">
                    {/* Profile Bonus Banner */}
                    {!user?.profile_bonus_rewarded && (
                        <div className="glass-card p-4 flex items-center justify-between gap-4 border-dashed animate-fadeInUp" style={{
                            borderColor: 'rgba(245,158,11,0.4)',
                            background: 'linear-gradient(135deg, rgba(245,158,11,0.07) 0%, rgba(251,191,36,0.03) 100%)',
                        }}>
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded-xl bg-amber-500/10 text-amber-500">
                                    <Gift className="w-5 h-5 animate-pulse" />
                                </div>
                                <div>
                                    <h4 className="font-bold text-sm text-foreground">Get 10 Free Tokens! 🎁</h4>
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
                                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>First Name</label>
                                    <input className="input-field" value={form.first_name} onChange={e => setForm({ ...form, first_name: e.target.value })} />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Last Name</label>
                                    <input className="input-field" value={form.last_name} onChange={e => setForm({ ...form, last_name: e.target.value })} />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Email</label>
                                    <input className="input-field" value={user?.email || ''} readOnly />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Mobile Number</label>
                                    <input className="input-field" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="Enter 10-digit mobile number" />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>College Name</label>
                                    <input className="input-field" value={form.college} onChange={e => setForm({ ...form, college: e.target.value })} placeholder="Enter medical college name" />
                                </div>
                                <div>
                                    <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Target Exam</label>
                                    <select className="input-field" value={form.target_exam} onChange={e => setForm({ ...form, target_exam: e.target.value })}>
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
                                    <span style={{ color: 'var(--text-secondary)' }}>Name</span><span>{user?.first_name} {user?.last_name}</span>
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
                            <div className="flex items-center justify-between">
                                <div>
                                    <div className="text-sm font-medium">Dark Mode</div>
                                    <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>App always uses dark theme</div>
                                </div>
                                <div className="badge" style={{ background: 'rgba(16,185,129,0.1)', color: '#10b981' }}>Active</div>
                            </div>
                            <div className="flex items-center justify-between">
                                <div>
                                    <div className="text-sm font-medium">AI Explanations</div>
                                    <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>Auto-generate AI explanations for questions</div>
                                </div>
                                <div className="badge" style={{ background: 'rgba(6,182,212,0.1)', color: 'var(--accent-primary)' }}>Enabled</div>
                            </div>
                        </div>
                    </div>

                    {/* Connected Devices */}
                    <div className="glass-card p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="font-bold flex items-center gap-2">
                                <Laptop className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                                Connected Devices
                            </h3>
                            <span className="text-xs font-medium px-2 py-1 rounded-full bg-slate-800 text-slate-300">
                                {devices.length} / {user?.is_subscribed ? '4' : '2'} Limits
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
                                <div className="text-sm text-muted-foreground">No active devices found.</div>
                            ) : (
                                devices.map((device, idx) => (
                                    <div key={device.id} className="flex items-center justify-between p-3 rounded-xl bg-slate-900/50 border border-slate-800">
                                        <div className="flex items-center gap-3">
                                            <div className="p-2 rounded-lg bg-slate-800/80">
                                                <Laptop className="w-4 h-4 text-slate-400" />
                                            </div>
                                            <div>
                                                <div className="text-sm font-medium flex items-center gap-2">
                                                    {device.device_name || 'Unknown Device'}
                                                    {idx === 0 && (
                                                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold uppercase">This Device</span>
                                                    )}
                                                </div>
                                                <div className="text-xs text-muted-foreground mt-0.5">
                                                    IP: {device.ip_address || 'Unknown'} • Last Active: {new Date(device.last_login).toLocaleDateString()}
                                                </div>
                                            </div>
                                        </div>
                                        <button 
                                            onClick={() => handleRemoveDevice(device.id)}
                                            className="p-2 rounded-lg hover:bg-red-500/10 text-red-500/70 hover:text-red-500 transition-colors"
                                            title="Logout Device"
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
                        <button onClick={() => { logout(); router.push('/'); }} className="btn-secondary text-sm">
                            Logout
                        </button>
                    </div>
                </div>
                </div>
            </div>
        </div>
    );
}
