/**
 * tokens/page.tsx — AI Token Wallet & Management page.
 * Shows: balance stats (available, purchased, credits), usage progress bars
 * (daily/weekly limits), token purchase options (₹10–₹500), transaction history.
 * Admin users see ∞ (unlimited) badge. Integrates with authAPI endpoints.
 */
/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import { authAPI } from '@/lib/api';
import {
    Coins, Zap, ShoppingCart, Clock, TrendingUp,
    Gift, Shield, CheckCircle, AlertCircle, Loader2,
    Users, ArrowRightLeft, Send, RefreshCw
} from 'lucide-react';

interface TokenBalance {
    available: number;
    purchased_tokens: number;
    feedback_credits: number;
    daily_limit: number;
    weekly_limit: number;
    daily_tokens_used: number;
    weekly_tokens_used: number;
    is_admin: boolean;
}

interface Transaction {
    id: number;
    transaction_type: string;
    amount: number;
    note: string;
    price_paid: string;
    created_at: string;
}

interface AdminUser {
    user_id: number;
    username: string;
    email: string;
    is_admin: boolean;
    available: number;
    purchased_tokens: number;
    feedback_credits: number;
    daily_tokens_used: number;
    weekly_tokens_used: number;
    total_tokens_used: number;
}

interface PlatformStats {
    total_users: number;
    total_purchased_tokens: number;
    total_feedback_credits: number;
    total_tokens_consumed: number;
    total_available_tokens: number;
    free_daily_per_user: number;
    free_weekly_per_user: number;
    max_free_daily_calls: number;
    max_free_weekly_calls: number;
    api_budget: {
        gemini_daily_limit: number;
        groq_daily_limit: number;
        deepseek_daily_limit: string;
        combined_daily_capacity: number;
        note: string;
    };
}

const PURCHASE_OPTIONS = [
    { amount: 10, price: 10, label: 'Starter' },
    { amount: 25, price: 25, label: 'Basic' },
    { amount: 50, price: 50, label: 'Popular', popular: true },
    { amount: 100, price: 100, label: 'Pro' },
    { amount: 250, price: 250, label: 'Premium' },
    { amount: 500, price: 500, label: 'Unlimited' },
];

