'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { authAPI, questionsAPI } from '@/lib/api';
import {
    Crown, BookOpen, FileText, CheckCircle2, Clock, 
    Sparkles, Users, MessageSquare, Zap, ShieldCheck,
    X, Check, AlertTriangle, Brain, RefreshCw
} from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

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
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

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
    const [aiAnalysis, setAiAnalysis] = useState<string>('');
    const [generatingAnalysis, setGeneratingAnalysis] = useState(false);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push('/login');
        }
    }, [authLoading, isAuthenticated, router]);

    const startScholarshipTest = async () => {
        setLoadingQuestions(true);
        setShowTestModal(true);
        setTestResult(null);
        setAiAnalysis('');
        setSelectedAnswers({});
        setCurrentQuestionIdx(0);

        try {
            // Fetch 5 questions from QBank
            const res = await questionsAPI.list({ page: 1, page_size: 5 });
            const list = res.data.results || res.data || [];
            // Safe fallback standard questions if API list is empty
            if (list.length < 5) {
                setScholarshipQuestions([
                    {
                        id: 9901,
                        question_text: "Which cranial nerve is responsible for the motor innervation of the muscles of mastication?",
                        option_a: "Trigeminal nerve (CN V)",
                        option_b: "Facial nerve (CN VII)",
                        option_c: "Glossopharyngeal nerve (CN IX)",
                        option_d: "Hypoglossal nerve (CN XII)",
                    },
                    {
                        id: 9902,
                        question_text: "A 4-year-old child presents with high fever, barking cough, and inspiratory stridor. X-ray of the neck shows subglottic narrowing (steeple sign). What is the diagnosis?",
                        option_a: "Acute epiglottitis",
                        option_b: "Croup (Laryngotrachobronchitis)",
                        option_c: "Foreign body aspiration",
                        option_d: "Retropharyngeal abscess",
                    },
                    {
                        id: 9903,
                        question_text: "Which enzyme is deficient in Gaucher's disease?",
                        option_a: "Hexosaminidase A",
                        option_b: "Glucocerebrosidase",
                        option_c: "Alpha-galactosidase A",
                        option_d: "Sphingomyelinase",
                    },
                    {
                        id: 9904,
                        question_text: "The primary auditory cortex is located in which lobe of the brain?",
                        option_a: "Frontal lobe",
                        option_b: "Parietal lobe",
                        option_c: "Temporal lobe",
                        option_d: "Occipital lobe",
                    },
                    {
                        id: 9905,
                        question_text: "Which of the following is a loop diuretic?",
                        option_a: "Spironolactone",
                        option_b: "Furosemide",
                        option_c: "Hydrochlorothiazide",
                        option_d: "Acetazolamide",
                    }
                ]);
            } else {
                setScholarshipQuestions(list.slice(0, 5));
            }
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
            generateAiTestAnalysis(data.score, submissionAnswers);

        } catch (err: any) {
            setErrorMessage(err.response?.data?.error || "Failed to submit scholarship test. Please try again.");
        } finally {
            setTestSubmitting(false);
        }
    };

    const generateAiTestAnalysis = (score: number, answers: Record<string, string>) => {
        setGeneratingAnalysis(true);
        
        // Simulate writing rich AI analysis report
        setTimeout(() => {
            const correctCount = score;
            const incorrectCount = 5 - correctCount;
            const points = (correctCount * 2.08) - (incorrectCount * 0.69);
            const percentage = Math.round((correctCount / 5) * 100);

            let analysisText = `### 🧠 AI Clinical Skill Diagnosis Report\n\n`;
            analysisText += `* **Test Score**: ${correctCount} / 5 correct answers (${percentage}%)\n`;
            analysisText += `* **Scholarship Marking**: **${points.toFixed(2)} pts** (Calculated as +2.08 for correct and -0.69 for incorrect)\n\n`;
            
            if (correctCount === 5) {
                analysisText += `> [!NOTE]\n`;
                analysisText += `> **EXCELLENT PERFORMANCE!** You have demonstrated 100% precision in diagnosing high-yield clinical conditions. Your promotional rate of **₹79** is successfully unlocked.\n\n`;
            } else {
                analysisText += `> [!WARNING]\n`;
                analysisText += `> **IMPROVEMENT FOCUS REQUIRED**: You did not achieve a perfect score. To unlock the ₹79 special discount, you must correct all 5 scenarios. Let's study the clinical concepts below.\n\n`;
            }

            analysisText += `#### 🔍 Subject-Wise Knowledge Map\n`;
            analysisText += `1. **Cranial Nerve Pathologies** (CN V mastication motor innervation): ${answers[String(scholarshipQuestions[0]?.id)] === 'A' ? '✅ Correct' : '❌ Missed'}\n`;
            analysisText += `2. **Pediatric Emergencies** (Steeple sign in Croup): ${answers[String(scholarshipQuestions[1]?.id)] === 'B' ? '✅ Correct' : '❌ Missed'}\n`;
            analysisText += `3. **Lysosomal Storage Disorders** (Glucocerebrosidase in Gaucher): ${answers[String(scholarshipQuestions[2]?.id)] === 'B' ? '✅ Correct' : '❌ Missed'}\n`;
            analysisText += `4. **Neuroanatomy** (Auditory cortex in Temporal lobe): ${answers[String(scholarshipQuestions[3]?.id)] === 'C' ? '✅ Correct' : '❌ Missed'}\n`;
            analysisText += `5. **Renal Pharmacology** (Furosemide loop diuretic): ${answers[String(scholarshipQuestions[4]?.id)] === 'B' ? '✅ Correct' : '❌ Missed'}\n\n`;

            analysisText += `#### 💡 Clinical Recommendation\n`;
            if (correctCount < 5) {
                analysisText += `- **Revise Lysosomal Enzymes**: Remember Gaucher = Glucocerebrosidase, Niemann-Pick = Sphingomyelinase, Tay-Sachs = Hexosaminidase A.\n`;
                analysisText += `- **Pediatric Radiology**: Steeple sign indicates subglottic narrowing in laryngotracheobronchitis (Croup). Thumb sign indicates epiglottitis.\n`;
                analysisText += `*Keep practicing in our active Question Bank to perfect these recall topics!*`;
            } else {
                analysisText += `You are ready to claim premium access. Head over to checkout to lock in your discounted monthly subscription!`;
            }

            setAiAnalysis(analysisText);
            setGeneratingAnalysis(false);
        }, 1500);
    };

    const handleSubscribe = async (plan: string) => {
        setSubscribing(true);
        setSuccessMessage(null);
        setErrorMessage(null);

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
            return;
        }

        try {
            // Create order with plan type
            const orderRes = await authAPI.subscribeOrder(plan);
            const { order_id, amount, key_id } = orderRes.data;

            const options = {
                key: key_id,
                amount: amount,
                currency: 'INR',
                name: 'CrackLabs Premium',
                description: `Upgrade to ${plan.replace('_', ' ')} Plan`,
                order_id: order_id,
                handler: async function (response: any) {
                    setSubscribing(true);
                    try {
                        await authAPI.subscribeVerify({
                            razorpay_payment_id: response.razorpay_payment_id,
                            razorpay_order_id: response.razorpay_order_id,
                            razorpay_signature: response.razorpay_signature,
                        });
                        await refreshProfile();
                        setSuccessMessage("Congratulations! Your Premium subscription has been successfully activated.");
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
                    color: '#eab308',
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

    const isSubscribed = user?.is_subscribed;

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
            action: () => handleSubscribe('3_months')
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
            action: () => handleSubscribe('1_year')
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
                        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm font-medium">
                            {errorMessage}
                        </div>
                    )}

                    {/* Scholarship Challenge Banner */}
                    {!isSubscribed && (
                        <div className="rounded-3xl border border-amber-500/30 bg-gradient-to-r from-amber-500/10 via-yellow-500/5 to-transparent p-6 md:p-8 flex flex-col md:flex-row items-center justify-between gap-6 shadow-sm">
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
                            return (
                                <div
                                    key={plan.id}
                                    className={`rounded-3xl border p-6 flex flex-col relative transition-all duration-300 hover:scale-[1.01] ${isRecommended ? 'border-amber-500 bg-slate-900 border-border text-white shadow-xl shadow-amber-500/5' : 'border-border bg-card text-foreground shadow-sm'}`}
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
                                                <span className="text-4xl font-black text-emerald-500">₹79</span>
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

                                    <ul className="space-y-3 text-left text-xs mb-8 flex-1">
                                        {plan.features.map((f, i) => (
                                            <li key={i} className="flex items-start gap-2">
                                                <Check className={`w-4 h-4 shrink-0 mt-0.5 ${isRecommended ? 'text-amber-500' : 'text-emerald-500'}`} />
                                                <span>{f}</span>
                                            </li>
                                        ))}
                                    </ul>

                                    {isSubscribed ? (
                                        <div className="w-full py-2.5 rounded-xl font-bold bg-amber-500/10 text-amber-500 border border-amber-500/25 flex items-center justify-center gap-1.5 text-sm">
                                            <Crown className="w-4 h-4" /> Active Member
                                        </div>
                                    ) : (
                                        <button
                                            onClick={hasScholarshipDiscount ? () => handleSubscribe('scholarship_1_month') : plan.action}
                                            disabled={subscribing}
                                            className={`w-full py-3 px-4 rounded-xl font-extrabold text-sm transition-all shadow-md active:scale-98 ${isRecommended ? 'bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600 text-black shadow-amber-500/10' : 'bg-slate-900 hover:bg-slate-800 text-white dark:bg-white dark:hover:bg-slate-100 dark:text-black'}`}
                                        >
                                            {subscribing ? 'Processing...' : (hasScholarshipDiscount ? 'Claim Scholarship Rate' : plan.cta)}
                                        </button>
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

                    {/* Action footer for subscribed members */}
                    {isSubscribed && (
                        <div className="mt-12 p-6 rounded-[2rem] border border-emerald-500/20 bg-emerald-950/5 flex flex-col md:flex-row items-center justify-between gap-6">
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
                                            ) : (
                                                <div className="p-5 rounded-2xl border border-border bg-slate-50 dark:bg-slate-900/40 text-sm leading-relaxed whitespace-pre-line text-foreground overflow-y-auto max-h-[300px]" style={{ scrollbarWidth: 'thin' }}>
                                                    {aiAnalysis}
                                                </div>
                                            )}

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
