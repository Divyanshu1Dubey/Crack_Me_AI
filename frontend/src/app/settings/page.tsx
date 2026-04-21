'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { authAPI } from '@/lib/api';
import { Settings, User, Bell, Save, CheckCircle, AlertCircle, LogOut } from 'lucide-react';

export default function SettingsPage() {
    const { user, isAuthenticated, loading: authLoading, logout, refreshProfile } = useAuth();
    const router = useRouter();
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
    const [form, setForm] = useState({ first_name: '', last_name: '', target_exam: '' });

    useEffect(() => {
        if (!authLoading && !isAuthenticated) router.push('/login');
    }, [authLoading, isAuthenticated, router]);

    useEffect(() => {
        if (user) {
            setForm({
                first_name: user.first_name || '',
                last_name: user.last_name || '',
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
