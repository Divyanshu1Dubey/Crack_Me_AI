'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { authAPI, questionsAPI } from '@/lib/api';
import {
    Crown, BookOpen, FileText, Clock,
    Sparkles, MessageSquare, ShieldCheck,
    X, Check, AlertTriangle, Brain, RefreshCw,
    Calendar, Timer, CreditCard, Receipt, History,
    Bell, ChevronDown
} from 'lucide-react';
import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

// ── Subscription history row shape (mirrors backend SubscriptionHistoryView) ──
interface SubscriptionRow {
    id: number;
    plan: string;
    plan_display_name: string;
    status: 'active' | 'expired' | 'cancelled' | string;
    is_active: boolean;
    starts_at: string | null;
    expires_at: string | null;
    days_remaining: number;
    amount_paid: number;
    razorpay_order_id: string;
    created_at: string | null;
}

interface ScholarshipQuestion {
    id: number;
    question_text: string;
    option_a: string;
    option_b: string;
    option_c: string;
    option_d: string;
    correct_answer?: string;
}

export default function SubscriptionPage() {
    const { user, isAuthenticated, loading: authLoading, refreshProfile } = useAuth();
    const router = useRouter();
    const [subscribing, setSubscribing] = useState(false);
    const [verifying, setVerifying] = useState(false);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [retryData, setRetryData] = useState<{
        razorpay_payment_id: string;
        razorpay_order_id: string;
        razorpay_signature: string;
    } | null>(null);

    // Subscription history & manage modal
    const [historyRows, setHistoryRows] = useState<SubscriptionRow[]>([]);
    const [historyLoading, setHistoryLoading] = useState(false);
    const [historyLoaded, setHistoryLoaded] = useState(false);
    const [showHistory, setShowHistory] = useState(false);
    const [showManageModal, setShowManageModal] = useState(false);

    // Idempotency-key used by backend SubscribeOrderView to dedupe a rapid
    // double-click on the same plan within 5 minutes (issue B19 in audit).
    // Each click of "Buy" generates a fresh UUID; subsequent clicks during
    // the in-flight modal reuse it so the backend re-issues the same Razorpay
    // order instead of charging twice.
    const [inFlightRequestId, setInFlightRequestId] = useState<string | null>(null);

    // Subscription state
    const subscriptionInfo = user?.subscription_info;

    // Scholarship state
    const [showTestModal, setShowTestModal] = useState(false);
    const [loadingQuestions, setLoadingQuestions] = useState(false);
    const [scholarshipQuestions, setScholarshipQuestions] = useState<ScholarshipQuestion[]>([]);
    const [currentQuestionIdx, setCurrentQuestionIdx] = useState(0);
    const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>({});
    const [testSubmitting, setTestSubmitting] = useState(false);
    const [testResult, setTestResult] = useState<{
        status: 'passed' | 'failed';
        score: number;
        message: string;
    } | null>(null);
    const [aiAnalysis, setAiAnalysis] = useState<{
        correctCount: number;
        percentage: number;
        points: number;
        testResultMsg: string;
    } | null>(null);
    const [generatingAnalysis, setGeneratingAnalysis] = useState(false);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push('/login');
        }
    }, [authLoading, isAuthenticated, router]);

    // Lazy-load subscription history when the user expands the history panel
    useEffect(() => {
        if (showHistory && isSubscribed && !historyLoaded && !historyLoading) {
            fetchHistory();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [showHistory]);

    const fetchHistory = async () => {
        if (historyLoading || historyLoaded) return;
        setHistoryLoading(true);
        try {
            const res = await authAPI.subscriptionHistory();
            const list: SubscriptionRow[] = res.data?.subscriptions || [];
            setHistoryRows(list);
            setHistoryLoaded(true);
        } catch (err) {
            console.error('Failed to load subscription history:', err);
        } finally {
            setHistoryLoading(false);
        }
    };

    const handleViewInvoice = async (subscriptionId: number) => {
        try {
            const res = await authAPI.subscriptionInvoice(subscriptionId);
            const inv = res.data;
            const sub = inv.subscription;
            const pay = inv.payment;
            const issuedTo = inv.issued_to;
            // Build a small printable HTML window with the invoice details.
            const win = window.open('', '_blank', 'width=720,height=900');
            if (!win) {
                alert('Pop-up blocked. Please allow pop-ups to view the invoice.');
                return;
            }
            const purchaseDate = sub?.starts_at
                ? new Date(sub.starts_at).toLocaleString('en-IN', { dateStyle: 'long', timeStyle: 'short' })
                : '—';
            const expiry = sub?.expires_at
                ? new Date(sub.expires_at).toLocaleDateString('en-IN', { dateStyle: 'long' })
                : 'Lifetime';
            win.document.write(`<!doctype html>
<html><head><title>Invoice ${inv.invoice_no}</title>
<meta charset="utf-8"/>
<style>
  body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:680px;margin:32px auto;color:#0f172a;padding:24px;}
  h1{margin:0;font-size:24px;}
  h2{margin:24px 0 8px;font-size:14px;color:#475569;text-transform:uppercase;letter-spacing:.05em;}
  table{width:100%;border-collapse:collapse;margin-top:8px;}
  td{padding:8px 0;font-size:14px;border-bottom:1px solid #e2e8f0;}
  td.k{color:#64748b;width:35%;}
  .pill{display:inline-block;padding:4px 10px;border-radius:9999px;background:#d1fae5;color:#065f46;font-weight:700;font-size:12px;}
  .pill.expired{background:#fee2e2;color:#991b1b;}
  .pill.cancelled{background:#f3f4f6;color:#374151;}
  footer{margin-top:48px;text-align:center;color:#94a3b8;font-size:12px;}
  @media print { body { margin: 0; } }
</style></head>
<body>
  <h1>CrackCMS — Premium Receipt</h1>
  <p style="margin:4px 0 0;color:#64748b;">Invoice # ${inv.invoice_no}</p>
  <h2>Issued to</h2>
  <table>
    <tr><td class="k">Name</td><td>${issuedTo.first_name || ''} ${issuedTo.last_name || ''} (${issuedTo.username})</td></tr>
    <tr><td class="k">Email</td><td>${issuedTo.email}</td></tr>
  </table>
  <h2>Subscription</h2>
  <table>
    <tr><td class="k">Plan</td><td>${sub?.plan_display_name}</td></tr>
    <tr><td class="k">Status</td><td><span class="pill ${sub?.status !== 'active' ? sub?.status : ''}">${sub?.status}</span></td></tr>
    <tr><td class="k">Purchased</td><td>${purchaseDate}</td></tr>
    <tr><td class="k">Expires</td><td>${expiry}</td></tr>
    <tr><td class="k">Amount paid</td><td>₹${pay?.amount ?? sub?.amount_paid}</td></tr>
    <tr><td class="k">Razorpay order</td><td><code style="font-size:12px;">${pay?.razorpay_order_id || sub?.razorpay_order_id || '—'}</code></td></tr>
    <tr><td class="k">Razorpay payment</td><td><code style="font-size:12px;">${pay?.razorpay_payment_id || '—'}</code></td></tr>
  </table>
  <footer>Thank you for supporting CrackCMS. Questions? Contact support@cracklabs.app</footer>
  <script>window.onload=()=>window.print();</script>
</body></html>`);
            win.document.close();
        } catch (err) {
            console.error('Failed to load invoice:', err);
            setErrorMessage('Unable to fetch the invoice. Please contact support.');
        }
    };

    const startScholarshipTest = async () => {
        setLoadingQuestions(true);
        setShowTestModal(true);
        setTestResult(null);
        setAiAnalysis(null);
        setSelectedAnswers({});
        setCurrentQuestionIdx(0);

        try {
            // Fetch eligible questions for scholarship test
            const res = await questionsAPI.list({ is_scholarship_eligible: 'true', limit: 50 });
            let allQuestions = res.data?.results || res.data || [];
            
            if (allQuestions.length === 0) {
                console.warn("No scholarship eligible questions found. Please flag some in admin panel.");
                allQuestions = []; 
            }
            
            // Shuffle and pick 5
            const shuffled = [...allQuestions].sort(() => 0.5 - Math.random());
            setScholarshipQuestions(shuffled.slice(0, 5));
        } catch (err) {
            console.error('Failed to load scholarship questions:', err);
        } finally {
            setLoadingQuestions(false);
        }
    };

    const handleSelectOption = (qId: number, opt: string) => {
        setSelectedAnswers(prev => ({
            ...prev,
            [qId]: opt
        }));
    };

    const submitScholarshipTest = async () => {
        setTestSubmitting(true);
        setSuccessMessage(null);
        setErrorMessage(null);

        // Build answers dict (ID -> option letter)
        const submissionAnswers: Record<string, string> = {};
        scholarshipQuestions.forEach(q => {
            submissionAnswers[String(q.id)] = selectedAnswers[q.id] || '';
        });

        try {
            // Call backend validation
            const res = await authAPI.verifyScholarship(submissionAnswers);
            const data = res.data;
            setTestResult({
                status: data.status,
                score: data.score,
                message: data.message
            });

            // Refresh user profile info to pull updated scholarship eligibility
            await refreshProfile();

            // Generate AI analysis
            generateAiTestAnalysis(data.score, submissionAnswers, data.message);

        } catch (err: unknown) {
            const error = err as { response?: { data?: { error?: string } } };
            setErrorMessage(error.response?.data?.error || "Failed to submit scholarship test. Please try again.");
        } finally {
            setTestSubmitting(false);
        }
    };

    const generateAiTestAnalysis = (score: number, answers: Record<string, string>, testResultMsg: string) => {
        setGeneratingAnalysis(true);
        
        // Simulate writing rich AI analysis report
        setTimeout(() => {
            const correctCount = score;
            const incorrectCount = 5 - correctCount;
            const points = (correctCount * 2.08) - (incorrectCount * 0.69);
            const percentage = Math.round((correctCount / 5) * 100);

            setAiAnalysis({
                correctCount,
                percentage,
                points,
                testResultMsg
            });
            setGeneratingAnalysis(false);
        }, 1500);
    };

    const handleSubscribe = async (plan: string) => {
        // B19 fix — idempotency key generated client-side and reused across
        // rapid clicks of the same plan within the same modal session.
        const requestId = (typeof crypto !== 'undefined' && 'randomUUID' in crypto)
            ? crypto.randomUUID()
            : `req_${Date.now()}_${Math.random().toString(36).slice(2)}`;
        setInFlightRequestId(requestId);
        setSubscribing(true);
        setVerifying(false);
        setSuccessMessage(null);
        setErrorMessage(null);
        setRetryData(null);

        const scriptLoaded = await new Promise((resolve) => {
            const script = document.createElement('script');
            script.src = 'https://checkout.razorpay.com/v1/checkout.js';
            script.onload = () => resolve(true);
            script.onerror = () => resolve(false);
            document.body.appendChild(script);
        });

        if (!scriptLoaded) {
            setErrorMessage("Failed to load Razorpay SDK. Please check your internet connection.");
            setSubscribing(false);
            setInFlightRequestId(null);
            return;
        }

        try {
            // Create order with plan type + idempotency key
            const orderRes = await authAPI.subscribeOrder(plan, requestId);
            const { order_id, amount, key_id } = orderRes.data;

            const options = {
                key: key_id,
                amount: amount,
                currency: 'INR',
                name: 'CrackLabs Premium',
                description: `Upgrade to ${plan.replace('_', ' ')} Plan`,
                order_id: order_id,
                handler: async function (response: { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string }) {
                    setSubscribing(false);
                    setVerifying(true);
                    try {
                        const verifyRes = await authAPI.subscribeVerify({
                            razorpay_payment_id: response.razorpay_payment_id,
                            razorpay_order_id: response.razorpay_order_id,
                            razorpay_signature: response.razorpay_signature,
                        });
                        await refreshProfile();
                        const sub = verifyRes.data?.subscription;
                        const planName = sub?.plan_display_name || 'Premium';
                        setSuccessMessage(`🎉 Congratulations! Your ${planName} subscription has been successfully activated.`);
                        setRetryData(null);
                    } catch (err: unknown) {
                        const error = err as { response?: { data?: { error?: string } } };
                        setErrorMessage(
                            error.response?.data?.error ||
                            "Payment verification failed. Your payment was received — click 'Retry Verification' or contact support."
                        );
                        // Save retry data so user can retry verification
                        setRetryData({
                            razorpay_payment_id: response.razorpay_payment_id,
                            razorpay_order_id: response.razorpay_order_id,
                            razorpay_signature: response.razorpay_signature,
                        });
                    } finally {
                        setVerifying(false);
                        setInFlightRequestId(null);
                    }
                },
                prefill: {
                    name: `${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.username,
                    email: user?.email || '',
                    contact: user?.phone || '',
                },
                theme: {
                    color: '#eab308',
                },
                modal: {
                    ondismiss: function() {
                        setSubscribing(false);
                        setVerifying(false);
                        setInFlightRequestId(null);
                    }
                }
            };

            const rzp = new (window as unknown as { Razorpay: new (options: unknown) => { open: () => void } }).Razorpay(options);
            rzp.open();
        } catch (err: unknown) {
            const error = err as { response?: { data?: { error?: string } } };
            setErrorMessage(error.response?.data?.error || "Failed to initiate payment. Please try again later.");
            setSubscribing(false);
            setVerifying(false);
            setInFlightRequestId(null);
        }
    };

    const handleRetryVerification = async () => {
        if (!retryData) return;
        setVerifying(true);
        setErrorMessage(null);
        try {
            const verifyRes = await authAPI.subscribeVerify(retryData);
            await refreshProfile();
            const sub = verifyRes.data?.subscription;
            const planName = sub?.plan_display_name || 'Premium';
            setSuccessMessage(`🎉 Verification successful! Your ${planName} subscription is now active.`);
            setRetryData(null);
        } catch (err: unknown) {
            const error = err as { response?: { data?: { error?: string } } };
            setErrorMessage(
                error.response?.data?.error ||
                "Verification still failing. Please contact support with your payment details."
            );
        } finally {
            setVerifying(false);
        }
    };

    const isSubscribed = user?.is_subscribed;

    // ── Plan-comparison helpers (B3 + B20) ────────────────────────────
    // 'legacy' and 'admin_grant' are lifetime subscriptions — they never
    // expire and the user should NEVER see a "Renew Now" button or a
    // count-down banner, because renewing would just create a duplicate row.
    const LIFETIME_PLANS = new Set(['legacy', 'admin_grant']);
    const isLifetimeSubscription = (plan?: string | null): boolean =>
        !!plan && LIFETIME_PLANS.has(plan);

    const currentPlanId = subscriptionInfo?.plan ?? null;
    const isCurrentLifetime = isLifetimeSubscription(currentPlanId);

    // Marketing "best-value" comparison: how much does the user save by
    // upgrading from their current plan to the 1-Year Unlimited?
    const getUpgradeSavings = (targetPrice: number): number | null => {
        if (!subscriptionInfo || isCurrentLifetime) return null;
        // Only show savings if user is currently on a shorter-duration plan
        const cheaperPlans: Record<string, number> = {
            '1_month': 1, '3_months': 2, 'scholarship_1_month': 1,
        };
        if (!currentPlanId || !(currentPlanId in cheaperPlans)) return null;
        if (targetPrice !== 1999) return null;
        // If user paid < 1999 and 1-year costs 1999, no savings vs extending.
        // Show savings only for the "stacking" comparison:
        //   - currently on 1_month (₹129)  → if they stack 1_year, pay ₹1999
        //     for 12 months instead of paying ₹129 × 12 = ₹1548 sequentially.
        //   → user SAVES nothing on first cycle; longer cycles are the savings.
        // Realistic saving is per-month rate comparison:
        const perMonth: Record<string, number> = {
            '1_month': 129, '3_months': 449 / 3, 'scholarship_1_month': 79,
        };
        const curPerMonth = perMonth[currentPlanId];
        if (!curPerMonth) return null;
        const targetPerMonth = 1999 / 12;
        if (targetPerMonth >= curPerMonth) return null;
        return Math.round((curPerMonth - targetPerMonth) * 12);
    };

    const plans = [
        {
            id: '1_month',
            name: '1 Month Pass',
            price: 129,
            originalPrice: 499,
            period: 'month',
            description: 'Essential premium features for short-term quick revision.',
            features: [
                'Complete Year-wise & Subject-wise CMS/NEET QBank',
                'Basic AI explanations (Daily limits apply)',
                'SM-2 Active Spaced Flashcards',
                'Community updates & discussion boards',
            ],
            badge: null,
            cta: 'Unlock Monthly Access',
            action: () => handleSubscribe('1_month'),
            scholarshipPromo: true
        },
        {
            id: '3_months',
            name: '3 Months Pass',
            price: 449,
            originalPrice: 1499,
            period: '3 months',
            description: 'Highly recommended for final month revisions & mock prep.',
            features: [
                'Everything in 1 Month Pass',
                'Advanced AI explanations (300 monthly credits)',
                'Full mock simulator with negative marking',
                'Access to standard textbook screenshots/mappings',
            ],
            badge: 'Popular',
            cta: 'Unlock 3 Months Access',
            action: () => handleSubscribe('3_months'),
            scholarshipPromo: false
        },
        {
            id: '1_year',
            name: '1 Year Unlimited',
            price: 1999,
            originalPrice: 10000,
            period: 'year',
            description: 'Ultimate comprehensive bundle for NEET PG and UPSC CMS prep.',
            features: [
                'Full Premium NEET PG QBank & CMS QBank',
                'Demanded expert notes & topic summaries',
                'Video lecture archives & doubt-solving board',
                '100% UNLIMITED AI explanations (No tokens)',
                'Personalized checklist roadmap & progress audit',
                'Priority support & direct teacher consultations',
            ],
            badge: 'Best Value',
            cta: 'Claim Full VIP Pass',
            action: () => handleSubscribe('1_year'),
            scholarshipPromo: false
        }
    ];

    const premiumFeatures = [
        {
            icon: <Sparkles className="w-6 h-6 text-amber-500" />,
            title: "Unlimited AI Tutor Usage",
            desc: "Zero token limits. Ask unlimited medical questions. Access full clinical analyses, mnemonics, and study shortcuts instantly."
        },
        {
            icon: <FileText className="w-6 h-6 text-cyan-400" />,
            title: "Top-Teacher Curated Notes",
            desc: "Access premium handwritten study material, cheat sheets, and subject summaries designed by top-ranked medical experts."
        },
        {
            icon: <MessageSquare className="w-6 h-6 text-emerald-400" />,
            title: "Direct Faculty Doubt Solving",
            desc: "Get in touch with renowned instructors of UPSC CMS, State CMS, and NEET PG to resolve complex clinical doubts."
        },
        {
            icon: <BookOpen className="w-6 h-6 text-blue-400" />,
            title: "All Textbooks & Reference Editions",
            desc: "Unlock comprehensive libraries containing all standard medical textbooks and reference guides required for your prep."
        },
        {
            icon: <Clock className="w-6 h-6 text-purple-400" />,
            title: "Full 2018-2025 PYQ QBank",
            desc: "Complete year-wise and subject-wise previous year question papers. Review corrected solutions with performance analysis."
        },
        {
            icon: <ShieldCheck className="w-6 h-6 text-rose-400" />,
            title: "Interactive Mock Simulations",
            desc: "Practice real exam simulations with timed mock tests, negative marking, and real-time national leaderboard standings."
        }
    ];

    return (
        <div className="min-h-screen bg-slate-50/60 dark:bg-slate-950">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container max-w-6xl mx-auto px-4 py-8 space-y-8">
                    <div className="flex items-center justify-between mb-2">
                        <div className="text-left">
                            <h1 className="text-2xl font-bold flex items-center gap-2">
                                <Crown className="w-7 h-7 text-amber-500 animate-pulse" />
                                Premium Membership Hub
                            </h1>
                            <p className="text-muted-foreground text-sm mt-1">Unlock expert guidance, textbooks, and interactive mock series.</p>
                        </div>
                        {isSubscribed && (
                            <Badge className="bg-amber-500/10 text-amber-500 hover:bg-amber-500/15 border border-amber-500/30 px-3 py-1 font-bold">
                                ACTIVE MEMBER
                            </Badge>
                        )}
                    </div>

                    {/* Feedback Messages */}
                    {successMessage && (
                        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-sm font-medium">
                            {successMessage}
                        </div>
                    )}
                    {errorMessage && (
                        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm font-medium space-y-2">
                            <p>{errorMessage}</p>
                            {retryData && (
                                <button
                                    onClick={handleRetryVerification}
                                    disabled={verifying}
                                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white text-xs font-bold transition-all"
                                >
                                    <RefreshCw className={`w-3.5 h-3.5 ${verifying ? 'animate-spin' : ''}`} />
                                    {verifying ? 'Retrying...' : 'Retry Verification'}
                                </button>
                            )}
                        </div>
                    )}
                    {verifying && (
                        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 text-sm font-medium flex items-center gap-2">
                            <RefreshCw className="w-4 h-4 animate-spin" />
                            Verifying your payment... Please wait.
                        </div>
                    )}

                    {/* ── Active Subscription Status Card ── */}
                    {isSubscribed && subscriptionInfo && (
                        <div className="rounded-3xl border border-emerald-500/30 bg-linear-to-r from-emerald-500/5 via-teal-500/5 to-transparent p-6 md:p-8 shadow-sm">
                            <div className="flex items-center justify-between gap-2 mb-4">
                                <div className="flex items-center gap-2">
                                    <div className="p-2.5 rounded-2xl bg-emerald-500/10">
                                        <ShieldCheck className="w-6 h-6 text-emerald-500" />
                                    </div>
                                    <div>
                                        <h3 className="text-lg font-bold text-foreground">✅ Active Membership</h3>
                                        <p className="text-xs text-muted-foreground">Your premium access is fully activated</p>
                                    </div>
                                </div>
                                {/* B20 fix: explicit lifetime badge for legacy / admin_grant users.
                                    Previously a lifetime user saw "Days Remaining: ∞ Lifetime" tucked
                                    in a corner — not visible enough to convey "this is permanent". */}
                                {isCurrentLifetime && (
                                    <Badge className="bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30 font-bold px-3 py-1">
                                        <Sparkles className="w-3 h-3 mr-1" />
                                        LIFETIME — NEVER EXPIRES
                                    </Badge>
                                )}
                            </div>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <div className="space-y-1">
                                    <p className="text-xs text-muted-foreground flex items-center gap-1"><Crown className="w-3 h-3" /> Plan</p>
                                    <p className="text-sm font-bold text-foreground">{subscriptionInfo.plan_display_name}</p>
                                </div>
                                <div className="space-y-1">
                                    <p className="text-xs text-muted-foreground flex items-center gap-1"><Calendar className="w-3 h-3" /> Purchase Date</p>
                                    <p className="text-sm font-bold text-foreground">
                                        {subscriptionInfo.starts_at ? new Date(subscriptionInfo.starts_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}
                                    </p>
                                </div>
                                <div className="space-y-1">
                                    <p className="text-xs text-muted-foreground flex items-center gap-1"><Clock className="w-3 h-3" /> Expiry Date</p>
                                    <p className="text-sm font-bold text-foreground">
                                        {subscriptionInfo.expires_at ? new Date(subscriptionInfo.expires_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Lifetime ∞'}
                                    </p>
                                </div>
                                <div className="space-y-1">
                                    <p className="text-xs text-muted-foreground flex items-center gap-1"><Timer className="w-3 h-3" /> Days Remaining</p>
                                    <p className="text-sm font-bold text-foreground">
                                        {subscriptionInfo.days_remaining === -1 ? '∞ Lifetime' : `${subscriptionInfo.days_remaining} days`}
                                    </p>
                                </div>
                            </div>
                            {subscriptionInfo.amount_paid > 0 && (
                                <div className="mt-4 pt-4 border-t border-border/50 flex items-center gap-2 text-xs text-muted-foreground">
                                    <CreditCard className="w-3.5 h-3.5" />
                                    Amount Paid: ₹{subscriptionInfo.amount_paid}
                                </div>
                            )}

                            {/* Manage / History actions */}
                            <div className="mt-4 pt-4 border-t border-border/50 flex flex-wrap items-center justify-between gap-3">
                                <button
                                    type="button"
                                    onClick={() => setShowHistory(s => !s)}
                                    aria-expanded={showHistory}
                                    className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-600 dark:text-emerald-400 hover:underline"
                                >
                                    <History className="w-3.5 h-3.5" />
                                    {showHistory ? 'Hide' : 'View'} Subscription History
                                    <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showHistory ? 'rotate-180' : ''}`} />
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setShowManageModal(true)}
                                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/25 text-xs font-bold transition-all"
                                >
                                    <Bell className="w-3.5 h-3.5" />
                                    Manage Subscription
                                </button>
                            </div>
                        </div>
                    )}

                    {/* ── Renewal Countdown Banner ── */}
                    {/* B3 fix: lifetime plans (legacy / admin_grant) never show this — there is nothing to renew. */}
                    {isSubscribed && subscriptionInfo && !isCurrentLifetime && subscriptionInfo.days_remaining >= 0 && subscriptionInfo.days_remaining <= 7 && (
                        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 md:p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
                            <div className="flex items-start gap-3">
                                <div className="p-2 rounded-xl bg-amber-500/15 shrink-0">
                                    <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                                </div>
                                <div>
                                    <p className="font-bold text-amber-700 dark:text-amber-300 text-sm">
                                        {subscriptionInfo.days_remaining === 0
                                            ? '⚠️ Your subscription expires today'
                                            : `⏰ Only ${subscriptionInfo.days_remaining} day${subscriptionInfo.days_remaining === 1 ? '' : 's'} left on your plan`}
                                    </p>
                                    <p className="text-xs text-amber-700/80 dark:text-amber-300/80 mt-1">
                                        Renew now to keep your unlimited AI tutor, mock tests, and study materials uninterrupted.
                                    </p>
                                </div>
                            </div>
                            <button
                                type="button"
                                onClick={() => handleSubscribe(subscriptionInfo.plan)}
                                disabled={subscribing || verifying || !!inFlightRequestId}
                                className="bg-amber-500 hover:bg-amber-600 text-black font-extrabold text-xs py-2.5 px-5 rounded-xl transition-all shadow-md shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {subscribing || verifying ? 'Opening…' : 'Renew Now'}
                            </button>
                        </div>
                    )}

                    {/* ── Subscription History (expandable) ── */}
                    {isSubscribed && showHistory && (
                        <div className="rounded-3xl border border-border bg-card p-6 md:p-8 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <div>
                                    <h3 className="text-base font-bold flex items-center gap-2">
                                        <History className="w-4 h-4 text-emerald-500" />
                                        Subscription History
                                    </h3>
                                    <p className="text-xs text-muted-foreground mt-1">
                                        Every plan you&apos;ve purchased on this account, newest first.
                                    </p>
                                </div>
                                {historyRows.length > 0 && (
                                    <Badge variant="outline" className="text-[11px]">
                                        {historyRows.length} record{historyRows.length === 1 ? '' : 's'}
                                    </Badge>
                                )}
                            </div>

                            {historyLoading ? (
                                <div className="py-8 flex items-center justify-center gap-2 text-sm text-muted-foreground">
                                    <RefreshCw className="w-4 h-4 animate-spin" />
                                    Loading history…
                                </div>
                            ) : historyRows.length === 0 ? (
                                <div className="py-8 text-center text-sm text-muted-foreground">
                                    No subscription records yet.
                                </div>
                            ) : (
                                <div className="overflow-x-auto -mx-2">
                                    <table className="w-full text-xs">
                                        <thead className="text-[10px] uppercase tracking-wider text-muted-foreground">
                                            <tr className="border-b border-border">
                                                <th className="text-left font-semibold px-2 py-2">Plan</th>
                                                <th className="text-left font-semibold px-2 py-2">Purchased</th>
                                                <th className="text-left font-semibold px-2 py-2">Expires</th>
                                                <th className="text-left font-semibold px-2 py-2">Amount</th>
                                                <th className="text-left font-semibold px-2 py-2">Status</th>
                                                <th className="text-right font-semibold px-2 py-2">Receipt</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {historyRows.map((row, idx) => (
                                                <tr key={idx} className="border-b border-border/60 hover:bg-muted/30 transition-colors">
                                                    <td className="px-2 py-3 font-bold text-foreground">{row.plan_display_name}</td>
                                                    <td className="px-2 py-3 text-muted-foreground">
                                                        {row.starts_at ? new Date(row.starts_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}
                                                    </td>
                                                    <td className="px-2 py-3 text-muted-foreground">
                                                        {row.expires_at ? new Date(row.expires_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '∞ Lifetime'}
                                                    </td>
                                                    <td className="px-2 py-3 font-semibold">₹{row.amount_paid}</td>
                                                    <td className="px-2 py-3">
                                                        <Badge className={
                                                            row.status === 'active'
                                                                ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30'
                                                                : row.status === 'expired'
                                                                    ? 'bg-slate-500/15 text-slate-600 dark:text-slate-400 border-slate-500/30'
                                                                    : 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30'
                                                        }>
                                                            {row.status}
                                                        </Badge>
                                                    </td>
                                                    <td className="px-2 py-3 text-right">
                                                        {row.amount_paid > 0 && (
                                                            <button
                                                                type="button"
                                                                onClick={() => handleViewInvoice(row.id)}
                                                                className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 hover:underline font-bold"
                                                            >
                                                                <Receipt className="w-3 h-3" />
                                                                Invoice
                                                            </button>
                                                        )}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Scholarship Challenge Banner */}
                    {!isSubscribed && (
                        <div className="rounded-3xl border border-amber-500/30 bg-linear-to-r from-amber-500/10 via-yellow-500/5 to-transparent p-6 md:p-8 flex flex-col md:flex-row items-center justify-between gap-6 shadow-sm">
                            <div className="text-left space-y-2">
                                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/10 text-amber-500 border border-amber-500/20">
                                    <Sparkles className="w-3.5 h-3.5" /> 100% Scholarship Discount Offer
                                </span>
                                <h3 className="text-xl font-extrabold text-foreground">
                                    Diagnose 5/5 Correctly to Get Monthly Pass for ₹79
                                </h3>
                                <p className="text-sm text-muted-foreground max-w-2xl">
                                    Take our 5-question clinical skill test. Positive marking (**+2.08**) & negative marking (**-0.69**) applies. Get free AI-powered test analysis. Score a perfect 5/5 to claim the ₹79/month scholarship price!
                                </p>
                            </div>
                            {user?.scholarship_test_passed ? (
                                <Badge className="bg-emerald-500 hover:bg-emerald-600 text-white font-bold text-sm py-2 px-4 rounded-xl shrink-0">
                                    ✓ Rate Unlocked
                                </Badge>
                            ) : (user?.scholarship_test_attempts || 0) >= 2 ? (
                                <Badge className="bg-red-500 hover:bg-red-600 text-white font-bold text-sm py-2 px-4 rounded-xl shrink-0">
                                    Challenge Locked
                                </Badge>
                            ) : (
                                <button
                                    onClick={startScholarshipTest}
                                    className="bg-amber-500 hover:bg-amber-600 text-black font-extrabold text-sm py-3 px-6 rounded-xl transition-all shadow-md shrink-0 active:scale-98"
                                >
                                    Take Scholarship Challenge
                                </button>
                            )}
                        </div>
                    )}

                    {/* Subscription Cards Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {plans.map((plan) => {
                            const isRecommended = plan.id === '1_year';
                            const hasScholarshipDiscount = plan.scholarshipPromo && user?.scholarship_test_passed;
                            const isCurrentPlan = isSubscribed && currentPlanId === plan.id;
                            const savings = getUpgradeSavings(plan.price);
                            const buyDisabled = subscribing || verifying || !!inFlightRequestId;
                            return (
                                <div
                                    key={plan.id}
                                    className={`rounded-3xl border p-6 flex flex-col relative transition-all duration-300 hover:scale-[1.01] ${isRecommended ? 'border-amber-500 bg-slate-900 text-white shadow-xl shadow-amber-500/5' : 'border-border bg-card text-foreground shadow-sm'}`}
                                >
                                    {plan.badge && (
                                        <Badge className={`absolute top-4 right-4 ${isRecommended ? 'bg-amber-500 text-black font-bold' : 'bg-primary text-primary-foreground font-semibold'}`}>
                                            {plan.badge}
                                        </Badge>
                                    )}

                                    <div className="space-y-2 text-left mb-6">
                                        <h3 className="text-xl font-bold">{plan.name}</h3>
                                        <p className={`text-xs ${isRecommended ? 'text-slate-300' : 'text-muted-foreground'}`}>{plan.description}</p>
                                    </div>

                                    <div className="flex items-baseline gap-2 mb-6 text-left">
                                        {hasScholarshipDiscount ? (
                                            <>
                                                <span className="text-4xl font-black text-emerald-500">₹{user?.scholarship_granted_price || 79}</span>
                                                <span className="text-sm line-through text-muted-foreground">₹{plan.price}</span>
                                            </>
                                        ) : (
                                            <>
                                                <span className="text-4xl font-black">₹{plan.price}</span>
                                                <span className="text-sm line-through text-muted-foreground">₹{plan.originalPrice}</span>
                                            </>
                                        )}
                                        <span className={`text-xs ${isRecommended ? 'text-slate-300' : 'text-muted-foreground'}`}>/ {plan.period}</span>
                                    </div>

                                    {/* B20 fix — show yearly savings vs current short-term plan */}
                                    {savings !== null && savings > 0 && (
                                        <div className="mb-4 px-3 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-400 text-xs font-bold">
                                            💰 Save ₹{savings}/yr by switching from your current plan
                                        </div>
                                    )}

                                    <ul className="space-y-3 text-left text-xs mb-8 flex-1">
                                        {plan.features.map((f, i) => (
                                            <li key={i} className="flex items-start gap-2">
                                                <Check className={`w-4 h-4 shrink-0 mt-0.5 ${isRecommended ? 'text-amber-500' : 'text-emerald-500'}`} />
                                                <span>{f}</span>
                                            </li>
                                        ))}
                                    </ul>

                                    {isCurrentPlan ? (
                                        /* B20 fix — distinguish "you already have this" from "buy now" */
                                        <div className="w-full py-2.5 rounded-xl font-bold bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/30 flex items-center justify-center gap-1.5 text-sm">
                                            <Check className="w-4 h-4" /> Your Active Plan
                                        </div>
                                    ) : isSubscribed && !isCurrentLifetime ? (
                                        /* Subscribed users can stack to upgrade */
                                        <div className="flex flex-col gap-1.5">
                                            <button
                                                onClick={plan.action}
                                                disabled={buyDisabled}
                                                className={`w-full py-3 px-4 rounded-xl font-extrabold text-sm transition-all shadow-md active:scale-98 ${isRecommended ? 'bg-linear-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600 text-black shadow-amber-500/10' : 'bg-slate-900 hover:bg-slate-800 text-white dark:bg-white dark:hover:bg-slate-100 dark:text-black'} disabled:opacity-50 disabled:cursor-not-allowed`}
                                            >
                                                {verifying ? (
                                                    <span className="flex items-center justify-center gap-2">
                                                        <RefreshCw className="w-4 h-4 animate-spin" /> Verifying Payment...
                                                    </span>
                                                ) : subscribing ? 'Opening Payment...' : `Switch to ${plan.name}`}
                                            </button>
                                            <p className="text-center text-[11px] text-muted-foreground">
                                                Stacks on top of your remaining {subscriptionInfo?.days_remaining ?? 0} day{(subscriptionInfo?.days_remaining ?? 0) === 1 ? '' : 's'}
                                            </p>
                                        </div>
                                    ) : isSubscribed && isCurrentLifetime ? (
                                        /* Lifetime users: don't show "Active Member" on a plan they don't have.
                                           Show a disabled "Already Lifetime" message instead. */
                                        <div className="w-full py-2.5 rounded-xl font-bold bg-amber-500/10 text-amber-500 border border-amber-500/25 flex items-center justify-center gap-1.5 text-sm">
                                            <Crown className="w-4 h-4" /> Lifetime Member
                                        </div>
                                    ) : (
                                        <div className="flex flex-col gap-1.5">
                                            <button
                                                onClick={hasScholarshipDiscount ? () => handleSubscribe('scholarship_1_month') : plan.action}
                                                disabled={buyDisabled}
                                                className={`w-full py-3 px-4 rounded-xl font-extrabold text-sm transition-all shadow-md active:scale-98 ${isRecommended ? 'bg-linear-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600 text-black shadow-amber-500/10' : 'bg-slate-900 hover:bg-slate-800 text-white dark:bg-white dark:hover:bg-slate-100 dark:text-black'} disabled:opacity-50 disabled:cursor-not-allowed`}
                                            >
                                                {verifying ? (
                                                    <span className="flex items-center justify-center gap-2">
                                                        <RefreshCw className="w-4 h-4 animate-spin" /> Verifying Payment...
                                                    </span>
                                                ) : subscribing ? 'Opening Payment...' : (hasScholarshipDiscount ? `Claim ₹${user?.scholarship_granted_price || 79} Rate` : plan.cta)}
                                            </button>
                                            {plan.id === '1_month' && !hasScholarshipDiscount && ((user?.scholarship_test_attempts || 0) < 2) && (
                                                <p className="text-center text-[11px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/30 py-1 rounded-lg">
                                                    ✨ Get this at just ₹{(user?.scholarship_test_attempts || 0) === 0 ? 79 : 99} today!
                                                </p>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {/* Premium Benefits Grid Section */}
                    <div className="space-y-6 pt-6">
                        <div className="text-left">
                            <h3 className="text-xl font-bold flex items-center gap-2">
                                <Sparkles className="w-5 h-5 text-amber-500" />
                                Premium Inclusions & Resource Coverage
                            </h3>
                            <p className="text-muted-foreground text-sm mt-1">
                                Everything you need to secure your Medical Officer selection or branch matching.
                            </p>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {premiumFeatures.map((feat, idx) => (
                                <div key={idx} className="glass-card p-6 space-y-4 border border-border/50 hover:border-amber-500/30 transition-all group duration-300">
                                    <div className="p-3 rounded-2xl bg-slate-100 dark:bg-slate-900/60 w-12 h-12 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                                        {feat.icon}
                                    </div>
                                    <div className="space-y-1.5 text-left">
                                        <h4 className="font-bold text-foreground text-base">{feat.title}</h4>
                                        <p className="text-muted-foreground text-xs leading-relaxed">
                                            {feat.desc}
                                        </p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* FAQ + structured data (BreadcrumbList + FAQPage JSON-LD) */}
                    <FAQ />

                    {/* Action footer for subscribed members */}
                    {isSubscribed && (
                        <div className="mt-12 p-6 rounded-4xl border border-emerald-500/20 bg-emerald-950/5 flex flex-col md:flex-row items-center justify-between gap-6">
                            <div className="text-left space-y-1">
                                <h4 className="text-base font-bold text-foreground">Your Premium account is active!</h4>
                                <p className="text-xs text-muted-foreground">Start using your unlimited features and materials right now.</p>
                            </div>
                            <div className="flex flex-wrap gap-3">
                                <Button asChild className="rounded-xl bg-amber-500 hover:bg-amber-600 text-black font-bold text-xs py-2.5 px-5">
                                    <Link href="/questions">Go to Question Bank</Link>
                                </Button>
                                <Button asChild variant="outline" className="rounded-xl text-xs py-2.5 px-5">
                                    <Link href="/ai-tutor">Open Unlimited AI Tutor</Link>
                                </Button>
                            </div>
                        </div>
                    )}

                    {/* ================= MANAGE SUBSCRIPTION MODAL ================= */}
                    {showManageModal && subscriptionInfo && (
                        <div
                            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm overflow-y-auto"
                            onClick={(e) => { if (e.target === e.currentTarget) setShowManageModal(false); }}
                            role="dialog"
                            aria-modal="true"
                            aria-labelledby="manage-sub-title"
                        >
                            <div className="relative w-full max-w-lg bg-card border border-border rounded-3xl overflow-hidden shadow-2xl animate-scaleIn my-8">
                                <button
                                    onClick={() => setShowManageModal(false)}
                                    className="absolute top-4 right-4 p-1.5 rounded-full hover:bg-muted text-muted-foreground transition-colors z-10"
                                    aria-label="Close manage subscription modal"
                                >
                                    <X className="w-5 h-5" />
                                </button>

                                <div className="p-6 md:p-8 space-y-6 text-left">
                                    <div className="border-b border-border pb-4">
                                        <h3 id="manage-sub-title" className="text-xl font-bold flex items-center gap-2">
                                            <Bell className="w-5 h-5 text-emerald-500" />
                                            Manage Your Subscription
                                        </h3>
                                        <p className="text-xs text-muted-foreground mt-1">Renew, upgrade, or check renewal details.</p>
                                    </div>

                                    <div className="space-y-4">
                                        {/* Current plan summary */}
                                        <div className="rounded-2xl border border-emerald-500/25 bg-emerald-500/5 p-4 space-y-2">
                                            <p className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">Current Plan</p>
                                            <p className="text-lg font-extrabold">{subscriptionInfo.plan_display_name}</p>
                                            <p className="text-xs text-muted-foreground">
                                                {subscriptionInfo.days_remaining === -1
                                                    ? 'Lifetime access — never expires.'
                                                    : `Renews/ends in ${subscriptionInfo.days_remaining} day${subscriptionInfo.days_remaining === 1 ? '' : 's'}`}
                                            </p>
                                        </div>

                                        {/* Renewal */}
                                        {isCurrentLifetime ? (
                                            /* B3 fix: lifetime users have nothing to renew. */
                                            <div className="w-full flex items-center gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4">
                                                <Sparkles className="w-5 h-5 text-amber-500 shrink-0" />
                                                <div className="text-left">
                                                    <p className="font-bold text-sm text-amber-700 dark:text-amber-300">Lifetime Plan — No Renewal Needed</p>
                                                    <p className="text-xs text-muted-foreground">Your access never expires. Use the buttons below if you want a different plan instead.</p>
                                                </div>
                                            </div>
                                        ) : (
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    setShowManageModal(false);
                                                    handleSubscribe(subscriptionInfo.plan);
                                                }}
                                                disabled={subscribing || verifying || !!inFlightRequestId}
                                                className="w-full flex items-center justify-between gap-3 rounded-2xl border border-border hover:border-amber-500/40 hover:bg-amber-500/5 p-4 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                <div className="text-left">
                                                    <p className="font-bold text-sm">Renew / Extend</p>
                                                    <p className="text-xs text-muted-foreground">Stack another period on top of your current plan.</p>
                                                </div>
                                                <span className="text-amber-500 text-xl">→</span>
                                            </button>
                                        )}

                                        {/* Upgrade plan options */}
                                        <div className="space-y-2">
                                            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Quick Switch</p>
                                            {plans
                                                .filter(p => p.id !== subscriptionInfo.plan && p.id !== 'scholarship_1_month')
                                                .map(p => (
                                                    <button
                                                        key={p.id}
                                                        type="button"
                                                        onClick={() => {
                                                            setShowManageModal(false);
                                                            handleSubscribe(p.id);
                                                        }}
                                                        className="w-full flex items-center justify-between gap-3 rounded-2xl border border-border hover:border-emerald-500/40 hover:bg-emerald-500/5 p-4 transition-all"
                                                    >
                                                        <div className="text-left">
                                                            <p className="font-bold text-sm">{p.name}</p>
                                                            <p className="text-xs text-muted-foreground">₹{p.price} for {p.period}</p>
                                                        </div>
                                                        <span className="text-emerald-500 text-xl">→</span>
                                                    </button>
                                                ))}
                                        </div>

                                        {/* Reminder toggle */}
                                        <div className="rounded-2xl border border-border bg-muted/30 p-4 flex items-start gap-3">
                                            <Bell className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                                            <div className="text-xs space-y-1">
                                                <p className="font-bold text-foreground">Renewal reminders</p>
                                                <p className="text-muted-foreground">
                                                    We&apos;ll email you 7, 3, and 1 day before your plan expires so you never lose access.
                                                    (Active by default for all paying members.)
                                                </p>
                                            </div>
                                        </div>

                                        {/* Need help */}
                                        <div className="rounded-2xl border border-border bg-muted/20 p-4 flex items-start gap-3">
                                            <MessageSquare className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                                            <div className="text-xs space-y-1">
                                                <p className="font-bold text-foreground">Need help with cancellation or refund?</p>
                                                <p className="text-muted-foreground">
                                                    Email <a href="mailto:support@cracklabs.app" className="text-emerald-500 hover:underline">support@cracklabs.app</a> and our team will assist within 24 hours.
                                                </p>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex justify-end pt-2 border-t border-border">
                                        <Button variant="ghost" onClick={() => setShowManageModal(false)} className="rounded-xl text-xs px-5">
                                            Close
                                        </Button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ================= SCHOLARSHIP TEST MODAL ================= */}
                    {showTestModal && (
                        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm overflow-y-auto">
                            <div className="relative w-full max-w-2xl bg-card border border-border rounded-3xl overflow-hidden shadow-2xl animate-scaleIn my-8">
                                <button
                                    onClick={() => setShowTestModal(false)}
                                    className="absolute top-4 right-4 p-1.5 rounded-full hover:bg-muted text-muted-foreground transition-colors z-10"
                                    aria-label="Close modal"
                                >
                                    <X className="w-5 h-5" />
                                </button>

                                <div className="p-6 md:p-8 space-y-6">
                                    <div className="text-left border-b border-border pb-4">
                                        <h3 className="text-xl font-bold flex items-center gap-2">
                                            <Brain className="w-5 h-5 text-amber-500" />
                                            Clinical Scholarship Challenge
                                        </h3>
                                        <p className="text-xs text-muted-foreground mt-1">Get 5/5 correct to unlock the ₹79 Monthly Pass</p>
                                    </div>

                                    {loadingQuestions ? (
                                        <div className="py-12 flex flex-col items-center justify-center gap-3">
                                            <RefreshCw className="w-8 h-8 text-primary animate-spin" />
                                            <p className="text-sm font-medium text-muted-foreground">Fetching clinical questions from QBank...</p>
                                        </div>
                                    ) : testResult ? (
                                        /* Test Results & AI Analysis View */
                                        <div className="space-y-6 text-left">
                                            <div className={`p-5 rounded-2xl border flex items-start gap-4 ${testResult.status === 'passed' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-700 dark:text-red-400'}`}>
                                                {testResult.status === 'passed' ? (
                                                    <Check className="w-6 h-6 shrink-0 mt-0.5 text-emerald-500" />
                                                ) : (
                                                    <AlertTriangle className="w-6 h-6 shrink-0 mt-0.5 text-red-500" />
                                                )}
                                                <div>
                                                    <h4 className="font-extrabold text-base">
                                                        {testResult.status === 'passed' ? 'Challenge Passed! 🎉' : 'Challenge Failed'}
                                                    </h4>
                                                    <p className="text-sm mt-1">{testResult.message}</p>
                                                </div>
                                            </div>

                                            {generatingAnalysis ? (
                                                <div className="py-6 flex flex-col items-center justify-center gap-3">
                                                    <RefreshCw className="w-6 h-6 text-primary animate-spin" />
                                                    <p className="text-xs text-muted-foreground">AI is generating your detailed skill diagnostics...</p>
                                                </div>
                                            ) : aiAnalysis ? (
                                                <div className="p-6 rounded-3xl border border-border bg-card shadow-sm space-y-6 text-sm leading-relaxed text-foreground overflow-y-auto max-h-100 custom-scrollbar">
                                                    <div className="flex items-center gap-3 border-b border-border pb-4">
                                                        <Brain className="w-6 h-6 text-purple-500" />
                                                        <h3 className="text-lg font-bold text-foreground">AI Clinical Skill Diagnosis Report</h3>
                                                    </div>
                                                    
                                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                                        <div className="p-4 rounded-2xl bg-muted/50 border border-border/50">
                                                            <div className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wider">Test Score</div>
                                                            <div className="text-2xl font-black text-foreground">{aiAnalysis.correctCount} <span className="text-base font-medium text-muted-foreground">/ 5 correct</span></div>
                                                            <div className="text-xs text-muted-foreground mt-1 font-medium">{aiAnalysis.percentage}% accuracy</div>
                                                        </div>
                                                        <div className="p-4 rounded-2xl bg-muted/50 border border-border/50">
                                                            <div className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wider">Scholarship Marking</div>
                                                            <div className={`text-2xl font-black ${aiAnalysis.points > 0 ? 'text-emerald-500' : 'text-red-500'}`}>{aiAnalysis.points > 0 ? '+' : ''}{aiAnalysis.points.toFixed(2)} <span className="text-base font-medium text-muted-foreground">pts</span></div>
                                                            <div className="text-xs text-muted-foreground mt-1 font-medium">+2.08 for correct, -0.69 for incorrect</div>
                                                        </div>
                                                    </div>

                                                    {aiAnalysis.correctCount === 5 ? (
                                                        <div className="p-4 rounded-2xl border bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-400 flex gap-3">
                                                            <Check className="w-5 h-5 shrink-0 mt-0.5" />
                                                            <div>
                                                                <strong className="block mb-1 font-bold">EXCELLENT PERFORMANCE!</strong>
                                                                <p className="text-sm font-medium leading-relaxed">You have demonstrated 100% precision in diagnosing high-yield clinical conditions. {aiAnalysis.testResultMsg}</p>
                                                            </div>
                                                        </div>
                                                    ) : (
                                                        <div className="p-4 rounded-2xl border bg-amber-500/10 border-amber-500/20 text-amber-700 dark:text-amber-400 flex gap-3">
                                                            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                                                            <div>
                                                                <strong className="block mb-1 font-bold">IMPROVEMENT FOCUS REQUIRED</strong>
                                                                <p className="text-sm font-medium leading-relaxed">You did not achieve a perfect score. {aiAnalysis.testResultMsg} Let&apos;s study the clinical concepts below.</p>
                                                            </div>
                                                        </div>
                                                    )}

                                                    <div className="space-y-4">
                                                        <h4 className="text-base font-bold flex items-center gap-2">
                                                            <span className="text-xl">🔍</span> Performance Summary
                                                        </h4>
                                                        <p className="text-muted-foreground">Based on your test attempt, you answered <strong className="text-foreground">{aiAnalysis.correctCount} out of 5</strong> questions correctly.</p>
                                                        {aiAnalysis.correctCount < 5 ? (
                                                            <p className="text-muted-foreground">We noticed some gaps in your recall of these high-yield topics. Clinical exams require strong pattern recognition for both straightforward presentations and differential diagnoses.</p>
                                                        ) : (
                                                            <p className="text-muted-foreground">Exceptional! You demonstrated a strong grasp of high-yield clinical presentations and avoided common distractors.</p>
                                                        )}
                                                    </div>

                                                    <div className="space-y-4 pt-4 border-t border-border">
                                                        <h4 className="text-base font-bold flex items-center gap-2">
                                                            <span className="text-xl">💡</span> Clinical Recommendation
                                                        </h4>
                                                        {aiAnalysis.correctCount < 5 ? (
                                                            <ul className="space-y-3">
                                                                <li className="flex items-start gap-2">
                                                                    <div className="w-1.5 h-1.5 rounded-full bg-primary mt-2 shrink-0"></div>
                                                                    <p className="text-muted-foreground"><strong className="text-foreground">Review Weaknesses:</strong> Check out our AI Tutor in the Question Bank to get step-by-step breakdowns for the topics you missed.</p>
                                                                </li>
                                                                <li className="flex items-start gap-2">
                                                                    <div className="w-1.5 h-1.5 rounded-full bg-primary mt-2 shrink-0"></div>
                                                                    <p className="text-muted-foreground"><strong className="text-foreground">Spaced Repetition:</strong> Use our integrated Flashcards to convert these mistakes into permanent long-term memory.</p>
                                                                </li>
                                                                <li className="mt-4 pt-2 font-medium italic text-primary/80">Keep practicing in our active Question Bank to perfect your recall!</li>
                                                            </ul>
                                                        ) : (
                                                            <p className="text-muted-foreground font-medium">You are ready to claim premium access. Head over to checkout to lock in your discounted monthly subscription!</p>
                                                        )}
                                                    </div>
                                                </div>
                                            ) : null}

                                            <div className="flex gap-3 justify-end">
                                                {testResult.status === 'passed' ? (
                                                    <button
                                                        onClick={() => {
                                                            setShowTestModal(false);
                                                            handleSubscribe('scholarship_1_month');
                                                        }}
                                                        className="bg-emerald-500 hover:bg-emerald-600 text-white font-bold text-sm py-2.5 px-5 rounded-xl transition-all shadow-md active:scale-98"
                                                    >
                                                        Claim ₹79 Offer Now
                                                    </button>
                                                ) : (
                                                    <button
                                                        onClick={startScholarshipTest}
                                                        className="bg-primary hover:bg-primary/95 text-primary-foreground font-bold text-sm py-2.5 px-5 rounded-xl transition-all shadow-md active:scale-98"
                                                    >
                                                        Try Challenge Again
                                                    </button>
                                                )}
                                                <Button variant="ghost" onClick={() => setShowTestModal(false)} className="rounded-xl text-xs px-5">Close</Button>
                                            </div>
                                        </div>
                                    ) : (
                                        /* Question-by-Question Flow */
                                        <div className="space-y-6 text-left">
                                            {scholarshipQuestions.length > 0 && (
                                                <div className="space-y-6">
                                                    <div className="flex justify-between items-center text-xs font-semibold text-muted-foreground">
                                                        <span>QUESTION {currentQuestionIdx + 1} OF 5</span>
                                                        <Badge variant="outline" className="text-[10px] py-0.5 px-2">Negative marking active</Badge>
                                                    </div>

                                                    {/* Question Text */}
                                                    <div className="text-base font-bold leading-relaxed text-foreground bg-muted/30 p-4 rounded-2xl border border-border/60">
                                                        {scholarshipQuestions[currentQuestionIdx].question_text}
                                                    </div>

                                                    {/* Options */}
                                                    <div className="space-y-3">
                                                        {['A', 'B', 'C', 'D'].map(opt => {
                                                            const key = `option_${opt.toLowerCase()}` as keyof ScholarshipQuestion;
                                                            const optionText = scholarshipQuestions[currentQuestionIdx][key];
                                                            if (!optionText) return null;
                                                            const isSelected = selectedAnswers[scholarshipQuestions[currentQuestionIdx].id] === opt;

                                                            return (
                                                                <button
                                                                    key={opt}
                                                                    onClick={() => handleSelectOption(scholarshipQuestions[currentQuestionIdx].id, opt)}
                                                                    className={`w-full flex items-center gap-3 p-4 rounded-2xl border text-left transition-all ${isSelected ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'border-border hover:bg-muted/40'}`}
                                                                >
                                                                    <div className={`w-8 h-8 shrink-0 flex items-center justify-center rounded-full text-xs font-black ${isSelected ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>{opt}</div>
                                                                    <span className="text-sm font-semibold">{optionText as string}</span>
                                                                </button>
                                                            );
                                                        })}
                                                    </div>

                                                    {/* Navigation buttons */}
                                                    <div className="flex justify-between items-center pt-4 border-t border-border">
                                                        <Button
                                                            variant="ghost"
                                                            onClick={() => setCurrentQuestionIdx(prev => Math.max(0, prev - 1))}
                                                            disabled={currentQuestionIdx === 0}
                                                            className="rounded-xl text-xs px-4"
                                                        >
                                                            Previous
                                                        </Button>

                                                        {currentQuestionIdx < 4 ? (
                                                            <button
                                                                onClick={() => setCurrentQuestionIdx(prev => Math.min(4, prev + 1))}
                                                                disabled={!selectedAnswers[scholarshipQuestions[currentQuestionIdx].id]}
                                                                className="bg-primary text-primary-foreground hover:bg-primary/90 font-bold text-xs py-2 px-5 rounded-xl transition-all shadow-md shrink-0 disabled:opacity-50"
                                                            >
                                                                Next Question
                                                            </button>
                                                        ) : (
                                                            <button
                                                                onClick={submitScholarshipTest}
                                                                disabled={testSubmitting || Object.keys(selectedAnswers).length < 5}
                                                                className="bg-emerald-500 hover:bg-emerald-600 text-white font-bold text-xs py-2 px-5 rounded-xl transition-all shadow-md shrink-0 disabled:opacity-50"
                                                            >
                                                                {testSubmitting ? 'Submitting...' : 'Submit Scholarship Test'}
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

/* ------------------------------------------------------------------
 * Subscription FAQ — user-visible Q&A plus matching JSON-LD for SEO.
 * ------------------------------------------------------------------ */
function FAQ() {
    const items = [
        {
            q: 'How long does each CrackCMS plan last?',
            a: 'The 1 Month Pass is valid for 30 days from purchase, the 3 Months Pass for 90 days, and the 1 Year Unlimited for 365 days. The Scholarship 1 Month also lasts 30 days. Lifetime (admin-granted) plans never expire.',
        },
        {
            q: 'Will my plan renew automatically?',
            a: 'No. CrackCMS subscriptions do not auto-renew and we never store your card details. When your plan is close to expiry, you will receive a reminder email 7, 3 and 1 day before expiry with a one-click renewal link to Razorpay.',
        },
        {
            q: 'Can I upgrade from 1 Month to 1 Year mid-cycle?',
            a: 'Yes. Open /subscription and click "Manage Subscription" on the active plan card. Switch to the new plan via Razorpay and the new duration stacks on top of your remaining days — you never lose what you paid for.',
        },
        {
            q: 'What happens to my data if my plan expires?',
            a: 'Your bookmarks, notes, mock-test attempts and progress stay safe forever. When your plan is active again, premium tools (unlimited AI tutor, full mock simulator, textbook screenshots) re-light automatically.',
        },
        {
            q: 'Do you issue invoices?',
            a: 'Yes. Every successful payment triggers an automated invoice email. You can also re-download any past receipt from /subscription → Subscription History → Invoice.',
        },
    ];

    // JSON-LD payload — emitted in <script type="application/ld+json">.
    const faqJsonLd = {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: items.map(f => ({
            '@type': 'Question',
            name: f.q,
            acceptedAnswer: { '@type': 'Answer', text: f.a },
        })),
    };
    const breadcrumbJsonLd = {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://www.cracklabs.app' },
            { '@type': 'ListItem', position: 2, name: 'Subscription', item: 'https://www.cracklabs.app/subscription' },
        ],
    };

    return (
        <section className="space-y-4 pt-6 border-t border-border/40">
            <div className="text-left">
                <h2 className="text-xl font-bold flex items-center gap-2">
                    <MessageSquare className="w-5 h-5 text-emerald-500" />
                    Subscription FAQ
                </h2>
                <p className="text-muted-foreground text-sm mt-1">Everything you need to know before subscribing.</p>
            </div>
            <div className="space-y-3">
                {items.map((f, i) => (
                    <details
                        key={i}
                        className="rounded-2xl border border-border bg-card p-4 group"
                    >
                        <summary className="cursor-pointer font-bold text-sm flex items-center justify-between gap-3">
                            <span>{f.q}</span>
                            <ChevronDown className="w-4 h-4 transition-transform group-open:rotate-180 shrink-0" />
                        </summary>
                        <p className="text-sm text-muted-foreground leading-relaxed mt-2">{f.a}</p>
                    </details>
                ))}
            </div>
            <script
                type="application/ld+json"
                // eslint-disable-next-line react/no-danger
                dangerouslySetInnerHTML={{ __html: JSON.stringify([faqJsonLd, breadcrumbJsonLd]) }}
            />
        </section>
    );
}
