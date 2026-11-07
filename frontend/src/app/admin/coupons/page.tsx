'use client';
/**
 * /admin/coupons — coupon codes (2026-11-07). Create a code (or let the server generate one), limit it
 * to plans / uses / dates / one student, share it as a code or a /subscription?coupon= link, switch it
 * off, and see who used which code. Prices are always computed by the server (accounts/coupons.py).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Check, Copy, Link2, Loader2, Plus, RefreshCw, Ticket, Trash2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth';
import {
    couponErrorMessage, couponShareLink, couponsAPI, describeDiscount, localInputToIso,
    type AdminCoupon, type CouponInput, type CouponRedemptionRow, type DiscountType,
} from '@/lib/couponsAPI';
import { PREMIUM_PLANS, type PurchasablePlanId } from '@/app/subscription/plans';

const PLAN_NAME: Record<string, string> = Object.fromEntries(PREMIUM_PLANS.map((p) => [p.id, p.name]));
const STATE_LABEL: Record<AdminCoupon['state'], { text: string; tone: string }> = {
    live: { text: 'Live', tone: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30' },
    scheduled: { text: 'Starts later', tone: 'bg-sky-500/15 text-sky-700 dark:text-sky-400 border-sky-500/30' },
    used_up: { text: 'Used up', tone: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30' },
    expired: { text: 'Expired', tone: 'bg-muted text-muted-foreground border-border' },
    off: { text: 'Off', tone: 'bg-muted text-muted-foreground border-border' },
};

interface FormState {
    code: string;
    discount_type: DiscountType;
    discount_value: string;
    plans: PurchasablePlanId[];
    max_uses: string;
    max_uses_per_user: string;
    valid_from: string;
    valid_until: string;
    assigned_email: string;
    description: string;
}

const EMPTY_FORM: FormState = {
    code: '', discount_type: 'percent', discount_value: '', plans: [], max_uses: '', max_uses_per_user: '1',
    valid_from: '', valid_until: '', assigned_email: '', description: '',
};

function formToInput(form: FormState): CouponInput {
    return {
        code: form.code.trim(),
        discount_type: form.discount_type,
        discount_value: Number(form.discount_value),
        plans: form.plans,
        max_uses: form.max_uses.trim() ? Number(form.max_uses) : null,
        max_uses_per_user: Number(form.max_uses_per_user || 1),
        valid_from: localInputToIso(form.valid_from),
        valid_until: localInputToIso(form.valid_until),
        assigned_email: form.assigned_email.trim(),
        description: form.description.trim(),
    };
}

function fmtDate(iso: string | null): string {
    if (!iso) return '—';
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
}

const inputClass = 'w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40';

export default function AdminCouponsPage() {
    const router = useRouter();
    const { user, loading: authLoading, isAuthenticated } = useAuth();
    const isAdmin = !!user && (user.role === 'admin' || !!user.is_admin);

    const [coupons, setCoupons] = useState<AdminCoupon[]>([]);
    const [redemptions, setRedemptions] = useState<CouponRedemptionRow[]>([]);
    const [loading, setLoading] = useState(true);
    const [notice, setNotice] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState<FormState>(EMPTY_FORM);
    const [saving, setSaving] = useState(false);
    const [busyId, setBusyId] = useState<number | null>(null);
    const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
    const [copied, setCopied] = useState<string | null>(null);
    const [filterCoupon, setFilterCoupon] = useState<number | ''>('');
    const [filterStatus, setFilterStatus] = useState<'redeemed' | ''>('redeemed');

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [list, used] = await Promise.all([
                couponsAPI.adminList(),
                couponsAPI.adminRedemptions({
                    coupon: filterCoupon === '' ? undefined : filterCoupon,
                    status: filterStatus === '' ? undefined : filterStatus,
                }),
            ]);
            setCoupons(list.data.results);
            setRedemptions(used.data.results);
        } catch (err) {
            setError(couponErrorMessage(err));
        } finally {
            setLoading(false);
        }
    }, [filterCoupon, filterStatus]);

    useEffect(() => {
        if (!authLoading && isAuthenticated && isAdmin) void load();
    }, [authLoading, isAuthenticated, isAdmin, load]);

    const totals = useMemo(() => ({
        live: coupons.filter((c) => c.state === 'live').length,
        redeemed: coupons.reduce((sum, c) => sum + c.redeemed, 0),
        discount: coupons.reduce((sum, c) => sum + c.discount_given, 0),
    }), [coupons]);

    async function copy(text: string, key: string) {
        try {
            await navigator.clipboard.writeText(text);
            setCopied(key);
            window.setTimeout(() => setCopied((current) => (current === key ? null : current)), 1500);
        } catch {
            setNotice(`Copy this: ${text}`);
        }
    }

    async function create(e: React.FormEvent) {
        e.preventDefault();
        setSaving(true);
        setError(null);
        try {
            const res = await couponsAPI.adminCreate(formToInput(form));
            setNotice(`Created ${res.data.code} (${describeDiscount(res.data.discount_type, res.data.discount_value)}). Share the code or its link.`);
            setForm(EMPTY_FORM);
            setShowForm(false);
            await load();
        } catch (err) {
            setError(couponErrorMessage(err));
        } finally {
            setSaving(false);
        }
    }

    async function toggle(coupon: AdminCoupon) {
        setBusyId(coupon.id);
        setError(null);
        try {
            await couponsAPI.adminUpdate(coupon.id, { is_active: !coupon.is_active });
            setNotice(`${coupon.code} is ${coupon.is_active ? 'switched off' : 'switched on'}.`);
            await load();
        } catch (err) {
            setError(couponErrorMessage(err));
        } finally {
            setBusyId(null);
        }
    }

    async function remove(coupon: AdminCoupon) {
        setBusyId(coupon.id);
        setError(null);
        try {
            await couponsAPI.adminDelete(coupon.id);
            setNotice(`${coupon.code} deleted.`);
            setConfirmDelete(null);
            await load();
        } catch (err) {
            setError(couponErrorMessage(err));
        } finally {
            setBusyId(null);
        }
    }

    if (authLoading) {
        return <p className="p-6 [.page-container_&]:px-0 text-muted-foreground">Checking access…</p>;
    }
    if (!isAuthenticated || !isAdmin) {
        return (
            <div className="mx-auto max-w-5xl px-4 py-12 [.page-container_&]:px-0 text-center text-foreground">
                <p className="mb-3 text-muted-foreground">You need admin access to view this page.</p>
                <Button onClick={() => router.push('/login?next=' + encodeURIComponent('/admin/coupons'))}>Sign in</Button>
            </div>
        );
    }

    const origin = typeof window !== 'undefined' ? window.location.origin : 'https://cracklabs.app';

    return (
        <div className="mx-auto max-w-7xl px-4 py-6 [.page-container_&]:p-0 text-foreground space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                    <Ticket className="h-5 w-5 text-primary" aria-hidden="true" />
                    <h1 className="text-xl font-semibold">Coupon codes</h1>
                    <span className="text-xs text-muted-foreground">
                        {totals.live} live · {totals.redeemed} used · ₹{totals.discount.toLocaleString('en-IN')} given in discounts
                    </span>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
                        <RefreshCw className={`mr-1 h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
                    </Button>
                    <Button size="sm" onClick={() => setShowForm((v) => !v)}>
                        <Plus className="mr-1 h-4 w-4" /> New coupon
                    </Button>
                </div>
            </div>

            {notice && <p className="rounded-md border border-border bg-muted px-3 py-2 text-sm" role="status">{notice}</p>}
            {error && <p className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300" role="alert">{error}</p>}

            {showForm && (
                <form onSubmit={create} className="rounded-xl border border-border bg-card p-4 space-y-3">
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <label className="text-xs font-medium space-y-1">
                            <span>Code (empty = generate)</span>
                            <input className={`${inputClass} uppercase`} value={form.code} maxLength={32} placeholder="e.g. ANATOMY50"
                                onChange={(e) => setForm({ ...form, code: e.target.value })} />
                        </label>
                        <label className="text-xs font-medium space-y-1">
                            <span>Discount</span>
                            <div className="flex gap-2">
                                <select className={inputClass} value={form.discount_type}
                                    onChange={(e) => setForm({ ...form, discount_type: e.target.value as DiscountType })}>
                                    <option value="percent">% off</option>
                                    <option value="fixed">₹ off</option>
                                </select>
                                <input className={inputClass} type="number" min={1} max={form.discount_type === 'percent' ? 100 : 100000}
                                    required value={form.discount_value} placeholder={form.discount_type === 'percent' ? '1-100' : 'rupees'}
                                    onChange={(e) => setForm({ ...form, discount_value: e.target.value })} />
                            </div>
                        </label>
                        <label className="text-xs font-medium space-y-1">
                            <span>Total uses (empty = no limit)</span>
                            <input className={inputClass} type="number" min={1} value={form.max_uses}
                                onChange={(e) => setForm({ ...form, max_uses: e.target.value })} />
                        </label>
                        <label className="text-xs font-medium space-y-1">
                            <span>Uses per student</span>
                            <input className={inputClass} type="number" min={1} max={100} value={form.max_uses_per_user}
                                onChange={(e) => setForm({ ...form, max_uses_per_user: e.target.value })} />
                        </label>
                        <label className="text-xs font-medium space-y-1">
                            <span>Valid from (optional)</span>
                            <input className={inputClass} type="datetime-local" value={form.valid_from}
                                onChange={(e) => setForm({ ...form, valid_from: e.target.value })} />
                        </label>
                        <label className="text-xs font-medium space-y-1">
                            <span>Valid until (optional)</span>
                            <input className={inputClass} type="datetime-local" value={form.valid_until}
                                onChange={(e) => setForm({ ...form, valid_until: e.target.value })} />
                        </label>
                        <label className="text-xs font-medium space-y-1 sm:col-span-2">
                            <span>Only for this student (account email, optional)</span>
                            <input className={inputClass} type="email" value={form.assigned_email} placeholder="student@example.com"
                                onChange={(e) => setForm({ ...form, assigned_email: e.target.value })} />
                        </label>
                    </div>
                    <fieldset className="text-xs font-medium">
                        <legend className="mb-1">Applies to (none ticked = all plans)</legend>
                        <div className="flex flex-wrap gap-4">
                            {PREMIUM_PLANS.map((plan) => (
                                <label key={plan.id} className="flex items-center gap-1.5 font-normal">
                                    <input type="checkbox" checked={form.plans.includes(plan.id)}
                                        onChange={(e) => setForm({
                                            ...form,
                                            plans: e.target.checked ? [...form.plans, plan.id] : form.plans.filter((p) => p !== plan.id),
                                        })} />
                                    {plan.name} (₹{plan.priceInr})
                                </label>
                            ))}
                        </div>
                    </fieldset>
                    <label className="block text-xs font-medium space-y-1">
                        <span>Note for admins (never shown to students)</span>
                        <input className={inputClass} value={form.description} maxLength={200} placeholder="e.g. Reward for reviewing 50 PSM questions"
                            onChange={(e) => setForm({ ...form, description: e.target.value })} />
                    </label>
                    <p className="text-xs text-muted-foreground">
                        A code worth the whole price activates the plan without payment. Codes never combine with the scholarship rate.
                    </p>
                    <div className="flex gap-2">
                        <Button type="submit" disabled={saving}>
                            {saving && <Loader2 className="mr-1 h-4 w-4 animate-spin" />} Create coupon
                        </Button>
                        <Button type="button" variant="ghost" onClick={() => { setShowForm(false); setForm(EMPTY_FORM); }}>Cancel</Button>
                    </div>
                </form>
            )}

            <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full min-w-[860px] text-sm">
                    <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <tr>
                            <th className="px-3 py-2">Code</th>
                            <th className="px-3 py-2">Discount</th>
                            <th className="px-3 py-2">Plans</th>
                            <th className="px-3 py-2">Used</th>
                            <th className="px-3 py-2">Valid until</th>
                            <th className="px-3 py-2">For</th>
                            <th className="px-3 py-2">State</th>
                            <th className="px-3 py-2 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {coupons.length === 0 && (
                            <tr><td colSpan={8} className="px-3 py-6 text-center text-muted-foreground">
                                {loading ? 'Loading…' : 'No coupon codes yet. Create one with “New coupon”.'}
                            </td></tr>
                        )}
                        {coupons.map((coupon) => (
                            <tr key={coupon.id} className="border-t border-border align-top">
                                <td className="px-3 py-2">
                                    <div className="font-mono font-semibold">{coupon.code}</div>
                                    {coupon.description && <div className="text-xs text-muted-foreground max-w-[220px]">{coupon.description}</div>}
                                </td>
                                <td className="px-3 py-2 whitespace-nowrap">{describeDiscount(coupon.discount_type, coupon.discount_value)}</td>
                                <td className="px-3 py-2 text-xs">{coupon.plans.length ? coupon.plans.map((p) => PLAN_NAME[p] || p).join(', ') : 'All plans'}</td>
                                <td className="px-3 py-2 whitespace-nowrap">
                                    {coupon.redeemed}{coupon.max_uses !== null ? ` / ${coupon.max_uses}` : ''}
                                    {coupon.checkouts_in_progress > 0 && <div className="text-xs text-muted-foreground">{coupon.checkouts_in_progress} paying now</div>}
                                    {coupon.redeemed > 0 && <div className="text-xs text-muted-foreground">₹{coupon.revenue.toLocaleString('en-IN')} paid</div>}
                                </td>
                                <td className="px-3 py-2 text-xs whitespace-nowrap">{fmtDate(coupon.valid_until)}</td>
                                <td className="px-3 py-2 text-xs">{coupon.assigned_user ? (coupon.assigned_user.email || coupon.assigned_user.username) : 'Anyone'}</td>
                                <td className="px-3 py-2">
                                    <Badge className={`border ${STATE_LABEL[coupon.state].tone}`}>{STATE_LABEL[coupon.state].text}</Badge>
                                </td>
                                <td className="px-3 py-2">
                                    <div className="flex flex-wrap justify-end gap-1">
                                        <Button size="sm" variant="ghost" title="Copy code" onClick={() => void copy(coupon.code, `code-${coupon.id}`)}>
                                            {copied === `code-${coupon.id}` ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                                        </Button>
                                        <Button size="sm" variant="ghost" title="Copy a link that fills in the code"
                                            onClick={() => void copy(couponShareLink(origin, coupon.code), `link-${coupon.id}`)}>
                                            {copied === `link-${coupon.id}` ? <Check className="h-4 w-4" /> : <Link2 className="h-4 w-4" />}
                                        </Button>
                                        <Button size="sm" variant="outline" disabled={busyId === coupon.id} onClick={() => void toggle(coupon)}>
                                            {coupon.is_active ? 'Switch off' : 'Switch on'}
                                        </Button>
                                        {coupon.redeemed === 0 && (confirmDelete === coupon.id ? (
                                            <>
                                                <Button size="sm" variant="destructive" disabled={busyId === coupon.id} onClick={() => void remove(coupon)}>Delete</Button>
                                                <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(null)}>Keep</Button>
                                            </>
                                        ) : (
                                            <Button size="sm" variant="ghost" title="Delete (only unused codes)" onClick={() => setConfirmDelete(coupon.id)}>
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        ))}
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <section className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="text-base font-semibold">Who used which code</h2>
                    <div className="flex flex-wrap gap-2 text-xs">
                        <select className={inputClass} value={filterCoupon} aria-label="Filter by code"
                            onChange={(e) => setFilterCoupon(e.target.value ? Number(e.target.value) : '')}>
                            <option value="">All codes</option>
                            {coupons.map((c) => <option key={c.id} value={c.id}>{c.code}</option>)}
                        </select>
                        <select className={inputClass} value={filterStatus} aria-label="Filter by status"
                            onChange={(e) => setFilterStatus(e.target.value === 'redeemed' ? 'redeemed' : '')}>
                            <option value="redeemed">Used (paid / activated)</option>
                            <option value="">Every checkout</option>
                        </select>
                    </div>
                </div>
                <div className="overflow-x-auto rounded-xl border border-border">
                    <table className="w-full min-w-[760px] text-sm">
                        <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                            <tr>
                                <th className="px-3 py-2">When</th>
                                <th className="px-3 py-2">Code</th>
                                <th className="px-3 py-2">Student</th>
                                <th className="px-3 py-2">Plan</th>
                                <th className="px-3 py-2">Price</th>
                                <th className="px-3 py-2">Discount</th>
                                <th className="px-3 py-2">Paid</th>
                                <th className="px-3 py-2">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {redemptions.length === 0 && (
                                <tr><td colSpan={8} className="px-3 py-6 text-center text-muted-foreground">{loading ? 'Loading…' : 'Nobody has used a code yet.'}</td></tr>
                            )}
                            {redemptions.map((row) => (
                                <tr key={row.id} className="border-t border-border">
                                    <td className="px-3 py-2 text-xs whitespace-nowrap">{fmtDate(row.redeemed_at || row.created_at)}</td>
                                    <td className="px-3 py-2 font-mono">{row.code}</td>
                                    <td className="px-3 py-2 text-xs">
                                        {row.user ? <><div className="font-medium">{row.user.username}</div><div className="text-muted-foreground">{row.user.email}</div></> : '—'}
                                    </td>
                                    <td className="px-3 py-2 text-xs">{PLAN_NAME[row.plan] || row.plan}</td>
                                    <td className="px-3 py-2">₹{row.original_amount.toLocaleString('en-IN')}</td>
                                    <td className="px-3 py-2">−₹{row.discount_amount.toLocaleString('en-IN')}</td>
                                    <td className="px-3 py-2 font-semibold">₹{row.final_amount.toLocaleString('en-IN')}</td>
                                    <td className="px-3 py-2 text-xs">
                                        {row.status === 'redeemed' ? 'Used' : row.status === 'reserved' ? 'Paying now' : 'Abandoned'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}
