'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { authAPI, analyticsAPI } from '@/lib/api';
import {
    Crown, BookOpen, FileText, CheckCircle2, Clock, 
    Sparkles, HelpCircle, Users, MessageSquare, Send, Gift
} from 'lucide-react';

export default function SubscriptionPage() {
    const { user, isAuthenticated, loading: authLoading, refreshProfile } = useAuth();
    const router = useRouter();
    const [subscribing, setSubscribing] = useState(false);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    // Request Material state
    const [reqType, setReqType] = useState('book');
    const [reqTitle, setReqTitle] = useState('');
    const [reqDetail, setReqDetail] = useState('');
    const [submittingReq, setSubmittingReq] = useState(false);
    const [reqSuccess, setReqSuccess] = useState(false);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push('/login');
        }
    }, [authLoading, isAuthenticated, router]);

    const handleSubscribe = async () => {
        setSubscribing(true);
        setSuccessMessage(null);
        setErrorMessage(null);
        try {
            await authAPI.subscribe();
            await refreshProfile();
            setSuccessMessage("Congratulations! Your Premium subscription has been activated.");
        } catch (err: any) {
            setErrorMessage(err.response?.data?.error || "Activation failed. Please try again later.");
        } finally {
            setSubscribing(false);
        }
    };

    const handleRequestSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!reqTitle.trim()) return;
        setSubmittingReq(true);
        setReqSuccess(false);
        try {
            const formattedMessage = `[PREMIUM USER REQUEST]
Type: ${reqType.toUpperCase()}
Item/Subject: ${reqTitle.trim()}
Details/Notes: ${reqDetail.trim() || 'None'}`;
            
            await analyticsAPI.submitFeedback({
                category: 'feature',
                rating: 5,
                title: `Premium Request: ${reqTitle.trim()}`,
                message: formattedMessage
            });
            
            setReqSuccess(true);
            setReqTitle('');
            setReqDetail('');
            setTimeout(() => setReqSuccess(false), 5000);
        } catch {
            alert("Failed to submit request. Please try again.");
        } finally {
            setSubmittingReq(false);
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

    return (
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content">
                <Header />
                <div className="page-container">
                    <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
                        <Crown className="w-7 h-7 text-amber-500 animate-pulse" />
                        Premium Hub
                    </h1>

                    {/* Subscription Hero Card */}
                    <div className="glass-card overflow-hidden mb-8 relative border-amber-500/20" style={{
                        background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%)',
                    }}>
                        {/* Glow effect */}
                        <div className="absolute top-0 right-0 w-96 h-96 bg-amber-500/5 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />

                        <div className="p-8 md:p-10 flex flex-col md:flex-row md:items-center justify-between gap-8 z-10 relative">
                            <div className="space-y-4 max-w-2xl">
                                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-500 border border-amber-500/20">
                                    <Sparkles className="w-3.5 h-3.5" /> Early Bird Offer
                                </div>
                                <h2 className="text-3xl font-extrabold tracking-tight text-white md:text-4xl">
                                    Complete CMS & NEET PG Preparation
                                </h2>
                                <p className="text-muted-foreground text-sm md:text-base leading-relaxed">
                                    Get exclusive access to top-tier handwritten materials, custom-curated teacher notes, full doubt support, and any medical book you request. Designed by renowned instructors to ensure your exam success.
                                </p>

                                <div className="flex flex-wrap gap-4 text-xs text-muted-foreground pt-2">
                                    <div className="flex items-center gap-1.5 bg-background/50 px-3 py-1.5 rounded-lg border border-border">
                                        <Clock className="w-3.5 h-3.5 text-amber-500" /> Offer Ends Soon
                                    </div>
                                    <div className="flex items-center gap-1.5 bg-background/50 px-3 py-1.5 rounded-lg border border-border">
                                        <Users className="w-3.5 h-3.5 text-cyan-400" /> Designed by Top Faculty
                                    </div>
                                </div>
                            </div>

                            <div className="glass-card p-6 flex flex-col items-center justify-center text-center w-full md:w-80 border-amber-500/30 shrink-0" style={{
                                background: 'rgba(15, 23, 42, 0.6)'
                            }}>
                                <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Special Pricing</span>
                                <div className="mt-2 flex items-baseline justify-center gap-2">
                                    <span className="text-5xl font-black text-white">₹199</span>
                                    <span className="text-sm line-through text-muted-foreground">₹10,000</span>
                                </div>
                                <span className="text-[10px] text-amber-500 font-semibold mt-1">Saves over 98% instantly</span>

                                {successMessage && (
                                    <div className="mt-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
                                        {successMessage}
                                    </div>
                                )}

                                {errorMessage && (
                                    <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium">
                                        {errorMessage}
                                    </div>
                                )}

                                {!isSubscribed ? (
                                    <button
                                        onClick={handleSubscribe}
                                        disabled={subscribing}
                                        className="w-full mt-6 py-3 px-4 rounded-xl font-bold transition-all bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600 text-black shadow-lg shadow-amber-500/15"
                                    >
                                        {subscribing ? 'Processing...' : 'Claim Offer Now'}
                                    </button>
                                ) : (
                                    <div className="w-full mt-6 py-2.5 px-4 rounded-xl font-bold bg-amber-500/10 text-amber-500 border border-amber-500/25 flex items-center justify-center gap-1.5">
                                        <Crown className="w-4 h-4" /> Active Premium Member
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Subscribed Mode: Requests Panel */}
                    {isSubscribed ? (
                        <div className="glass-card p-6 md:p-8 animate-fadeInUp border-emerald-500/10">
                            <h3 className="text-xl font-bold mb-2 flex items-center gap-2 text-white">
                                <MessageSquare className="w-5 h-5 text-emerald-400" />
                                Subscriber Custom Request Desk
                            </h3>
                            <p className="text-muted-foreground text-sm mb-6">
                                As a Premium subscriber, you have priority demand rights. Request any textbook edition, particular teacher note, video topic, or ask your medical questions. We will deliver it to you directly.
                            </p>

                            {reqSuccess && (
                                <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm flex items-center gap-2">
                                    <CheckCircle2 className="w-5 h-5 shrink-0" />
                                    Your request has been successfully transmitted to the faculty. We will update you shortly!
                                </div>
                            )}

                            <form onSubmit={handleRequestSubmit} className="space-y-4 max-w-3xl">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Request Category</label>
                                        <select
                                            className="input-field"
                                            value={reqType}
                                            onChange={e => setReqType(e.target.value)}
                                        >
                                            <option value="book">Textbook / Book Edition</option>
                                            <option value="notes">Handwritten Notes / Subject Summaries</option>
                                            <option value="lectures">Video Lecture Request</option>
                                            <option value="doubt">CMS / NEET PG Question Doubt</option>
                                            <option value="other">Other Special Request</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Item Title / Subject Name</label>
                                        <input
                                            required
                                            type="text"
                                            className="input-field"
                                            placeholder="e.g. Ghai Pediatrics 10th Ed, or ECG Notes"
                                            value={reqTitle}
                                            onChange={e => setReqTitle(e.target.value)}
                                        />
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-xs font-medium mb-1.5 text-muted-foreground">Additional Details (Optional)</label>
                                    <textarea
                                        className="input-field min-h-[100px]"
                                        placeholder="Add any specific page range, author names, or doubts you want resolved..."
                                        value={reqDetail}
                                        onChange={e => setReqDetail(e.target.value)}
                                    />
                                </div>

                                <button
                                    type="submit"
                                    disabled={submittingReq || !reqTitle.trim()}
                                    className="btn-primary flex items-center justify-center gap-2 px-5 py-2.5"
                                >
                                    <Send className="w-4 h-4" />
                                    {submittingReq ? 'Sending...' : 'Submit Request'}
                                </button>
                            </form>
                        </div>
                    ) : (
                        /* Unsubscribed Mode: Premium Features Grid */
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            <div className="glass-card p-6 space-y-3">
                                <div className="p-3 rounded-2xl bg-amber-500/10 text-amber-500 w-12 h-12 flex items-center justify-center">
                                    <BookOpen className="w-6 h-6" />
                                </div>
                                <h3 className="font-bold text-lg text-white">All Necessary Textbooks</h3>
                                <p className="text-muted-foreground text-sm leading-relaxed">
                                    Unlock any edition of books requested for UPSC CMS and NEET PG. Whichever books you want, we supply.
                                </p>
                            </div>

                            <div className="glass-card p-6 space-y-3">
                                <div className="p-3 rounded-2xl bg-cyan-500/10 text-cyan-400 w-12 h-12 flex items-center justify-center">
                                    <FileText className="w-6 h-6" />
                                </div>
                                <h3 className="font-bold text-lg text-white">Handwritten Notes & Summaries</h3>
                                <p className="text-muted-foreground text-sm leading-relaxed">
                                    Quickly revise high-yield subjects using hand-curated materials and diagrams from top rankers.
                                </p>
                            </div>

                            <div className="glass-card p-6 space-y-3">
                                <div className="p-3 rounded-2xl bg-emerald-500/10 text-emerald-400 w-12 h-12 flex items-center justify-center">
                                    <Clock className="w-6 h-6" />
                                </div>
                                <h3 className="font-bold text-lg text-white">Curated Lectures & Doubts</h3>
                                <p className="text-muted-foreground text-sm leading-relaxed">
                                    Directly ask doubts to renowned experts in UPSC CMS, State CMS, and NEET PG exams.
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