export default function TokensPage() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [balance, setBalance] = useState<TokenBalance | null>(null);
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedPurchase, setSelectedPurchase] = useState<number | null>(null);
    const [purchasing, setPurchasing] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

    // Admin state
    const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
    const [platformStats, setPlatformStats] = useState<PlatformStats | null>(null);
    const [adminTab, setAdminTab] = useState<'overview' | 'grant' | 'transfer'>('overview');
    const [grantUserId, setGrantUserId] = useState('');
    const [grantAmount, setGrantAmount] = useState('');
    const [grantNote, setGrantNote] = useState('');
    const [transferFrom, setTransferFrom] = useState('');
    const [transferTo, setTransferTo] = useState('');
    const [transferAmount, setTransferAmount] = useState('');
    const [transferNote, setTransferNote] = useState('');
    const [adminLoading, setAdminLoading] = useState(false);
    const [adminAction, setAdminAction] = useState(false);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) { router.push('/login'); return; }
        if (isAuthenticated) {
            Promise.all([
                authAPI.getTokenBalance().catch(() => ({ data: null })),
                authAPI.getTokenHistory().catch(() => ({ data: [] })),
            ]).then(([balRes, histRes]) => {
                if (balRes.data) setBalance(balRes.data);
                setTransactions(Array.isArray(histRes.data) ? histRes.data : histRes.data?.results || []);
            }).finally(() => setLoading(false));
        }
    }, [authLoading, isAuthenticated, router]);

    // Load admin data when balance confirms admin
    useEffect(() => {
        if (balance?.is_admin) {
            setAdminLoading(true);
            authAPI.adminGetAllUsers()
                .then(res => {
                    setAdminUsers(res.data.users || []);
                    setPlatformStats(res.data.platform_stats || null);
                })
                .catch(() => {})
                .finally(() => setAdminLoading(false));
        }
    }, [balance]);

    const loadAdminData = async () => {
        setAdminLoading(true);
        try {
            const res = await authAPI.adminGetAllUsers();
            setAdminUsers(res.data.users || []);
            setPlatformStats(res.data.platform_stats || null);
        } catch { /* ignore */ }
        setAdminLoading(false);
    };

    const handleGrant = async () => {
        if (!grantUserId || !grantAmount || adminAction) return;
        setAdminAction(true);
        setMessage(null);
        try {
            const res = await authAPI.adminGrantTokens({
                user_id: parseInt(grantUserId),
                amount: parseInt(grantAmount),
                note: grantNote,
            });
            setMessage({ type: 'success', text: res.data.message });
            setGrantUserId(''); setGrantAmount(''); setGrantNote('');
            loadAdminData();
        } catch (err: any) {
            setMessage({ type: 'error', text: err.response?.data?.error || 'Grant failed' });
        }
        setAdminAction(false);
    };

    const handleTransfer = async () => {
        if (!transferTo || !transferAmount || adminAction) return;
        setAdminAction(true);
        setMessage(null);
        try {
            const res = await authAPI.adminTransferTokens({
                from_user_id: transferFrom ? parseInt(transferFrom) : undefined,
                to_user_id: parseInt(transferTo),
                amount: parseInt(transferAmount),
                note: transferNote,
            });
            setMessage({ type: 'success', text: res.data.message });
            setTransferFrom(''); setTransferTo(''); setTransferAmount(''); setTransferNote('');
            loadAdminData();
        } catch (err: any) {
            setMessage({ type: 'error', text: err.response?.data?.error || 'Transfer failed' });
        }
        setAdminAction(false);
    };

    const handlePurchase = async () => {
        if (!selectedPurchase || purchasing) return;
        setPurchasing(true);
        setMessage(null);
        try {
            await authAPI.purchaseTokens({ amount: selectedPurchase });
            setMessage({ type: 'success', text: `Successfully purchased ${selectedPurchase} tokens!` });
            setSelectedPurchase(null);
            // Refresh data
            const [balRes, histRes] = await Promise.all([
                authAPI.getTokenBalance(),
                authAPI.getTokenHistory(),
            ]);
            setBalance(balRes.data);
            setTransactions(Array.isArray(histRes.data) ? histRes.data : histRes.data?.results || []);
        } catch {
            setMessage({ type: 'error', text: 'Purchase failed. Please try again.' });
        } finally {
            setPurchasing(false);
        }
    };

    const txTypeLabel = (type: string) => {
        switch (type) {
            case 'purchase': return { label: 'Purchased', color: '#06b6d4', icon: <ShoppingCart className="w-3.5 h-3.5" /> };
            case 'feedback_reward': return { label: 'Feedback Reward', color: '#10b981', icon: <Gift className="w-3.5 h-3.5" /> };
            case 'admin_grant': return { label: 'Admin Grant', color: '#8b5cf6', icon: <Shield className="w-3.5 h-3.5" /> };
            case 'admin_revoke': return { label: 'Admin Revoke', color: '#ef4444', icon: <Shield className="w-3.5 h-3.5" /> };
            case 'admin_transfer': return { label: 'Transfer', color: '#3b82f6', icon: <ArrowRightLeft className="w-3.5 h-3.5" /> };
            case 'refund': return { label: 'Refund', color: '#f59e0b', icon: <TrendingUp className="w-3.5 h-3.5" /> };
            default: return { label: type, color: 'var(--text-secondary)', icon: <Coins className="w-3.5 h-3.5" /> };
        }
    };

    if (authLoading || loading) {
        return (
            <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
                <div className="animate-pulse text-xl gradient-text">Loading Tokens...</div>
            </div>
        );
    }

    return (
        <div style={{ background: 'var(--bg-primary)' }} className="min-h-screen">
            <Sidebar />
            <div className="main-content">
                {/* Header */}
                <div className="mb-6">
                    <h1 className="text-2xl font-bold flex items-center gap-3">
                        <Coins className="w-7 h-7" style={{ color: '#f59e0b' }} />
                        AI Tokens
                    </h1>
                    <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
                        Manage your AI tokens — each AI-powered feature costs 1 token
                    </p>
                </div>

                {/* Alert message */}
                {message && (
                    <div className="glass-card p-4 mb-6 flex items-center gap-3 animate-fadeInUp" style={{
                        borderColor: message.type === 'success' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)',
                        background: message.type === 'success' ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
                    }}>
                        {message.type === 'success' ? <CheckCircle className="w-5 h-5" style={{ color: '#10b981' }} /> : <AlertCircle className="w-5 h-5" style={{ color: '#ef4444' }} />}
                        <span className="text-sm">{message.text}</span>
                    </div>
                )}

                {/* Admin Badge */}
                {balance?.is_admin && (
                    <div className="glass-card p-4 mb-6 flex items-center gap-3" style={{ borderColor: 'rgba(139,92,246,0.3)', background: 'rgba(139,92,246,0.06)' }}>
                        <Shield className="w-5 h-5" style={{ color: '#8b5cf6' }} />
                        <div>
                            <span className="text-sm font-bold" style={{ color: '#8b5cf6' }}>Admin Account</span>
                            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>You have unlimited AI tokens. No restrictions apply.</p>
                        </div>
                    </div>
                )}

                {/* ─── SUPER ADMIN TOKEN MANAGEMENT ─── */}
                {balance?.is_admin && (
                    <div className="mb-8">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-bold flex items-center gap-2">
                                <Users className="w-5 h-5" style={{ color: '#8b5cf6' }} />
                                Token Management
                            </h2>
                            <button onClick={loadAdminData} className="text-xs flex items-center gap-1 px-3 py-1.5 rounded-lg" style={{ background: 'rgba(139,92,246,0.1)', color: '#8b5cf6' }}>
                                <RefreshCw className={`w-3 h-3 ${adminLoading ? 'animate-spin' : ''}`} /> Refresh
                            </button>
                        </div>

                        {/* Platform Stats */}
                        {platformStats && (
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                                <div className="glass-card p-3 text-center">
                                    <div className="text-2xl font-bold" style={{ color: '#8b5cf6' }}>{platformStats.total_users}</div>
                                    <div className="text-[10px] uppercase" style={{ color: 'var(--text-secondary)' }}>Total Users</div>
                                </div>
                                <div className="glass-card p-3 text-center">
                                    <div className="text-2xl font-bold" style={{ color: '#10b981' }}>{platformStats.total_available_tokens}</div>
                                    <div className="text-[10px] uppercase" style={{ color: 'var(--text-secondary)' }}>Tokens In Circulation</div>
                                </div>
                                <div className="glass-card p-3 text-center">
                                    <div className="text-2xl font-bold" style={{ color: '#f59e0b' }}>{platformStats.total_tokens_consumed}</div>
                                    <div className="text-[10px] uppercase" style={{ color: 'var(--text-secondary)' }}>Total Consumed</div>
                                </div>
                                <div className="glass-card p-3 text-center">
                                    <div className="text-2xl font-bold" style={{ color: '#06b6d4' }}>{platformStats.api_budget.combined_daily_capacity}</div>
                                    <div className="text-[10px] uppercase" style={{ color: 'var(--text-secondary)' }}>API Calls/Day</div>
                                </div>
                            </div>
                        )}

                        {/* Admin Tabs */}
                        <div className="flex gap-2 mb-4">
                            {(['overview', 'grant', 'transfer'] as const).map(tab => (
                                <button key={tab} onClick={() => setAdminTab(tab)}
                                    className="px-4 py-2 rounded-lg text-xs font-bold uppercase transition-all"
                                    style={{
                                        background: adminTab === tab ? 'rgba(139,92,246,0.15)' : 'var(--bg-secondary)',
                                        color: adminTab === tab ? '#8b5cf6' : 'var(--text-secondary)',
                                        border: adminTab === tab ? '1px solid rgba(139,92,246,0.3)' : '1px solid transparent',
                                    }}>
                                    {tab === 'overview' && <Users className="w-3 h-3 inline mr-1" />}
                                    {tab === 'grant' && <Send className="w-3 h-3 inline mr-1" />}
                                    {tab === 'transfer' && <ArrowRightLeft className="w-3 h-3 inline mr-1" />}
                                    {tab}
                                </button>
                            ))}
                        </div>

                        {/* Overview Tab — All Users */}
                        {adminTab === 'overview' && (
                            <div className="glass-card p-4">
                                {adminLoading ? (
                                    <div className="text-center py-8"><Loader2 className="w-6 h-6 animate-spin mx-auto" style={{ color: '#8b5cf6' }} /></div>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-xs">
                                            <thead>
                                                <tr style={{ color: 'var(--text-secondary)' }}>
                                                    <th className="text-left py-2 px-2">ID</th>
                                                    <th className="text-left py-2 px-2">User</th>
                                                    <th className="text-right py-2 px-2">Available</th>
                                                    <th className="text-right py-2 px-2">Purchased</th>
                                                    <th className="text-right py-2 px-2">Credits</th>
                                                    <th className="text-right py-2 px-2">Daily Used</th>
                                                    <th className="text-right py-2 px-2">Total Used</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {adminUsers.map(u => (
                                                    <tr key={u.user_id} className="border-t" style={{ borderColor: 'rgba(139,149,168,0.1)' }}>
                                                        <td className="py-2 px-2 font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>{u.user_id}</td>
                                                        <td className="py-2 px-2">
                                                            <div className="font-medium">{u.username}</div>
                                                            <div style={{ color: 'var(--text-secondary)' }}>{u.email}</div>
                                                            {u.is_admin && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded" style={{ background: 'rgba(139,92,246,0.15)', color: '#8b5cf6' }}>ADMIN</span>}
                                                        </td>
                                                        <td className="text-right py-2 px-2 font-bold" style={{ color: u.is_admin ? '#8b5cf6' : '#f59e0b' }}>
                                                            {u.is_admin ? '∞' : u.available}
                                                        </td>
                                                        <td className="text-right py-2 px-2" style={{ color: '#06b6d4' }}>{u.purchased_tokens}</td>
                                                        <td className="text-right py-2 px-2" style={{ color: '#10b981' }}>{u.feedback_credits}</td>
                                                        <td className="text-right py-2 px-2" style={{ color: '#ec4899' }}>{u.daily_tokens_used}</td>
                                                        <td className="text-right py-2 px-2">{u.total_tokens_used}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Grant/Revoke Tab */}
                        {adminTab === 'grant' && (
                            <div className="glass-card p-5">
                                <p className="text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
                                    Grant tokens (positive amount) or revoke tokens (negative amount) for any user.
                                </p>
                                <div className="grid md:grid-cols-3 gap-3 mb-4">
                                    <div>
                                        <label className="text-[10px] uppercase font-bold block mb-1" style={{ color: 'var(--text-secondary)' }}>User ID</label>
                                        <input type="number" value={grantUserId} onChange={e => setGrantUserId(e.target.value)}
                                            className="w-full px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)', border: '1px solid rgba(139,149,168,0.2)', color: 'var(--text-primary)' }}
                                            placeholder="e.g. 5" />
                                    </div>
                                    <div>
                                        <label className="text-[10px] uppercase font-bold block mb-1" style={{ color: 'var(--text-secondary)' }}>Amount</label>
                                        <input type="number" value={grantAmount} onChange={e => setGrantAmount(e.target.value)}
                                            className="w-full px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)', border: '1px solid rgba(139,149,168,0.2)', color: 'var(--text-primary)' }}
                                            placeholder="+50 or -20" />
                                    </div>
                                    <div>
                                        <label className="text-[10px] uppercase font-bold block mb-1" style={{ color: 'var(--text-secondary)' }}>Note (optional)</label>
                                        <input type="text" value={grantNote} onChange={e => setGrantNote(e.target.value)}
                                            className="w-full px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)', border: '1px solid rgba(139,149,168,0.2)', color: 'var(--text-primary)' }}
                                            placeholder="Reason..." />
                                    </div>
                                </div>
                                <button onClick={handleGrant} disabled={adminAction || !grantUserId || !grantAmount}
                                    className="btn-primary px-6 py-2 text-sm" style={{ opacity: adminAction || !grantUserId || !grantAmount ? 0.5 : 1 }}>
                                    {adminAction ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                                    {parseInt(grantAmount) < 0 ? 'Revoke Tokens' : 'Grant Tokens'}
                                </button>
                            </div>
                        )}

                        {/* Transfer Tab */}
                        {adminTab === 'transfer' && (
                            <div className="glass-card p-5">
                                <p className="text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
                                    Transfer tokens from one user to another. Leave &quot;From&quot; empty to create tokens from system.
                                </p>
                                <div className="grid md:grid-cols-2 gap-3 mb-3">
                                    <div>
                                        <label className="text-[10px] uppercase font-bold block mb-1" style={{ color: 'var(--text-secondary)' }}>From User ID (optional)</label>
                                        <input type="number" value={transferFrom} onChange={e => setTransferFrom(e.target.value)}
                                            className="w-full px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)', border: '1px solid rgba(139,149,168,0.2)', color: 'var(--text-primary)' }}
                                            placeholder="Leave empty for system grant" />
                                    </div>
                                    <div>
                                        <label className="text-[10px] uppercase font-bold block mb-1" style={{ color: 'var(--text-secondary)' }}>To User ID</label>
                                        <input type="number" value={transferTo} onChange={e => setTransferTo(e.target.value)}
                                            className="w-full px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)', border: '1px solid rgba(139,149,168,0.2)', color: 'var(--text-primary)' }}
                                            placeholder="e.g. 8" />
                                    </div>
                                </div>
                                <div className="grid md:grid-cols-2 gap-3 mb-4">
                                    <div>
                                        <label className="text-[10px] uppercase font-bold block mb-1" style={{ color: 'var(--text-secondary)' }}>Amount</label>
                                        <input type="number" value={transferAmount} onChange={e => setTransferAmount(e.target.value)}
                                            className="w-full px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)', border: '1px solid rgba(139,149,168,0.2)', color: 'var(--text-primary)' }}
                                            placeholder="e.g. 20" />
                                    </div>
                                    <div>
                                        <label className="text-[10px] uppercase font-bold block mb-1" style={{ color: 'var(--text-secondary)' }}>Note (optional)</label>
                                        <input type="text" value={transferNote} onChange={e => setTransferNote(e.target.value)}
                                            className="w-full px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)', border: '1px solid rgba(139,149,168,0.2)', color: 'var(--text-primary)' }}
                                            placeholder="Reason for transfer..." />
                                    </div>
                                </div>
                                <button onClick={handleTransfer} disabled={adminAction || !transferTo || !transferAmount}
                                    className="btn-primary px-6 py-2 text-sm" style={{ opacity: adminAction || !transferTo || !transferAmount ? 0.5 : 1 }}>
                                    {adminAction ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRightLeft className="w-4 h-4" />}
                                    Transfer Tokens
                                </button>
                            </div>
                        )}
                    </div>
                )}

                {/* Balance Stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    <div className="token-stat-card">
                        <div className="flex items-center gap-2 mb-2">
                            <Zap className="w-5 h-5" style={{ color: '#f59e0b' }} />
                            <span className="text-xs font-bold uppercase" style={{ color: 'var(--text-secondary)' }}>Available</span>
                        </div>
                        <div className="text-3xl font-bold" style={{ color: balance?.is_admin ? '#8b5cf6' : '#f59e0b' }}>
                            {balance?.is_admin ? '∞' : balance?.available || 0}
                        </div>
                    </div>
                    <div className="token-stat-card">
                        <div className="flex items-center gap-2 mb-2">
                            <ShoppingCart className="w-5 h-5" style={{ color: '#06b6d4' }} />
                            <span className="text-xs font-bold uppercase" style={{ color: 'var(--text-secondary)' }}>Purchased</span>
                        </div>
                        <div className="text-3xl font-bold" style={{ color: '#06b6d4' }}>
                            {balance?.purchased_tokens || 0}
                        </div>
                    </div>
                    <div className="token-stat-card">
                        <div className="flex items-center gap-2 mb-2">
                            <Gift className="w-5 h-5" style={{ color: '#10b981' }} />
                            <span className="text-xs font-bold uppercase" style={{ color: 'var(--text-secondary)' }}>Credits</span>
                        </div>
                        <div className="text-3xl font-bold" style={{ color: '#10b981' }}>
                            {balance?.feedback_credits || 0}
                        </div>
                    </div>
                    <div className="token-stat-card">
                        <div className="flex items-center gap-2 mb-2">
                            <Clock className="w-5 h-5" style={{ color: '#ec4899' }} />
                            <span className="text-xs font-bold uppercase" style={{ color: 'var(--text-secondary)' }}>Daily Used</span>
                        </div>
                        <div className="text-3xl font-bold" style={{ color: '#ec4899' }}>
                            {balance?.daily_tokens_used || 0}<span className="text-sm font-normal" style={{ color: 'var(--text-secondary)' }}>/{balance?.daily_limit || 10}</span>
                        </div>
                    </div>
                </div>

                {/* Usage Progress Bar */}
                {!balance?.is_admin && balance && (
                    <div className="glass-card p-5 mb-8">
                        <h3 className="text-sm font-bold mb-4">Usage This Period</h3>
                        <div className="space-y-3">
                            <div>
                                <div className="flex justify-between text-xs mb-1">
                                    <span style={{ color: 'var(--text-secondary)' }}>Daily Usage</span>
                                    <span>{balance.daily_tokens_used}/{balance.daily_limit}</span>
                                </div>
                                <div className="w-full h-2 rounded-full" style={{ background: 'rgba(139,149,168,0.1)' }}>
                                    <div className="h-full rounded-full transition-all" style={{
                                        width: `${Math.min(100, (balance.daily_tokens_used / balance.daily_limit) * 100)}%`,
                                        background: balance.daily_tokens_used >= balance.daily_limit ? '#ef4444' : 'var(--accent-primary)'
                                    }} />
                                </div>
                            </div>
                            <div>
                                <div className="flex justify-between text-xs mb-1">
                                    <span style={{ color: 'var(--text-secondary)' }}>Weekly Usage</span>
                                    <span>{balance.weekly_tokens_used}/{balance.weekly_limit}</span>
                                </div>
                                <div className="w-full h-2 rounded-full" style={{ background: 'rgba(139,149,168,0.1)' }}>
                                    <div className="h-full rounded-full transition-all" style={{
                                        width: `${Math.min(100, (balance.weekly_tokens_used / balance.weekly_limit) * 100)}%`,
                                        background: balance.weekly_tokens_used >= balance.weekly_limit ? '#ef4444' : '#8b5cf6'
                                    }} />
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Purchase Section */}
                {!balance?.is_admin && (
                    <div className="mb-8">
                        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
                            <ShoppingCart className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                            Buy More Tokens
                        </h2>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
                            {PURCHASE_OPTIONS.map(opt => (
                                <div key={opt.amount}
                                    className={`token-purchase-option ${selectedPurchase === opt.amount ? 'selected' : ''}`}
                                    onClick={() => setSelectedPurchase(opt.amount)}>
                                    {opt.popular && (
                                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full mb-2 inline-block" style={{ background: 'rgba(6,182,212,0.15)', color: 'var(--accent-primary)' }}>
                                            MOST POPULAR
                                        </span>
                                    )}
                                    <div className="text-2xl font-bold gradient-text">{opt.amount}</div>
                                    <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>tokens</div>
                                    <div className="text-lg font-bold mt-2">₹{opt.price}</div>
                                    <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{opt.label}</div>
                                </div>
                            ))}
                        </div>
                        {selectedPurchase && (
                            <button onClick={handlePurchase} disabled={purchasing} className="btn-primary w-full justify-center py-3">
                                {purchasing ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShoppingCart className="w-4 h-4" />}
                                {purchasing ? 'Processing...' : `Buy ${selectedPurchase} Tokens for ₹${selectedPurchase}`}
                            </button>
                        )}
                        <p className="text-xs mt-2 text-center" style={{ color: 'var(--text-secondary)' }}>
                            Purchased tokens never expire and are used after your free daily/weekly tokens
                        </p>
                    </div>
                )}

                {/* How Tokens Work */}
                <div className="glass-card p-6 mb-8">
                    <h3 className="text-sm font-bold mb-3 flex items-center gap-2">
                        <Zap className="w-4 h-4" style={{ color: '#f59e0b' }} />
                        How Tokens Work
                    </h3>
                    <div className="grid md:grid-cols-2 gap-4 text-xs" style={{ color: 'var(--text-secondary)' }}>
                        <div className="space-y-2">
                            <p><strong style={{ color: 'var(--text-primary)' }}>Free Tokens:</strong> You get {balance?.daily_limit || 10} tokens/day and {balance?.weekly_limit || 50} tokens/week for free.</p>
                            <p><strong style={{ color: 'var(--text-primary)' }}>What costs a token:</strong> AI Tutor, Mnemonics, Explain Concept, Question Analysis, AI Study Plan, AI Question Generation.</p>
                        </div>
                        <div className="space-y-2">
                            <p><strong style={{ color: 'var(--text-primary)' }}>Priority Order:</strong> Free tokens are used first, then feedback credits, then purchased tokens.</p>
                            <p><strong style={{ color: 'var(--text-primary)' }}>Earn Credits:</strong> Report question errors — if verified correct by admin, you earn {balance?.feedback_credits !== undefined ? '2' : '2'} bonus tokens!</p>
                        </div>
                    </div>
                </div>

                {/* Transaction History */}
                <div className="glass-card p-6">
                    <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
                        <Clock className="w-4 h-4" style={{ color: 'var(--accent-primary)' }} />
                        Transaction History
                    </h3>
                    {transactions.length === 0 ? (
                        <p className="text-sm text-center py-6" style={{ color: 'var(--text-secondary)' }}>
                            No transactions yet. Your token purchases and rewards will appear here.
                        </p>
                    ) : (
                        <div className="space-y-2">
                            {transactions.map(tx => {
                                const info = txTypeLabel(tx.transaction_type);
                                return (
                                    <div key={tx.id} className="flex items-center justify-between py-3 px-3 rounded-lg" style={{ background: 'var(--bg-secondary)' }}>
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: `${info.color}15`, color: info.color }}>
                                                {info.icon}
                                            </div>
                                            <div>
                                                <div className="text-sm font-medium">{info.label}</div>
                                                <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{tx.note}</div>
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <div className="text-sm font-bold" style={{ color: info.color }}>+{tx.amount}</div>
                                            <div className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>
                                                {new Date(tx.created_at).toLocaleDateString()}
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
