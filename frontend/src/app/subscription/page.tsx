'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { authAPI } from '@/lib/api';
import {
    Crown, BookOpen, FileText, CheckCircle2, Clock, 
    Sparkles, Users, MessageSquare, Zap, ShieldCheck
} from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export default function SubscriptionPage() {
    const { user, isAuthenticated, loading: authLoading, refreshProfile } = useAuth();
    const router = useRouter();
    const [subscribing, setSubscribing] = useState(false);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push('/login');
        }
    }, [authLoading, isAuthenticated, router]);

    const handleSubscribe = async () => {
        setSubscribing(true);
        setSuccessMessage(null);
        setErrorMessage(null);

        // Load Razorpay script
        const scriptLoaded = await new Promise((resolve) => {
            const script = document.createElement('script');
            script.src = 'https://checkout.razorpay.com/v1/checkout.js';
            script.onload = () => resolve(true);
            script.onerror = () => resolve(false);
            document.body.appendChild(script);
        });

        if (!scriptLoaded) {
            setErrorMessage("Failed to load Razorpay SDK. Please check your internet connection and try again.");
            setSubscribing(false);
            return;
        }

        try {
            // 1. Create order on backend
            const orderRes = await authAPI.subscribeOrder();
            const { order_id, amount, key_id } = orderRes.data;

            // 2. Open Razorpay checkout modal
            const options = {
                key: key_id,
                amount: amount,
                currency: 'INR',
                name: 'CrackLabs Premium',
                description: '₹199 Early Bird Premium Plan',
                order_id: order_id,
                handler: async function (response: any) {
                    setSubscribing(true);
                    try {
                        // 3. Verify payment signature on backend
                        await authAPI.subscribeVerify({
                            razorpay_payment_id: response.razorpay_payment_id,
                            razorpay_order_id: response.razorpay_order_id,
                            razorpay_signature: response.razorpay_signature,
                        });
                        await refreshProfile();
                        setSuccessMessage("Congratulations! Your Premium subscription has been activated.");
                    } catch (err: any) {
                        setErrorMessage(err.response?.data?.error || "Payment verification failed. Please contact support.");
                    } finally {
                        setSubscribing(false);
                    }
                },
                prefill: {
                    name: `${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.username,
                    email: user?.email || '',
                    contact: user?.phone || '',
                },
                theme: {
                    color: '#eab308', // Amber theme matching premium look
                },
                modal: {
                    ondismiss: function() {
                        setSubscribing(false);
                    }
                }
            };

            const rzp = new (window as any).Razorpay(options);
            rzp.open();
        } catch (err: any) {
            setErrorMessage(err.response?.data?.error || "Failed to initiate payment. Please try again later.");
            setSubscribing(false);
        }
    };

    if (authLoading || !isAuthenticated) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
        );
    }

    const isSubscribed = user?.is_subscribed;

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
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container max-w-6xl mx-auto px-4 py-8">
                    <div className="flex items-center justify-between mb-8">
                        <h1 className="text-2xl font-bold flex items-center gap-2">
                            <Crown className="w-7 h-7 text-amber-500 animate-pulse" />
                            Premium Membership Hub
                        </h1>
                        {isSubscribed && (
                            <Badge className="bg-amber-500/10 text-amber-500 hover:bg-amber-500/15 border border-amber-500/30 px-3 py-1 font-bold">
                                ACTIVE MEMBER
                            </Badge>
                        )}
                    </div>

                    {/* Subscription Hero Card */}
                    <div className="glass-card overflow-hidden mb-12 relative border-amber-500/20" style={{
                        background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%)',
                    }}>
                        {/* Glow effects */}
                        <div className="absolute top-0 right-0 w-96 h-96 bg-amber-500/5 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />
                        <div className="absolute bottom-0 left-0 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl -ml-20 -mb-20 pointer-events-none" />

                        <div className="p-8 md:p-10 flex flex-col md:flex-row md:items-center justify-between gap-8 z-10 relative">
                            <div className="space-y-4 max-w-2xl text-left">
                                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-500 border border-amber-500/20">
                                    <Sparkles className="w-3.5 h-3.5" /> Early Bird Launch Offer
                                </div>
                                <h2 className="text-3xl font-extrabold tracking-tight text-white md:text-4xl leading-tight">
                                    Unlock MBBS, UPSC CMS & State CMS Mastery
                                </h2>
                                <p className="text-slate-300 text-sm md:text-base leading-relaxed">
                                    Get complete coverage for **MBBS university papers, UPSC CMS, and State CMS exams** along with expert academic guidance. Unlock all required and requested materials, standard textbooks, premium notes, doubt portals, and our complete QBank. This extremely low price is available for a limited time only to help every medical aspirant succeed!
                                </p>

                                <div className="flex flex-wrap gap-4 text-xs text-slate-400 pt-2">
                                    <div className="flex items-center gap-1.5 bg-background/50 px-3 py-1.5 rounded-lg border border-border">
                                        <Clock className="w-3.5 h-3.5 text-amber-500" /> Limited Time Offer
                                    </div>
                                    <div className="flex items-center gap-1.5 bg-background/50 px-3 py-1.5 rounded-lg border border-border">
                                        <Users className="w-3.5 h-3.5 text-cyan-400" /> Renowned Medical Faculty
                                    </div>
                                    <div className="flex items-center gap-1.5 bg-background/50 px-3 py-1.5 rounded-lg border border-border">
                                        <Zap className="w-3.5 h-3.5 text-emerald-400" /> Unlimited AI tutor (No tokens)
                                    </div>
                                </div>
                            </div>

                            <div className="glass-card p-6 flex flex-col items-center justify-center text-center w-full md:w-80 border-amber-500/30 shrink-0" style={{
                                background: 'rgba(15, 23, 42, 0.6)'
                            }}>
                                <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">One-Time Payment</span>
                                <div className="mt-2 flex items-baseline justify-center gap-2">
                                    <span className="text-5xl font-black text-white">₹199</span>
                                    <span className="text-sm line-through text-muted-foreground">₹10,000</span>
                                </div>
                                <span className="text-[10px] text-amber-500 font-semibold mt-1">Price rises to ₹10K+ in some days</span>

                                {successMessage && (
                                    <div className="mt-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium w-full">
                                        {successMessage}
                                    </div>
                                )}

                                {errorMessage && (
                                    <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium w-full">
                                        {errorMessage}
                                    </div>
                                )}

                                {!isSubscribed ? (
                                    <button
                                        onClick={handleSubscribe}
                                        disabled={subscribing}
                                        className="w-full mt-6 py-3 px-4 rounded-xl font-bold transition-all bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600 text-black shadow-lg shadow-amber-500/15 active:scale-98"
                                    >
                                        {subscribing ? 'Processing...' : 'Claim Early Bird Offer'}
                                    </button>
                                ) : (
                                    <div className="w-full mt-6 py-2.5 px-4 rounded-xl font-bold bg-amber-500/10 text-amber-500 border border-amber-500/25 flex items-center justify-center gap-1.5">
                                        <Crown className="w-4 h-4" /> Active Premium Member
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Premium Benefits Grid Section */}
                    <div className="space-y-6">
                        <div className="text-left">
                            <h3 className="text-xl font-bold text-white flex items-center gap-2">
                                <Sparkles className="w-5 h-5 text-amber-500" />
                                What's Included in Your Premium Membership
                            </h3>
                            <p className="text-muted-foreground text-sm mt-1">
                                Complete coverage of everything a medical student needs to crack UPSC CMS and NEET PG.
                            </p>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {premiumFeatures.map((feat, idx) => (
                                <div key={idx} className="glass-card p-6 space-y-4 border border-border/50 hover:border-amber-500/30 transition-all group duration-300">
                                    <div className="p-3 rounded-2xl bg-slate-900/60 w-12 h-12 flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                                        {feat.icon}
                                    </div>
                                    <div className="space-y-1.5 text-left">
                                        <h4 className="font-bold text-white text-base">{feat.title}</h4>
                                        <p className="text-slate-400 text-xs leading-relaxed">
                                            {feat.desc}
                                        </p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Action footer for subscribed members */}
                    {isSubscribed && (
                        <div className="mt-12 p-6 rounded-[2rem] border border-emerald-500/20 bg-emerald-950/10 backdrop-blur-md flex flex-col md:flex-row items-center justify-between gap-6">
                            <div className="text-left space-y-1">
                                <h4 className="text-base font-bold text-white">Your Premium account is active!</h4>
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
                </div>
            </div>
        </div>
    );
}
